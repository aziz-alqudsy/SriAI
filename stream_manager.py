import asyncio
import subprocess
import logging
import os
from typing import Optional
import signal

logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.is_streaming = False
        self.stream_key = os.getenv('YOUTUBE_STREAM_KEY')
        self.rtmp_url = os.getenv('YOUTUBE_RTMP_URL', 'rtmp://a.rtmp.youtube.com/live2/')

    async def start_streaming(self):
        if self.is_streaming:
            logger.warning("Stream is already running")
            return False

        if not self.stream_key:
            logger.error("YouTube stream key not configured")
            return False

        try:
            # FFmpeg command to stream desktop audio + microphone to YouTube
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'dshow',  # DirectShow for Windows
                '-i', 'audio=Stereo Mix',  # Desktop audio (you may need to enable this in Windows)
                '-f', 'dshow',
                '-i', 'audio=Microphone',  # Microphone input
                '-filter_complex', '[0:a][1:a]amix=inputs=2[out]',  # Mix both audio sources
                '-map', '[out]',
                '-acodec', 'aac',
                '-ab', '128k',
                '-ar', '44100',
                '-f', 'flv',
                f'{self.rtmp_url}{self.stream_key}'
            ]

            # Alternative command for systems without Stereo Mix
            fallback_cmd = [
                'ffmpeg',
                '-f', 'dshow',
                '-i', 'audio=Microphone',
                '-acodec', 'aac',
                '-ab', '128k',
                '-ar', '44100',
                '-f', 'flv',
                f'{self.rtmp_url}{self.stream_key}'
            ]

            logger.info("Starting YouTube stream...")

            # Try main command first, fallback if it fails
            try:
                self.ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )
                await asyncio.sleep(3)  # Wait a moment to see if it starts successfully

                if self.ffmpeg_process.poll() is not None:
                    # Process exited, try fallback
                    logger.warning("Primary stream command failed, trying fallback...")
                    self.ffmpeg_process = subprocess.Popen(
                        fallback_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE
                    )

            except Exception:
                logger.warning("Primary stream command failed, trying fallback...")
                self.ffmpeg_process = subprocess.Popen(
                    fallback_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )

            self.is_streaming = True
            logger.info("YouTube stream started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False

    async def stop_streaming(self):
        if not self.is_streaming or not self.ffmpeg_process:
            logger.warning("No stream is currently running")
            return False

        try:
            logger.info("Stopping YouTube stream...")

            # Send SIGTERM to gracefully stop FFmpeg
            if self.ffmpeg_process.poll() is None:
                self.ffmpeg_process.terminate()

                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process()),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # Force kill if it doesn't stop gracefully
                    logger.warning("Force killing FFmpeg process")
                    self.ffmpeg_process.kill()

            self.ffmpeg_process = None
            self.is_streaming = False
            logger.info("YouTube stream stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping stream: {e}")
            return False

    async def _wait_for_process(self):
        while self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            await asyncio.sleep(0.1)

    def get_stream_status(self) -> dict:
        return {
            'is_streaming': self.is_streaming,
            'has_process': self.ffmpeg_process is not None,
            'process_alive': self.ffmpeg_process.poll() is None if self.ffmpeg_process else False,
            'stream_configured': bool(self.stream_key)
        }

    async def restart_stream(self):
        if self.is_streaming:
            await self.stop_streaming()
        await asyncio.sleep(2)  # Brief pause
        return await self.start_streaming()

# Audio-only streaming for lower bandwidth usage
class AudioOnlyStreamManager(StreamManager):
    async def start_streaming(self):
        if self.is_streaming:
            logger.warning("Stream is already running")
            return False

        if not self.stream_key:
            logger.error("YouTube stream key not configured")
            return False

        try:
            # Simple audio-only stream - much lower bandwidth
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'dshow',
                '-i', 'audio=Microphone',
                '-acodec', 'aac',
                '-ab', '64k',  # Lower bitrate for minimal cost
                '-ar', '22050',  # Lower sample rate
                '-f', 'flv',
                f'{self.rtmp_url}{self.stream_key}'
            ]

            logger.info("Starting audio-only YouTube stream...")

            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )

            self.is_streaming = True
            logger.info("Audio-only stream started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            return False