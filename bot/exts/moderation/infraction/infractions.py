import logging
import textwrap
import typing as t

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Roles, Event
from bot.database.models import Guild, Infraction
from bot.exts.moderation.modlog import ModLog
from bot.utils.converters import Duration, Expiry, MemberOrUser, FetchedMember
from bot.exts.moderation.infraction import _utils
from bot.exts.moderation.infraction._scheduler import InfractionScheduler
from bot.utils.messages import format_user

log = logging.getLogger(__name__)


class Infractions(InfractionScheduler, commands.Cog):
    """Apply and pardon infractions on users for moderation purposes."""

    category = "Moderation"
    category_description = "Server moderation tools."

    def __init__(self, bot: Bot):
        super().__init__(bot, supported_infractions={"ban", "kick", "mute", "note", "warning", "voice_ban"})

        self.category = "Moderation"

    @property
    def mod_log(self) -> t.Optional[ModLog]:
        """Get the currently loaded ModLog cog instance."""
        return self.bot.get_cog("ModLog")

    async def get_muted_role(self, guild_id: int) -> discord.Role:
        guild_db = await Guild.get(str(guild_id))
        guild = await self.bot.fetch_guild(guild_id)
        muted_role = guild.get_role(int(guild_db.muted_role))
        return muted_role

    async def get_voiceban_role(self, guild_id: int) -> discord.Role:
        guild_db = await Guild.get(str(guild_id))
        guild = await self.bot.fetch_guild(guild_id)
        voiceban_role = guild.get_role(int(guild_db.voiceban_role))
        return voiceban_role

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Reapply active mute infractions for returning members."""
        active_mutes = [
            infraction for infraction in
            await Infraction.query.where(
                Infraction.type == "mute" and
                Infraction.user == member.id
            ).gino.all() if infraction.active
        ]

        if active_mutes:
            reason = f"Re-applying active mute: {active_mutes[0].id}"
            action = member.add_roles(await self.get_muted_role(member.guild.id), reason=reason)

            await self.reapply_infraction(active_mutes[0], action)

    # region: Permanent infractions

    @commands.command()
    async def warn(self, ctx: commands.Context, user: MemberOrUser, *, reason: t.Optional[str] = None) -> None:
        """Warn a user for the given reason."""
        if not isinstance(user, discord.Member):
            await ctx.send(":x: The user doesn't appear to be on the server.")
            return

        infraction = await _utils.post_infraction(ctx, user, "warning", reason, active=False)
        if infraction is None:
            return

        await self.apply_infraction(ctx, infraction, user)

    @commands.command()
    async def kick(self, ctx: commands.Context, user: MemberOrUser, *, reason: t.Optional[str] = None) -> None:
        """Kick a user for the given reason."""
        if not isinstance(user, discord.Member):
            await ctx.send(":x: The user doesn't appear to be on the server.")
            return

        await self.apply_kick(ctx, user, reason)

    @commands.command()
    async def ban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        duration: t.Optional[Expiry] = None,
        *,
        reason: t.Optional[str] = None
    ) -> None:
        """
        Permanently ban a user for the given reason and stop watching them with Big Brother.
        If duration is specified, it temporarily bans that user for the given duration.
        """
        await self.apply_ban(ctx, user, reason, expires_at=duration)

    @commands.command(aliases=('pban',))
    async def purgeban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        duration: t.Optional[Expiry] = None,
        *,
        reason: t.Optional[str] = None
    ) -> None:
        """
        Same as ban but removes all their messages of the last 24 hours.
        If duration is specified, it temporarily bans that user for the given duration.
        """
        await self.apply_ban(ctx, user, reason, 1, expires_at=duration)

    @commands.command(aliases=('vban',))
    async def voiceban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        duration: t.Optional[Expiry] = None,
        *,
        reason: t.Optional[str]
    ) -> None:
        """
        Permanently ban user from using voice channels.
        If duration is specified, it temporarily voice bans that user for the given duration.
        """
        await self.apply_voice_ban(ctx, user, reason, expires_at=duration)

    # endregion
    # region: Temporary infractions

    @commands.command(aliases=["mute"])
    async def tempmute(
        self, ctx: commands.Context,
        user: MemberOrUser,
        duration: t.Optional[Expiry] = None,
        *,
        reason: t.Optional[str] = None
    ) -> None:
        """
        Temporarily mute a user for the given reason and duration.
        A unit of time should be appended to the duration.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Alternatively, an ISO 8601 timestamp can be provided for the duration.
        If no duration is given, a one hour duration is used by default.
        """
        if not isinstance(user, discord.Member):
            await ctx.send(":x: The user doesn't appear to be on the server.")
            return

        if duration is None:
            duration = await Duration().convert(ctx, "1h")
        await self.apply_mute(ctx, user, reason, expires_at=duration)

    @commands.command(aliases=("tban",))
    async def tempban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        duration: Expiry,
        *,
        reason: t.Optional[str] = None
    ) -> None:
        """
        Temporarily ban a user for the given reason and duration.
        A unit of time should be appended to the duration.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Alternatively, an ISO 8601 timestamp can be provided for the duration.
        """
        await self.apply_ban(ctx, user, reason, expires_at=duration)

    @commands.command(aliases=("tempvban", "tvban"))
    async def tempvoiceban(
            self,
            ctx: commands.Context,
            user: MemberOrUser,
            duration: Expiry,
            *,
            reason: t.Optional[str]
    ) -> None:
        """
        Temporarily voice ban a user for the given reason and duration.
        A unit of time should be appended to the duration.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Alternatively, an ISO 8601 timestamp can be provided for the duration.
        """
        await self.apply_voice_ban(ctx, user, reason, expires_at=duration)

    # endregion
    # region: Permanent shadow infractions

    @commands.command(hidden=True)
    async def note(self, ctx: commands.Context, user: MemberOrUser, *, reason: t.Optional[str] = None) -> None:
        """Create a private note for a user with the given reason without notifying the user."""
        infraction = await _utils.post_infraction(ctx, user, "note", reason, hidden=True, active=False)
        if infraction is None:
            return

        await self.apply_infraction(ctx, infraction, user)

    @commands.command(hidden=True, aliases=['shadowban', 'sban'])
    async def shadow_ban(self, ctx: commands.Context, user: MemberOrUser, *, reason: t.Optional[str] = None) -> None:
        """Permanently ban a user for the given reason without notifying the user."""
        await self.apply_ban(ctx, user, reason, hidden=True)

    # endregion
    # region: Temporary shadow infractions

    @commands.command(hidden=True, aliases=["shadowtempban", "stempban", "stban"])
    async def shadow_tempban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        duration: Expiry,
        *,
        reason: t.Optional[str] = None
    ) -> None:
        """
        Temporarily ban a user for the given reason and duration without notifying the user.
        A unit of time should be appended to the duration.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Alternatively, an ISO 8601 timestamp can be provided for the duration.
        """
        await self.apply_ban(ctx, user, reason, expires_at=duration, hidden=True)

    # endregion
    # region: Remove infractions (un- commands)

    @commands.command()
    async def unmute(self, ctx: commands.Context, user: MemberOrUser) -> None:
        """Prematurely end the active mute infraction for the user."""
        await self.pardon_infraction(ctx, "mute", user)

    @commands.command()
    async def unban(self, ctx: commands.Context, user: MemberOrUser) -> None:
        """Prematurely end the active ban infraction for the user."""
        await self.pardon_infraction(ctx, "ban", user)

    @commands.command(aliases=("uvban",))
    async def unvoiceban(self, ctx: commands.Context, user: MemberOrUser) -> None:
        """Prematurely end the active voice ban infraction for the user."""
        await self.pardon_infraction(ctx, "voice_ban", user)

    # region: Base apply functions

    async def apply_mute(self, ctx: commands.Context, user: discord.Member, reason: t.Optional[str], **kwargs) -> None:
        """Apply a mute infraction with kwargs passed to `post_infraction`."""
        if active := await _utils.get_active_infraction(ctx, user, "mute", send_msg=False):
            if active.actor != self.bot.user.id:
                await _utils.send_active_infraction_message(ctx, active)
                return

            # Allow the current mute attempt to override an automatically triggered mute.
            log_text = await self.deactivate_infraction(active, notify=False)
            if "Failure" in log_text:
                await ctx.send(
                    f":x: can't override infraction **mute** for {user.mention}: "
                    f"failed to deactivate. {log_text['Failure']}"
                )
                return

        infraction = await _utils.post_infraction(ctx, user, "mute", reason, active=True, **kwargs)
        if infraction is None:
            return

        self.mod_log.ignore(Event.member_update, user.id)

        async def action() -> None:
            # Skip members that left the server
            if not isinstance(user, discord.Member):
                return

            await user.add_roles(await self.get_muted_role(ctx.guild.id), reason=reason)

            log.trace(f"Attempting to kick {user} from voice because they've been muted.")
            await user.move_to(None, reason=reason)

        await self.apply_infraction(ctx, infraction, user, action())

    async def apply_kick(self, ctx: commands.Context, user: discord.Member, reason: t.Optional[str], **kwargs) -> None:
        """Apply a kick infraction with kwargs passed to `post_infraction`."""
        infraction = await _utils.post_infraction(ctx, user, "kick", reason, active=False, **kwargs)
        if infraction is None:
            return

        self.mod_log.ignore(Event.member_remove, user.id)

        if reason:
            reason = textwrap.shorten(reason, width=512, placeholder="...")

        action = user.kick(reason=reason)
        await self.apply_infraction(ctx, infraction, user, action)

    async def apply_ban(
        self,
        ctx: commands.Context,
        user: MemberOrUser,
        reason: t.Optional[str],
        purge_days: t.Optional[int] = 0,
        **kwargs
    ) -> None:
        """
        Apply a ban infraction with kwargs passed to `post_infraction`.
        Will also remove the banned user from the Big Brother watch list if applicable.
        """
        # In the case of a permanent ban, we don't need get_active_infractions to tell us if one is active
        is_temporary = kwargs.get("expires_at") is not None
        active_infraction = await _utils.get_active_infraction(ctx, user, "ban", is_temporary)

        if active_infraction:
            if is_temporary:
                log.trace("Tempban ignored as it cannot overwrite an active ban.")
                return

            if active_infraction.get('expires_at') is None:
                log.trace("Permaban already exists, notify.")
                await ctx.send(f":x: User is already permanently banned (#{active_infraction['id']}).")
                return

            log.trace("Old tempban is being replaced by new permaban.")
            await self.pardon_infraction(ctx, "ban", user, send_msg=is_temporary)

        infraction = await _utils.post_infraction(ctx, user, "ban", reason, active=True, **kwargs)
        if infraction is None:
            return

        purge = "purge " if purge_days else ""

        self.mod_log.ignore(Event.member_remove, user.id)

        if reason:
            reason = textwrap.shorten(reason, width=512, placeholder="...")

        action = ctx.guild.ban(user, reason=reason, delete_message_days=purge_days)
        await self.apply_infraction(ctx, infraction, user, action, purge=purge)

    async def apply_voice_ban(self, ctx: commands.Context, user: MemberOrUser, reason: t.Optional[str], **kwargs) -> None:
        """Apply a voice ban infraction with kwargs passed to `post_infraction`."""
        if await _utils.get_active_infraction(ctx, user, "voice_ban"):
            return

        infraction = await _utils.post_infraction(ctx, user, "voice_ban", reason, active=True, **kwargs)
        if infraction is None:
            return

        self.mod_log.ignore(Event.member_update, user.id)

        if reason:
            reason = textwrap.shorten(reason, width=512, placeholder="...")

        async def action() -> None:
            # Skip members that left the server
            if not isinstance(user, discord.Member):
                return

            await user.move_to(None, reason="Disconnected from voice to apply voiceban.")
            await user.add_roles(await self.get_voiceban_role(ctx.guild.id), reason=reason)

        await self.apply_infraction(ctx, infraction, user, action())

    # region: Base pardon functions

    async def pardon_mute(
            self,
            user_id: int,
            guild: discord.Guild,
            reason: t.Optional[str],
            *,
            notify: bool = True
    ) -> t.Dict[str, str]:
        """Remove a user's muted role, optionally DM them a notification, and return a log dict."""
        user = await guild.fetch_member(user_id)
        log_text = {}

        if user:
            # Remove the muted role.
            self.mod_log.ignore(Event.member_update, user.id)
            await user.remove_roles(await self.get_muted_role(guild.id), reason=reason)

            if notify:
                # DM the user about the expiration.
                notified = await _utils.notify_pardon(
                    user=user,
                    title="You have been unmuted",
                    content="You may now send messages in the server.",
                    icon_url=_utils.INFRACTION_ICONS["mute"][1]
                )
                log_text["DM"] = "Sent" if notified else "**Failed**"

            log_text["Member"] = format_user(user)
        else:
            log.info(f"Failed to unmute user {user_id}: user not found")
            log_text["Failure"] = "User was not found in the guild."

        return log_text

    async def pardon_ban(self, user_id: int, guild: discord.Guild, reason: t.Optional[str]) -> t.Dict[str, str]:
        """Remove a user's ban on the Discord guild and return a log dict."""
        user = discord.Object(user_id)
        log_text = {}

        self.mod_log.ignore(Event.member_unban, user_id)

        try:
            await guild.unban(user, reason=reason)
        except discord.NotFound:
            log.info(f"Failed to unban user {user_id}: no active ban found on Discord")
            log_text["Note"] = "No active ban found on Discord."

        return log_text

    async def pardon_voice_ban(
            self,
            user_id: int,
            guild: discord.Guild,
            reason: t.Optional[str],
            *,
            notify: bool = True
    ) -> t.Dict[str, str]:
        """Optionally DM the user a pardon notification and return a log dict."""
        user = guild.get_member(user_id)
        log_text = {}

        if user:
            # Remove the voiceban role.
            self.mod_log.ignore(Event.member_update, user.id)
            await user.remove_roles(await self.get_voiceban_role(guild.id), reason=reason)
            if notify:
                # DM user about infraction expiration
                notified = await _utils.notify_pardon(
                    user=user,
                    title="Voice ban ended",
                    content=f"You have been unbanned and can join voice again in the {guild.name} server.",
                    icon_url=_utils.INFRACTION_ICONS["voice_ban"][1]
                )
                log_text["DM"] = "Sent" if notified else "**Failed**"

            log_text["Member"] = format_user(user)
        else:
            log_text["Info"] = "User was not found in the guild."

        return log_text

    async def _pardon_action(self, infraction: Infraction, notify: bool) -> t.Optional[t.Dict[str, str]]:
        """
        Execute deactivation steps specific to the infraction's type and return a log dict.
        If `notify` is True, notify the user of the pardon via DM where applicable.
        If an infraction type is unsupported, return None instead.
        """
        guild = await self.bot.fetch_guild(infraction.guild)
        user_id = infraction.user
        reason = f"Infraction #{infraction.id} expired or was pardoned."

        if infraction.type == "mute":
            return await self.pardon_mute(user_id, guild, reason, notify=notify)
        elif infraction.type == "ban":
            return await self.pardon_ban(user_id, guild, reason)
        elif infraction.type == "voice_ban":
            return await self.pardon_voice_ban(user_id, guild, reason, notify=notify)

    # endregion

    # This cannot be static (must have a __func__ attribute).
    async def cog_check(self, ctx: commands.Context) -> bool:
        """Only allow moderators to invoke the commands in this cog."""
        return await commands.has_any_role(*Roles.moderation_roles).predicate(ctx)

    # This cannot be static (must have a __func__ attribute).
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Send a notification to the invoking context on a Union failure."""
        if isinstance(error, commands.BadUnionArgument):
            if discord.User in error.converters or discord.Member in error.converters:
                await ctx.send(str(error.errors[0]))
                error.handled = True


def setup(bot: Bot) -> None:
    """load the Infractions cog"""
    bot.add_cog(Infractions(bot))
