import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from common.database.db import Database

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True # Required for Economy (XP/Rain)

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    # Load Cogs
    initial_extensions = ['cogs.music_cog', 'cogs.economy_cog', 'cogs.help_cog']
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f"Loaded {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}: {e}")

# Duplicate ping command removed (handled by HelpCog)

@bot.command(name='restart', help='Restarts the bot (Admin only)')
@commands.is_owner()
async def restart(ctx):
    await ctx.send('Restarting...')
    await bot.close()
    import sys
    sys.exit(0)

async def main():
    # Support both docker env var (mapped) and native .env (direct)
    token = os.getenv('DISCORD_TOKEN') or os.getenv('MUSIC_BOT_TOKEN')
    if not token or token == 'your_music_bot_token_here':
        print("Error: MUSIC_BOT_TOKEN not found in .env file.")
        return
    
    # GUARD RAIL: Connect to DB *before* logging in
    # This specifically prevents "Zombie" native processes (which lack DB) 
    # from staying online and confusing users.
    print("⏳ Connecting to Database...")
    try:
        await Database.get_pool()
        print("✅ Database connection established.")
    except Exception as e:
        print(f"❌ CRITICAL failure: Could not connect to Database. Bot will NOT start.\nReason: {e}")
        return

    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # cleanup
        asyncio.run(Database.close())
