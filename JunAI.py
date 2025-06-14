import discord
import requests
import tempfile
import os
import asyncio
import keyboard
import time
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from discord import FFmpegPCMAudio
from dotenv import load_dotenv
from openai import OpenAI

# --- Load API Keys ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
ELEVEN_VOICE_ID = os.getenv("ELEVEN_VOICE_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Setup Discord ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = discord.Client(intents=intents)
vc = None

user_histories = {}

# --- Rekam suara ke WAV ---
def record_audio_while_key_pressed(filename="temp.wav", fs=44100, key='esc'):
    print("🎙️ Rekaman dimulai (selama tombol ditekan)...")
    frames = []

    def callback(indata, frames_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=fs, channels=1, callback=callback):
        while keyboard.is_pressed(key):
            time.sleep(0.05)

    print("🛑 Tombol dilepas, rekaman selesai.")

    audio_np = np.concatenate(frames, axis=0)
    wav.write(filename, fs, audio_np)


# --- STT: ElevenLabs ---
def transcribe_with_elevenlabs(audio_path):
    with open(audio_path, 'rb') as f:
        files = {'file': f}
        data = {'model_id': 'scribe_v1_experimental'}
        headers = {
            "Accept": "application/json",
            "xi-api-key": ELEVEN_API_KEY
        }
        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers=headers,
            files=files,
            data=data
        )
    if response.status_code == 200:
        return response.json()["text"]
    else:
        print("❌ STT error:", response.text)
        return ""

# --- GPT: OpenAI v1.0 SDK ---
def ask_chatgpt(prompt, user_id):
    global user_histories

    if user_id not in user_histories:
        user_histories[user_id] = [
            {"role": "system", "content": "Kamu adalah Jun, teman ngobrol yang lugu, polos, manis, gemas, manja, cengeng, dan berbicara seperti adik ke kakaknya. Kadang suka melucu dan sarkas terhadap pernyataan yang tidak masuk akal."},
        ]

    chat_history = user_histories[user_id]
    chat_history.append({"role": "user", "content": prompt})
    log_conversation(user_id, "user", prompt)

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=chat_history
    )

    reply = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": reply})
    log_conversation(user_id, "assistant", reply)

    # Batasi panjang
    if len(chat_history) > 9:
        user_histories[user_id] = [chat_history[0]] + chat_history[-8:]

    return reply

# --- Log Conversations ---
if not os.path.exists("logs"):
    os.makedirs("logs")

def log_conversation(user_id, role, content):
    log_file = f"logs/{user_id}.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{role.upper()}] {content}\n")

# --- TTS: ElevenLabs ---
def generate_tts(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print("❌ TTS error:", response.text)
        return None

    mp3_path = tempfile.mktemp(suffix=".mp3")
    with open(mp3_path, "wb") as f:
        f.write(response.content)
    return mp3_path

# --- Discord Events ---
@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} aktif.")
    print("➡️ Tekan [1] supaya bot join voice channel")
    print("➡️ Tekan [Escape] untuk bicara dan tunggu balasan")

async def input_loop():
    global vc
    loop = asyncio.get_event_loop()

    def handle_key_event():
        if keyboard.is_pressed('1'):
            for guild in bot.guilds:
                for member in guild.members:
                    if member.id != bot.user.id and member.voice and member.voice.channel:
                        return ('join', member.voice.channel)
        elif keyboard.is_pressed('esc'):
            return ('talk', None)
        return (None, None)

    while True:
        await asyncio.sleep(0.2)
        action, data = await loop.run_in_executor(None, handle_key_event)
        if action == 'join':
            if not vc or not vc.is_connected():
                vc = await data.connect()
                print("📥 Bot masuk ke voice channel:", data.name)
        elif action == 'talk':
            print("⏺ Tombol Escape ditekan")
            try:
                await asyncio.to_thread(record_audio_while_key_pressed, "temp.wav")
                print("📤 Mengirim ke ElevenLabs STT...")
                text = await asyncio.to_thread(transcribe_with_elevenlabs, "temp.wav")
                print("📝 Transkrip:", text)
                if not text.strip():
                    continue
                user_id = "local_user"
                reply = await asyncio.to_thread(ask_chatgpt, text, user_id)
                print("🤖 GPT Balas:", reply)
                mp3 = await asyncio.to_thread(generate_tts, reply)
                if mp3 and vc:
                    print("🔊 Memutar suara ke VC...")
                    vc.play(FFmpegPCMAudio(mp3))
                    while vc.is_playing():
                        await asyncio.sleep(0.5)
            except Exception as e:
                print("❌ ERROR saat proses rekaman/balas:", e)

@bot.event
async def on_connect():
    bot.loop.create_task(input_loop())

bot.run(DISCORD_BOT_TOKEN)
