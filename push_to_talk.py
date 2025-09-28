"""
Push-to-Talk System for SriAI
Allows user to hold a key while speaking, then release to trigger speech processing
"""

import logging
import threading
import time
from typing import Callable, Optional
import speech_recognition as sr
from pynput import keyboard
import os

logger = logging.getLogger(__name__)

class PushToTalkListener:
    def __init__(self, callback_func: Callable[[str], None], recording_state_callback: Optional[Callable[[bool], None]] = None):
        """
        Initialize push-to-talk system

        Args:
            callback_func: Function to call with recognized speech text
            recording_state_callback: Optional callback to notify when recording starts/stops
        """
        self.callback_func = callback_func
        self.recording_state_callback = recording_state_callback
        self.recognizer = sr.Recognizer()
        self.microphone = None

        # Push-to-talk state
        self.is_recording = False
        self.is_listening_active = False
        self.recording_thread = None
        self.keyboard_listener = None

        # Configuration from environment or defaults
        self.talk_key = os.getenv('PUSH_TO_TALK_KEY', 'f1').lower()  # Default F1 key
        self.min_recording_duration = 0.5  # Minimum recording duration in seconds
        self.max_recording_duration = 30.0  # Maximum recording duration in seconds

        # Key mapping for common problematic keys
        self.key_mappings = {
            'grave': ['grave', '`', 'backtick'],
            'space': ['space', ' '],
            'ctrl': ['ctrl', 'ctrl_l', 'ctrl_r', 'control'],
            'alt': ['alt', 'alt_l', 'alt_r'],
            'shift': ['shift', 'shift_l', 'shift_r'],
            'tab': ['tab'],
            'f1': ['f1'],
            'f2': ['f2'],
            'f3': ['f3'],
            'f4': ['f4']
        }

        # Validate key configuration
        self._validate_key_config()

        # Audio buffer for recording
        self.audio_buffer = None
        self.recording_start_time = 0

        # Initialize microphone
        try:
            self.microphone = sr.Microphone()
            logger.info("Push-to-talk microphone initialized")

            # Adjust for ambient noise
            with self.microphone as source:
                logger.info("Adjusting push-to-talk microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)

            # Configure recognizer for push-to-talk (optimized for longer speech)
            self.recognizer.energy_threshold = 150  # Lower threshold for better sensitivity
            self.recognizer.dynamic_energy_threshold = False  # Keep fixed threshold for consistency
            self.recognizer.pause_threshold = 2.0  # Allow much longer pauses within speech (2 seconds)
            self.recognizer.phrase_threshold = 0.3  # Minimum silence to consider phrase start
            self.recognizer.non_speaking_duration = 2.0  # Allow longer pauses before stopping (2 seconds)

            logger.info("Push-to-talk system initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize push-to-talk microphone: {e}")
            self.microphone = None

    def _validate_key_config(self):
        """Validate the configured push-to-talk key"""
        problematic_keys = ['fn', 'function']

        if self.talk_key in problematic_keys:
            logger.error(f"❌ PUSH_TO_TALK_KEY '{self.talk_key}' tidak didukung!")
            logger.error("💡 Key 'fn' adalah modifier hardware yang tidak bisa dideteksi")
            logger.error("📝 Gunakan key lain seperti: f1, f2, space, ctrl, alt, tab")
            logger.error("🔧 Edit .env dan ubah PUSH_TO_TALK_KEY=f1 (atau key lain)")
            return False

        recommended_keys = ['f1', 'f2', 'f3', 'f4', 'space', 'ctrl', 'alt', 'shift', 'tab', 'grave']
        if self.talk_key not in recommended_keys and len(self.talk_key) > 1:
            logger.warning(f"⚠ Key '{self.talk_key}' mungkin tidak kompatibel")
            logger.warning(f"💡 Recommended keys: {', '.join(recommended_keys[:6])}")

        logger.info(f"✅ Push-to-talk key configured: '{self.talk_key}'")
        return True

    def start_listening(self) -> bool:
        """Start push-to-talk keyboard listener"""
        if not self.microphone:
            logger.error("Push-to-talk microphone not available")
            return False

        if self.is_listening_active:
            logger.info("Push-to-talk already active")
            return True

        try:
            # Start keyboard listener
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self.keyboard_listener.start()
            self.is_listening_active = True

            logger.info(f"🎤 Push-to-talk active! Hold [{self.talk_key.upper()}] key while speaking")
            logger.info(f"Target key: '{self.talk_key}' (configured from PUSH_TO_TALK_KEY)")

            # Show mapped alternatives
            if self.talk_key in self.key_mappings:
                alternatives = self.key_mappings[self.talk_key]
                logger.info(f"Key alternatives: {alternatives}")

            # Enable debug only if explicitly requested
            debug_mode = os.getenv('PTT_DEBUG', 'false').lower() == 'true'
            if debug_mode:
                import logging
                keyboard_logger = logging.getLogger('push_to_talk')
                keyboard_logger.setLevel(logging.DEBUG)
                logger.info("⚠ Debug mode enabled - akan log key presses untuk troubleshooting")

            return True

        except Exception as e:
            logger.error(f"Failed to start push-to-talk listener: {e}")
            import traceback
            logger.error(f"Push-to-talk start error traceback: {traceback.format_exc()}")
            return False

    def stop_listening(self):
        """Stop push-to-talk system"""
        self.is_listening_active = False

        # Stop keyboard listener
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

        # Stop any ongoing recording
        if self.is_recording:
            self.is_recording = False
            if self.recording_thread:
                self.recording_thread.join(timeout=2)

        logger.info("Push-to-talk stopped")

    def _on_key_press(self, key):
        """Handle key press events"""
        try:
            # Check if the pressed key matches our talk key
            key_name = self._get_key_name(key)

            # Only log when target key is pressed (reduce noise)
            if self._is_target_key(key_name) and not self.is_recording:
                # Debug logging only for matching keys (when explicitly enabled)
                debug_mode = os.getenv('PTT_DEBUG', 'false').lower() == 'true'
                if debug_mode:
                    logger.info(f"🔍 Key pressed: '{key_name}' | Target: '{self.talk_key}' | Match: True")

            if self._is_target_key(key_name) and not self.is_recording:
                logger.info(f"Talk key '{key_name}' (mapped to '{self.talk_key}') detected! Starting recording...")

                # Notify voice handler that recording is starting
                if self.recording_state_callback:
                    try:
                        self.recording_state_callback(True)  # True = recording starting
                    except Exception as e:
                        logger.warning(f"Error notifying recording state start: {e}")

                self._start_recording()

        except Exception as e:
            logger.error(f"Error in key press handler: {e}")
            import traceback
            logger.error(f"Key press traceback: {traceback.format_exc()}")

    def _on_key_release(self, key):
        """Handle key release events"""
        try:
            # Check if the released key matches our talk key
            key_name = self._get_key_name(key)

            # Only log debug info if debug mode is enabled
            if os.getenv('PTT_DEBUG', 'false').lower() == 'true':
                logger.debug(f"Key released: '{key_name}' (target: '{self.talk_key}')")

            if self._is_target_key(key_name) and self.is_recording:
                logger.info(f"Talk key '{key_name}' (mapped to '{self.talk_key}') released! Stopping recording...")
                self._stop_recording()

        except Exception as e:
            logger.error(f"Error in key release handler: {e}")
            import traceback
            logger.error(f"Key release traceback: {traceback.format_exc()}")

    def _get_key_name(self, key) -> str:
        """Get normalized key name"""
        try:
            # Detailed debugging only if debug mode is enabled
            debug_mode = os.getenv('PTT_DEBUG', 'false').lower() == 'true'

            if debug_mode:
                key_attrs = {
                    'hasattr_name': hasattr(key, 'name'),
                    'hasattr_char': hasattr(key, 'char'),
                    'hasattr_vk': hasattr(key, 'vk'),
                    'key_type': type(key).__name__,
                    'key_str': str(key)
                }
                logger.debug(f"Key attributes: {key_attrs}")

            if hasattr(key, 'name'):
                key_name = key.name.lower()
                if debug_mode:
                    logger.debug(f"Using key.name: '{key_name}'")
                return key_name
            elif hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
                if debug_mode:
                    logger.debug(f"Using key.char: '{key_name}'")
                return key_name
            else:
                key_name = str(key).lower().replace("'", "")
                if debug_mode:
                    logger.debug(f"Using str(key): '{key_name}'")
                return key_name
        except Exception as e:
            logger.error(f"Error in _get_key_name: {e}")
            return ""

    def _is_target_key(self, detected_key_name: str) -> bool:
        """Check if detected key matches our target key (with mappings)"""
        # Direct match
        if detected_key_name == self.talk_key:
            return True

        # Check mappings
        if self.talk_key in self.key_mappings:
            return detected_key_name in self.key_mappings[self.talk_key]

        # No mapping found, just do direct comparison
        return False

    def _start_recording(self):
        """Start recording audio"""
        if self.is_recording:
            return

        self.is_recording = True
        self.recording_start_time = time.time()

        # Start recording in a separate thread (callback already called in key press handler)
        self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
        self.recording_thread.start()

        logger.info(f"🔴 Recording started - Keep holding [{self.talk_key.upper()}] key...")

    def _stop_recording(self):
        """Stop recording and process audio"""
        if not self.is_recording:
            return

        recording_duration = time.time() - self.recording_start_time

        # Check minimum duration
        if recording_duration < self.min_recording_duration:
            logger.info(f"Recording too short ({recording_duration:.1f}s), ignoring")
            self.is_recording = False

            # Notify voice handler that recording has stopped
            if self.recording_state_callback:
                try:
                    self.recording_state_callback(False)  # False = recording stopped
                except Exception as e:
                    logger.warning(f"Error notifying recording state stop: {e}")
            return

        self.is_recording = False
        logger.info(f"🔴 Recording stopped ({recording_duration:.1f}s) - Processing speech...")

        # Notify voice handler that recording has stopped
        if self.recording_state_callback:
            try:
                self.recording_state_callback(False)  # False = recording stopped
            except Exception as e:
                logger.warning(f"Error notifying recording state stop: {e}")

    def _record_audio(self):
        """Record audio while key is held down - improved approach with better buffering"""
        audio_chunks = []
        try:
            logger.info("Recording thread started - listening for speech...")

            with self.microphone as source:
                logger.info("Microphone ready - speak now!")

                # Record continuously while key is pressed
                while self.is_recording:
                    try:
                        # Use shorter segments to capture continuous speech
                        audio_chunk = self.recognizer.listen(
                            source,
                            timeout=0.5,  # Short timeout for responsiveness
                            phrase_time_limit=2  # 2 second chunks max
                        )
                        audio_chunks.append(audio_chunk)
                        logger.debug("Audio chunk captured")

                    except sr.WaitTimeoutError:
                        # Timeout is normal - continue if still recording
                        if self.is_recording:
                            continue
                        else:
                            break
                    except Exception as chunk_error:
                        logger.warning(f"Error capturing audio chunk: {chunk_error}")
                        break

                # Process all collected audio chunks if we have any
                if audio_chunks:
                    recording_duration = time.time() - self.recording_start_time

                    if recording_duration >= self.min_recording_duration:
                        logger.info(f"Audio chunks captured ({len(audio_chunks)} chunks, {recording_duration:.1f}s total)")

                        # Use the largest chunk (likely contains most speech)
                        largest_chunk = max(audio_chunks, key=lambda x: len(x.get_raw_data()))
                        self._process_recorded_audio(largest_chunk)
                    else:
                        logger.info(f"Recording too short ({recording_duration:.1f}s), ignoring")
                else:
                    logger.warning("No audio captured during recording")

        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            import traceback
            logger.error(f"Recording thread traceback: {traceback.format_exc()}")
        finally:
            self.is_recording = False

            # Ensure recording state is properly reset even if there were errors
            if self.recording_state_callback:
                try:
                    self.recording_state_callback(False)  # False = recording stopped
                except Exception as e:
                    logger.warning(f"Error notifying recording state stop in finally: {e}")

            logger.info("Recording thread finished")

    def _process_recorded_audio(self, audio_data):
        """Process recorded audio and extract speech"""
        try:
            logger.info("Processing recorded speech...")

            # Check if audio data is valid
            if not audio_data:
                logger.warning("No audio data to process")
                return

            try:
                raw_data = audio_data.get_raw_data()
                logger.info(f"Audio data size: {len(raw_data)} bytes")
                if len(raw_data) < 1000:  # Very small audio
                    logger.warning("Audio data too small, likely no speech recorded")
                    return
            except Exception as e:
                logger.error(f"Error checking audio data: {e}")

            # Use Indonesian speech recognition with longer timeout
            try:
                # Try Indonesian first with extended timeout for longer speech
                logger.info("Attempting Indonesian speech recognition...")
                text = self.recognizer.recognize_google(audio_data, language="id-ID", timeout=15)
                logger.info(f"Recognized (id-ID): {text}")
            except sr.UnknownValueError:
                logger.info("Indonesian recognition failed, trying English...")
                try:
                    # Fallback to English with extended timeout
                    text = self.recognizer.recognize_google(audio_data, language="en-US", timeout=15)
                    logger.info(f"Recognized (en-US): {text}")
                except sr.UnknownValueError:
                    logger.warning("Speech recognition failed for both Indonesian and English")
                    logger.info("Could not understand the recorded audio - this may be due to:")
                    logger.info("1. No speech during recording")
                    logger.info("2. Audio quality too poor")
                    logger.info("3. Microphone is in use by another application")
                    logger.info("4. Background noise interference")
                    return

            # Clean and enhance text
            if text.strip():
                enhanced_text = self._enhance_speech_text(text.strip())
                logger.info(f"Enhanced speech: '{text}' -> '{enhanced_text}'")

                # Send to callback (voice handler)
                if self.callback_func:
                    self.callback_func(enhanced_text)

        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
        except Exception as e:
            logger.error(f"Error processing recorded audio: {e}")

    def _enhance_speech_text(self, text: str) -> str:
        """Enhance recognized speech text"""
        # Convert to lowercase for consistency
        enhanced = text.lower().strip()

        # Fix common Indonesian speech recognition errors
        replacements = {
            'sry': 'sri',
            'shri': 'sri',
            'seri': 'sri',
            'cri': 'sri',
            'tree': 'sri',
            'free': 'sri'
        }

        for old, new in replacements.items():
            enhanced = enhanced.replace(old, new)

        return enhanced

    def is_available(self) -> bool:
        """Check if push-to-talk system is available"""
        return self.microphone is not None

    def get_config_info(self) -> dict:
        """Get current push-to-talk configuration"""
        return {
            "talk_key": self.talk_key.upper(),
            "min_duration": self.min_recording_duration,
            "max_duration": self.max_recording_duration,
            "is_active": self.is_listening_active,
            "microphone_available": self.is_available()
        }