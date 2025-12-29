import discord
from discord.ext import commands, tasks
import yt_dlp
import asyncio
import subprocess
import shlex
import os
import json
import redis.asyncio as redis
from common.database.db import Database

# Suppress noisy yt-dlp logs
yt_dlp.utils.std_headers['User-Agent'] = 'Mozilla/5.0'

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

FILTERS = {
    "bassboost": "bass=g=20,dynaudnorm=f=200",
    "nightcore": "asetrate=48000*1.25,aresample=48000,atempo=1.0",
    "8d": "apulsator=hz=0.125",
    "normal": ""
}

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queue = []
        self.current_song = None
        self.volume_level = 0.5
        self.loop_mode = "off"
        self.active_filter = "normal"
        
        # Smart Redis URL detection
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        # If native (windows), verify we can actually resolve 'redis' hostname.
        # If not, fallback to localhost.
        try:
             import socket
             host = redis_url.split('@')[-1].split(':')[0].replace('//', '') # naive parse
             socket.gethostbyname(host)
        except:
             print("⚠️ Could not resolve Redis host. Falling back to localhost.")
             redis_url = 'redis://localhost:6379/0'

        self.redis = redis.from_url(redis_url, decode_responses=True)
        
        self.inactivity_check.start()
        if not os.path.exists('./cache'):
            os.makedirs('./cache')
            
        self.bot.loop.create_task(self.restore_state())

    async def restore_state(self):
        await self.bot.wait_until_ready()
        # In a real multi-guild bot, iterate all guilds. 
        # For simplicity, we skip auto-restore on boot for now to avoid complexity of getting guild IDs without events.
        pass

    async def save_state(self, guild_id):
        key = f"music_queue:{guild_id}"
        await self.redis.delete(key)
        if self.music_queue:
            json_songs = [json.dumps(s) for s in self.music_queue]
            await self.redis.rpush(key, *json_songs)
        
        await self.redis.hset(f"music_state:{guild_id}", mapping={
            "loop_mode": self.loop_mode,
            "filter": self.active_filter
        })

    def get_ffmpeg_options(self, start_timestamp="00:00:00"):
        options = FFMPEG_OPTIONS.copy()
        options['before_options'] = f"-ss {start_timestamp} " + options['before_options']
        filter_str = FILTERS.get(self.active_filter, "")
        if filter_str:
            options['options'] += f' -af "{filter_str}"'
        return options

    async def play_music(self, ctx, song, start_timestamp="00:00:00"):
        url = song['url']
        try:
            ffmpeg_opts = self.get_ffmpeg_options(start_timestamp)
            ffmpeg_exec = './ffmpeg' if os.path.isfile('./ffmpeg') else 'ffmpeg'
            
            loop = self.bot.loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTIONS).extract_info(url, download=False))
            if 'entries' in data: data = data['entries'][0]
            stream_url = data['url']
            
            source = discord.FFmpegPCMAudio(stream_url, executable=ffmpeg_exec, **ffmpeg_opts)
            volume_source = discord.PCMVolumeTransformer(source, volume=self.volume_level)
            
            if ctx.voice_client is None:
                if ctx.author.voice:
                    await ctx.author.voice.channel.connect()
                else:
                    return await ctx.send("You are not in a voice channel.")

            if ctx.voice_client:
                if ctx.voice_client.is_playing(): ctx.voice_client.stop()
                ctx.voice_client.play(volume_source, after=lambda e: self.check_queue(ctx, e))
                
                if start_timestamp == "00:00:00":
                    await self.send_now_playing(ctx, song)
                    if 'requester_id' in song:
                        economy = self.bot.get_cog("EconomyCog")
                        if economy: await economy.add_xp(song['requester_id'], 5, ctx.channel)
        
        except Exception as e:
            await ctx.send(f"Error playing {song['title']}: {e}")
            self.check_queue(ctx, e)

    def check_queue(self, ctx, error):
        if error: print(f"Player error: {error}")
        
        if self.loop_mode == "song" and self.current_song:
            asyncio.run_coroutine_threadsafe(self.play_music(ctx, self.current_song), self.bot.loop)
            return

        if self.loop_mode == "queue" and self.current_song:
            self.music_queue.append(self.current_song)
            asyncio.run_coroutine_threadsafe(self.save_state(ctx.guild.id), self.bot.loop)

        if len(self.music_queue) > 0:
            next_song = self.music_queue.pop(0)
            self.current_song = next_song
            asyncio.run_coroutine_threadsafe(self.play_music(ctx, next_song), self.bot.loop)
            asyncio.run_coroutine_threadsafe(self.save_state(ctx.guild.id), self.bot.loop)
        else:
            self.current_song = None
            asyncio.run_coroutine_threadsafe(self.save_state(ctx.guild.id), self.bot.loop)

    async def send_now_playing(self, ctx, song):
        embed = discord.Embed(title="Now Playing 🎶", description=f"[{song['title']}]({song['url']})", color=discord.Color.green())
        status = []
        if self.loop_mode != "off": status.append(f"🔁 {self.loop_mode.capitalize()}")
        if self.active_filter != "normal": status.append(f"🎚️ {self.active_filter.capitalize()}")
        if status: embed.set_footer(text=" | ".join(status))
        await ctx.send(embed=embed)

    @commands.command(name="join")
    async def join(self, ctx):
        if ctx.author.voice:
            if ctx.voice_client: await ctx.voice_client.move_to(ctx.author.voice.channel)
            else: await ctx.author.voice.channel.connect()
        else: await ctx.send("Join a voice channel first!")

    @commands.command(name="play", help="Play a song")
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice: return await ctx.send("Join VC first!")
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        
        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0])
                
                song = {
                    'url': info['webpage_url'], 
                    'title': info['title'], 
                    'requester_id': ctx.author.id,
                    'duration': info.get('duration', 0)
                }

                if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                    self.music_queue.append(song)
                    await self.save_state(ctx.guild.id)
                    await ctx.send(f"Added to queue: **{song['title']}**")
                else:
                    self.current_song = song
                    await self.play_music(ctx, song)
                    await self.save_state(ctx.guild.id)
            except Exception as e:
                await ctx.send(f"Error: {e}")

    @commands.command(name="skip")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            temp_loop = self.loop_mode
            if self.loop_mode == "song":
                self.loop_mode = "off"
            ctx.voice_client.stop()
            await ctx.send("Skipped ⏭️")

    @commands.command(name="loop")
    async def loop(self, ctx, mode: str):
        if mode in ["off", "song", "queue"]:
            self.loop_mode = mode
            await self.save_state(ctx.guild.id)
            await ctx.send(f"Loop mode: **{mode}**")
        else: await ctx.send("Modes: off, song, queue")

    @commands.command(name="filter")
    async def filter(self, ctx, filter_name: str):
        if filter_name in FILTERS:
            self.active_filter = filter_name
            await self.save_state(ctx.guild.id)
            await ctx.send(f"Filter set to: **{filter_name}**.")
        else: await ctx.send(f"Filters: {', '.join(FILTERS.keys())}")

    @commands.command(name="seek")
    async def seek(self, ctx, timestamp: str):
        if ctx.voice_client and ctx.voice_client.is_playing() and self.current_song:
            await ctx.send(f"Seeking to {timestamp}...")
            await self.play_music(ctx, self.current_song, start_timestamp=timestamp)

    @commands.command(name="queue")
    async def queue(self, ctx):
        if not self.music_queue and not self.current_song: return await ctx.send("Queue empty.")
        desc = ""
        if self.current_song: desc += f"**Now Playing**: {self.current_song['title']}\n\n"
        desc += "**Up Next**:\n"
        for i, s in enumerate(self.music_queue[:10]): desc += f"{i+1}. {s['title']}\n"
        embed = discord.Embed(title="Queue", description=desc, color=discord.Color.blue())
        await ctx.send(embed=embed)

    @commands.command(name="remove")
    async def remove(self, ctx, index: int):
        if 1 <= index <= len(self.music_queue):
            removed = self.music_queue.pop(index-1)
            await self.save_state(ctx.guild.id)
            await ctx.send(f"Removed: {removed['title']}")

    @commands.command(name="bump")
    async def bump(self, ctx, index: int):
        economy = self.bot.get_cog("EconomyCog")
        if economy and not await economy.remove_balance(ctx.author.id, 100):
            return await ctx.send("Need 100 💎 to bump!")
        
        if 1 <= index <= len(self.music_queue):
            song = self.music_queue.pop(index-1)
            self.music_queue.insert(0, song)
            await self.save_state(ctx.guild.id)
            await ctx.send(f"Bumped **{song['title']}**!")

    @commands.command(name="stop")
    async def stop(self, ctx):
        self.music_queue = []
        self.current_song = None
        self.loop_mode = "off"
        await self.save_state(ctx.guild.id)
        if ctx.voice_client: await ctx.voice_client.disconnect()
        await ctx.send("Stopped.")

    @commands.group(name="playlist", aliases=["pl"], invoke_without_command=True)
    async def playlist(self, ctx):
        await ctx.send("Use: `!playlist save <name>`, `load <name>`, `list`")

    @playlist.command(name="save")
    async def pl_save(self, ctx, name: str):
        songs = ([self.current_song] if self.current_song else []) + self.music_queue
        if not songs: return await ctx.send("Nothing to save.")
        if len(songs) > 20: songs = songs[:20]
        
        json_songs = json.dumps(songs)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            try:
                await conn.execute("INSERT INTO playlists (user_id, name, songs) VALUES ($1, $2, $3)", ctx.author.id, name, json_songs)
                await ctx.send(f"Playlist **{name}** saved!")
            except: await ctx.send(f"Playlist **{name}** already exists.")

    @playlist.command(name="load")
    async def pl_load(self, ctx, name: str):
        if not ctx.author.voice: return await ctx.send("Join VC first.")
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT songs FROM playlists WHERE user_id = $1 AND name = $2", ctx.author.id, name)
            if not row: return await ctx.send("Not found.")
            for s in json.loads(row['songs']): self.music_queue.append(s)
            await ctx.send(f"Loaded **{name}**!")
            if not (ctx.voice_client and ctx.voice_client.is_playing()) and not self.current_song:
                self.check_queue(ctx, None)

    @playlist.command(name="list")
    async def pl_list(self, ctx):
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, jsonb_array_length(songs) as count FROM playlists WHERE user_id = $1", ctx.author.id)
            if not rows: return await ctx.send("No playlists.")
            desc = "\n".join([f"• **{r['name']}** ({r['count']} songs)" for r in rows])
            await ctx.send(embed=discord.Embed(title="Playlists", description=desc, color=discord.Color.green()))

    @tasks.loop(minutes=5)
    async def inactivity_check(self):
        for guild in self.bot.guilds:
            if guild.voice_client and guild.voice_client.is_connected():
                if not guild.voice_client.is_playing() and not guild.voice_client.is_paused():
                     await guild.voice_client.disconnect()
                if len(guild.voice_client.channel.members) == 1:
                    await guild.voice_client.disconnect()

    @inactivity_check.before_loop
    async def before_inactivity(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
