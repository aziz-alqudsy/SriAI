# SriAI - AI Adik Perempuan untuk Streaming & Gaming

Kenalan sama Sri, adik perempuan AI yang manis dan cerdas yang siap menemani streaming dan gaming kamu! Dia berbicara Bahasa Indonesia dengan natural dan hanya merespons ketika dipanggil namanya - hemat biaya API!

## ✨ Fitur Utama

### 🎤 **Voice-to-Voice Conversation**
- **Local Voice Input**: Dengar suara kamu via microphone komputer (gratis!)
- **Smart Name Recognition**: Hanya merespons ketika dipanggil "Sri"
- **Local TTS Output**: Sri bicara via speaker komputer (Windows SAPI)
- **Anti-Duplicate**: Tidak ada echo atau duplikasi suara

### 🤖 **AI Yang Cerdas**
- **Gemini 2.5 Flash**: AI model terbaru dari Google (gratis 15 RPM)
- **Game Context Aware**: Sri tahu game apa yang kamu main
- **Personality**: Adik perempuan yang supportive dan ceria
- **Indonesian Native**: 100% berbahasa Indonesia natural

### 🎮 **Perfect untuk Gaming & Streaming**
- **OBS Ready**: Voice conversation terekam perfect di OBS
- **Gaming Commands**: Sri bisa kasih tips dan support saat gaming
- **Stream Interaction**: Bantu manage audience dan chat
- **Background Process**: Tidak mengganggu performance game

### 📺 **Discord Integration**
- **Auto Join/Leave**: Ikut masuk/keluar voice channel otomatis
- **Text Backup**: Response juga muncul di chat Discord
- **Smart Commands**: `!join`, `!leave`, `!shutdown`
- **Proper Cleanup**: Tidak ada background process zombie

## 🚀 Instalasi & Setup

### 1. Prerequisites
```bash
# Windows 10/11
Python 3.8+
Git (optional)
```

### 2. Download & Install
```bash
# Clone repository
git clone https://github.com/your-username/SriAI.git
cd SriAI

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup API Keys

**Discord Bot:**
1. Buka https://discord.com/developers/applications
2. Create New Application → Bot
3. Copy Bot Token
4. Enable "Message Content Intent" & "Server Members Intent"

**Google Gemini:**
1. Buka https://makersuite.google.com/app/apikey
2. Create API Key (gratis!)

### 4. Konfigurasi .env
```bash
# Copy template
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
MAIN_USER=your_discord_username  # PENTING: nama Discord kamu
VOICE_CHANNEL_NAME=Sri-Voice     # nama voice channel
```

### 5. Invite Bot ke Server
Permissions yang dibutuhkan:
- Send Messages
- View Channels
- Connect (Voice)
- Speak (Voice)
- Use Voice Activity

URL invite:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=36703232&scope=bot
```

### 6. Jalankan Bot
```bash
python main.py
```

## 🎮 Cara Menggunakan

### Voice Interaction
1. **Join voice channel** yang sudah dikonfigurasi (default: "Sri-Voice")
2. **Ketik `!join`** di text channel untuk mengaktifkan Sri
3. **Bicara dengan memanggil "Sri"**: "Halo Sri", "Sri gimana?", dll
4. **Sri akan merespons** via speaker dan text chat

### Smart Response System
✅ **Sri AKAN merespons:**
- "Halo Sri selamat malam"
- "Sri, apa kabar?"
- "Sri gimana gamenya?"
- "Maju Sri" (saat gaming)

❌ **Sri TIDAK akan merespons:**
- "kanan kanan" (gaming callout tanpa nama)
- "oke let's go" (general chat)
- "mundur-mundur" (directional commands)

### Gaming Integration
```
🎮 Gaming Commands yang Dipahami Sri:
- "Sri maju" → Sri kasih support
- "Sri gimana nih?" → Sri kasih analysis
- "Sri help" → Sri kasih tips
- Game context otomatis terdeteksi (Valorant, PUBG, dll)
```

### Discord Commands
```bash
!join      # Aktifkan voice-to-voice mode
!leave     # Stop voice listening (bot masih aktif)
!shutdown  # Matikan bot sepenuhnya
```

### OBS Recording Setup
1. **Desktop Audio**: ON (untuk suara Sri + game)
2. **Microphone**: ON (untuk suara kamu)
3. **Result**: Perfect voice conversation recording!

## 🔧 Troubleshooting

### Masalah Voice Input
**"Sri tidak dengar suara saya"**
- Cek microphone permissions Windows
- Pastikan tidak ada aplikasi lain yang gunakan mic
- Test dengan Windows Voice Recorder

