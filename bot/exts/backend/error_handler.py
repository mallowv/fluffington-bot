from pathlib import Path

import yaml
import random
import discord
from discord.ext import commands
from discord.ext.commands import errors

from bot.bot import Bot

with Path("bot/resources/responses.yaml").open("r") as f:
    NEGATIVE_RESPONSES = yaml.load(f, yaml.FullLoader).get("necative")


class ErrorHandler(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        error_embed = discord.Embed(color=discord.Colour.red())
        if isinstance(error, errors.CommandNotFound):
            error_embed.title = random.choice(NEGATIVE_RESPONSES)
            error_embed.description = f"{ctx.invoked_with} command does not exist"
            await ctx.send(embed=error_embed)
            return
        error_embed.title = random.choice(NEGATIVE_RESPONSES)
        error_embed.description = str(error)
        await ctx.send(embed=error_embed)


def setup(bot: Bot):
    """load the ErrorHandler cog"""
    bot.add_cog(ErrorHandler(bot))
