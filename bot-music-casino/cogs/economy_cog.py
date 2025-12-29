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

# Central Bank Configuration
BANK_ID = 0
GENESIS_SUPPLY = 1_000_000_000

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_rains = []
        self.award_points.start()
        self.check_rains.start()

    # --- CORE BANKING FUNCTIONS ---

    async def get_balance(self, user_id):
        """Get balance of any user (or Bank)."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
            return val if val is not None else 0

    async def get_bank_reserves(self):
        """Get the Central Bank's current holdings."""
        return await self.get_balance(BANK_ID)

    async def transfer(self, from_id, to_id, amount, reason="Transaction"):
        """
        The ATOMIC movement of funds. 
        Money is never created/destroyed here, only moved.
        Returns: True if success, False if insufficient funds.
        """
        if amount <= 0: return False
        
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Take from Sender
                # We use specific check to ensure balance >= amount
                # For Bank (ID 0), we might allow going negative if we wanted Bailouts, 
                # but for Closed Loop we enforce strict solvency.
                result = await conn.execute(
                    "UPDATE users SET balance = balance - $2 WHERE user_id = $1 AND balance >= $2",
                    from_id, amount
                )
                
                if result == "UPDATE 0":
                    return False # Insufficient Funds
                
                # 2. Give to Receiver (Ensure receiver exists)
                await conn.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING", to_id)
                await conn.execute("UPDATE users SET balance = balance + $2 WHERE user_id = $1", to_id, amount)
                
                # 3. Log Transaction (Optional but good for audit)
                # await conn.execute("INSERT INTO transactions ...") 
                
        return True

    # --- HIGHER LEVEL BANKING ---

    async def payout_from_bank(self, user_id, amount, reason="Reward"):
        """
        Pay a user from the Bank Reserve.
        Fails if Bank is insolvent (Empty).
        """
        success = await self.transfer(BANK_ID, user_id, amount, reason)
        if success:
            # Badge Check: Rich
            await self.check_rich_badge(user_id)
        return success

    async def pay_to_bank(self, user_id, amount, reason="Sink"):
        """
        User pays the Bank (Shop, Loss, Tax).
        """
        return await self.transfer(user_id, BANK_ID, amount, reason)

    async def ensure_user(self, user_id):
        """Ensures the user exists in the DB (for profile viewing etc)."""
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO users (user_id, balance) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING", user_id)

    async def get_user_data(self, user_id):
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None
            
    async def check_rich_badge(self, user_id):
        data = await self.get_user_data(user_id)
        if data['balance'] >= 1000 and "💎 Rich" not in (data['badges'] or []):
             pool = await Database.get_pool()
             async with pool.acquire() as conn:
                await conn.execute("UPDATE users SET badges = array_append(badges, $2) WHERE user_id = $1", user_id, "💎 Rich")

    async def add_xp(self, user_id, amount, channel=None):
        # XP is NOT currency, it can be infinite.
        await self.ensure_user(user_id)
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET xp = xp + $2 WHERE user_id = $1", user_id, amount)
            row = await conn.fetchrow("SELECT xp, level, badges FROM users WHERE user_id = $1", user_id)
            xp, current_level = row['xp'], row['level']
            new_level = (xp // XP_PER_LEVEL) + 1
            if new_level > current_level:
                await conn.execute("UPDATE users SET level = $2 WHERE user_id = $1", user_id, new_level)
                if new_level >= 5 and "🎧 Listener" not in (row['badges'] or []):
                    await conn.execute("UPDATE users SET badges = array_append(badges, $2) WHERE user_id = $1", user_id, "🎧 Listener")
                if channel:
                     asyncio.run_coroutine_threadsafe(
                        channel.send(f"🎉 <@{user_id}> reached **Charisma Level {new_level}**! 💘"),
                        self.bot.loop
                    )

    # --- TASKS & LOOPS ---

    def get_solvency_multiplier(self, bank_balance):
        """The 'Thermostat': Returns reward multiplier based on Bank Reserves."""
        ratio = bank_balance / GENESIS_SUPPLY
        
        if ratio > 0.8: return 2.0   # Stimulus
        if ratio > 0.4: return 1.0   # Healthy
        if ratio > 0.2: return 0.5   # Austerity
        if ratio > 0.05: return 0.1  # Crisis
        return 0.0                   # Bankrupt

    @tasks.loop(seconds=60)
    async def award_points(self):
        bank_bal = await self.get_bank_reserves()
        multiplier = self.get_solvency_multiplier(bank_bal)
        if multiplier == 0: return # Bankrupt
        
        # ... logic for awarding points ...
        pass

    @commands.command(name="airdrop", help="Distribute money from Bank to ALL online users (Admin only)")
    @commands.is_owner()
    async def airdrop(self, ctx, amount: int):
        """Admin command to stimulate the economy."""
        if amount <= 0: return await ctx.send("Amount must be positive.")

        online_members = [m for m in ctx.guild.members if not m.bot and m.status != discord.Status.offline]
        if not online_members: return await ctx.send("No one is online!")

        amount_per_person = amount // len(online_members)
        if amount_per_person < 1: return await ctx.send("Amount too small.")

        bank_reserves = await self.get_bank_reserves()
        if bank_reserves < amount: return await ctx.send(f"❌ Bank only has {bank_reserves} 💎.")

        for member in online_members:
            await self.ensure_user(member.id)
            await self.payout_from_bank(member.id, amount_per_person, "Airdrop")
        
        await ctx.send(f"🎈 Global Airdrop! **{amount:,} 💎** distributed to {len(online_members)} citizens ({amount_per_person:,} each).")

        for guild in self.bot.guilds:
            if guild.voice_client and guild.voice_client.is_connected():
                channel = guild.voice_client.channel
                for member in channel.members:
                    if not member.bot:
                        data = await self.get_user_data(member.id)
                        if not data: continue
                        
                        base_income = 1
                        if data["level"] >= 20: base_income = 3
                        elif data["level"] >= 10: base_income = 2
                        
                        final_income = int(base_income * multiplier)
                        if final_income > 0:
                            if await self.payout_from_bank(member.id, final_income, "Passive"):
                                await self.add_xp(member.id, PASSIVE_XP_MINUTE, channel=None)

    @award_points.before_loop
    async def before_award_points(self):
        await self.bot.wait_until_ready()

    # --- COMMANDS ---

    @commands.command(name="centralbank", aliases=["cb", "reserve"], help="View Bank Reserves")
    async def centralbank(self, ctx):
        reserves = await self.get_bank_reserves()
        ratio = (reserves / GENESIS_SUPPLY) * 100
        
        status = "🟢 Healthy"
        if ratio > 80: status = "🔵 Stimulus Mode (2x Rewards)"
        elif ratio < 40: status = "🟠 Austerity Mode (0.5x Rewards)"
        elif ratio < 20: status = "🔴 CRISIS MODE (0.1x Rewards)"
        
        embed = discord.Embed(title="🏦 Central Bank of Ethereal", color=discord.Color.green())
        embed.add_field(name="Reserves", value=f"**{reserves:,} 💎**", inline=True)
        embed.add_field(name="Solvency Ratio", value=f"**{ratio:.1f}%**", inline=True)
        embed.add_field(name="Economic Status", value=status, inline=False)
        embed.set_footer(text="Bank Funds = Total Supply - User Holdings")
        await ctx.send(embed=embed)

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
        
        # Calculate progress
        current_level_xp_start = (level - 1) * XP_PER_LEVEL
        next_level_xp_start = level * XP_PER_LEVEL
        if xp < current_level_xp_start: xp = current_level_xp_start
        needed = XP_PER_LEVEL
        current = xp - current_level_xp_start
        progress_percent = int((current / needed) * 10)
        progress_percent = max(0, min(10, progress_percent))
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
        embed = discord.Embed(title="💎 Diamond Shop (Funds return to Bank)", color=discord.Color.purple())
        for category, items in SHOP_ITEMS.items():
            item_list = []
            for key, data in items.items():
                item_list.append(f"`{key.ljust(10)}` {data['name']} (**{data['price']:,} 💎**)")
            embed.add_field(name=f"--- {category} ---", value="\n".join(item_list), inline=False)
        embed.set_footer(text="Use !buy <item id>")
        await ctx.send(embed=embed)

    @commands.command(name="buy", help="Buy an item from the shop")
    async def buy(self, ctx, *, item_key: str):
        item_key = item_key.lower()
        user_id = ctx.author.id
        
        target_item = None
        for category, items in SHOP_ITEMS.items():
            if item_key in items: target_item = items[item_key]; break
        
        if not target_item: return await ctx.send("Item not found. Check `!shop`.")
        price, name = target_item["price"], target_item["name"]
        
        # Consumable Logic
        if item_key == "skip":
            if await self.pay_to_bank(user_id, price, "Buy Skip"):
                 music_cog = self.bot.get_cog("MusicCog")
                 if music_cog and ctx.voice_client and ctx.voice_client.is_playing():
                     await ctx.send(f"💎 **{ctx.author.name}** bought a SKIP!")
                     await music_cog.skip(ctx)
                 else:
                     await self.payout_from_bank(user_id, price, "Refund Skip")
                     await ctx.send("Nothing playing! Refunded.")
            else: await ctx.send(f"You need **{price} 💎**!")
            return

        # Permanent Logic
        data = await self.get_user_data(user_id)
        if name in (data['inventory'] or []): return await ctx.send(f"You already own **{name}**!")
            
        if await self.pay_to_bank(user_id, price, f"Buy {name}"):
            pool = await Database.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("UPDATE users SET inventory = array_append(inventory, $2) WHERE user_id = $1", user_id, name)
            await ctx.send(f"🛍️ Bought **{name}** for {price:,} 💎! (Funds returned to Bank)")
        else: await ctx.send(f"You need **{price:,} 💎**!")

    @commands.command(name="pay", help="Pay another user (5% Tax)")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0: return await ctx.send("Amount must be positive.")
        if member.bot or member.id == ctx.author.id: return await ctx.send("Invalid recipient.")
        
        # Tax Calculation
        tax = int(amount * 0.05)
        recipient_receives = amount - tax
        
        # 1. Take Full Amount from Sender
        if await self.transfer(ctx.author.id, BANK_ID, amount, "Transfer Escrow"): # Move to Bank first?
            # Actually simpler: Direct User->User for net, User->Bank for tax.
            # But "transfer" checks balance. We need atomic.
            # Let's do: User->Bank (Tax), User->Recipient (Net). 
            # Risk: Have money for Tax but not Net?
            # Better: Move FULL amount to Bank, then Bank pays Recipient.
             
            # Step 2: Pay Recipient from Bank
            await self.payout_from_bank(member.id, recipient_receives, f"Payment from {ctx.author.name}")
            
            await ctx.send(f"💸 **{ctx.author.name}** sent **{amount} 💎** to {member.mention}.\n(Tax: {tax} 💎, Recipient got: {recipient_receives} 💎)")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="coinflip", aliases=["cf"], help="Bet against the House (50/50)")
    async def coinflip(self, ctx, amount: int):
        if amount <= 0: return await ctx.send("Bet must be positive.")
        
        # Check Table Limits (0.1% of Reserves)
        reserves = await self.get_bank_reserves()
        max_bet = int(reserves * 0.001)
        if amount > max_bet: return await ctx.send(f"Table Limit Exceeded! Max bet is **{max_bet:,} 💎** (0.1% of Bank).")

        # 1. Take Bet (User -> Bank)
        if await self.pay_to_bank(ctx.author.id, amount, "CF Bet"):
            win = random.random() < COINFLIP_WIN_CHANCE
            if win:
                winnings = int(amount * COINFLIP_MULTIPLIER)
                # 2. Pay Winnings (Bank -> User)
                if await self.payout_from_bank(ctx.author.id, winnings, "CF Win"):
                    await ctx.send(f"🪙 **Heads!** You won **{winnings} 💎**!")
                else: 
                     # CRITICAL FAILURE (Bankrupt)
                     await ctx.send(f"🪙 **Heads!** ... but the Bank is broke! 😱 (IOU Issued)")
            else:
                await ctx.send(f"🪙 **Tails!** The House wins **{amount} 💎**.")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="slots", help="Bet on Slots (House Edge)")
    async def slots(self, ctx, amount: int):
        if amount <= 0: return await ctx.send("Bet must be positive.")
        reserves = await self.get_bank_reserves()
        max_bet = int(reserves * 0.001)
        if amount > max_bet: return await ctx.send(f"Table Limit Exceeded! Max bet is **{max_bet:,} 💎**.")
            
        if await self.pay_to_bank(ctx.author.id, amount, "Slots Bet"):
            # Logic: House takes bet. If win, House pays multiplier.
            is_win = random.random() < SLOTS_WIN_CHANCE
            result = []
            if is_win:
                s = random.choice(SLOTS_SYMBOLS); result = [s, s, s]
            else:
                while True:
                    result = [random.choice(SLOTS_SYMBOLS) for _ in range(3)]
                    if len(set(result)) > 1: break # Not all same
            
            await ctx.send(f"🎰 | {' | '.join(result)} | 🎰")
            
            if is_win:
                winnings = int(amount * SLOTS_MULTIPLIER)
                if await self.payout_from_bank(ctx.author.id, winnings, "Slots Jackpot"):
                    await ctx.send(f"🚨 **JACKPOT!** You won **{winnings} 💎**!")
                    await self.check_rich_badge(ctx.author.id) # Re-check badge
                else:
                    await ctx.send("🚨 **JACKPOT!** ... The Bank cannot pay! 💀")
            else:
                await ctx.send("Better luck next time!")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="rain", aliases=["hongbao", "rp"], help="Distribute YOUR money")
    async def rain(self, ctx, amount: int, delay: int = 0):
        # Rain is Peer-to-Peer. User A -> Many Users.
        # Implementation: User pays Bank. Bank distributes to Users.
        # This keeps it clean.
        ALLOWED_TIERS = [120, 480, 980, 4800]
        if amount not in ALLOWED_TIERS: return await ctx.send(f"Allowed tiers: {ALLOWED_TIERS}")
        
        if not ctx.author.voice or not ctx.author.voice.channel: return await ctx.send("Join VC first!")

        if await self.pay_to_bank(ctx.author.id, amount, "Rain Deposit"):
            due_time = time.time() + (delay * 60)
            rain_data = {
                "sender_id": ctx.author.id, "sender_name": ctx.author.name,
                "amount": amount, "due_time": due_time,
                "channel_id": ctx.author.voice.channel.id, "guild_id": ctx.guild.id
            }
            self.pending_rains.append(rain_data)
            if delay == 0:
                await self.process_rain(rain_data)
                self.pending_rains.remove(rain_data)
            else:
                await ctx.send(f"🌧️ Scheduled Rain in {delay} mins!")
        else:
            await ctx.send("Insufficient funds!")

    async def process_rain(self, rain_data):
        # Logic matches previous, but uses payout_from_bank
        # If no one joins, refund to sender
        guild = self.bot.get_guild(rain_data["guild_id"])
        if not guild: return
        channel = guild.get_channel(rain_data["channel_id"])
        
        members = [m for m in channel.members if not m.bot and m.id != rain_data["sender_id"]]
        if not members:
            # Refund
            await self.payout_from_bank(rain_data["sender_id"], rain_data["amount"], "Rain Refund")
            return

        # Distribution (Standard equal share for now for simplicity in closed loop)
        share = rain_data["amount"] // len(members)
        remainder = rain_data["amount"] % len(members)
        
        msg = [f"🌧️ **RAIN!** {rain_data['sender_name']} dropped {rain_data['amount']}!"]
        for m in members:
            # Everyone gets share
            amt = share + (1 if remainder > 0 else 0)
            remainder -= 1
            if amt > 0:
                await self.payout_from_bank(m.id, amt, "Rain Catch")
                msg.append(f"> {m.mention} got {amt}")
        
        await channel.send("\n".join(msg))

    @tasks.loop(seconds=60)
    async def check_rains(self):
        # ... (Same logic, just calls process_rain)
        now = time.time()
        to_remove = []
        for r in self.pending_rains:
            if now >= r["due_time"]:
                await self.process_rain(r)
                to_remove.append(r)
        for r in to_remove: self.pending_rains.remove(r)
    
    @check_rains.before_loop
    async def before_check_rains(self): await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
