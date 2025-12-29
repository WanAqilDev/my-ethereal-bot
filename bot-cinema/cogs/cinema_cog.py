import discord
from discord.ext import commands
import socketio
import os
import json
import asyncio
from common.database.db import Database

class CinemaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        from common.version import get_version
        print(f"🎬 Cinema Bot v{get_version()} Initializing...")
        self.sio = socketio.AsyncClient()
        self.is_connected = False
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        
        # We need to connect to Redis for pub/sub if we want to bypass Socket.IO server for some things?
        # Actually, the plan is: Bot <-> Socket.IO Server (API) <-> React App
        # So Bot acts as a client.
        
        # Connect to API Socket.IO
        self.bot.loop.create_task(self.connect_socket())

    async def connect_socket(self):
        await self.bot.wait_until_ready()
        server_url = 'http://api:8000'
        
        while not self.is_connected:
            try:
                print(f"Attempting Socket.IO connection to {server_url}...")
                await self.sio.connect(server_url, socketio_path='/socket.io', transports=['websocket', 'polling'])
                print("Connected to Socket.IO Server")
                self.is_connected = True
                break
            except Exception as e:
                print(f"Socket.IO Connection Failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    @commands.group(name="cinema", invoke_without_command=True)
    async def cinema(self, ctx):
        await ctx.send("Use: `!cinema create`, `!cinema join <session_id>`, `!cinema play <url>`")

    @cinema.command(name="create")
    async def create_session(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("Join a Voice Channel first!")
        
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Create Session
            row = await conn.fetchrow(
                """
                INSERT INTO cinema_sessions (host_id, guild_id, channel_id) 
                VALUES ($1, $2, $3) 
                RETURNING session_id
                """,
                ctx.author.id, ctx.guild.id, ctx.author.voice.channel.id
            )
            session_id = str(row['session_id'])
            
            # Emit create event
            if self.is_connected:
                await self.sio.emit('create_session', {'session_id': session_id, 'host_id': ctx.author.id})
                
            await ctx.send(f"🎬 Session Created! ID: `{session_id}`\nFriends can use `!cinema join {session_id}` to buy a ticket (50 💎).")

    @cinema.command(name="join")
    async def join_session(self, ctx, session_id: str):
        TICKET_PRICE = 50
        
        # Check Balance & Deduct
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Check if session exists
            session = await conn.fetchrow("SELECT * FROM cinema_sessions WHERE session_id = $1::uuid AND is_active = TRUE", session_id)
            if not session:
                return await ctx.send("Invalid or inactive session.")

            # Check if user already has ticket
            ticket = await conn.fetchrow("SELECT * FROM cinema_tickets WHERE session_id = $1::uuid AND user_id = $2", session_id, ctx.author.id)
            if ticket:
                return await ctx.send("You already have a ticket! Open the Web App to watch.")

            # Transaction
            # 1. Update Balance (User -> Bank)
            async with conn.transaction():
                result = await conn.execute(
                    "UPDATE users SET balance = balance - $2 WHERE user_id = $1 AND balance >= $2",
                    ctx.author.id, TICKET_PRICE
                )
                if result == "UPDATE 0":
                    return await ctx.send(f"Insufficient funds! Ticket costs **{TICKET_PRICE} 💎**.")
                
                # Transfer to Bank (ID 0)
                await conn.execute("UPDATE users SET balance = balance + $2 WHERE user_id = $1", 0, TICKET_PRICE)
            
            # 2. Issue Ticket
            await conn.execute("INSERT INTO cinema_tickets (session_id, user_id) VALUES ($1::uuid, $2)", session_id, ctx.author.id)
            
            await ctx.send(f"🎟️ Ticket purchased! Enjoy the show.")
            
            # Emit join event
            if self.is_connected:
                await self.sio.emit('user_joined', {'session_id': session_id, 'user_id': ctx.author.id})

    @cinema.command(name="play")
    async def play_video(self, ctx, url: str):
        # Only host can play?
        # Check permissions
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Get Session hosted by this user in this guild
            session = await conn.fetchrow(
                "SELECT session_id FROM cinema_sessions WHERE host_id = $1 AND guild_id = $2 AND is_active = TRUE ORDER BY created_at DESC LIMIT 1",
                ctx.author.id, ctx.guild.id
            )
            if not session:
                return await ctx.send("You don't have an active session.")
            
            session_id = str(session['session_id'])
            
            # Update DB
            await conn.execute("UPDATE cinema_sessions SET video_url = $2 WHERE session_id = $1::uuid", session_id, url)
            
            # Emit Sync Event
            if self.is_connected:
                await self.sio.emit('play_video', {'session_id': session_id, 'url': url})
            
            await ctx.send(f"🍿 Playing: <{url}>")

async def setup(bot):
    await bot.add_cog(CinemaCog(bot))
