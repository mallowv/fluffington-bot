import logging

import coloredlogs
import discord
from discord.ext import commands

from bot.bot import Bot

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)


class Verification(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logger.info(f"{member.id} joined {member.guild.name}")
        await member.send(
            f"Hey {member.mention}, thanks for joining {member.guild.name}"
        )


def setup(bot: Bot) -> None:
    """load the Verification cog"""
    bot.add_cog(Verification(bot))
