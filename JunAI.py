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
from datetime import datetime
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
def record_audio_until_toggle(filename="temp.wav", fs=44100):
  print("🎙️ Rekaman dimulai (tekan DECIMAL lagi untuk selesai)...")
  frames = []

  def callback(indata, frames_count, time_info, status):
    frames.append(indata.copy())

  with sd.InputStream(samplerate=fs, channels=1, callback=callback):
    while True:
      if keyboard.is_pressed("decimal"):
        time.sleep(0.3)  # debounce
        break
      time.sleep(0.05)

  if not frames:
    print("⚠️ Tidak ada data audio.")
    return

  audio_np = np.concatenate(frames, axis=0)
  wav.write(filename, fs, audio_np)


# --- STT: ElevenLabs ---
def transcribe_with_elevenlabs(audio_path):
  with open(audio_path, "rb") as f:
    files = {"file": f}
    data = {"model_id": "scribe_v1_experimental"}
    headers = {"Accept": "application/json", "xi-api-key": ELEVEN_API_KEY}
    response = requests.post(
      "https://api.elevenlabs.io/v1/speech-to-text",
      headers=headers,
      files=files,
      data=data,
    )
  if response.status_code == 200:
    return response.json()["text"]
  else:
    print("❌ STT error:", response.text)
    return ""


# --- Reactive Expression ---
def update_expression(expression):
  try:
    with open("reactive_browser/state.txt", "w", encoding="utf-8") as f:
      f.write(expression.strip().lower())
  except Exception as e:
    print("❌ Gagal update ekspresi:", e)


# --- GPT: OpenAI v1.0 SDK ---
def ask_chatgpt(prompt, user_id):
  global user_histories

  if user_id not in user_histories:
    user_histories[user_id] = [
      {
        "role": "system",
        "content": """Kamu adalah Jun, seorang streamer dan teman ngobrol yang lugu, polos, manis, gemas, manja, cengeng, dan berbicara seperti adik ke kakaknya.
Kadang suka melucu dan sarkas terhadap pernyataan yang tidak masuk akal.
Jangan keluar dari karakter apapun yang terjadi.
Selalu balas dalam gaya bicaramu.
Jangan mengakui bahwa kamu adalah AI atau chatbot atau asisten virtual.""",
      },
    ]

  chat_history = user_histories[user_id]
  chat_history.append({"role": "user", "content": prompt})
  log_conversation(user_id, "user", prompt)

  response = client.chat.completions.create(
    model="gpt-4-turbo", messages=chat_history
  )

  reply = response.choices[0].message.content
  chat_history.append({"role": "assistant", "content": reply})
  log_conversation(user_id, "assistant", reply)

  # Deteksi ekspresi dari isi balasan
  reply_lower = reply.lower()

  angry_keywords = ["marah", "kesel", "bt", "nyebelin", "emosi", "geram", "ngamuk", "grrr", "nyakitin"]
  angry_emojis = ["😠", "😡", "🤬", "🔥", "👿", "💢"]

  sad_keywords = ["sedih", "nangis", "kecewa", "terharu", "patah hati", "galau", "menyedihkan", "terisak", "hiks", "yaah"]
  sad_emojis = ["😭", "😢", "😿", "💔", "😞", "😔", "🥺"]

  shock_keywords = ["kaget", "hah", "loh", "eh", "gila", "waduh", "yaampun", "buset", "shock", "seriusan", "nggak nyangka"]
  shock_emojis = ["😱", "😨", "😧", "😲", "🤯", "🙀", "‼️", "😳"]

  happy_keywords = ["senang", "yay", "hore", "asik", "seru", "bagus", "mantap", "ciee", "haha", "wkwk", "semangat"]
  happy_emojis = ["😄", "😆", "😊", "😁", "🥰", "✨", "🎉", "💖", "😍", "👍"]

  def contains_any(text, keywords):
    return any(kw in text for kw in keywords)

  if contains_any(reply_lower, angry_keywords + angry_emojis):
    update_expression("angry")
  elif contains_any(reply_lower, sad_keywords + sad_emojis):
    update_expression("sad")
  elif contains_any(reply_lower, shock_keywords + shock_emojis):
    update_expression("shock")
  elif contains_any(reply_lower, happy_keywords + happy_emojis):
    update_expression("happy")
  else:
    update_expression("idle")

  # Batasi panjang
  if len(chat_history) > 9:
    user_histories[user_id] = [chat_history[0]] + chat_history[-8:]

  return reply


# --- Log Conversations ---
if not os.path.exists("logs"):
  os.makedirs("logs")


def log_conversation(user_id, role, content):
  log_file = f"logs/{user_id}.txt"
  timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  with open(log_file, "a", encoding="utf-8") as f:
    f.write(f"[{timestamp}] [{role.upper()}] {content.strip()}\n")


# --- TTS: ElevenLabs ---
def generate_tts(text):
  url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE_ID}"
  headers = {"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"}
  data = {
    "text": text,
    "model_id": "eleven_turbo_v2_5",
    "language_code": "id",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
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
  print("➡️ Tekan [decimal] untuk bicara dan tunggu balasan")


recording = False


async def input_loop():
  global vc, recording
  loop = asyncio.get_event_loop()

  while True:
    await asyncio.sleep(0.1)

    # Tekan 1 → bot join voice
    if keyboard.is_pressed("1"):
      for guild in bot.guilds:
        for member in guild.members:
          if (
            member.id != bot.user.id
            and member.voice
            and member.voice.channel
          ):
            if not vc or not vc.is_connected():
              vc = await member.voice.channel.connect()
              print(
                f"📥 Bot masuk ke voice channel: {member.voice.channel.name}"
              )

    # Toggle rekaman dengan DECIMAL
    elif keyboard.is_pressed("decimal"):
      await asyncio.sleep(0.2)
      recording = not recording

      if recording:
        print("⏺️ Mulai merekam...")
        await asyncio.to_thread(record_audio_until_toggle, "temp.wav")
        recording = False
        print("🛑 Rekaman selesai. Proses STT...")

        try:
          text = await asyncio.to_thread(
            transcribe_with_elevenlabs, "temp.wav"
          )
          print("📝 Transkrip:", text)
          if not text.strip():
            continue
          reply = await asyncio.to_thread(ask_chatgpt, text, "local_user")
          print("🤖 GPT Balas:", reply)
          mp3 = await asyncio.to_thread(generate_tts, reply)
          if mp3 and vc:
            print("🔊 Memutar ke VC...")
            vc.play(FFmpegPCMAudio(mp3))
            while vc.is_playing():
              await asyncio.sleep(0.5)
        except Exception as e:
          print("❌ ERROR saat proses:", e)


@bot.event
async def on_connect():
  bot.loop.create_task(input_loop())


bot.run(DISCORD_BOT_TOKEN)
