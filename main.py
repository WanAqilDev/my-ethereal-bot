import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    try:
        await bot.load_extension('music_cog')
        print("Music Cog loaded.")
    except Exception as e:
        print(f"Error loading Music Cog: {e}")

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token or token == 'your_token_here':
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(token)
