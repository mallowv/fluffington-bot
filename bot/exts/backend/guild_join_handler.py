import discord
from discord.ext import commands

from bot.bot import Bot
from bot.database.models import Guild


class GuildJoinHandler(commands.Cog):
    """
    to handle when fluffington gets added to a server
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        server_logs_channel = discord.utils.find(
            lambda c: c.name.lower() in ("server-logs", "modlog"), guild.channels
        )
        muted_role = discord.utils.find(
            lambda r: r.name.lower() in ("muted",), guild.roles
        )
        voiceban_role = discord.utils.find(
            lambda r: r.name.lower() in ("voicebanned",), guild.roles
        )
        if muted_role and voiceban_role:
            pass
        elif not muted_role and not voiceban_role:
            voiceban_perms = discord.Permissions.none()
            voiceban_perms.update(send_messages=True, send_messages_in_threads=True)
            voiceban_role = await guild.create_role(name="Voicebanned", permissions=voiceban_perms)

            muted_perms = discord.Permissions.none()
            muted_role = await guild.create_role(name="Muted", permissions=muted_perms)
        elif not muted_role:
            muted_perms = discord.Permissions.none()
            muted_role = await guild.create_role(name="Muted", permissions=muted_perms)
        elif not voiceban_role:
            voiceban_perms = discord.Permissions.none()
            voiceban_perms.update(send_messages=True, send_messages_in_threads=True)
            voiceban_role = await guild.create_role(name="Voicebanned", permissions=voiceban_perms)

        await Guild.create(
            id=str(guild.id),
            server_log_channel=str(server_logs_channel.id) if server_logs_channel else None,
            muted_role=str(muted_role.id),
            voiceban_role=str(voiceban_role.id)
        )

        for text_channel in guild.text_channels:
            if text_channel.permissions_for(guild.default_role).read_messages:
                await text_channel.set_permissions(muted_role, send_messages=False)


def setup(bot: Bot):
    """load the GuildJoinHandler cog"""
    bot.add_cog(GuildJoinHandler(bot))
