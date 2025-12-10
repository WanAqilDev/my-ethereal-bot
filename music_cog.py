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
        self.music_queue = []
        self.current_song = None
        self.volume_level = DEFAULT_VOLUME
        self.download_tasks = {} # Track active downloads
        
        if not os.path.exists('./cache'):
            os.makedirs('./cache')

    async def download_song(self, song):
        url = song['url']
        # Use a safe filename based on URL hash or ID if available
        # For simplicity, let's use a simple hash of the URL
        import hashlib
        file_id = hashlib.md5(url.encode()).hexdigest()
        output_template = f"./cache/{file_id}.%(ext)s"
        
        print(f"Starting background download for: {song['title']}")
        
        def run_download():
            opts = YDL_OPTIONS.copy()
            opts['outtmpl'] = output_template
            opts['format'] = 'bestaudio/best'
            # Ensure we don't use the pipe options
            if 'source_address' in opts: del opts['source_address']
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        try:
            filename = await self.bot.loop.run_in_executor(None, run_download)
            song['local_path'] = filename
            print(f"Download complete: {song['title']} -> {filename}")
        except Exception as e:
            print(f"Download failed for {song['title']}: {e}")
        finally:
            # Remove from active tasks
            if url in self.download_tasks:
                del self.download_tasks[url]

    def trigger_prefetch(self):
        # Prefetch next 2 songs
        to_prefetch = self.music_queue[:2]
        for song in to_prefetch:
            url = song['url']
            if 'local_path' not in song and url not in self.download_tasks:
                # Use run_coroutine_threadsafe because this might be called from a thread
                task = asyncio.run_coroutine_threadsafe(self.download_song(song), self.bot.loop)
                self.download_tasks[url] = task

    def check_queue(self, ctx, error):
        if error:
            print(f"Player error: {error}")
        
        # Cleanup previous song if it was a local file
        if self.current_song and 'local_path' in self.current_song:
            try:
                if os.path.exists(self.current_song['local_path']):
                    os.remove(self.current_song['local_path'])
                    print(f"Deleted cached file: {self.current_song['local_path']}")
            except Exception as e:
                print(f"Error deleting file: {e}")

        if len(self.music_queue) > 0:
            next_song = self.music_queue.pop(0)
            self.current_song = next_song
            asyncio.run_coroutine_threadsafe(self.play_music(ctx, next_song), self.bot.loop)
            
            # Trigger prefetch for the new state of the queue
            self.trigger_prefetch()
        else:
            self.current_song = None

    async def play_music(self, ctx, song):
        url = song['url']
        title = song['title']
        
        try:
            source = None
            if 'local_path' in song and os.path.exists(song['local_path']):
                print(f"Playing from cache: {song['local_path']}")
                
                # Determine ffmpeg executable
                ffmpeg_exec = './ffmpeg' if os.path.isfile('./ffmpeg') else 'ffmpeg'
                
                source = discord.FFmpegPCMAudio(song['local_path'], executable=ffmpeg_exec)
            else:
                print(f"Streaming from URL: {url}")
                source, _ = await YTDLStreamSource.from_url(url, loop=self.bot.loop)
                
            volume_source = discord.PCMVolumeTransformer(source, volume=self.volume_level)
            
            if ctx.voice_client:
                ctx.voice_client.play(volume_source, after=lambda e: self.check_queue(ctx, e))
                await ctx.send(f"Now playing: **{title}**")
        except Exception as e:
            await ctx.send(f"Error playing {title}: {e}")
            self.check_queue(ctx, e)

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
            await channel.connect()
        
        async with ctx.typing():
            try:
                # Search first to get the URL
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0])
                    url = info['url']
                    webpage_url = info.get('webpage_url', url)
                    title = info.get('title', 'Unknown')

                song = {'url': webpage_url, 'title': title}

                if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                    if len(self.music_queue) >= 20:
                        return await ctx.send("Queue is full! (Limit: 20 songs)")
                    
                    self.music_queue.append(song)
                    await ctx.send(f"Added to queue: **{title}**")
                    self.trigger_prefetch() # Start downloading if needed
                else:
                    self.current_song = song
                    await self.play_music(ctx, song)
                    self.trigger_prefetch() # Check if there are others to download (unlikely here but good practice)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                await ctx.send(f"Error playing: {e}")

    @commands.command(name="skip", help="Skips the current song")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            # Graceful fade out before skipping
            if isinstance(ctx.voice_client.source, discord.PCMVolumeTransformer):
                start_volume = ctx.voice_client.source.volume
                steps = 10
                for i in range(steps):
                    ctx.voice_client.source.volume = start_volume * (1 - (i + 1) / steps)
                    await asyncio.sleep(0.05) # Fast fade (0.5s)
            
            ctx.voice_client.stop()
            await ctx.send("Skipped ⏭️")
        else:
            await ctx.send("Nothing to skip.")

    @commands.command(name="queue", help="Shows the current queue")
    async def queue(self, ctx):
        if len(self.music_queue) == 0 and not self.current_song:
            return await ctx.send("Queue is empty.")
        
        embed_desc = ""
        
        # Show currently playing
        if self.current_song:
            embed_desc += f"**Now Playing:**\n🎶 {self.current_song['title']}\n\n"
        
        # Show up to 10 songs from queue
        if len(self.music_queue) > 0:
            embed_desc += "**Up Next:**\n"
            for i, song in enumerate(self.music_queue[:10]):
                embed_desc += f"`{i+1}.` {song['title']}\n"
            
            if len(self.music_queue) > 10:
                embed_desc += f"\n*...and {len(self.music_queue) - 10} more*"
        else:
            embed_desc += "*Queue is empty*"

        # Create a nice embed
        embed = discord.Embed(
            title="Music Queue 🎵",
            description=embed_desc,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total songs in queue: {len(self.music_queue)}/20")
        
        await ctx.send(embed=embed)

    @commands.command(name="clear", help="Clears the queue")
    async def clear(self, ctx):
        self.music_queue = []
        await ctx.send("Queue cleared 🗑️")

    @commands.command(name="volume", help="Changes the player's volume")
    async def volume(self, ctx, volume: int):
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        if volume < 0 or volume > 100:
            return await ctx.send("Volume must be between 0 and 100.")

        if ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100
            self.volume_level = volume / 100
            await ctx.send(f"Changed volume to {volume}%")
        else:
            self.volume_level = volume / 100
            await ctx.send(f"Volume set to {volume}% (will apply to next song)")

    @commands.command(name="stop", help="Stops and disconnects")
    async def stop(self, ctx):
        # Cleanup queue files
        for song in self.music_queue:
            if 'local_path' in song and os.path.exists(song['local_path']):
                try:
                    os.remove(song['local_path'])
                except: pass
        
        # Cleanup current song file
        if self.current_song and 'local_path' in self.current_song and os.path.exists(self.current_song['local_path']):
            try:
                os.remove(self.current_song['local_path'])
            except: pass

        self.music_queue = [] # Clear queue on stop
        self.volume_level = DEFAULT_VOLUME # Reset volume on stop
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("Stopped and disconnected 👋")

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
