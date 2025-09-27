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
intents.message_content = True  # Privileged intent - enable in Discord Developer Portal
intents.voice_states = True
intents.guilds = True

class StreamAIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.ai_assistant = AIAssistant()
        self.voice_handler = VoiceHandler(self)
        self.stream_manager = StreamManager()

        # Track recent voice responses to avoid duplicates
        self.recent_voice_responses = []
        self.voice_response_timeout = 5  # seconds

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Sri is in {len(self.guilds)} guilds')

    async def on_message(self, message):
        # Don't respond to bot's own messages
        if message.author == self.user:
            return

        # Check if this message was recently processed as voice input
        import time
        current_time = time.time()

        # Clean old voice responses
        self.recent_voice_responses = [
            (msg, timestamp) for msg, timestamp in self.recent_voice_responses
            if current_time - timestamp < self.voice_response_timeout
        ]

        # Check if this message content was recently processed as voice
        message_lower = message.content.lower().strip()
        for recent_msg, timestamp in self.recent_voice_responses:
            if message_lower == recent_msg.lower().strip():
                logger.info(f"Skipping text response - already processed as voice: {message_lower}")
                await self.process_commands(message)
                return

        # Process the message through AI assistant
        response = await self.ai_assistant.process_message(message.content, message.author.display_name)

        if response:
            # Send text response to chat
            await message.channel.send(response)

            # Use local TTS for voice response to avoid duplication with Discord voice
            if self.voice_handler.local_tts and self.voice_handler.local_tts.is_available():
                self.voice_handler.local_tts.speak(response)

        # Process commands as well
        await self.process_commands(message)

    async def on_voice_state_update(self, member, before, after):
        if member == self.user:
            return

        target_channel_name = os.getenv('VOICE_CHANNEL_NAME', 'Sri-Voice')

        # User left the target channel
        if before.channel and before.channel.name == target_channel_name:
            if not after.channel or after.channel.name != target_channel_name:
                # Only handle if they actually left (not moved within same channel)
                await self.voice_handler.handle_user_leave(member, before.channel)

        # Note: Auto-join disabled to prevent connection issues
        # Use !join command instead

bot = StreamAIBot()

@bot.command(name='join')
async def join_voice(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel

        # Start local voice listener first (always works) - store channel context
        voice_listening_started = bot.voice_handler.local_voice_listener.start_listening()

        # Set the channel context for voice responses
        bot.voice_handler.voice_input_channel = ctx.channel

        # Always prioritize voice input working, try voice output as bonus
        if voice_listening_started:
            try:
                # Try to join Discord voice for TTS output (bonus feature)
                success = await bot.voice_handler.join_channel(channel)
                if success:
                    await ctx.send(f"🎉 **PERFECT! Full Voice-to-Voice aktif!** 🎉\n\n🎤 **Voice Input**: Bicara ke microphone komputer\n🔊 **Voice Output**: Sri balas via Discord voice + speaker komputer\n💬 **Text Backup**: Response juga muncul di chat\n\n**Sri siap ngobrol voice-to-voice!**")
                else:
                    await ctx.send("🎤 **Voice-to-Voice aktif!** 🎤\n\n🎙️ **Voice Input**: Bicara ke microphone komputer\n🔊 **Voice Output**: Sri balas via speaker komputer\n💬 **Text Chat**: Response juga muncul di chat\n\n**Discord voice gagal, tapi voice conversation tetap jalan!**")
            except Exception as e:
                logger.error(f"Voice join error: {e}")
                await ctx.send("🎤 **Voice Input aktif!** 🎤\n\n• Bicara ke microphone komputer\n• Sri akan balas lewat text chat\n• Voice connection bermasalah, tapi fitur utama tetap jalan!")
        else:
            await ctx.send("Maaf Kak, ada masalah dengan microphone. Sri dalam mode text-only ya! 💬")
    else:
        # Even without voice channel, can still do voice input → text output
        voice_listening_started = bot.voice_handler.local_voice_listener.start_listening()

        # Set the channel context for voice responses
        bot.voice_handler.voice_input_channel = ctx.channel

        if voice_listening_started:
            await ctx.send("🎤 **Mode Voice Input aktif!** 🎤\n• Bicara ke microphone komputer\n• Sri akan balas lewat text chat\n• Kak tidak perlu ada di voice channel!")
        else:
            await ctx.send("Kak harus masuk voice channel dulu, atau ada masalah dengan microphone!")

@bot.command(name='leave')
async def leave_voice(ctx):
    # Stop all voice functions
    await bot.voice_handler.stop_listening()

    # Disconnect from Discord voice if connected
    disconnected_from_discord = False
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        disconnected_from_discord = True

    # Always clear voice client reference
    bot.voice_handler.voice_client = None

    if disconnected_from_discord:
        await ctx.send("✅ **Sri sudah keluar sepenuhnya!**\n\n🔇 Voice listening dihentikan\n📞 Keluar dari Discord voice channel\n💬 Sri masih aktif untuk chat text")
    else:
        await ctx.send("✅ **Sri sudah berhenti mendengarkan!**\n\n🔇 Voice listening dihentikan\n💬 Sri masih aktif untuk chat text")

@bot.command(name='start_stream')
async def start_stream(ctx):
    await bot.stream_manager.start_streaming()
    await ctx.send("Siap Kak! Stream YouTube udah dimulai!")

@bot.command(name='stop_stream')
async def stop_stream(ctx):
    await bot.stream_manager.stop_streaming()
    await ctx.send("Stream udah distop ya, Kak!")

@bot.command(name='shutdown')
async def shutdown_bot(ctx):
    # Send goodbye message
    await ctx.send("👋 **Dadah Kak! Sri mau istirahat dulu...**\n\n🔇 Stopping all voice functions...\n📞 Disconnecting from voice...\n🛑 Shutting down bot...")

    # Stop all voice functions
    await bot.voice_handler.stop_listening()

    # Disconnect from voice if connected
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

    # Stop local TTS if available
    if hasattr(bot.voice_handler, 'local_tts') and bot.voice_handler.local_tts:
        try:
            bot.voice_handler.local_tts.stop()
        except:
            pass

    # Close bot connection
    await bot.close()
    logger.info("Sri bot has been shut down by user command")

    # Exit the program
    import sys
    sys.exit(0)

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Please check your .env file configuration.")
        exit(1)

    logger.info("Starting SriAI bot...")
    bot.run(token)
