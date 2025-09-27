import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import logging
from ai_assistant import AIAssistant
from voice_handler import VoiceHandler
from stream_manager import StreamManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class StreamAIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.ai_assistant = AIAssistant()
        self.voice_handler = VoiceHandler(self)
        self.stream_manager = StreamManager()

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Sri is in {len(self.guilds)} guilds')

    async def on_voice_state_update(self, member, before, after):
        if member == self.user:
            return

        if after.channel and after.channel.name == os.getenv('VOICE_CHANNEL_NAME', 'Sri-Voice'):
            await self.voice_handler.handle_user_join(member, after.channel)
        elif before.channel and before.channel.name == os.getenv('VOICE_CHANNEL_NAME', 'Sri-Voice'):
            await self.voice_handler.handle_user_leave(member, before.channel)

bot = StreamAIBot()

@bot.command(name='join')
async def join_voice(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await bot.voice_handler.join_channel(channel)
        await ctx.send(f"Halo Kak! Sri udah join ke {channel.name}!")
    else:
        await ctx.send("Kak harus masuk voice channel dulu!")

@bot.command(name='leave')
async def leave_voice(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Dadah Kak! Sri keluar dari voice channel dulu ya!")
    else:
        await ctx.send("Sri belum ada di voice channel, Kak!")

@bot.command(name='start_stream')
async def start_stream(ctx):
    await bot.stream_manager.start_streaming()
    await ctx.send("Siap Kak! Stream YouTube udah dimulai!")

@bot.command(name='stop_stream')
async def stop_stream(ctx):
    await bot.stream_manager.stop_streaming()
    await ctx.send("Stream udah distop ya, Kak!")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Please check your .env file configuration.")
        exit(1)

    logger.info("Starting SriAI bot...")
    bot.run(token)
