from discord.ext import commands

from bot import constants
from bot.database.models import Guild


class BotPrefixHandler:
    """
    handles bot prefixes across servers
    """

    # firebase_admin.initialize_app(Client.firebase_creds)

    @staticmethod
    async def get_prefix(bot, message):
        prefix = None
        if not bot.static_prefix:
            if message.guild:
                guild = await Guild.get(str(message.guild.id))
                prefix = guild.prefix if guild else None

            return (
                commands.when_mentioned_or(prefix)(bot, message)
                if prefix
                else commands.when_mentioned_or(constants.Bot.prefix)(bot, message)
            )
        return commands.when_mentioned_or(constants.Bot.prefix)(bot, message)
