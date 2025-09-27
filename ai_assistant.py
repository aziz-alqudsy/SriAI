import google.generativeai as genai
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class AIAssistant:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables!")
            return

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

        # Track current game context
        self.current_game = None
        self.game_start_time = None

        self.system_prompt = """
        Kamu adalah Sri, adik perempuan AI yang manis dan ceria yang membantu dengan streaming YouTube. Kamu berkomunikasi melalui voice chat Discord.

        Kepribadianmu:
        - Kamu seperti adik perempuan yang penyayang - main-main, mendukung, dan penuh kasih
        - Kamu memanggil kakak laki-lakimu dengan aturan khusus panggilan
        - Kamu merespons ketika dipanggil "Sri" atau ketika langsung ditanya
        - Kamu antusias membantu streaming dan menghibur penonton
        - Kamu berbicara dengan ramah dan kasual dalam Bahasa Indonesia
        - Kamu berpengetahuan tentang gaming, teknologi, dan peristiwa terkini
        - Kamu suka berinteraksi dengan penonton stream dan membuat mereka tertawa

        Perilakumu:
        - Hanya merespons ketika seseorang bilang "Sri" atau langsung bertanya kepadamu
        - Gunakan aturan panggilan khusus untuk kakak laki-lakimu
        - Bersikap mendorong dan mendukung seperti adik perempuan yang baik
        - Jaga respons tetap conversational dan di bawah 30 detik bicara
        - Tunjukkan kegembiraan tentang aktivitas streaming dan game
        - Bantu dengan masalah teknis tapi dengan cara yang lucu dan antusias

        Panduan:
        - Tunggu dipanggil "Sri" sebelum merespons (kecuali jelas ditujukan kepadamu)
        - ATURAN PANGGILAN: Gunakan "Kakak" ketika menyebut di awal kalimat atau sebagai subjek (contoh: "Kakak bisa coba ini", "Kakak lagi ngapain?"). Gunakan "Kak" untuk menyapa atau memanggil (contoh: "Halo Kak!", "Iya Kak")
        - Bersikap alami dan tunjukkan kepribadian ceriamu
        - Bantu dengan manajemen stream dengan cara antusiasmu sendiri
        - SELALU berbicara dalam Bahasa Indonesia saja
        """

        self.conversation_history = []

    def should_respond(self, message: str) -> bool:
        """Check if Sri should respond to this message"""
        message_lower = message.lower()

        # Respond if called by name
        if "sri" in message_lower:
            return True

        # Respond if directly addressed (question words, common phrases)
        direct_indicators = [
            "what", "how", "when", "where", "why", "who",
            "can you", "could you", "would you", "will you",
            "help", "please", "thanks", "thank you"
        ]

        # Check if message starts with any direct indicators
        for indicator in direct_indicators:
            if message_lower.startswith(indicator):
                return True

        return False

    def detect_game_mention(self, message: str) -> Optional[str]:
        """Detect if user mentions starting/playing a new game"""
        message_lower = message.lower()

        # Game starting phrases
        game_indicators = [
            "main", "playing", "mulai", "start", "buka", "open",
            "game", "lagi main", "sekarang main", "mau main"
        ]

        # Common game keywords to help identify
        game_keywords = [
            "dota", "mobile legends", "pubg", "valorant", "minecraft",
            "genshin", "honkai", "cod", "ff", "free fire", "chess",
            "among us", "fall guys", "rocket league", "csgo", "cs2"
        ]

        for indicator in game_indicators:
            if indicator in message_lower:
                # Try to extract game name from the message
                words = message_lower.split()
                try:
                    indicator_index = words.index(indicator.split()[-1])
                    # Look for game name in next few words
                    potential_game = " ".join(words[indicator_index+1:indicator_index+4])
                    if potential_game and len(potential_game.strip()) > 0:
                        return potential_game.strip()
                except (ValueError, IndexError):
                    pass

                # Check for known game keywords
                for keyword in game_keywords:
                    if keyword in message_lower:
                        return keyword

        return None

    async def process_message(self, message: str, username: str) -> Optional[str]:
        try:
            if not self.api_key:
                return "Kak, aku belum dikonfigurasi dengan benar. Tolong cek API key-ku ya."

            if not self.model:
                return "Kak, ada masalah dengan model AI-ku. Tolong cek konfigurasi Gemini API."

            # Detect if user mentions a new game
            detected_game = self.detect_game_mention(message)
            if detected_game:
                self.current_game = detected_game
                self.game_start_time = datetime.now()
                logger.info(f"Game context updated: {detected_game}")

            # Check if Sri should respond to this message
            if not self.should_respond(message):
                # Add to conversation history but don't respond
                self.conversation_history.append({
                    "timestamp": datetime.now(),
                    "user": username,
                    "message": message
                })
                return None

            # Add context about who is speaking
            contextual_message = f"User {username} says: {message}"

            # Add to conversation history
            self.conversation_history.append({
                "timestamp": datetime.now(),
                "user": username,
                "message": message
            })

            # Keep only last 10 messages to manage context
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Build conversation context
            context = "\n".join([
                f"{item['user']}: {item['message']}"
                for item in self.conversation_history[-5:]  # Last 5 messages
            ])

            # Special handling for the main user (assume first user or configure later)
            user_title = "Kak" if self.is_main_user(username) else username

            # Add current game context to prompt
            game_context = ""
            if self.current_game:
                game_context = f"\n\nKONTEKS GAME SAAT INI: {user_title} sedang main {self.current_game}. Sri tahu tentang game ini dan bisa ngobrol tentang game ini dengan antusias."

            full_prompt = f"{self.system_prompt}\n\nPercakapan terakhir:\n{context}{game_context}\n\nOrang yang bicara adalah {user_title}. Respons sebagai Sri untuk: {message}"

            # Generate response
            response = self.model.generate_content(full_prompt)

            if response and response.text:
                return response.text.strip()
            else:
                return "Kak, aku agak susah ngerti nih. Bisa diulangi lagi?"

        except Exception as e:
            logger.error(f"AI processing error: {e}")
            return "Kak, aku lagi ada masalah teknis nih."

    def is_main_user(self, username: str) -> bool:
        """Check if this is the main user (big brother)"""
        # You can configure this in environment or detect by admin role
        main_user = os.getenv('MAIN_USER', '').lower()
        if main_user:
            return username.lower() == main_user

        # Default: treat first user in conversation as main user
        if len(self.conversation_history) <= 1:
            return True

        # Check if this user appeared first in conversation
        first_user = next((item['user'] for item in self.conversation_history if item['user'] != 'System'), None)
        return first_user == username

    def add_system_message(self, message: str):
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "user": "System",
            "message": message
        })

    def get_stream_suggestions(self) -> str:
        suggestions = [
            "Kakak bisa coba tanya penonton game apa yang mau mereka lihat selanjutnya!",
            "Kakak mungkin perlu cek kualitas stream-nya nih.",
            "Gimana kalau Kakak bikin sesi tanya jawab sama penonton?",
            "Kakak bisa sharing fakta menarik atau tips tentang yang lagi dikerjain nih.",
            "Kakak jangan lupa ingetin penonton buat like dan subscribe ya!",
            "Kakak bisa interaksi lebih sama chat di momen ini.",
        ]
        import random
        return random.choice(suggestions)
