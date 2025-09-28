"""
ElevenLabs TTS Integration for SriAI
Optimized for Starter Plan ($5/month)
"""

import os
import logging
import asyncio
import aiohttp
import json
from typing import Optional
import tempfile
import pygame

logger = logging.getLogger(__name__)

class ElevenLabsTTS:
    def __init__(self):
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            logger.error("ELEVENLABS_API_KEY not found in environment variables!")
            self.available = False
            return

        self.base_url = "https://api.elevenlabs.io/v1"
        self.available = True

        # Starter Plan Optimization
        self.config = {
            # Use cheapest model for cost optimization
            "model_id": "eleven_turbo_v2_5",  # Fastest & cheapest

            # Voice settings optimized for Indonesian
            "voice_settings": {
                "stability": 0.6,        # Good balance
                "similarity_boost": 0.8, # Clear pronunciation
                "style": 0.3,           # Slight variation
                "use_speaker_boost": True
            },

            # Cost management for $5/month
            "max_chars_per_request": 500,    # Prevent huge requests
            "daily_char_limit": 5000,        # ~$3.75/day max (safety buffer)
            "chunk_size": 250,               # Split long texts
        }

        # Initialize pygame for audio playback
        try:
            pygame.mixer.init()
            logger.info("ElevenLabs TTS initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize audio player: {e}")
            self.available = False

        # Character usage tracking
        self.daily_usage = 0
        self.last_reset_date = None
        self._reset_daily_usage_if_needed()

        # Voice ID configuration - priority order:
        # 1. Environment variable ELEVENLABS_VOICE_ID (user configured)
        # 2. Auto-detection from available voices
        self.user_voice_id = os.getenv('ELEVENLABS_VOICE_ID', '').strip()

        if self.user_voice_id:
            self.selected_voice_id = self.user_voice_id
            logger.info(f"Using user-configured voice ID: {self.user_voice_id}")
        else:
            # Indonesian voice preferences (will auto-detect best available)
            self.preferred_voices = [
                "indonesian_female", "indonesian_male",
                "multilingual_female", "multilingual_male",
                "Rachel", "Bella"  # Fallback English voices
            ]
            self.selected_voice_id = None
            logger.info("No voice ID configured, will auto-detect best available voice")

    def _reset_daily_usage_if_needed(self):
        """Reset daily usage counter if it's a new day"""
        from datetime import date
        today = date.today()

        if self.last_reset_date != today:
            self.daily_usage = 0
            self.last_reset_date = today
            logger.info("Daily ElevenLabs usage counter reset")

    async def _get_available_voices(self):
        """Get list of available voices and select best Indonesian voice (only if no user voice ID)"""
        # Skip auto-detection if user has configured a specific voice ID
        if self.user_voice_id:
            logger.info(f"Skipping voice auto-detection, using configured voice ID: {self.user_voice_id}")
            return

        try:
            headers = {"xi-api-key": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/voices", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        voices = data.get('voices', [])

                        # Look for Indonesian or multilingual voices
                        for voice in voices:
                            name = voice.get('name', '').lower()
                            if any(pref in name for pref in ['indonesian', 'multilingual']):
                                self.selected_voice_id = voice.get('voice_id')
                                logger.info(f"Selected voice: {voice.get('name')} ({self.selected_voice_id})")
                                return

                        # Fallback to first available voice
                        if voices:
                            self.selected_voice_id = voices[0].get('voice_id')
                            logger.info(f"Using fallback voice: {voices[0].get('name')}")

        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            # Use default voice ID if available
            self.selected_voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel (English)

    def _check_usage_limit(self, text_length: int) -> bool:
        """Check if request is within daily usage limits"""
        self._reset_daily_usage_if_needed()

        if self.daily_usage + text_length > self.config["daily_char_limit"]:
            logger.warning(f"Daily usage limit reached: {self.daily_usage}/{self.config['daily_char_limit']}")
            return False
        return True

    def _optimize_text(self, text: str) -> str:
        """Optimize text for cost and quality"""
        # Remove excessive whitespace
        text = ' '.join(text.split())

        # Truncate if too long
        max_chars = self.config["max_chars_per_request"]
        if len(text) > max_chars:
            # Try to cut at sentence boundary
            sentences = text.split('.')
            optimized = ""
            for sentence in sentences:
                if len(optimized + sentence + ".") <= max_chars:
                    optimized += sentence + "."
                else:
                    break

            if not optimized.strip():
                optimized = text[:max_chars-3] + "..."

            logger.info(f"Text optimized: {len(text)} → {len(optimized)} chars")
            return optimized

        return text

    async def _text_to_speech_api(self, text: str) -> Optional[bytes]:
        """Call ElevenLabs API to generate speech"""
        try:
            if not self.selected_voice_id:
                await self._get_available_voices()

            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "text": text,
                "model_id": self.config["model_id"],
                "voice_settings": self.config["voice_settings"]
            }

            url = f"{self.base_url}/text-to-speech/{self.selected_voice_id}"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        audio_data = await response.read()

                        # Update usage tracking
                        self.daily_usage += len(text)
                        cost_estimate = len(text) * 0.00075  # ~$0.75 per 1K chars for Starter
                        logger.info(f"ElevenLabs TTS: {len(text)} chars, ~${cost_estimate:.4f}, daily: {self.daily_usage}")

                        return audio_data
                    else:
                        error_text = await response.text()
                        if response.status == 429:
                            logger.warning(f"ElevenLabs rate limit hit (429): System busy. Falling back to Local TTS.")
                        else:
                            logger.error(f"ElevenLabs API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"ElevenLabs API request failed: {e}")
            return None

    async def speak_async(self, text: str) -> bool:
        """Generate and play speech asynchronously"""
        if not self.available:
            return False

        # Optimize text and check limits
        optimized_text = self._optimize_text(text)
        if not self._check_usage_limit(len(optimized_text)):
            logger.warning("ElevenLabs usage limit exceeded, skipping TTS")
            return False

        try:
            # Generate speech
            logger.info(f"ElevenLabs TTS: Generating speech for: {optimized_text[:50]}...")
            audio_data = await self._text_to_speech_api(optimized_text)

            if not audio_data:
                return False

            # Save to temporary file and play
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            # Play audio using pygame
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()

            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            # Cleanup
            try:
                os.unlink(temp_path)
            except:
                pass

            logger.info("ElevenLabs TTS: Playback completed")
            return True

        except Exception as e:
            logger.error(f"ElevenLabs TTS playback error: {e}")
            return False

    def speak(self, text: str) -> bool:
        """Synchronous wrapper for async speak"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.speak_async(text))
        except Exception as e:
            logger.error(f"ElevenLabs TTS sync wrapper error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if ElevenLabs TTS is available"""
        return self.available and bool(self.api_key)

    def get_usage_info(self) -> dict:
        """Get current usage information"""
        self._reset_daily_usage_if_needed()
        remaining = max(0, self.config["daily_char_limit"] - self.daily_usage)

        return {
            "daily_used": self.daily_usage,
            "daily_limit": self.config["daily_char_limit"],
            "remaining": remaining,
            "cost_estimate_today": self.daily_usage * 0.00075
        }

    async def get_available_voices_list(self) -> list:
        """Get list of all available voices for user to choose from"""
        try:
            headers = {"xi-api-key": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/voices", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        voices = data.get('voices', [])

                        # Return formatted list with voice ID, name, and description
                        voice_list = []
                        for voice in voices:
                            voice_info = {
                                "voice_id": voice.get('voice_id', ''),
                                "name": voice.get('name', ''),
                                "description": voice.get('description', ''),
                                "category": voice.get('category', ''),
                                "labels": voice.get('labels', {})
                            }
                            voice_list.append(voice_info)

                        return voice_list
                    else:
                        logger.error(f"Failed to get voices: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error getting available voices: {e}")
            return []