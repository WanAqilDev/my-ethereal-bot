import discord
from discord.ext import commands
import yt_dlp
import asyncio
import subprocess
import shlex
import os

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

DEFAULT_VOLUME = 0.5

class YTDLStreamSource(discord.AudioSource):
    def __init__(self, process, volume=DEFAULT_VOLUME):
        self.process = process
        self.volume = volume

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        
        # Get video info first
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        
        if 'entries' in info:
            info = info['entries'][0]
            
        real_url = info['url']
        title = info.get('title', 'Unknown')

        # Construct the pipe command
        # yt-dlp -o - "URL" | ffmpeg -i pipe:0 ...
        
        # We use the real URL here because passing the search term to yt-dlp -o - might be tricky with quotes
        # But wait, yt-dlp -o - "URL" works.
        
        # Determine executables
        # Check for local ffmpeg
        if os.path.isfile('./ffmpeg'):
            ffmpeg_exec = './ffmpeg'
        else:
            ffmpeg_exec = 'ffmpeg'

        # Check for local yt-dlp in .venv
        if os.path.isfile('./.venv/bin/yt-dlp'):
            yt_dlp_exec = './.venv/bin/yt-dlp'
        else:
            yt_dlp_exec = 'yt-dlp'

        # Command to pipe yt-dlp output to ffmpeg
        yt_dlp_cmd = f'{yt_dlp_exec} -o - "{real_url}"'
        ffmpeg_cmd = f'{ffmpeg_exec} -i pipe:0 -f s16le -ar 48000 -ac 2 -loglevel warning pipe:1'
        
        full_cmd = f'{yt_dlp_cmd} | {ffmpeg_cmd}'
        
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            shell=True,
            bufsize=10**6 # Large buffer
        )
        
        return cls(process), title

    def read(self):
        ret = self.process.stdout.read(3840) # 20ms of audio at 48kHz stereo 16-bit
        if len(ret) != 3840:
            return b''
        return ret

    def cleanup(self):
        self.process.kill()

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join", help="Joins the voice channel")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("Join a voice channel first!")

        channel = ctx.author.voice.channel
        if not ctx.voice_client:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

    @commands.command(name="play", help="Plays a song from search term")
    async def play(self, ctx, *, search: str):
        if not ctx.author.voice:
            return await ctx.send("Join a voice channel first!")

        channel = ctx.author.voice.channel
        if not ctx.voice_client:
            vc = await channel.connect()
        else:
            vc = ctx.voice_client

        async with ctx.typing():
            try:
                # Search first to get the URL
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0])
                    url = info['url'] # This is the direct stream URL usually, but for yt-dlp -o - we might want the webpage URL?
                    # Actually, if we pass the webpage URL to yt-dlp -o -, it downloads it.
                    # If we pass the direct stream URL (googlevideo.com...), yt-dlp might just download it too.
                    # Let's use the webpage URL (webpage_url) if available, or just the ID.
                    webpage_url = info.get('webpage_url', url)
                    title = info.get('title', 'Unknown')

                await ctx.send(f"Playing **{title}**")
                
                # Create the source
                source, _ = await YTDLStreamSource.from_url(webpage_url, loop=self.bot.loop)
                
                # Wrap in PCMVolumeTransformer for volume control
                volume_source = discord.PCMVolumeTransformer(source, volume=DEFAULT_VOLUME)
                
                if vc.is_playing():
                    # Graceful stop: Fade out
                    if isinstance(vc.source, discord.PCMVolumeTransformer):
                        start_volume = vc.source.volume
                        steps = 10
                        for i in range(steps):
                            vc.source.volume = start_volume * (1 - (i + 1) / steps)
                            await asyncio.sleep(0.1)
                    vc.stop()
                
                vc.play(volume_source, after=lambda e: print(f"Player error: {e}") if e else None)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                await ctx.send(f"Error playing: {e}")

    @commands.command(name="volume", help="Changes the player's volume")
    async def volume(self, ctx, volume: int):
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        if volume < 0 or volume > 100:
            return await ctx.send("Volume must be between 0 and 100.")

        if ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100
            await ctx.send(f"Changed volume to {volume}%")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="stop", help="Stops and disconnects")
    async def stop(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

    @commands.command(name="leave", help="Leaves the voice channel")
    async def leave(self, ctx):
        await self.stop(ctx)

    @commands.command(name="pause", help="Pauses the current song playing")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Paused ⏸️")

    @commands.command(name="resume", help="Resumes playing")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Resumed ▶️")

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
