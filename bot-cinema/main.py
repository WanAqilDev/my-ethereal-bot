import discord
from discord.ext import commands
import os
import asyncio
from common.database.db import Database

# Basic Setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True # Required for Session Validation

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Cinema Bot connected as {bot.user}')
    
    # Load Cogs
    try:
        await bot.load_extension('cogs.cinema_cog')
        print("Cinema Cog loaded.")
    except Exception as e:
        print(f"Failed to load Cinema Cog: {e}")

async def main():
    token = os.getenv('DISCORD_TOKEN') or os.getenv('CINEMA_BOT_TOKEN')
    if not token or token == 'your_cinema_bot_token_here':
         print("Error: CINEMA_BOT_TOKEN not found.")
         return
    
    # GUARD RAIL: Connect to DB first
    print("⏳ Connecting to Database...")
    try:
        await Database.get_pool()
        print("✅ Database connection established.")
    except Exception as e:
        print(f"❌ CRITICAL: Database connection failed. Bot shutting down.\nReason: {e}")
        return
    
    async with bot:
         await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(Database.close())
