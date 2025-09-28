import logging
import asyncio
import subprocess
import tempfile
import os
import time

logger = logging.getLogger(__name__)

class LocalTTS:
    def __init__(self):
        """Initialize local text-to-speech using Windows PowerShell SAPI"""
        try:
            self.available = True
            self.is_speaking = False

            # Test if PowerShell TTS works
            test_result = subprocess.run([
                'powershell', '-Command',
                'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("test"); $synth.Dispose()'
            ], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)

            if test_result.returncode == 0:
                logger.info("Local TTS initialized successfully using Windows PowerShell SAPI")
                self.available = True
            else:
                logger.error("PowerShell TTS test failed")
                self.available = False

        except Exception as e:
            logger.error(f"Failed to initialize local TTS: {e}")
            self.available = False

    def speak(self, text: str):
        """Speak text using Windows PowerShell SAPI (non-blocking)"""
        if not self.available or not text.strip():
            return False

        if self.is_speaking:
            logger.info("TTS already speaking, queuing not implemented yet")
            return False

        # Use asyncio to run TTS in background
        asyncio.create_task(self._speak_async(text.strip()))
        return True  # Return True for successful initiation

    async def _speak_async(self, text: str):
        """Async TTS using PowerShell subprocess"""
        try:
            self.is_speaking = True
            logger.info(f"TTS: Starting to speak: {text[:50]}...")

            # Escape text for PowerShell
            escaped_text = text.replace('"', '""').replace("'", "''")

            # PowerShell command to use SAPI with female voice
            powershell_cmd = f'''
            Add-Type -AssemblyName System.Speech
            $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $synth.SelectVoiceByHints('Female')
            $synth.Rate = 0
            $synth.Speak("{escaped_text}")
            $synth.Dispose()
            '''

            # Run PowerShell command
            process = await asyncio.create_subprocess_exec(
                'powershell', '-Command', powershell_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            await process.wait()
            logger.info(f"TTS: Finished speaking: {text[:30]}...")

        except Exception as e:
            logger.error(f"TTS: Error during speech: {e}")
        finally:
            self.is_speaking = False

    def stop(self):
        """Stop TTS (not needed for subprocess approach)"""
        pass

    def is_available(self):
        """Check if TTS is available"""
        return self.available