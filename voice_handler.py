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
from local_voice_listener import LocalVoiceListener
from local_tts import LocalTTS

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, bot):
        self.bot = bot
        self.whisper_model = whisper.load_model("base")  # Free, lightweight model
        self.tts_engine = pyttsx3.init()
        self.tts_queue = Queue()
        self.is_recording = False
        self.voice_client: Optional[discord.VoiceClient] = None

        # Initialize local voice listener
        self.local_voice_listener = LocalVoiceListener(self._process_voice_input)

        # Store the channel where voice input was activated
        self.voice_input_channel = None

        # Initialize local TTS for computer speakers
        self.local_tts = LocalTTS()

        # Track recent voice conversation for context awareness
        self.last_voice_interaction_time = 0
        self.voice_context_timeout = 30  # 30 seconds context window

        # Track recent voice inputs to avoid duplicates
        self.recent_voice_inputs = []
        self.voice_input_timeout = 3  # 3 seconds to consider as duplicate

        # Track when Sri is speaking to pause voice input
        self.sri_is_speaking = False

        # Configure TTS
        self.tts_engine.setProperty('rate', 150)
        voices = self.tts_engine.getProperty('voices')
        if voices:
            self.tts_engine.setProperty('voice', voices[0].id)

        # Start TTS thread
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

        # Start voice queue processor
        self._start_voice_queue_processor()

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

        # Try local voice listener first
        if self.local_voice_listener.is_available():
            success = self.local_voice_listener.start_listening()
            if success:
                logger.info("Started local voice listening - you can now speak to Sri!")
                return
            else:
                logger.warning("Failed to start local voice listening")

        # Fallback message
        logger.info("Voice input not available - Sri will respond to your text messages with voice")

    async def stop_listening(self):
        # Stop local voice listener
        if self.local_voice_listener:
            self.local_voice_listener.stop_listening()

        # Stop Discord voice recording (if any)
        if self.voice_client and self.is_recording:
            try:
                self.voice_client.stop_recording()
                self.is_recording = False
                logger.info("Stopped voice recording")
            except Exception as e:
                logger.error(f"Failed to stop recording: {e}")

    async def _process_voice_input(self, text: str):
        """Process voice input from local microphone"""
        try:
            logger.info(f"Processing voice input: {text}")

            # Check for duplicate voice input
            import time
            current_time = time.time()

            # Clean old voice inputs
            self.recent_voice_inputs = [
                (msg, timestamp) for msg, timestamp in self.recent_voice_inputs
                if current_time - timestamp < self.voice_input_timeout
            ]

            # Check if this input was recently processed
            text_lower = text.lower().strip()
            for recent_input, timestamp in self.recent_voice_inputs:
                if text_lower == recent_input.lower().strip():
                    logger.info(f"Skipping duplicate voice input: {text}")
                    return

            # Add this input to recent list
            self.recent_voice_inputs.append((text, current_time))

            # Get user name from MAIN_USER environment variable
            import os
            username = os.getenv('MAIN_USER', 'User')

            # Check if we're in a voice conversation context
            in_voice_context = (current_time - self.last_voice_interaction_time) < self.voice_context_timeout

            # For voice input, only respond if Sri is explicitly mentioned
            # Don't override should_respond - use the original logic
            # This ensures Sri only responds when her name is called, even for voice input

            # Process through AI assistant
            response = await self.bot.ai_assistant.process_message(text, username)

            # Update last interaction time if Sri responded
            if response:
                self.last_voice_interaction_time = current_time

                # Mark this voice input as processed to avoid duplicate text response
                import time
                self.bot.recent_voice_responses.append((text, time.time()))

            if response:
                logger.info(f"Sri responding to voice: {response}")

                # Send text response to Discord
                try:
                    target_channel = None

                    # First, try to use the stored channel where voice input was activated
                    if self.voice_input_channel and hasattr(self.voice_input_channel, 'send'):
                        target_channel = self.voice_input_channel
                        logger.info(f"Using stored voice input channel: {target_channel.name}")
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
                        await target_channel.send(f"🎤 **Voice input detected:** {text}\n\n{response}")
                        logger.info(f"Sent voice response to channel: {target_channel.name}")
                    else:
                        logger.warning("No available channel to send voice response")

                except Exception as e:
                    logger.error(f"Failed to send voice response to Discord: {e}")

                # Use local TTS for computer speakers only (avoid duplication)
                try:
                    if self.local_tts and self.local_tts.is_available():
                        logger.info(f"Sending to local TTS: {response[:50]}...")

                        # Pause voice listening while Sri is speaking
                        self.sri_is_speaking = True
                        if self.local_voice_listener:
                            self.local_voice_listener.pause_listening()

                        self.local_tts.speak(response)
                        logger.info("Voice response sent to local TTS queue")

                        # Resume voice listening after a delay (TTS is async)
                        asyncio.create_task(self._resume_voice_listening_after_speech(response))
                    else:
                        logger.warning("Local TTS not available for voice response")
                except Exception as e:
                    logger.error(f"Error with local TTS: {e}")

        except Exception as e:
            logger.error(f"Error processing voice input: {e}")

    def _start_voice_queue_processor(self):
        """Start background task to process voice queue"""
        loop = asyncio.get_event_loop()
        loop.create_task(self._voice_queue_processor())

    async def _resume_voice_listening_after_speech(self, response_text: str):
        """Resume voice listening after Sri finishes speaking"""
        try:
            # Estimate speech duration (more conservative: 120 words per minute, 5 chars per word)
            char_count = len(response_text)
            estimated_duration = max(3, char_count / (120 * 5 / 60))  # minimum 3 seconds

            logger.info(f"Estimated speech duration: {estimated_duration:.1f} seconds")
            await asyncio.sleep(estimated_duration + 2)  # Add 2 second buffer

            self.sri_is_speaking = False
            # Resume voice listening with fresh timeout
            if self.local_voice_listener:
                self.local_voice_listener.resume_listening()
            logger.info("Resumed voice listening with fresh timeout - Sri finished speaking")
        except Exception as e:
            logger.error(f"Error in resume voice listening: {e}")
            self.sri_is_speaking = False  # Failsafe

    async def _voice_queue_processor(self):
        """Process voice input from queue"""
        while True:
            try:
                # Check for voice input every 100ms
                await asyncio.sleep(0.1)

                # Skip processing if Sri is currently speaking
                if self.sri_is_speaking:
                    # Voice listener is paused, so no need to drain queue
                    continue

                if self.local_voice_listener:
                    voice_input = self.local_voice_listener.get_voice_input()
                    if voice_input:
                        await self._process_voice_input(voice_input)

            except Exception as e:
                logger.error(f"Error in voice queue processor: {e}")
                await asyncio.sleep(1)

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
                            # Use local TTS instead of Discord voice to avoid duplication
                            if self.local_tts and self.local_tts.is_available():
                                self.local_tts.speak(response)

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

    async def _speak(self, text: str):
        if text and self.voice_client and self.voice_client.is_connected():
            self.tts_queue.put(text)

    def speak_text(self, text: str):
        asyncio.create_task(self._speak(text))
