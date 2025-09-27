# Sri - AI Adik Perempuan untuk YouTube Streaming

Kenalan sama Sri, adik perempuan AI yang manis dan membantu streaming YouTube! Dia berkomunikasi melalui Discord voice channel dan hanya merespons ketika dipanggil namanya. Menggunakan solusi open-source untuk meminimalkan biaya.

## Features

- 🎤 **Speech-to-Text**: Uses OpenAI Whisper (free, runs locally)
- 🔊 **Text-to-Speech**: Uses pyttsx3 (free, cross-platform)
- 🤖 **AI Conversation**: Google Gemini API (free tier: 15 RPM, 1M tokens/day)
- 📺 **YouTube Streaming**: Audio streaming via FFmpeg
- 🎮 **Discord Integration**: Voice channel support
- 💰 **Minimal Cost**: Designed to use free tiers and open-source tools

## Quick Start

### 1. Prerequisites

- Python 3.8+
- FFmpeg installed and in PATH
- Discord Bot Token
- Google Gemini API Key (free at https://makersuite.google.com/app/apikey)
- YouTube Stream Key

### 2. Installation

```bash
# Clone or download the project
git clone <your-repo-url>
cd SriAI

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### 3. Configuration

Edit `.env` file with your credentials:

```env
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
YOUTUBE_STREAM_KEY=your_youtube_stream_key_here
YOUTUBE_RTMP_URL=rtmp://a.rtmp.youtube.com/live2/
BOT_NAME=Sri
VOICE_CHANNEL_NAME=Sri-Voice
MAIN_USER=your_discord_username_here
```

### 4. Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a New Application
3. Go to "Bot" section
4. Create a Bot
5. Copy the Token to your `.env` file
6. Enable these Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent (optional)

### 5. Discord Bot Permissions

Invite your bot with these permissions:
- Connect (Voice)
- Speak (Voice)
- Use Voice Activity
- Send Messages
- View Channels

Invite URL format:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=36703232&scope=bot
```

### 6. YouTube Setup

1. Go to YouTube Studio
2. Click "Go Live"
3. Select "Stream" option
4. Copy your Stream Key to `.env`

### 7. Run the Bot

```bash
python main.py
```

## Usage

### Discord Commands

- `!join` - Join your current voice channel
- `!leave` - Leave the voice channel
- `!start_stream` - Start YouTube streaming
- `!stop_stream` - Stop YouTube streaming

### Voice Interaction

1. Join ke voice channel yang sudah dikonfigurasi (default: "Sri-Voice")
2. Sri akan otomatis join ketika kamu join
3. Panggil "Sri" atau tanya langsung - dia akan transcribe dan merespons sebagai adik perempuanmu
4. Dia manggil kamu "Kak" dan berbicara dalam Bahasa Indonesia melalui Discord
5. Sri hanya merespons ketika dipanggil nama atau langsung ditanya

**Contoh Percakapan:**
- "Sri, apa kabar?" → "Halo Kak! Aku baik-baik aja nih!"
- "Sri, game apa yang bagus buat di-stream?" → "Kakak bisa coba game yang lagi trending!"
- "Sri, gimana stream hari ini?" → "Kakak udah siap banget! Aku excited nih!"

**Aturan Panggilan Sri:**
- **"Kak"** - untuk menyapa atau memanggil: "Halo Kak!", "Iya Kak"
- **"Kakak"** - ketika menyebut sebagai subjek: "Kakak bisa coba ini", "Kakak lagi ngapain?"

### Streaming

- Use `!start_stream` to begin streaming audio to YouTube
- Audio from Discord voice channel will be streamed
- Use `!stop_stream` to end the stream

## Cost Breakdown

### Free Components:
- **OpenAI Whisper**: Free, runs locally
- **pyttsx3**: Free text-to-speech engine
- **Discord Bot**: Free
- **FFmpeg**: Free, open-source
- **YouTube Streaming**: Free

### API Costs:
- **Google Gemini**: Free tier (15 requests/minute, 1M tokens/day)
- After free tier: ~$1-3/month for moderate usage

**Total Monthly Cost: $0-3** depending on usage

## Troubleshooting

### Audio Issues

1. **No desktop audio in stream**:
   - Enable "Stereo Mix" in Windows Sound settings
   - Or use microphone-only mode

2. **Poor voice recognition**:
   - Ensure clear audio input
   - Check Discord voice settings
   - Reduce background noise

3. **TTS not working**:
   - Check if pyttsx3 voices are installed
   - Try different voice settings

### Streaming Issues

1. **Stream won't start**:
   - Verify YouTube stream key
   - Check FFmpeg installation
   - Ensure audio devices are available

2. **High bandwidth usage**:
   - Use AudioOnlyStreamManager for lower bitrate
   - Adjust audio quality settings in stream_manager.py

### Discord Issues

1. **Bot can't join voice**:
   - Check bot permissions
   - Verify voice channel name in .env
   - Ensure bot is in the server

## Advanced Configuration

### Custom AI Personality

Edit `ai_assistant.py` line 20-40 to customize the AI's personality:

```python
self.system_prompt = """
Your custom personality here...
"""
```

### Audio Quality Settings

In `stream_manager.py`, adjust bitrate and quality:
- `-ab '128k'` - Audio bitrate (lower = less bandwidth)
- `-ar '44100'` - Sample rate (22050 for lower quality)

### Voice Recognition Model

Change Whisper model in `voice_handler.py`:
- `base` - Good balance (default)
- `tiny` - Fastest, lower accuracy
- `small` - Good for most uses
- `medium` - Better accuracy, slower

## File Structure

```
SriAI/
├── main.py              # Main bot application
├── ai_assistant.py      # AI conversation handler
├── voice_handler.py     # Speech-to-text & text-to-speech
├── stream_manager.py    # YouTube streaming logic
├── requirements.txt     # Python dependencies
├── .env.example        # Environment template
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - Feel free to modify and distribute

## Support

Untuk masalah dan pertanyaan:
1. Cek bagian troubleshooting
2. Review permissions Discord bot
3. Pastikan semua API keys benar
4. Cek instalasi FFmpeg

## Changelog

- **v1.0.0**: Initial SriAI release
- Adik perempuan AI yang berbicara Bahasa Indonesia
- Sistem panggilan "Kak" dan "Kakak"
- Streaming YouTube dengan voice interaction