from firebase_admin import firestore
from discord.ext import commands

from bot import constants


class BotPrefixHandler:
    """
    handles bot prefixes across servers
    """

    # firebase_admin.initialize_app(Client.firebase_creds)

    @staticmethod
    def get_prefix(bot, message):
        if not bot.static_prefix:
            db = firestore.client()
            prefixes_ref = db.collection("prefixes")
            prefix = [
                doc.to_dict()
                for doc in prefixes_ref.stream()
                if doc.id == str(message.guild.id)
            ][0].get("prefix")

            return (
                commands.when_mentioned_or(prefix)(bot, message)
                if prefix
                else commands.when_mentioned_or(constants.Client.prefix)(bot, message)
            )
        return commands.when_mentioned_or(constants.Client.prefix)(bot, message)
