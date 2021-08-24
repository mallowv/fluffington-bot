from datetime import datetime

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Guilds, Colours


class ModLog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        channel = message.channel
        author = message.author

        if not message.guild:
            return

        if message.author.bot:
            return

        log = message.content
        footer = f"Author id: {message.author.id} | Message id: {message.id}"
        server_logs: discord.TextChannel = self.bot.get_channel(
            Guilds.server_logs_channels.get(message.guild.id)
        )
        embed: discord.Embed = discord.Embed(
            colour=Colours.soft_red,
            description=f"""
            **Message deleted by {author.mention} in <#{channel.id}>**
            {log}
            """,
        )
        embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
        embed.set_footer(text=footer)
        embed.timestamp = datetime.utcnow()
        await server_logs.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, message_before, message_after):
        channel = message_before.channel
        author = message_before.author

        pass


def setup(bot: Bot):
    """load the ModLog cog"""
    bot.add_cog(ModLog(bot))
