import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from common.database.db import Database

# Leveling Constants
XP_PER_LEVEL = 100
PASSIVE_XP_MINUTE = 1
DJ_XP_SONG = 5

# Casino Configuration
COINFLIP_MULTIPLIER = 2.0
COINFLIP_WIN_CHANCE = 0.5 # 50% Chance

SLOTS_MULTIPLIER = 10.0
SLOTS_WIN_CHANCE = 0.05 # 5% Chance (Hit Jackpot)
SLOTS_SYMBOLS = ["🍒", "🍋", "🍇", "💎", "7️⃣"]

# Rain Configuration
# 'standard': Everyone gets 1, then remainder is random. (Fair-ish)
# 'lottery': Entire amount is distributed randomly (Winner takes most? No, just fully random 1-by-1 distribution).
RAIN_MODE = 'standard' 

# Shop Configuration
# Shop Configuration
SHOP_ITEMS = {
    "Essentials": {
        "cookie": {"name": "🍪 Cookie", "price": 10},
        "coffee": {"name": "☕ Coffee", "price": 50},
        "rose": {"name": "🌹 Rose", "price": 100},
        "beer": {"name": "🍺 Beer", "price": 150},
        "pizza": {"name": "🍕 Pizza", "price": 200},
        "bronze_ring": {"name": "💍 Bronze Ring", "price": 300},
        "teddy": {"name": "🧸 Teddy Bear", "price": 300},
        "sunglasses": {"name": "🕶️ Sunglasses", "price": 400},
        "hat": {"name": "🧢 Cool Hat", "price": 450},
        "plant": {"name": "🪴 Potted Plant", "price": 500},
    },
    "Lifestyle": {
        "silver_ring": {"name": "💍 Silver Ring", "price": 1000},
        "sneakers": {"name": "👟 Air Jordans", "price": 2000},
        "necklace": {"name": "📿 Gold Necklace", "price": 2500},
        "bag": {"name": "👜 Designer Bag", "price": 3000},
        "console": {"name": "🎮 Gaming Console", "price": 4000},
        "iphone": {"name": "📱 iPhone 16", "price": 5000},
        "laptop": {"name": "💻 Gaming Laptop", "price": 6000},
        "guitar": {"name": "🎸 Electric Guitar", "price": 7000},
        "camera": {"name": "📷 DSLR Camera", "price": 8000},
        "watch": {"name": "⌚ Gold Watch", "price": 10000},
    },
    "Luxury": {
        "diamond_ring": {"name": "💍 Diamond Ring", "price": 15000},
        "motorcycle": {"name": "🏍️ Motorcycle", "price": 20000},
        "car": {"name": "🏎️ Sports Car", "price": 50000},
        "boat": {"name": "🛥️ Luxury Boat", "price": 75000},
        "tiny_house": {"name": "🏠 Tiny House", "price": 100000},
        "penthouse": {"name": "🏙️ Penthouse", "price": 200000},
        "mansion": {"name": "🏰 Mansion", "price": 300000},
        "robot": {"name": "🤖 Robot Butler", "price": 400000},
        "island": {"name": "🏝️ Private Island", "price": 500000},
    },
    "Services": {
        "skip": {"name": "⏭️ Skip Song", "price": 10, "type": "consumable"}
    }
}

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_rains = [] # In-memory for now
        self.award_points.start()
        self.check_rains.start()

    async def ensure_user(self, user_id):
        """Ensures the user exists in the database."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", user_id)

    async def get_user_data(self, user_id):
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None

    async def add_balance(self, user_id, amount):
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET balance = balance + $2 WHERE user_id = $1", user_id, amount)
            
            # Badge Check: Rich (Simple check after update)
            if amount > 0:
                row = await conn.fetchrow("SELECT balance, badges FROM users WHERE user_id = $1", user_id)
                if row['balance'] >= 1000 and "💎 Rich" not in (row['badges'] or []):
                    await conn.execute("UPDATE users SET badges = array_append(badges, $2) WHERE user_id = $1", user_id, "💎 Rich")

    async def remove_balance(self, user_id, amount):
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # Atomic check and update
            result = await conn.execute(
                "UPDATE users SET balance = balance - $2 WHERE user_id = $1 AND balance >= $2",
                user_id, amount
            )
            # "UPDATE 1" means success, "UPDATE 0" means fail (insufficient funds)
            return result == "UPDATE 1"

    async def add_xp(self, user_id, amount, channel=None):
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            # 1. Add XP
            await conn.execute("UPDATE users SET xp = xp + $2 WHERE user_id = $1", user_id, amount)
            
            # 2. Check Level Up
            row = await conn.fetchrow("SELECT xp, level, badges FROM users WHERE user_id = $1", user_id)
            xp, current_level = row['xp'], row['level']
            
            new_level = (xp // XP_PER_LEVEL) + 1
            if new_level > current_level:
                await conn.execute("UPDATE users SET level = $2 WHERE user_id = $1", user_id, new_level)
                
                # Badge Check: Listener
                if new_level >= 5 and "🎧 Listener" not in (row['badges'] or []):
                    await conn.execute("UPDATE users SET badges = array_append(badges, $2) WHERE user_id = $1", user_id, "🎧 Listener")
                
                if channel:
                    asyncio.run_coroutine_threadsafe(
                        channel.send(f"🎉 <@{user_id}> reached **Charisma Level {new_level}**! 💘"),
                        self.bot.loop
                    )

    @tasks.loop(seconds=60)
    async def award_points(self):
        # Award XP and Diamonds to everyone in a voice channel with the bot
        for guild in self.bot.guilds:
            if guild.voice_client and guild.voice_client.is_connected():
                channel = guild.voice_client.channel
                for member in channel.members:
                    if not member.bot:
                        data = await self.get_user_data(member.id)
                        if not data: continue
                        
                        level = data["level"]
                        
                        # Tiered Income
                        income = 1
                        if level >= 20: income = 3
                        elif level >= 10: income = 2
                        
                        await self.add_balance(member.id, income)
                        await self.add_xp(member.id, PASSIVE_XP_MINUTE, channel=None)

    @award_points.before_loop
    async def before_award_points(self):
        await self.bot.wait_until_ready()

    @commands.command(name="profile", aliases=["p", "wallet", "bal"], help="Check your profile")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = await self.get_user_data(member.id)
        
        level = data["level"]
        xp = data["xp"]
        balance = data["balance"]
        badges_list = data["badges"] or []
        badges = " ".join(badges_list) if badges_list else "None"
        inv_list = data["inventory"] or []
        inventory = ", ".join(inv_list) if inv_list else "Empty"
        
        # Calculate progress to next level
        current_level_xp_start = (level - 1) * XP_PER_LEVEL
        next_level_xp_start = level * XP_PER_LEVEL
        
        if xp < current_level_xp_start: xp = current_level_xp_start
        
        needed = XP_PER_LEVEL
        current = xp - current_level_xp_start
        
        progress_percent = int((current / needed) * 10)
        progress_percent = max(0, min(10, progress_percent)) # Clamp
        progress_bar = "🟦" * progress_percent + "⬜" * (10 - progress_percent)

        embed = discord.Embed(title=f"{member.name}'s Profile", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Charisma 💘", value=f"**Level {level}**\n{progress_bar}\n{xp}/{next_level_xp_start} XP", inline=True)
        embed.add_field(name="Wallet 💎", value=f"**{balance}** Diamonds", inline=True)
        embed.add_field(name="Badges 🏅", value=badges, inline=False)
        embed.add_field(name="Inventory 🎒", value=inventory, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="shop", help="View items for sale")
    async def shop(self, ctx):
        embed = discord.Embed(
            title="💎 Diamond Shop",
            description="Spend your hard-earned diamonds here!",
            color=discord.Color.purple()
        )
        
        for category, items in SHOP_ITEMS.items():
            item_list = []
            for key, data in items.items():
                item_list.append(f"`{key.ljust(10)}` {data['name']} (**{data['price']:,} 💎**)")
            
            embed.add_field(name=f"--- {category} ---", value="\n".join(item_list), inline=False)
            
        embed.set_footer(text="Use !buy <item id> to purchase. Example: !buy car")
        await ctx.send(embed=embed)

    @commands.command(name="buy", help="Buy an item from the shop")
    async def buy(self, ctx, *, item_key: str):
        item_key = item_key.lower()
        user_id = ctx.author.id
        
        # 1. Find the item in our dictionary
        target_item = None
        for category, items in SHOP_ITEMS.items():
            if item_key in items:
                target_item = items[item_key]
                break
        
        if not target_item:
            return await ctx.send("Item not found. Check `!shop` for valid item IDs (e.g., `!buy cookie`).")
            
        price = target_item["price"]
        name = target_item["name"]
        
        # 2. Check Logic for Consumables vs Permanent
        if item_key == "skip":
            if await self.remove_balance(user_id, price):
                 music_cog = self.bot.get_cog("MusicCog")
                 if music_cog and ctx.voice_client and ctx.voice_client.is_playing():
                     await ctx.send(f"💎 **{ctx.author.name}** bought a SKIP for {price} diamonds!")
                     await music_cog.skip(ctx)
                 else:
                     await self.add_balance(user_id, price) # Refund
                     await ctx.send("Nothing playing to skip! Refunded.")
            else:
                await ctx.send(f"You need **{price} 💎**!")
            return

        # 3. Permanent Items Logic
        # Check if already owned
        data = await self.get_user_data(user_id)
        inventory = data['inventory'] or []
        
        if name in inventory:
            return await ctx.send(f"You already own a **{name}**!")
            
        # 4. Transaction
        if await self.remove_balance(user_id, price):
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("UPDATE users SET inventory = array_append(inventory, $2) WHERE user_id = $1", user_id, name)
            await ctx.send(f"🛍️ **{ctx.author.name}** bought **{name}** for {price:,} 💎!")
        else:
            await ctx.send(f"You need **{price:,} 💎**!")

    @commands.command(name="pay", help="Pay another user")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        if member.bot:
            return await ctx.send("You can't pay bots.")
        if member.id == ctx.author.id:
            return await ctx.send("You can't pay yourself.")
            
        if await self.remove_balance(ctx.author.id, amount):
            await self.add_balance(member.id, amount)
            await ctx.send(f"💸 **{ctx.author.name}** sent **{amount} 💎** to {member.mention}!")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="coinflip", aliases=["cf"], help="Bet diamonds on a coin flip")
    async def coinflip(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Bet must be positive.")
        
        if await self.remove_balance(ctx.author.id, amount):
            # Determine Win/Loss based on exact probability
            win = random.random() < COINFLIP_WIN_CHANCE
            
            if win:
                winnings = int(amount * COINFLIP_MULTIPLIER)
                await self.add_balance(ctx.author.id, winnings)
                await ctx.send(f"🪙 **Heads!** You won **{winnings} 💎**!")
            else:
                await ctx.send(f"🪙 **Tails!** You lost **{amount} 💎**.")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="slots", help="Bet diamonds on slots (10x payout)")
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Bet must be positive.")
            
        if await self.remove_balance(ctx.author.id, amount):
            # 1. Determine Win/Loss
            is_win = random.random() < SLOTS_WIN_CHANCE
            
            result = []
            if is_win:
                # Force a win: 3 identical symbols
                symbol = random.choice(SLOTS_SYMBOLS)
                result = [symbol, symbol, symbol]
            else:
                # Force a loss: Generate randoms until they are NOT all equal
                # (With small symbols list, random chance of equality exists)
                while True:
                    result = [random.choice(SLOTS_SYMBOLS) for _ in range(3)]
                    if result[0] != result[1] or result[1] != result[2]:
                        break
            
            await ctx.send(f"🎰 | {' | '.join(result)} | 🎰")
            
            if is_win:
                winnings = int(amount * SLOTS_MULTIPLIER)
                await self.add_balance(ctx.author.id, winnings)
                await ctx.send(f"🚨 **JACKPOT!** You won **{winnings} 💎**!")
                
                # Badge Check: High Roller
                data = await self.get_user_data(ctx.author.id)
                if "🎰 High Roller" not in (data["badges"] or []):
                    pool = await Database.get_pool()
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE users SET badges = array_append(badges, $2) WHERE user_id = $1", ctx.author.id, "🎰 High Roller")
                    await ctx.send(f"🏅 You earned the **High Roller** badge!")
            else:
                await ctx.send("Better luck next time!")
        else:
            await ctx.send("Insufficient funds!")

    # Admin command to give points (for testing)
    @commands.command(name="give", help="Admin: Give diamonds")
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_permissions(manage_guild=True))
    async def give(self, ctx, member: discord.Member, amount: int):
        await self.add_balance(member.id, amount)
        await ctx.send(f"Gave {amount} 💎 to {member.mention}")

    @commands.command(name="givexp", help="Admin: Give XP")
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_permissions(manage_guild=True))
    async def givexp(self, ctx, member: discord.Member, amount: int):
        await self.add_xp(member.id, amount, channel=ctx.channel)
        await ctx.send(f"Gave {amount} XP to {member.mention}")

    @commands.command(name="rain", aliases=["hongbao", "redpacket", "rp"], help="Make it rain diamonds! 🌧️")
    async def rain(self, ctx, amount: int, delay: int = 0):
        # Fixed Tiers
        ALLOWED_TIERS = [120, 480, 980, 4800]
        ALLOWED_DELAYS = [0, 5, 10, 15]

        if amount not in ALLOWED_TIERS:
            return await ctx.send(f"Invalid amount! Allowed tiers: {', '.join(map(str, ALLOWED_TIERS))} 💎")
        
        if delay not in ALLOWED_DELAYS:
            return await ctx.send(f"Invalid delay! Allowed delays: {', '.join(map(str, ALLOWED_DELAYS))} minutes")

        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a Voice Channel to make it rain!")

        if await self.remove_balance(ctx.author.id, amount):
            due_time = time.time() + (delay * 60)
            
            rain_data = {
                "sender_id": ctx.author.id,
                "sender_name": ctx.author.name,
                "amount": amount,
                "due_time": due_time,
                "channel_id": ctx.author.voice.channel.id,
                "guild_id": ctx.guild.id
            }
            
            # Persisting to memory only for MVP
            self.pending_rains.append(rain_data)
            
            if delay == 0:
                await self.process_rain(rain_data)
                self.pending_rains.remove(rain_data)
            else:
                await ctx.send(f"🌧️ **{ctx.author.name}** scheduled a **{amount} 💎 Rain** in {delay} minutes! Stay in the VC!")
        else:
            await ctx.send("Insufficient funds!")

    async def process_rain(self, rain_data):
        guild = self.bot.get_guild(rain_data["guild_id"])
        if not guild: return
        
        channel = guild.get_channel(rain_data["channel_id"])
        if not channel: return
        
        # Get recipients (exclude bots and sender)
        recipients = [m for m in channel.members if not m.bot and m.id != rain_data["sender_id"]]
        
        if not recipients:
            # Refund if no one is there
            await self.add_balance(rain_data["sender_id"], rain_data["amount"])
            try:
                sender = guild.get_member(rain_data["sender_id"])
                if sender: await sender.send(f"Your rain of {rain_data['amount']} 💎 was refunded because no one was in the VC.")
            except: pass
            return

        amount = rain_data["amount"]
        
        # Distribution Logic
        distribution = {}
        remaining = amount
        
        # Mode: Standard (Fair Base)
        if RAIN_MODE == 'standard':
            # Give everyone 1 first if possible
            if remaining >= len(recipients):
                distribution = {member: 1 for member in recipients}
                remaining -= len(recipients)
            else:
                # Not enough for everyone? Fallback to zero base, pure lottery
                distribution = {member: 0 for member in recipients}
        else:
            # Mode: Lottery (Zero Base)
            distribution = {member: 0 for member in recipients}
        
        # Distribute remaining 1 by 1 randomly
        while remaining > 0:
            lucky_member = random.choice(recipients)
            if lucky_member not in distribution: distribution[lucky_member] = 0
            distribution[lucky_member] += 1
            remaining -= 1
        
        # 3. Apply changes and announce
        msg_lines = [f"🌧️ **IT'S RAINING DIAMONDS!** 🌧️\n**{rain_data['sender_name']}** dropped **{amount} 💎**!"]
        
        sorted_dist = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
        
        for member, amt in sorted_dist:
            if amt > 0:
                await self.add_balance(member.id, amt)
                msg_lines.append(f"> {member.mention} caught **{amt} 💎**")
            
        await channel.send("\n".join(msg_lines))

    @tasks.loop(seconds=60)
    async def check_rains(self):
        if not self.pending_rains:
            return
            
        now = time.time()
        to_remove = []
        
        for rain_data in self.pending_rains:
            if now >= rain_data["due_time"]:
                await self.process_rain(rain_data)
                to_remove.append(rain_data)
        
        for item in to_remove:
            self.pending_rains.remove(item)

    @check_rains.before_loop
    async def before_check_rains(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
