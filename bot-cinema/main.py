import discord
from discord.ext import commands
import os
import asyncio
from common.database.db import Database

# Basic Setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Cinema Bot connected as {bot.user}')

    # Initialize Database
    try:
        await Database.get_pool()
        print("Database connected.")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")

    # Load Cogs
    try:
        await bot.load_extension('cogs.cinema_cog')
        print("Cinema Cog loaded.")
    except Exception as e:
        print(f"Failed to load Cinema Cog: {e}")

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found.")
        return
    
    async with bot:
         await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(Database.close())
