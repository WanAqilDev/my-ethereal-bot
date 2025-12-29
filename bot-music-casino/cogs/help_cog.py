import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", help="Shows this help menu")
    async def help(self, ctx, *, command_name: str = None):
        if command_name:
            # Show specific command help
            cmd = self.bot.get_command(command_name)
            if not cmd or cmd.hidden:
                return await ctx.send(f"❌ Command `{command_name}` not found.")
            
            embed = discord.Embed(title=f"Command: !{cmd.name}", description=cmd.help or "No description provided.", color=discord.Color.blue())
            
            # Aliases
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join([f"`{a}`" for a in cmd.aliases]), inline=False)
            
            # Usage
            params = " ".join([f"<{p}>" for p in cmd.clean_params])
            embed.add_field(name="Usage", value=f"`!{cmd.name} {params}`", inline=False)
            
            await ctx.send(embed=embed)
        else:
            # Dynamic Help Menu
            embed = discord.Embed(
                title="🤖 Bot Help Menu",
                description="Use `!help <command>` for more details.",
                color=discord.Color.gold()
            )
            
            # Iterate over cogs to group commands
            for cog_name, cog in self.bot.cogs.items():
                commands_list = cog.get_commands()
                if not commands_list: continue
                
                # Filter out hidden commands and standard checks
                visible_cmds = [c for c in commands_list if not c.hidden]
                if not visible_cmds: continue
                
                # Format list
                cmd_names = sorted([f"`!{c.name}`" for c in visible_cmds])
                
                # pretty print cog name
                if cog_name == "MusicCog": name = "🎵 Music"
                elif cog_name == "EconomyCog": name = "💎 Economy"
                elif cog_name == "HelpCog": continue # Skip help cog itself in listing
                else: name = f"⚙️ {cog_name}"
                
                embed.add_field(name=name, value=", ".join(cmd_names), inline=False)
            
            # Add Admin commands (from main.py or unclassified)
            # This requires iterating bot.commands and checking if cog is None
            misc_cmds = [c for c in self.bot.commands if c.cog is None and not c.hidden]
            if misc_cmds:
                cmd_names = sorted([f"`!{c.name}`" for c in misc_cmds])
                embed.add_field(name="🛠️ Misc / Admin", value=", ".join(cmd_names), inline=False)

            embed.set_footer(text="Made with 💖 by Snow ft. Antigravity")
            await ctx.send(embed=embed)

    @commands.command(name="ping", help="Check bot latency and version")
    async def ping(self, ctx):
        from common.version import get_version
        version = get_version()
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 **Pong!** {latency}ms\n🤖 **Version:** `{version}`")

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