**"Voice recognition tidak akurat"**
- Bicara lebih jelas dan pelan
- Kurangi background noise
- Pastikan mic dekat dengan mulut

### Masalah AI Response
**"Sri bilang [nama streamer] bukan nama saya"**
- Set `MAIN_USER=nama_discord_kamu` di file `.env`
- Restart bot: `!shutdown` lalu jalankan lagi

**"Sri merespons semua yang saya bilang"**
- Sudah diperbaiki! Sri sekarang hanya merespons saat dipanggil nama

### Masalah Discord
**"Bot tidak bisa join voice channel"**
- Cek bot permissions (Connect + Speak)
- Pastikan `VOICE_CHANNEL_NAME` benar di `.env`
- Coba invite ulang bot dengan permissions lengkap

## 💡 Tips & Best Practices

### Untuk Gaming
- Panggil Sri saat butuh support: "Sri gimana nih?"
- Gunakan untuk callout penting: "Sri enemy kanan"
- Sri bisa kasih motivasi saat kalah: "Sri semangatin dong"

### Untuk Streaming
- Sri bisa interaksi dengan chat viewers
- Gunakan untuk fill dead air saat loading
- Sri bisa kasih game tips untuk audience

### Performance Optimization
- Set Whisper model ke "base" (default) untuk balance speed/accuracy
- Jika PC lemah, ganti ke "tiny" model di `voice_handler.py`
- Close aplikasi berat saat voice conversation

## 📊 Cost Analysis

### 100% Gratis:
- ✅ Local voice recognition (Whisper)
- ✅ Local text-to-speech (Windows SAPI)
- ✅ Discord bot hosting
- ✅ Basic functionality

### API Costs (Gemini):
- **Free Tier**: 15 requests/menit, 1M token/hari
- **Moderate Usage**: $0-2/bulan
- **Heavy Usage**: $2-5/bulan

**Estimate: $0-5/bulan** (jauh lebih murah dari ChatGPT API!)

## 🛠 Advanced Configuration

### Custom Personality
Edit `ai_assistant.py` line 23-49:
```python
self.system_prompt = """
Kamu adalah Sri, adik perempuan AI...
[custom personality here]
"""
```

### Voice Model Settings
Di `voice_handler.py` line 23:
```python
# Faster but less accurate
self.whisper_model = whisper.load_model("tiny")

# Better accuracy but slower
self.whisper_model = whisper.load_model("small")
```

### Gaming Context
Sri otomatis deteksi game dari kata kunci:
- "main valorant" → Context: Valorant
- "buka dota" → Context: Dota 2
- "pubg yuk" → Context: PUBG

## 📁 Project Structure
```
SriAI/
├── main.py                 # Main application & Discord commands
├── ai_assistant.py         # Gemini AI integration & personality
├── voice_handler.py        # Voice input/output & conversation logic
├── local_voice_listener.py # Local microphone handling
├── local_tts.py           # Local text-to-speech
├── stream_manager.py      # YouTube streaming (optional)
├── requirements.txt       # Python dependencies
├── .env.example          # Configuration template
├── .gitignore            # Git ignore rules
└── README.md             # This documentation
```

## 📈 Recent Updates

### v2.1.0 - Major Voice Improvements
- ✅ **Fixed duplicate voice output**: Hanya 1 suara Sri (bukan 2)
- ✅ **Smart name recognition**: Sri hanya merespons saat dipanggil
- ✅ **Proper MAIN_USER support**: Sri panggil nama kamu dengan benar
- ✅ **Better leave command**: `!leave` stop semua voice function
- ✅ **New shutdown command**: `!shutdown` untuk exit bot sepenuhnya
- ✅ **Conservative pattern matching**: Kurangi false positive responses
- ✅ **OBS recording ready**: Perfect voice conversation recording

### v2.0.0 - SriAI Complete Rewrite
- 🎯 **Indonesian AI sister personality**
- 🎤 **Local voice-to-voice conversation**
- 🎮 **Gaming context awareness**
- 📺 **OBS streaming integration**

## 🤝 Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📜 License

MIT License - Bebas dimodifikasi dan distribusi

## 🆘 Support & Community

**Butuh bantuan?**
1. Cek troubleshooting section di atas
2. Baca dokumentasi dengan teliti
3. Pastikan semua prerequisites terpenuhi
4. Test dengan setup minimal dulu

**Feature requests & bug reports:**
- Open GitHub Issues
- Sertakan log error lengkap
- Jelaskan steps to reproduce

---

**🎉 Selamat menggunakan SriAI! Semoga Sri jadi teman gaming & streaming terbaik kamu!**