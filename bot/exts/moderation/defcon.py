from datetime import datetime
import logging

import discord
from discord.ext import commands
from dateutil.relativedelta import relativedelta

from bot.bot import Bot
from bot.constants import Roles, Colours
from bot.database.models import Guild

logger = logging.getLogger(__name__)
REJECTION_MESSAGE = """
Hi, {user} - Thanks for your interest in our server!
Due to a current (or detected) cyberattack on our community, we've limited access to the {guild} server
for new accounts. Since
your account is relatively new, we're unable to provide access to the server at this time.
Even so, thanks for joining! We're very excited at the possibility of having you here, and we hope that this situation
will be resolved soon.
"""


class DefCon(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.treshold = relativedelta(days=5)
        self.shutdowned = {}

    @property
    def mod_log(self):
        """Get the currently loaded ModLog cog instance."""
        return self.bot.get_cog("ModLog")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        now = datetime.utcnow()
        if self.shutdowned.get(member.guild.id):
            if now - member.created_at < (now + self.treshold - now):
                msg_sent = False

                try:
                    await member.send(
                        REJECTION_MESSAGE.format(
                            user=member.mention, guild=member.guild.name
                        )
                    )

                    msg_sent = True
                except Exception:
                    logger.exception(
                        f"Unable to send rejection message to user: {member}"
                    )

                await member.kick(reason="DEFCON active, user is too new")
                message = f"{format_user(member)} was denied entry because their account is too new."

                if not message_sent:
                    message = f"{message}\n\nUnable to send rejection message via DM; they probably have DMs disabled."

                await self.mod_log.send_log_message(
                    "https://cdn.discordapp.com/emojis/472475292078964738.png",
                    Colours.soft_red,
                    "Entry denied",
                    message,
                    member.avatar,
                    Guild.get(member.guild.id).server_log_channel,
                )

    @commands.group(name="defcon", aliases=("dc",))
    async def defcon_group(self, ctx: commands.Context):
        if not ctx.subcommand_passed:
            await ctx.send_help(ctx.command)

    @defcon_group.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def shutdown(self, ctx: commands.Context):
        """Shut down the server by setting send permissions of everyone to False."""
        role = ctx.guild.default_role
        permissions = role.permissions

        self.shutdowned[ctx.guild.id] = True
        permissions.update(send_messages=False, add_reactions=False, connect=False)
        await role.edit(reason="DEFCON shutdown", permissions=permissions)
        await ctx.send(":white_check_mark::lock:  server locked down")

    @defcon_group.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def unshutdown(self, ctx: commands.Context) -> None:
        """Open up the server again by setting send permissions of everyone to None."""
        role = ctx.guild.default_role
        permissions = role.permissions

        self.shutdowned[ctx.guild.id] = False
        permissions.update(send_messages=True, add_reactions=True, connect=True)
        await role.edit(reason="DEFCON unshutdown", permissions=permissions)
        await ctx.send(":white_check_mark::unlock: server reopened")


def setup(bot: Bot):
    """load the DefCon cog"""
    bot.add_cog(DefCon(bot))
