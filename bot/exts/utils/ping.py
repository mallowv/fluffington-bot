from datetime import datetime
import time

from discord import Embed
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Channels, Roles

DESCRIPTIONS = ("Command proccesing time", "API ping", "Bot latency")
ROUND_LATENCY = 3


class Latency(commands.Cog):
    """Getting the latency between the bot and websites."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """
        Gets different measures of latency within the bot.

        Returns bot and Discord Protocol latency.
        """
        bot_ping = (datetime.utcnow() - ctx.message.created_at.replace(tzinfo=None)).total_seconds() * 1000
        if bot_ping <= 0:
            bot_ping = "Your clock is out of sync, could not calculate ping"

        else:
            bot_ping = f"{bot_ping:.{ROUND_LATENCY}f} ms"
        start_time = time.time()
        message = await ctx.send("Testing Ping...")
        end_time = time.time()

        api_ping = f"{(end_time - start_time) * 1000:.{ROUND_LATENCY}f} ms"
        discord_ping = f"{self.bot.latency * 1000:.{ROUND_LATENCY}f} ms"

        embed = Embed(title="Pong!")

        for desc, latency in zip(DESCRIPTIONS, [bot_ping, api_ping, discord_ping]):
            embed.add_field(name=desc, value=latency, inline=False)

        await message.edit(embed=embed, content="")


def setup(bot: Bot):
    """load the Latency cog"""
    bot.add_cog(Latency(bot))
