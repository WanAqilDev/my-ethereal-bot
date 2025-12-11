import discord
from discord.ext import commands

# Command Examples Dictionary
COMMAND_EXAMPLES = {
    "play": "!play Despacito\n!play https://youtube.com/watch?v=...",
    "skip": "!skip",
    "stop": "!stop",
    "queue": "!queue",
    "volume": "!volume 50",
    "join": "!join",
    "leave": "!leave",
    "search": "!search lofi hip hop",
    "profile": "!profile\n!profile @User",
    "shop": "!shop",
    "buy": "!buy skip\n!buy ring",
    "rain": "!rain 120\n!rain 4800 15",
    "pay": "!pay @User 100",
    "coinflip": "!coinflip 100",
    "slots": "!slots 100",
    "give": "!give @User 1000",
    "givexp": "!givexp @User 500"
}

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", help="Shows this help menu")
    async def help(self, ctx, command_name: str = None):
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
            usage = f"!{cmd.name} {cmd.signature}"
            embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
            
            # Example
            if cmd.name in COMMAND_EXAMPLES:
                embed.add_field(name="Example", value=f"```\n{COMMAND_EXAMPLES[cmd.name]}\n```", inline=False)
            
            await ctx.send(embed=embed)
        else:
            # Show main menu
            embed = discord.Embed(
                title="🤖 Bot Help Menu",
                description="Use `!help <command>` for more details.",
                color=discord.Color.gold()
            )

            # Helper function to format command list
            def format_cmds(cmd_list):
                lines = []
                for name in cmd_list:
                    cmd = self.bot.get_command(name)
                    if cmd:
                        # Format: `!name` - Description
                        desc = cmd.help.split('\n')[0] if cmd.help else "No description"
                        if len(desc) > 30: desc = desc[:27] + "..."
                        lines.append(f"`!{name}` - {desc}")
                return "\n".join(lines)

            # Music Category
            music_cmds = ["play", "skip", "stop", "queue", "volume", "join", "leave"]
            embed.add_field(name="🎵 Music", value=format_cmds(music_cmds), inline=False)

            # Economy Category
            economy_cmds = ["profile", "shop", "buy", "rain", "pay", "coinflip", "slots"]
            embed.add_field(name="💎 Economy", value=format_cmds(economy_cmds), inline=False)

            embed.set_footer(text="Made with 💖 by Snow ft. Antigravity")
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
