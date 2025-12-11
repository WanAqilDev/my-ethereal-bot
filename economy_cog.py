import discord
from discord.ext import commands, tasks
import json
import os
import random
import asyncio

ECONOMY_FILE = "economy.json"

# Leveling Constants
XP_PER_LEVEL = 100
PASSIVE_XP_MINUTE = 1
DJ_XP_SONG = 5

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = self.load_economy()
        self.award_points.start()
        self.check_rains.start()

    def load_economy(self):
        if not os.path.exists(ECONOMY_FILE):
            return {}
        try:
            with open(ECONOMY_FILE, "r") as f:
                data = json.load(f)
                # Migration logic: Convert old simple int balance to dict
                new_data = {}
                for user_id, value in data.items():
                    if isinstance(value, int):
                        new_data[user_id] = {
                            "balance": value,
                            "xp": 0,
                            "level": 1,
                            "badges": [],
                            "inventory": []
                        }
                    else:
                        new_data[user_id] = value
                return new_data
        except:
            return {}

    def save_economy(self):
        with open(ECONOMY_FILE, "w") as f:
            json.dump(self.economy, f, indent=4)

    def get_user_data(self, user_id):
        user_id = str(user_id)
        if user_id not in self.economy:
            self.economy[user_id] = {
                "balance": 0,
                "xp": 0,
                "level": 1,
                "badges": [],
                "inventory": []
            }
        return self.economy[user_id]

    def get_balance(self, user_id):
        return self.get_user_data(user_id)["balance"]

    def add_balance(self, user_id, amount):
        data = self.get_user_data(user_id)
        data["balance"] += amount
        
        # Badge Check: Rich
        if data["balance"] >= 1000 and "💎 Rich" not in data["badges"]:
            data["badges"].append("💎 Rich")
            
        self.save_economy()

    def remove_balance(self, user_id, amount):
        data = self.get_user_data(user_id)
        if data["balance"] >= amount:
            data["balance"] -= amount
            self.save_economy()
            return True
        return False

    def add_xp(self, user_id, amount, channel=None):
        data = self.get_user_data(user_id)
        data["xp"] += amount
        
        # Level Up Logic
        # Formula: Level * 100 XP needed for next level
        # Simplified: XP determines level directly? No, let's stick to threshold.
        # Actually, let's use a simple cumulative threshold for now.
        # Level 1: 0-99
        # Level 2: 100-199
        # Level N: (N-1)*100 to N*100 - 1
        
        new_level = (data["xp"] // XP_PER_LEVEL) + 1
        
        if new_level > data["level"]:
            data["level"] = new_level
            # Badge Check: Listener
            if new_level >= 5 and "🎧 Listener" not in data["badges"]:
                data["badges"].append("🎧 Listener")
            
            if channel:
                asyncio.run_coroutine_threadsafe(
                    channel.send(f"🎉 <@{user_id}> reached **Charisma Level {new_level}**! 💘"),
                    self.bot.loop
                )
        
        self.save_economy()

    @tasks.loop(seconds=60)
    async def award_points(self):
        # Award XP and Diamonds to everyone in a voice channel with the bot
        for guild in self.bot.guilds:
            if guild.voice_client and guild.voice_client.is_connected():
                channel = guild.voice_client.channel
                for member in channel.members:
                    if not member.bot:
                        user_data = self.get_user_data(member.id)
                        level = user_data["level"]
                        
                        # Tiered Income
                        income = 1
                        if level >= 20: income = 3
                        elif level >= 10: income = 2
                        
                        self.add_balance(member.id, income)
                        self.add_xp(member.id, PASSIVE_XP_MINUTE, channel=None) # Silent level up during passive

    @award_points.before_loop
    async def before_award_points(self):
        await self.bot.wait_until_ready()

    @commands.command(name="profile", aliases=["p", "wallet", "bal"], help="Check your profile")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = self.get_user_data(member.id)
        
        level = data["level"]
        xp = data["xp"]
        balance = data["balance"]
        badges = " ".join(data["badges"]) if data["badges"] else "None"
        inventory = ", ".join(data["inventory"]) if data["inventory"] else "Empty"
        
        # Calculate progress to next level
        current_level_xp_start = (level - 1) * XP_PER_LEVEL
        next_level_xp_start = level * XP_PER_LEVEL
        xp_needed = next_level_xp_start - xp
        progress_percent = int(((xp - current_level_xp_start) / XP_PER_LEVEL) * 10)
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
        embed.add_field(name="--- 🎵 Music ---", value="Use commands to buy", inline=False)
        embed.add_field(name="1. Skip Song ⏭️", value="**50 💎**\nForce skip the current song.", inline=True)
        
        embed.add_field(name="--- 💍 Flex ---", value="Permanent items", inline=False)
        embed.add_field(name="2. Diamond Ring 💍", value="**500 💎**\nShiny on your profile.", inline=True)
        embed.add_field(name="3. Super Yacht 🛥️", value="**10,000 💎**\nThe ultimate flex.", inline=True)

        embed.add_field(name="--- 🌧️ Rain ---", value="`!rain <tier> <delay>`", inline=False)
        embed.add_field(name="Tiers", value="120, 480, 980, 4800 💎", inline=True)
        embed.add_field(name="Delays", value="0, 5, 10, 15 mins", inline=True)
        
        embed.set_footer(text="Use !buy <item name> to purchase")
        await ctx.send(embed=embed)

    @commands.command(name="buy", help="Buy an item from the shop")
    async def buy(self, ctx, *, item: str):
        item = item.lower()
        user_id = ctx.author.id
        data = self.get_user_data(user_id)
        
        if item in ["skip", "song skip", "1"]:
            cost = 50
            if self.remove_balance(user_id, cost):
                # Trigger the skip logic from MusicCog
                music_cog = self.bot.get_cog("MusicCog")
                if music_cog:
                    if ctx.voice_client and ctx.voice_client.is_playing():
                        await ctx.send(f"💎 **{ctx.author.name}** bought a SKIP for {cost} diamonds!")
                        await music_cog.skip(ctx)
                    else:
                        self.add_balance(user_id, cost)
                        await ctx.send("Nothing is playing! Refunded 50 💎.")
                else:
                    self.add_balance(user_id, cost)
                    await ctx.send("Music system error. Refunded.")
            else:
                await ctx.send(f"You need **{cost} 💎**! (Bal: {data['balance']})")
        
        elif item in ["ring", "diamond ring", "2"]:
            cost = 500
            if "💍 Diamond Ring" in data["inventory"]:
                return await ctx.send("You already have a ring!")
            
            if self.remove_balance(user_id, cost):
                data["inventory"].append("💍 Diamond Ring")
                self.save_economy()
                await ctx.send(f"💍 **{ctx.author.name}** proposed to themselves! They now own a Diamond Ring!")
            else:
                await ctx.send(f"You need **{cost} 💎**!")

        elif item in ["yacht", "super yacht", "3"]:
            cost = 10000
            if "🛥️ Super Yacht" in data["inventory"]:
                return await ctx.send("You already have a yacht!")

            if self.remove_balance(user_id, cost):
                data["inventory"].append("🛥️ Super Yacht")
                self.save_economy()
                await ctx.send(f"🛥️ **{ctx.author.name}** is sailing away! They bought a Super Yacht!")
            else:
                await ctx.send(f"You need **{cost} 💎**!")
            
        else:
            await ctx.send("Item not found. Check `!shop`.")

    @commands.command(name="pay", help="Pay another user")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        if member.bot:
            return await ctx.send("You can't pay bots.")
        if member.id == ctx.author.id:
            return await ctx.send("You can't pay yourself.")
            
        if self.remove_balance(ctx.author.id, amount):
            self.add_balance(member.id, amount)
            await ctx.send(f"💸 **{ctx.author.name}** sent **{amount} 💎** to {member.mention}!")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="coinflip", aliases=["cf"], help="Bet diamonds on a coin flip")
    async def coinflip(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Bet must be positive.")
        
        if self.remove_balance(ctx.author.id, amount):
            win = random.choice([True, False])
            if win:
                winnings = amount * 2
                self.add_balance(ctx.author.id, winnings)
                await ctx.send(f"🪙 **Heads!** You won **{winnings} 💎**!")
            else:
                await ctx.send(f"🪙 **Tails!** You lost **{amount} 💎**.")
        else:
            await ctx.send("Insufficient funds!")

    @commands.command(name="slots", help="Bet diamonds on slots (10x payout)")
    async def slots(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Bet must be positive.")
            
        if self.remove_balance(ctx.author.id, amount):
            emojis = ["🍒", "🍋", "🍇", "💎", "7️⃣"]
            result = [random.choice(emojis) for _ in range(3)]
            
            await ctx.send(f"🎰 | {' | '.join(result)} | 🎰")
            
            if result[0] == result[1] == result[2]:
                winnings = amount * 10
                self.add_balance(ctx.author.id, winnings)
                await ctx.send(f"🚨 **JACKPOT!** You won **{winnings} 💎**!")
                
                # Badge Check: High Roller
                data = self.get_user_data(ctx.author.id)
                if "🎰 High Roller" not in data["badges"]:
                    data["badges"].append("🎰 High Roller")
                    self.save_economy()
                    await ctx.send(f"🏅 You earned the **High Roller** badge!")
            else:
                await ctx.send("Better luck next time!")
        else:
            await ctx.send("Insufficient funds!")

    # Admin command to give points (for testing)
    @commands.command(name="give", help="Admin: Give diamonds")
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_permissions(manage_guild=True))
    async def give(self, ctx, member: discord.Member, amount: int):
        self.add_balance(member.id, amount)
        await ctx.send(f"Gave {amount} 💎 to {member.mention}")

    @commands.command(name="givexp", help="Admin: Give XP")
    @commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True), commands.has_permissions(manage_guild=True))
    async def givexp(self, ctx, member: discord.Member, amount: int):
        self.add_xp(member.id, amount, channel=ctx.channel)
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

        if self.remove_balance(ctx.author.id, amount):
            import time
            due_time = time.time() + (delay * 60)
            
            rain_data = {
                "sender_id": ctx.author.id,
                "sender_name": ctx.author.name,
                "amount": amount,
                "due_time": due_time,
                "channel_id": ctx.author.voice.channel.id,
                "guild_id": ctx.guild.id
            }
            
            if "pending_rains" not in self.economy:
                self.economy["pending_rains"] = []
            
            self.economy["pending_rains"].append(rain_data)
            self.save_economy()
            
            if delay == 0:
                await self.process_rain(rain_data)
                self.economy["pending_rains"].remove(rain_data)
                self.save_economy()
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
            self.add_balance(rain_data["sender_id"], rain_data["amount"])
            # Try to notify sender
            try:
                sender = guild.get_member(rain_data["sender_id"])
                if sender: await sender.send(f"Your rain of {rain_data['amount']} 💎 was refunded because no one was in the VC.")
            except: pass
            return

        amount = rain_data["amount"]
        
        # Distribution Logic
        # 1. Give everyone 1 diamond minimum
        distribution = {member: 1 for member in recipients}
        remaining = amount - len(recipients)
        
        # 2. Distribute remaining randomly
        while remaining > 0:
            lucky_member = random.choice(recipients)
            distribution[lucky_member] += 1
            remaining -= 1
        
        # 3. Apply changes and announce
        msg_lines = [f"🌧️ **IT'S RAINING DIAMONDS!** 🌧️\n**{rain_data['sender_name']}** dropped **{amount} 💎**!"]
        
        # Sort by amount received (highest first)
        sorted_dist = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
        
        for member, amt in sorted_dist:
            self.add_balance(member.id, amt)
            msg_lines.append(f"> {member.mention} caught **{amt} 💎**")
            
        await channel.send("\n".join(msg_lines))

    @tasks.loop(seconds=60)
    async def check_rains(self):
        if "pending_rains" not in self.economy:
            return
            
        import time
        now = time.time()
        to_remove = []
        
        for rain_data in self.economy["pending_rains"]:
            if now >= rain_data["due_time"]:
                await self.process_rain(rain_data)
                to_remove.append(rain_data)
        
        if to_remove:
            for item in to_remove:
                self.economy["pending_rains"].remove(item)
            self.save_economy()

    @check_rains.before_loop
    async def before_check_rains(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
