import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Colours


class Information(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def roles(self, ctx: commands.Context):
        embed = discord.Embed(title="Roles", colour=Colours.bot_blue)
        desc = []
        for role in reversed(ctx.guild.roles[1:]):
            desc.append(role.mention)

        desc = "\n".join(desc)
        embed.description = desc
        await ctx.send(embed=embed)


def setup(bot: Bot):
    """load the Information cog"""
    bot.add_cog(Information(bot))
