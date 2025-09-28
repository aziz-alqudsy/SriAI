import discord
from discord.ext import commands, tasks
import asyncio
import os
from dotenv import load_dotenv
import logging
import signal
import sys
from ai_assistant import AIAssistant
from voice_handler import VoiceHandler
from stream_manager import StreamManager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(threadName)s] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
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

        # Health monitoring
        self.startup_time = None
        self.last_health_check = None

    def cleanup_resources(self):
        """Clean up all bot resources (sync version for signal handlers)"""
        logger.info("Starting bot resource cleanup...")
        try:
            # Cleanup voice handler
            if hasattr(self, 'voice_handler') and self.voice_handler:
                # Cleanup push-to-talk system
                if hasattr(self.voice_handler, 'push_to_talk') and self.voice_handler.push_to_talk:
                    try:
                        self.voice_handler.push_to_talk.stop_listening()
                    except Exception as ptt_error:
                        logger.warning(f"Error stopping push-to-talk: {ptt_error}")

                if hasattr(self.voice_handler, 'local_tts') and self.voice_handler.local_tts:
                    try:
                        self.voice_handler.local_tts.stop()
                    except Exception as tts_error:
                        logger.warning(f"Error stopping TTS: {tts_error}")

            # Stream manager cleanup is handled elsewhere to avoid async issues
            logger.info("Bot resource cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"Error during bot cleanup: {cleanup_error}")

    async def async_cleanup_resources(self):
        """Clean up all bot resources (async version for proper shutdown)"""
        logger.info("Starting async bot resource cleanup...")
        try:
            # Cleanup voice handler
            if hasattr(self, 'voice_handler') and self.voice_handler:
                # Cleanup push-to-talk system
                if hasattr(self.voice_handler, 'push_to_talk') and self.voice_handler.push_to_talk:
                    try:
                        self.voice_handler.push_to_talk.stop_listening()
                    except Exception as ptt_error:
                        logger.warning(f"Error stopping push-to-talk: {ptt_error}")

                if hasattr(self.voice_handler, 'local_tts') and self.voice_handler.local_tts:
                    try:
                        self.voice_handler.local_tts.stop()
                    except Exception as tts_error:
                        logger.warning(f"Error stopping TTS: {tts_error}")

            # Cleanup stream manager properly with async
            if hasattr(self, 'stream_manager') and self.stream_manager:
                try:
                    await self.stream_manager.stop_streaming()
                    logger.info("Stream manager stopped successfully")
                except Exception as stream_error:
                    logger.warning(f"Error stopping stream: {stream_error}")

            logger.info("Async bot resource cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"Error during async bot cleanup: {cleanup_error}")

    @tasks.loop(minutes=5)
    async def health_monitor(self):
        """Monitor bot health and log status"""
        try:
            import time
            current_time = time.time()

            # Check voice system health
            voice_healthy = True
            if hasattr(self, 'voice_handler') and self.voice_handler:
                # Only check push-to-talk system now
                voice_healthy = self.voice_handler.push_to_talk.is_available()

            # Log health status
            uptime_mins = (current_time - self.startup_time) / 60 if self.startup_time else 0
            logger.info(f"Health Check - Uptime: {uptime_mins:.1f}m, Voice: {'✓' if voice_healthy else '✗'}, Guilds: {len(self.guilds)}")

            # Check memory usage
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                if memory_mb > 500:  # Alert if over 500MB
                    logger.warning(f"High memory usage detected: {memory_mb:.1f} MB")
            except Exception:
                pass

            self.last_health_check = current_time

        except Exception as health_error:
            logger.error(f"Health monitor error: {health_error}")

    @health_monitor.before_loop
    async def before_health_monitor(self):
        await self.wait_until_ready()

    async def on_ready(self):
        import time
        self.startup_time = time.time()
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Sri is in {len(self.guilds)} guilds')

        # Start health monitoring
        if not self.health_monitor.is_running():
            self.health_monitor.start()
            logger.info("Health monitoring started")

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

            # Use ElevenLabs TTS with Local TTS fallback for voice response
            self.voice_handler.speak_text(response)

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

        # Set the channel context for voice responses
        bot.voice_handler.voice_input_channel = ctx.channel

        # Start push-to-talk voice input system
        await bot.voice_handler.start_listening(ctx.channel)

        # Get push-to-talk configuration
        ptt_config = bot.voice_handler.push_to_talk.get_config_info()

        # Always try voice output as bonus
        try:
            # Try to join Discord voice for TTS output (bonus feature)
            success = await bot.voice_handler.join_channel(channel)
            if success:
                await ctx.send(f"🎉 **PERFECT! Push-to-Talk Voice aktif!** 🎉\n\n🎙️ **Mode**: Push-to-Talk Only - Tekan `{ptt_config['talk_key'].upper()}`\n🔊 **Voice Output**: Sri balas via Discord voice + speaker\n💬 **Text Backup**: Response juga muncul di chat\n\n**Sri siap ngobrol!**")
            else:
                await ctx.send(f"🎤 **Push-to-Talk aktif!** 🎤\n\n🎙️ **Mode**: Tekan dan tahan `{ptt_config['talk_key'].upper()}`\n🔊 **Voice Output**: Sri balas via speaker komputer\n💬 **Text Chat**: Response juga muncul di chat\n\n**Discord voice gagal, tapi voice conversation tetap jalan!**")
        except Exception as e:
            logger.error(f"Voice join error: {e}")
            await ctx.send(f"🎤 **Push-to-Talk aktif!** 🎤\n\n• Mode: Push-to-Talk Only\n• Sri akan balas lewat text chat\n• Voice connection bermasalah, tapi fitur utama tetap jalan!")
    else:
        # Even without voice channel, can still do voice input → text output
        # Set the channel context for voice responses
        bot.voice_handler.voice_input_channel = ctx.channel

        # Start voice input system
        await bot.voice_handler.start_listening(ctx.channel)

        # Get push-to-talk configuration
        ptt_config = bot.voice_handler.push_to_talk.get_config_info()
        await ctx.send(f"🎤 **Push-to-Talk aktif!** 🎤\n• Tekan dan tahan `{ptt_config['talk_key'].upper()}`\n• Sri akan balas lewat text chat\n• Kak tidak perlu ada di voice channel!")

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

@bot.command(name='tts_usage')
async def tts_usage(ctx):
    """Show ElevenLabs TTS usage information"""
    if hasattr(bot.voice_handler, 'elevenlabs_tts') and bot.voice_handler.elevenlabs_tts.is_available():
        usage = bot.voice_handler.elevenlabs_tts.get_usage_info()

        embed = discord.Embed(
            title="🎤 ElevenLabs TTS Usage",
            color=0x00ff00,
            description="Informasi penggunaan TTS hari ini"
        )

        embed.add_field(name="📊 Karakter Hari Ini", value=f"{usage['daily_used']:,} / {usage['daily_limit']:,}", inline=True)
        embed.add_field(name="💰 Estimasi Biaya", value=f"${usage['cost_estimate_today']:.4f}", inline=True)
        embed.add_field(name="📈 Sisa Quota", value=f"{usage['remaining']:,} karakter", inline=True)

        # Add progress bar
        usage_percent = (usage['daily_used'] / usage['daily_limit']) * 100
        progress_bar = "█" * int(usage_percent // 5) + "░" * (20 - int(usage_percent // 5))
        embed.add_field(name="📋 Progress", value=f"`{progress_bar}` {usage_percent:.1f}%", inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠ ElevenLabs TTS tidak aktif. Cek ELEVENLABS_API_KEY di .env")

@bot.command(name='voices')
async def list_voices(ctx):
    """Show available ElevenLabs voices for user to choose from"""
    if hasattr(bot.voice_handler, 'elevenlabs_tts') and bot.voice_handler.elevenlabs_tts.is_available():
        voices = await bot.voice_handler.elevenlabs_tts.get_available_voices_list()

        if voices:
            embed = discord.Embed(
                title="🎤 Available ElevenLabs Voices",
                color=0x00ff00,
                description="Copy voice ID ke file `.env` sebagai `ELEVENLABS_VOICE_ID=`"
            )

            # Group voices by category or show top voices
            top_voices = voices[:10]  # Show first 10 voices

            voice_text = ""
            for voice in top_voices:
                voice_text += f"**{voice['name']}**\n"
                voice_text += f"ID: `{voice['voice_id']}`\n"
                if voice.get('description'):
                    voice_text += f"_{voice['description'][:50]}..._\n"
                voice_text += "\n"

            embed.add_field(name="🔊 Voice Options", value=voice_text, inline=False)

            # Current voice info
            current_voice = "Auto-selected" if not bot.voice_handler.elevenlabs_tts.user_voice_id else bot.voice_handler.elevenlabs_tts.user_voice_id
            embed.add_field(name="🎯 Current Voice", value=f"`{current_voice}`", inline=False)

            embed.add_field(
                name="📝 How to Change Voice",
                value="1. Copy voice ID yang diinginkan\n2. Tambahkan ke file `.env`: `ELEVENLABS_VOICE_ID=voice_id_here`\n3. Restart bot",
                inline=False
            )

            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Gagal mendapatkan daftar voice dari ElevenLabs")
    else:
        await ctx.send("⚠ ElevenLabs TTS tidak aktif. Cek ELEVENLABS_API_KEY di .env")

@bot.command(name='voice_mode')
async def voice_mode_info(ctx):
    """Show current voice input mode and configuration"""

    embed = discord.Embed(
        title="🎙️ Voice Input Configuration",
        color=0x00ff00
    )

    ptt_config = bot.voice_handler.push_to_talk.get_config_info()
    embed.add_field(
        name="🔘 Current Mode",
        value="**Push-to-Talk**",
        inline=True
    )
    embed.add_field(
        name="🎯 Talk Key",
        value=f"`{ptt_config['talk_key']}`",
        inline=True
    )
    embed.add_field(
        name="📊 Status",
        value="✅ Active" if ptt_config['is_active'] else "❌ Inactive",
        inline=True
    )
    embed.add_field(
        name="⚙️ Settings",
        value=f"Min: {ptt_config['min_duration']}s\nMax: {ptt_config['max_duration']}s",
        inline=True
    )
    embed.add_field(
        name="📝 How to Use",
        value=f"1. Tekan dan tahan tombol `{ptt_config['talk_key'].upper()}`\n2. Bicara dengan jelas\n3. Lepas tombol untuk memproses\n4. Sri akan merespons!",
        inline=False
    )
    embed.add_field(
        name="ℹ️ Info",
        value="SriAI uses push-to-talk for clear voice communication.",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='test_key')
async def test_push_to_talk_key(ctx):
    """Test push-to-talk key detection"""
    if bot.voice_handler.push_to_talk.is_available():
        ptt_config = bot.voice_handler.push_to_talk.get_config_info()

        embed = discord.Embed(
            title="🔧 Push-to-Talk Key Test",
            color=0xff9900,
            description=f"Testing key: `{ptt_config['talk_key']}`"
        )

        embed.add_field(
            name="📝 Instructions",
            value=f"1. Press and hold `{ptt_config['talk_key'].upper()}` key\n2. Check console/logs for key detection\n3. Release key\n4. Check if recording starts/stops",
            inline=False
        )

        embed.add_field(
            name="🔍 Debug Info",
            value=f"**Current Key**: `{ptt_config['talk_key']}`\n**Status**: {'✅ Active' if ptt_config['is_active'] else '❌ Inactive'}\n**Microphone**: {'✅ Available' if ptt_config['microphone_available'] else '❌ Unavailable'}",
            inline=False
        )

        if ptt_config['talk_key'] in ['fn', 'function']:
            embed.add_field(
                name="⚠ Key Problem Detected",
                value="❌ FN key tidak bisa dideteksi!\n💡 Gunakan key lain seperti F1, F2, Space, Ctrl",
                inline=False
            )

        embed.add_field(
            name="🛠 Alternative Keys",
            value="`F1` `F2` `F3` `F4` `Space` `Ctrl` `Alt` `Tab`",
            inline=False
        )

        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Push-to-talk system tidak tersedia")

@bot.command(name='shutdown')
async def shutdown_bot(ctx):
    # Send goodbye message
    await ctx.send("👋 **Dadah Kak! Sri mau istirahat dulu...**\n\n🔇 Stopping all voice functions...\n📞 Disconnecting from voice...\n🛑 Shutting down bot...")

    # Use proper async cleanup
    await bot.async_cleanup_resources()

    # Disconnect from voice if connected
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

    # Close bot connection
    await bot.close()
    logger.info("Sri bot has been shut down by user command")

    # Exit the program
    import sys
    sys.exit(0)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    bot.cleanup_resources()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Please check your .env file configuration.")
        exit(1)

    logger.info("Starting SriAI bot...")
    logger.info(f"Process ID: {os.getpid()}")

    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user (Ctrl+C)")
    except discord.LoginFailure:
        logger.error("Failed to login - invalid Discord token")
    except discord.ConnectionClosed:
        logger.error("Discord connection closed unexpectedly")
    except Exception as e:
        logger.error(f"CRITICAL: Bot crashed with unexpected error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")

        # Log system state for debugging
        try:
            import psutil
            process = psutil.Process()
            logger.error(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
            logger.error(f"CPU usage: {process.cpu_percent():.1f}%")
            logger.error(f"Thread count: {process.num_threads()}")
            logger.error(f"Open files: {len(process.open_files())}")
        except Exception as debug_error:
            logger.error(f"Could not gather system info: {debug_error}")

        # Force cleanup on crash
        try:
            bot.cleanup_resources()
        except Exception as cleanup_error:
            logger.error(f"Error during emergency cleanup: {cleanup_error}")

        raise  # Re-raise for proper exit code
    finally:
        try:
            bot.cleanup_resources()
        except Exception as final_cleanup_error:
            logger.error(f"Error during final cleanup: {final_cleanup_error}")

        logger.info("Bot shutdown complete")
