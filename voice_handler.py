import discord
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

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, bot):
        self.bot = bot
        self.whisper_model = whisper.load_model("base")  # Free, lightweight model
        self.tts_engine = pyttsx3.init()
        self.tts_queue = Queue()
        self.is_recording = False
        self.voice_client: Optional[discord.VoiceClient] = None

        # Configure TTS
        self.tts_engine.setProperty('rate', 150)
        voices = self.tts_engine.getProperty('voices')
        if voices:
            self.tts_engine.setProperty('voice', voices[0].id)

        # Start TTS thread
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()

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
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()

            logger.info(f"Connected to voice channel: {channel.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return False

    async def leave_channel(self):
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
            logger.info("Disconnected from voice channel")

    async def handle_user_join(self, member, channel):
        logger.info(f"{member.name} joined {channel.name}")
        if not self.voice_client:
            await self.join_channel(channel)

    async def handle_user_leave(self, member, channel):
        logger.info(f"{member.name} left {channel.name}")
        if self.voice_client and len(channel.members) <= 1:  # Only bot left
            await self.leave_channel()

    async def start_listening(self):
        if not self.voice_client or not self.voice_client.is_connected():
            logger.warning("Not connected to voice channel")
            return

        self.is_recording = True
        self.voice_client.start_recording(
            discord.sinks.WaveSink(),
            self._recording_finished,
            channel=self.voice_client.channel
        )
        logger.info("Started voice recording")

    async def stop_listening(self):
        if self.voice_client and self.is_recording:
            self.voice_client.stop_recording()
            self.is_recording = False
            logger.info("Stopped voice recording")

    def _recording_finished(self, sink, channel, *args):
        asyncio.create_task(self._process_recordings(sink, channel))

    async def _process_recordings(self, sink: discord.sinks.WaveSink, channel):
        try:
            for user_id, audio_data in sink.audio_data.items():
                user = self.bot.get_user(user_id)
                if user and user != self.bot.user:
                    text = await self._transcribe_audio(audio_data)
                    if text.strip():
                        logger.info(f"Transcribed from {user.name}: {text}")
                        # Send to AI assistant for processing
                        response = await self.bot.ai_assistant.process_message(text, user.name)
                        if response:  # Sri will only respond if she should
                            logger.info(f"Sri responding: {response}")
                            await self._speak(response)
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
