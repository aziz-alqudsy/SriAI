import discord
from discord import sinks
import asyncio
import whisper
import io
import wave
import numpy as np
import logging
from typing import Optional
import tempfile
import os
import pyttsx3
import threading
from queue import Queue
from local_tts import LocalTTS
from elevenlabs_tts import ElevenLabsTTS
from push_to_talk import PushToTalkListener

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, bot):
        self.bot = bot
        self.whisper_model = whisper.load_model("base")  # Free, lightweight model
        self.tts_engine = pyttsx3.init()
        self.tts_queue = Queue()
        self.is_recording = False
        self.voice_client: Optional[discord.VoiceClient] = None

        # Push-to-talk only system
        self.push_to_talk = PushToTalkListener(self._process_push_to_talk_input, None)

        # Store the channel where voice input was activated
        self.voice_input_channel = None

        logger.info("SriAI configured for push-to-talk only mode")

        # Initialize TTS systems (ElevenLabs primary, Local TTS fallback)
        self.elevenlabs_tts = ElevenLabsTTS()
        self.local_tts = LocalTTS()

        # Set primary TTS based on availability
        if self.elevenlabs_tts.is_available():
            self.primary_tts = self.elevenlabs_tts
            self.fallback_tts = self.local_tts
            logger.info("🎤 ElevenLabs TTS set as primary, Local TTS as fallback")
        else:
            self.primary_tts = self.local_tts
            self.fallback_tts = None
            logger.warning("⚠ ElevenLabs not available, using Local TTS only")

        # Track when Sri is speaking for TTS management
        self.sri_is_speaking = False

        # Configure TTS
        self.tts_engine.setProperty('rate', 150)
        voices = self.tts_engine.getProperty('voices')
        if voices:
            self.tts_engine.setProperty('voice', voices[0].id)

        # Start TTS thread
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

        # Voice processing handled by push-to-talk directly

    def _tts_worker(self):
        while True:
            try:
                text = self.tts_queue.get(timeout=1)
                if text is None:
                    break
                self._generate_speech(text)
                self.tts_queue.task_done()
            except:
                continue

    def _generate_speech(self, text: str):
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name

            self.tts_engine.save_to_file(text, temp_path)
            self.tts_engine.runAndWait()

            if self.voice_client and self.voice_client.is_connected():
                audio_source = discord.FFmpegPCMAudio(temp_path)
                self.voice_client.play(audio_source, after=lambda e: os.unlink(temp_path) if e is None else logger.error(f"TTS playback error: {e}"))
            else:
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"TTS generation error: {e}")

    async def join_channel(self, channel):
        try:
            # Clean up any existing connection first
            if self.voice_client:
                try:
                    await self.voice_client.disconnect(force=True)
                except:
                    pass
                self.voice_client = None
                await asyncio.sleep(1)

            # Try single connection attempt for TTS-only mode
            try:
                self.voice_client = await channel.connect(timeout=15.0)
                logger.info(f"Connected to voice channel for TTS: {channel.name}")
                await asyncio.sleep(1)
                return True
            except Exception as e:
                logger.warning(f"Voice connection failed: {e}")
                logger.info("Falling back to text-only mode")
                self.voice_client = None
                return False

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            self.voice_client = None
            return False

    async def leave_channel(self):
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected from voice channel")

    async def handle_user_join(self, member, channel):
        logger.info(f"{member.name} joined {channel.name}")
        if not self.voice_client or not self.voice_client.is_connected():
            success = await self.join_channel(channel)
            if success:
                # Start listening after successful join
                await self.start_listening()
        elif not self.is_recording:
            # Already connected but not recording, start listening
            await self.start_listening()

    async def handle_user_leave(self, member, channel):
        logger.info(f"{member.name} left {channel.name}")
        # Wait a bit before checking if we should leave to avoid race conditions
        await asyncio.sleep(2)
        if self.voice_client and self.voice_client.channel == channel:
            # Count non-bot members only
            human_members = [m for m in channel.members if not m.bot]
            if len(human_members) == 0:
                logger.info("No human members left, leaving voice channel")
                await self.leave_channel()
            else:
                logger.info(f"{len(human_members)} human members still in channel")

    async def start_listening(self, channel=None):
        # Store the channel for voice responses
        if channel:
            self.voice_input_channel = channel

        # Start push-to-talk system
        if self.push_to_talk.is_available():
            success = self.push_to_talk.start_listening()
            if success:
                ptt_config = self.push_to_talk.get_config_info()
                logger.info(f"🎤 Push-to-talk activated - Hold [{ptt_config['talk_key']}] key while speaking!")
                return
            else:
                logger.warning("Failed to start push-to-talk system")
        else:
            logger.error("Push-to-talk system not available")

        logger.info("Voice input not available - Sri will respond to your text messages with voice")

    async def stop_listening(self):
        # Stop push-to-talk system
        if self.push_to_talk:
            self.push_to_talk.stop_listening()

        # Stop Discord voice recording (if any)
        if self.voice_client and self.is_recording:
            try:
                self.voice_client.stop_recording()
                self.is_recording = False
                logger.info("Stopped voice recording")
            except Exception as e:
                logger.error(f"Failed to stop recording: {e}")


    def _process_push_to_talk_input(self, text: str):
        """Process voice input from push-to-talk system (synchronous version)"""
        try:
            # Get the bot's event loop (main loop) and schedule the async task
            loop = self.bot.loop
            if loop and loop.is_running():
                # Schedule the coroutine to run on the main event loop
                asyncio.run_coroutine_threadsafe(
                    self._process_push_to_talk_input_async(text),
                    loop
                )
            else:
                logger.error("Bot event loop not available for push-to-talk processing")
        except Exception as e:
            logger.error(f"Error scheduling push-to-talk task: {e}")

    async def _process_push_to_talk_input_async(self, text: str):
        """Process voice input from push-to-talk system"""
        try:
            logger.info(f"Processing push-to-talk input: {text}")

            # Get user name from MAIN_USER environment variable
            import os
            username = os.getenv('MAIN_USER', 'User')

            # For push-to-talk, always process the input (no need to check for "Sri" mention)
            # since user intentionally pressed the button to talk
            logger.info(f"Calling AI assistant with text: '{text}' from user: '{username}'")
            response = await self.bot.ai_assistant.process_message(text, username, force_respond=True)
            logger.info(f"AI assistant response: {response}")

            if response:
                logger.info(f"Sri responding to push-to-talk: {response}")

                # Send text response to Discord
                try:
                    target_channel = None

                    # Use stored voice input channel
                    if self.voice_input_channel and hasattr(self.voice_input_channel, 'send'):
                        target_channel = self.voice_input_channel
                    else:
                        # Fallback: Find any available channel
                        for guild in self.bot.guilds:
                            for channel in guild.text_channels:
                                if channel.permissions_for(guild.me).send_messages:
                                    target_channel = channel
                                    break
                            if target_channel:
                                break

                    if target_channel:
                        await target_channel.send(f"🎙️ **Push-to-talk:** {text}\n\n{response}")
                        logger.info(f"Sent push-to-talk response to channel: {target_channel.name}")

                except Exception as e:
                    logger.error(f"Failed to send push-to-talk response to Discord: {e}")

                # Use TTS for voice response
                try:
                    success = await self._speak_with_fallback(response)
                    if not success:
                        logger.warning("Both ElevenLabs and Local TTS failed for push-to-talk response")
                except Exception as e:
                    logger.error(f"Error with TTS system for push-to-talk: {e}")

        except Exception as e:
            logger.error(f"Error processing push-to-talk input: {e}")


    def _recording_finished(self, sink, channel, *args):
        asyncio.create_task(self._process_recordings(sink, channel))

    async def _process_recordings(self, sink: sinks.WaveSink, channel):
        try:
            for user_id, audio_data in sink.audio_data.items():
                user = self.bot.get_user(user_id)
                if user and user != self.bot.user:
                    text = await self._transcribe_audio(audio_data)
                    if text.strip():
                        logger.info(f"Transcribed from {user.name}: {text}")
                        # Send to AI assistant for processing
                        response = await self.bot.ai_assistant.process_message(text, user.display_name)
                        if response:  # Sri will only respond if she should
                            logger.info(f"Sri responding: {response}")
                            # Use ElevenLabs TTS with Local TTS fallback
                            try:
                                await self._speak_with_fallback(response)
                            except Exception as tts_error:
                                logger.error(f"Error with TTS system: {tts_error}")

            # Restart recording after processing
            if self.voice_client and self.voice_client.is_connected():
                await asyncio.sleep(0.5)  # Small delay
                await self.start_listening()
        except Exception as e:
            logger.error(f"Error processing recordings: {e}")

    async def _transcribe_audio(self, audio_data) -> str:
        try:
            # Convert audio data to numpy array
            audio_array = np.frombuffer(audio_data.read(), dtype=np.int16)
            audio_array = audio_array.astype(np.float32) / 32768.0

            # Use Whisper to transcribe
            result = self.whisper_model.transcribe(audio_array)
            return result["text"].strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    async def _speak_with_fallback(self, text: str) -> bool:
        """Speak text using primary TTS (ElevenLabs) with fallback to Local TTS"""
        logger.info(f"🎤 TTS: {text[:50]}...")

        # Mark as speaking for TTS management
        self.sri_is_speaking = True

        success = False

        # Try primary TTS (ElevenLabs) first
        try:
            if hasattr(self.primary_tts, 'speak_async'):
                success = await self.primary_tts.speak_async(text)
            else:
                success = self.primary_tts.speak(text)

            if success:
                logger.info("✓ ElevenLabs TTS completed successfully")
            else:
                logger.warning("⚠ ElevenLabs failed, trying Local TTS fallback")

        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            success = False

        # Try fallback if primary failed
        if not success and self.fallback_tts:
            try:
                success = self.fallback_tts.speak(text)
                if success:
                    logger.info("✓ Local TTS fallback completed")
                else:
                    logger.error("✗ Both TTS systems failed")
            except Exception as e:
                logger.error(f"Local TTS fallback error: {e}")

        # Mark as finished speaking
        self.sri_is_speaking = False

        return success

    def speak_text(self, text: str):
        """Synchronous wrapper for ElevenLabs TTS with fallback"""
        try:
            asyncio.create_task(self._speak_with_fallback(text))
        except Exception as e:
            logger.error(f"Error in speak_text: {e}")
            # Emergency fallback to local TTS
            if self.local_tts and self.local_tts.is_available():
                self.local_tts.speak(text)
