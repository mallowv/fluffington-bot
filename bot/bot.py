import asyncio
import logging

import coloredlogs
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

    name = constants.Client.name

    def __init__(self, **kwargs):
        super(Bot, self).__init__(**kwargs)
        self._guild_available = asyncio.Event()
        self.loop.create_task(self.send_log(self.name, "Connected!"))

    def add_cog(self, cog):
        """
        Delegate to super to register `cog`.

        This only serves to make the info log, so that extensions don't have to.
        """
        super(Bot, self).add_cog(cog)
        logger.info(f"Cog loaded: {cog.qualified_name}")

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

    async def wait_until_guild_available(self) -> None:
        """
        Wait until the PyDis guild becomes available (and the cache is ready).
        The on_ready event is inadequate because it only waits 2 seconds for a GUILD_CREATE
        gateway event before giving up and thus not populating the cache for unavailable guilds.
        """
        await self._guild_available.wait()


firebase_admin.initialize_app(constants.Client.firebase_creds)
db = firestore.client()
config = [
    doc.to_dict() for doc in db.collection("config").stream() if doc.id == "main"
][0]
prefix: any = (
    constants.Client.prefix
    if config["fixed_and_single_prefix"]
    else BotPrefixHandler.get_prefix
)

bot: Bot = Bot(
    command_prefix=prefix,
    activity=discord.Game(name=f"Commands: {prefix}help"),
)

# @bot.event
# async def on_ready():
#     await bot.send_log(bot.name, "Connected!")
