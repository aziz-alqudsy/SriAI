import speech_recognition as sr
import asyncio
import logging
import threading
from queue import Queue
import time
import re

logger = logging.getLogger(__name__)

class LocalVoiceListener:
    def __init__(self, callback_func):
        self.callback_func = callback_func
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        self.listen_thread = None
        self.voice_queue = Queue()
        self.last_voice_input = None
        self.last_input_time = 0
        self.duplicate_lock = threading.Lock()  # Thread-safe duplicate detection

        # Initialize microphone with enhanced settings
        try:
            self.microphone = sr.Microphone()
            logger.info("Using default system microphone")

            # Enhanced microphone settings
            with self.microphone as source:
                logger.info("Adjusting for ambient noise...")
                logger.info(f"Initial energy threshold: {self.recognizer.energy_threshold}")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                logger.info(f"Post-adjustment energy threshold: {self.recognizer.energy_threshold}")

            # Enhanced recognizer settings for better accuracy
            self.recognizer.energy_threshold = 300  # Higher threshold to avoid picking up TTS echo
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 5  # Longer pause to capture full sentences
            self.recognizer.operation_timeout = None  # No operation timeout

            logger.info(f"Microphone energy threshold: {self.recognizer.energy_threshold}")


            logger.info("Local voice listener initialized successfully with enhanced settings")
        except Exception as e:
            logger.error(f"Failed to initialize microphone: {e}")
            self.microphone = None

    def start_listening(self):
        if not self.microphone:
            logger.error("Microphone not available")
            return False

        # Ensure any existing thread is properly stopped before starting new one
        if self.listen_thread and self.listen_thread.is_alive():
            logger.info("Stopping existing listening thread before starting new one")
            self.is_listening = False
            self.listen_thread.join(timeout=3)

        if self.is_listening:
            logger.info("Already listening")
            return True

        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        logger.info("Started local voice listening")
        return True

    def pause_listening(self):
        """Pause voice listening temporarily"""
        self.is_listening = False
        if self.listen_thread and self.listen_thread.is_alive():
            # Give the thread more time to finish cleanly
            self.listen_thread.join(timeout=3)
            if self.listen_thread.is_alive():
                logger.warning("Voice listening thread did not stop cleanly")
        logger.info("Paused local voice listening")

    def resume_listening(self):
        """Resume voice listening with fresh timeout"""
        if not self.microphone:
            logger.error("Microphone not available")
            return False

        # Ensure old thread is completely stopped before creating new one
        if self.listen_thread and self.listen_thread.is_alive():
            logger.info("Waiting for previous listening thread to finish...")
            self.is_listening = False
            self.listen_thread.join(timeout=3)
            if self.listen_thread.is_alive():
                logger.warning("Previous thread still alive, may cause duplicate processing")

        if self.is_listening:
            logger.info("Already listening")
            return True

        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        logger.info("Resumed local voice listening with fresh timeout")
        return True

    def stop_listening(self):
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=1)
        logger.info("Stopped local voice listening")

    def _listen_loop(self):
        thread_id = threading.get_ident()
        logger.info(f"Voice listening loop started (Thread ID: {thread_id})")

        try:
            while self.is_listening:
                try:
                    # Use a fresh microphone instance to avoid context manager conflicts
                    mic = sr.Microphone()
                    with mic as source:
                        # Listen for audio with timeout - longer phrase limit for full sentences
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)

                    logger.info("Audio detected, processing voice input...")

                    # Try to recognize speech using Google's free service
                    text = None
                    languages = ['id-ID', 'id', 'en-US']  # Indonesian variants + English fallback

                    for lang in languages:
                        try:
                            text = self.recognizer.recognize_google(audio, language=lang)
                            if text and text.strip():
                                logger.info(f"Recognized with {lang}: {text}")
                                break
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError:
                            continue

                    if text and text.strip():
                        # Enhance the recognized text
                        enhanced_text = self._enhance_speech_text(text.strip())
                        logger.info(f"Recognized speech: '{text}' -> Enhanced: '{enhanced_text}'")

                        # Check for duplicate input
                        import time
                        current_time = time.time()

                        # Thread-safe duplicate detection
                        with self.duplicate_lock:
                            if (enhanced_text != self.last_voice_input or
                                current_time - self.last_input_time > 3):  # 3 second timeout to prevent echo/rapid duplicates
                                # Put the enhanced text in queue
                                self.voice_queue.put(enhanced_text)
                                self.last_voice_input = enhanced_text
                                self.last_input_time = current_time
                                logger.info(f"Added voice input to queue: {enhanced_text} (Thread {thread_id})")
                            else:
                                logger.info(f"Skipping duplicate/rapid voice input: {enhanced_text} (Thread {thread_id})")

                except sr.WaitTimeoutError:
                    # Timeout is normal, continue listening
                    continue
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    logger.debug("Could not understand audio")
                except sr.RequestError as e:
                    logger.error(f"Could not request results from speech service: {e}")
                    time.sleep(1)  # Wait before retrying
                except Exception as listen_error:
                    logger.error(f"Error in voice listening cycle (Thread {thread_id}): {listen_error}")
                    logger.error(f"Error type: {type(listen_error).__name__}")

                    # Check if it's a critical error
                    if isinstance(listen_error, (OSError, RuntimeError)):
                        logger.error("Critical audio system error detected")
                        self.is_listening = False
                        break

                    time.sleep(1)  # Wait before retrying

        except Exception as thread_error:
            logger.error(f"CRITICAL: Voice listening thread crashed (Thread {thread_id}): {thread_error}")
            logger.error(f"Thread error type: {type(thread_error).__name__}")
            import traceback
            logger.error(f"Thread traceback:\n{traceback.format_exc()}")

        finally:
            # Cleanup resources
            try:
                if hasattr(self, 'microphone') and self.microphone:
                    # Ensure microphone is properly cleaned up
                    if hasattr(self.microphone, 'stream') and self.microphone.stream:
                        self.microphone.stream.close()
            except Exception as cleanup_error:
                logger.warning(f"Error during microphone cleanup: {cleanup_error}")

            logger.info(f"Voice listening loop ended (Thread {thread_id})")

    def is_available(self):
        return self.microphone is not None

    def is_healthy(self):
        """Check if voice listener is in a healthy state"""
        try:
            if not self.is_available():
                return False

            # Check if listening thread is alive when it should be
            if self.is_listening:
                if not self.listen_thread or not self.listen_thread.is_alive():
                    logger.warning("Voice listening thread should be running but isn't")
                    return False

            return True
        except Exception as health_error:
            logger.error(f"Error checking voice listener health: {health_error}")
            return False

    def get_voice_input(self):
        """Get recognized voice input from queue"""
        try:
            return self.voice_queue.get_nowait()
        except:
            return None

    def cleanup(self):
        """Clean up all resources"""
        logger.info("Cleaning up voice listener resources...")
        try:
            # Stop listening
            self.stop_listening()

            # Clean up microphone
            if hasattr(self, 'microphone') and self.microphone:
                try:
                    if hasattr(self.microphone, 'stream') and self.microphone.stream:
                        self.microphone.stream.close()
                except Exception as mic_cleanup_error:
                    logger.warning(f"Error cleaning up microphone: {mic_cleanup_error}")

            # Clear queue
            while not self.voice_queue.empty():
                try:
                    self.voice_queue.get_nowait()
                except:
                    break

            logger.info("Voice listener cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"Error during voice listener cleanup: {cleanup_error}")

    def _enhance_speech_text(self, text: str) -> str:
        """Enhanced speech text with Sri name detection and common fixes"""
        if not text:
            return text

        # Convert to lowercase for processing
        enhanced_text = text.lower().strip()
        logger.debug(f"Original speech: {text}")

        # Sri name variants that speech recognition might produce
        sri_variants = [
            r'\bseri\b', r'\bshri\b', r'\bsree\b', r'\bsri\b',
            r'\btree\b', r'\bsea\b', r'\bsee\b', r'\bfree\b',
            r'\bsore\b(?=\s*(selamat|halo|hai|apa))', # "selamat malam sore" = "selamat malam sri"
            r'\bthe\b(?=\s*(selamat|halo|hai|apa))', # "the selamat malam" = "sri selamat malam"
            r'\bser\b', r'\bsir\b', r'\bsri\b',
        ]

        # Replace Sri variants with "sri"
        for variant in sri_variants:
            enhanced_text = re.sub(variant, 'sri', enhanced_text, flags=re.IGNORECASE)

        # Very conservative greeting pattern detection - only for clear Sri-directed speech
        greeting_patterns = [
            # Only fix obvious greetings that are clearly misrecognized
            # "halo [unclear]" at start with greeting continuation -> "halo sri"
            (r'^(halo|hai|hello)\s+\w{1,3}\s*(selamat)', r'\1 sri \2'),
            # Standalone time-based greetings -> assume greeting Sri
            (r'^(selamat\s+(malam|pagi|siang|sore))$', r'\1 sri'),
            # Only apply conservative fixes for clear Sri-directed patterns
        ]

        for pattern, replacement in greeting_patterns:
            if re.search(pattern, enhanced_text, re.IGNORECASE):
                enhanced_text = re.sub(pattern, replacement, enhanced_text, flags=re.IGNORECASE)
                logger.info(f"Applied greeting pattern fix: {text} -> {enhanced_text}")

        # Special case: Only add "sri" to explicit greetings that are clearly meant for Sri
        # Be more conservative - only add "sri" to obvious greetings directed at her
        if len(enhanced_text.split()) <= 2:
            # Only very specific greetings that are clearly meant for Sri
            explicit_greetings = [
                'halo', 'hai', 'hello', 'selamat malam', 'selamat pagi',
                'selamat siang', 'selamat sore', 'hi', 'hey'
            ]

            # Only add "sri" if it's an exact match to these greetings (standalone)
            if enhanced_text.strip() in explicit_greetings and 'sri' not in enhanced_text:
                enhanced_text = f"{enhanced_text} sri"
                logger.info(f"Added 'sri' to standalone greeting: '{text}' -> '{enhanced_text}'")
            # Remove automatic pattern fixes for non-greeting phrases

        # Final cleanup
        enhanced_text = re.sub(r'\s+', ' ', enhanced_text).strip()

        if enhanced_text != text.lower():
            logger.info(f"Speech enhanced: '{text}' -> '{enhanced_text}'")

        return enhanced_text