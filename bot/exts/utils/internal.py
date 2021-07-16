from datetime import datetime
import logging
from os import utime
from collections import Counter

import coloredlogs
import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Roles

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)


class Internals(commands.Cog):
    """
    Super secret internal commands and tools, shhhh
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.socket_events: Counter = Counter()
        self.socket_event_total = 0
        self.socket_since: utime = datetime.utcnow()

    @commands.Cog.listener()
    async def on_socket_response(self, msg: dict) -> None:
        """When a websocket event is received, increase our counters."""
        if event_type := msg.get("t"):
            self.socket_event_total += 1
            self.socket_events[event_type] += 1

    @commands.group(name="internal", aliases=["int"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def internal_group(self, ctx: commands.context):
        """Internal commands. Top secret!"""
        if not ctx.invoked_subcommand:
            await ctx.send("invalid use of internal")

    @internal_group.command(name="socketstats", aliases=("socket", "stats"))
    @commands.has_any_role(*Roles.moderation_roles)
    async def socketstats(self, ctx: commands.Context) -> None:
        """Fetch information on the socket events received from Discord."""
        running_s = (datetime.utcnow() - self.socket_since).total_seconds()

        per_s = self.socket_event_total / running_s

        stats_embed = discord.Embed(
            title="WebSocket statistics",
            description=f"Receiving {per_s:0.2f} events per second.",
            color=discord.Color.blurple(),
        )

        for event_type, count in self.socket_events.most_common(25):
            stats_embed.add_field(name=event_type, value=f"{count:,}", inline=True)

        await ctx.send(embed=stats_embed)


def setup(bot: Bot) -> None:
    """load the Internals cog"""
    bot.add_cog(Internals(bot))
