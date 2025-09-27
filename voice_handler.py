import discord
import asyncio
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
        self.tts_engine = pyttsx3.init()
        self.tts_queue = Queue()
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
                if self.voice_client.channel != channel:
                    await self.voice_client.move_to(channel)
                    logger.info(f"Moved to voice channel: {channel.name}")
                else:
                    logger.info(f"Already connected to voice channel: {channel.name}")
            else:
                self.voice_client = await channel.connect(reconnect=True, timeout=20.0)
                logger.info(f"Connected to voice channel: {channel.name}")
            return True
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
        if not self.voice_client:
            await self.join_channel(channel)

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

    # Voice recording functionality disabled - requires discord.py with voice recording support
    async def start_listening(self):
        logger.warning("Voice recording not supported in current discord.py version")

    async def stop_listening(self):
        logger.warning("Voice recording not supported in current discord.py version")

    async def _speak(self, text: str):
        if text and self.voice_client and self.voice_client.is_connected():
            self.tts_queue.put(text)

    def speak_text(self, text: str):
        asyncio.create_task(self._speak(text))
