import asyncio
import logging

import coloredlogs
import arrow
import discord
from discord import DiscordException, Embed
from discord.ext import commands
import firebase_admin
from firebase_admin import firestore

import bot.constants as constants
from bot.utils.bot_prefix import BotPrefixHandler

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)


class Bot(commands.bot.Bot):
    """
    Base bot instance.

    While in debug mode, the asset upload methods (avatar, banner, ...) will not
    perform the upload, and will instead only log the passed download urls and pretend
    that the upload was successful. See the `mock_in_debug` decorator for further details.
    """

    startup_time = arrow.utcnow()
    name = constants.Client.name

    def __init__(self, **kwargs):
        super(Bot, self).__init__(**kwargs)
        self._guild_available = asyncio.Event()
        self.loop.create_task(self.send_log(self.name, "Connected!"))
        self.debug = True
        self.static_prefix = self.debug

    @classmethod
    def create(cls):
        intents = discord.Intents.default()
        intents.members = True
        return cls(
            command_prefix=BotPrefixHandler.get_prefix,
            activity=discord.Game(name=f"Commands: {constants.Client.prefix}help"),
            intents=intents,
        )

    def add_cog(self, cog):
        """
        Delegate to super to register `cog`.

        This only serves to make the info log, so that extensions don't have to.
        """
        super(Bot, self).add_cog(cog)
        logger.info(f"Cog loaded: {cog.qualified_name}")

    def load_extension(self, name, *, package=None):
        super(Bot, self).load_extension(name, package=package)
        logger.info(f"Extension loaded: {name}")

    def unload_extension(self, name, *, package=None):
        super(Bot, self).unload_extension(name, package=package)
        logger.info(f"Extension unloaded: {name}")

    async def send_log(
        self, title: str, details: str = None, *, icon: str = None
    ) -> None:
        """Send an embed message to the devlog channel."""
        await self.wait_until_ready()
        devlog = self.get_channel(constants.Channels.devlog_channel)

        if not devlog:
            logger.info(
                f"Fetching devlog channel as it wasn't found in the cache (ID: {constants.Channels.devlog})"
            )
            try:
                devlog = await self.fetch_channel(constants.Channels.devlog)
            except discord.HTTPException as discord_exc:
                logger.exception("Fetch failed", exc_info=discord_exc)
                return

        if not icon:
            icon = self.user.avatar_url_as(format="png")

        embed = Embed(description=details)
        embed.set_author(name=title, icon_url=icon)

        await devlog.send(embed=embed)
        logger.info(f"{self.name} Connected!")
