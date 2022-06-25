import logging
import textwrap
import typing as t
from abc import abstractmethod
from datetime import datetime

import discord
from discord.ext.commands import Context

from bot.bot import Bot
from bot.constants import Colours
import bot.exts.moderation.infraction._utils as _utils
from bot.utils import time, scheduling, messages
from bot.exts.moderation.modlog import ModLog
from bot.utils.converters import MemberOrUser
from bot.database.models import Infraction

log = logging.getLogger(__name__)


class InfractionScheduler:
    """Handles the application, pardoning, and expiration of infractions."""

    def __init__(self, bot: Bot, supported_infractions: t.Container[str]) -> None:
        self.bot = bot
        self.scheduler = scheduling.Scheduler(self.__class__.__name__)
        self.bot.loop.create_task(self.reschedule_infractions(supported_infractions))

    @property
    def mod_log(self) -> ModLog:
        """Get the currently loaded ModLog cog instance."""
        return self.bot.get_cog("ModLog")

    async def reschedule_infractions(self, supported_infractions: t.Container[str]) -> None:
        """Schedule expiration for previous infractions."""
        await self.bot.wait_until_database_ready()

        infractions = [infraction
                       for infraction in
                       await Infraction.query.order_by(
                           Infraction.expiry).gino.all() if infraction.type in supported_infractions and
                       infraction.active and not infraction.permanent
                       ]

        to_schedule = [i for i in infractions if i.id not in self.scheduler]

        for infraction in to_schedule:
            log.trace("Scheduling %r", infraction)
            self.schedule_expiration(infraction)

        # Call ourselves again when the last infraction would expire. This will be the "oldest" infraction we've seen
        # from the database so far, and new ones are scheduled as part of application.
        # We make sure to fire this
        if to_schedule:
            next_reschedule_point = max(
                infraction.expiry for infraction in to_schedule
            )
            log.trace("Will reschedule remaining infractions at %s", next_reschedule_point)

            self.scheduler.schedule_at(next_reschedule_point, -1, self.reschedule_infractions(supported_infractions))

        log.trace("Done rescheduling")

    async def reapply_infraction(
            self,
            infraction: Infraction,
            apply_coro: t.Optional[t.Awaitable]
    ) -> None:
        """Reapply an infraction if it's still active or deactivate it if less than 60 sec left."""
        # Calculate the time remaining, in seconds, for the mute.
        expiry = infraction.expiry
        delta = (expiry - datetime.utcnow()).total_seconds()

        # Mark as inactive if less than a minute remains.
        if delta < 60:
            log.info(
                "Infraction will be deactivated instead of re-applied "
                "because less than 1 minute remains."
            )
            await self.deactivate_infraction(infraction)
            return

        # Allowing mod log since this is a passive action that should be logged.
        try:
            await apply_coro
        except discord.HTTPException as e:
            # When user joined and then right after this left again before action completed, this can't apply roles
            if e.code == 10007 or e.status == 404:
                log.info(
                    f"Can't reapply {infraction.type} to user {infraction.user} because user left the guild."
                )
            else:
                log.exception(
                    f"Got unexpected HTTPException (HTTP {e.status}, Discord code {e.code})"
                    f"when awaiting {infraction.type} coroutine for {infraction.user}."
                )
        else:
            log.info(f"Re-applied {infraction.type} to user {infraction.user} upon rejoining.")

    async def apply_infraction(
            self,
            ctx: Context,
            infraction: Infraction,
            user: MemberOrUser,
            action_coro: t.Optional[t.Awaitable] = None,
            user_reason: t.Optional[str] = None,
            additional_info: str = "",
            purge: t.Optional[str] = ""
    ) -> bool:
        """
        Apply an infraction to the user, log the infraction, and optionally notify the user.
        `action_coro`, if not provided, will result in the infraction not getting scheduled for deletion.
        `user_reason`, if provided, will be sent to the user in place of the infraction reason.
        `additional_info` will be attached to the text field in the mod-log embed.
        Returns whether or not the infraction succeeded.
        """
        infr_type = infraction.type
        icon = _utils.INFRACTION_ICONS[infr_type][0]
        reason = infraction.reason
        expiry = time.format_infraction_with_duration(infraction.expiry)
        id_ = infraction.id

        if user_reason is None:
            user_reason = reason

        log.trace(f"Applying {infr_type} infraction #{id_} to {user}.")

        # Default values for the confirmation message and mod log.
        confirm_msg = ":ok_hand: applied"

        # Specifying an expiry for a note or warning makes no sense.
        if infr_type in ("note", "warning"):
            expiry_msg = ""
        else:
            expiry_msg = f" until {expiry}" if expiry else " permanently"

        dm_result = ""
        dm_log_text = ""
        expiry_log_text = f"\nExpires: {expiry}" if expiry else ""
        log_title = "applied"
        log_content = None
        failed = False

        # DM the user about the infraction if it's not a shadow/hidden infraction.
        # This needs to happen before we apply the infraction, as the bot cannot
        # send DMs to user that it doesn't share a guild with. If we were to
        # apply kick/ban infractions first, this would mean that we'd make it
        # impossible for us to deliver a DM. See python-discord/bot#982.
        if not infraction.hidden:
            dm_result = f":warning:"
            dm_log_text = "\nDM: **Failed**"

            # Accordingly display whether the user was successfully notified via DM.
            if await _utils.notify_infraction(user, infr_type.replace("_", " ").title(), expiry, user_reason, icon):
                dm_result = ":incoming_envelope: "
                dm_log_text = "\nDM: Sent"

        end_msg = ""
        if infraction.actor == self.bot.user.id:
            log.trace(
                f"Infraction #{id_} actor is bot; including the reason in the confirmation message."
            )
            if reason:
                end_msg = f" (reason: {textwrap.shorten(reason, width=1500, placeholder='...')})"

        if action_coro:
            log.trace(f"Awaiting the infraction #{id_} application action coroutine.")
            try:
                await action_coro
                if expiry:
                    # Schedule the expiration of the infraction.
                    self.schedule_expiration(infraction)
            except discord.HTTPException as e:
                # Accordingly display that applying the infraction failed.
                # Don't use ctx.message.author; antispam only patches ctx.author.
                confirm_msg = ":x: failed to apply"
                expiry_msg = ""
                log_content = ctx.author.mention
                log_title = "failed to apply"

                log_msg = f"Failed to apply {' '.join(infr_type.split('_'))} infraction #{id_} to {user}"
                if isinstance(e, discord.Forbidden):
                    log.warning(f"{log_msg}: bot lacks permissions.")
                elif e.code == 10007 or e.status == 404:
                    log.info(
                        f"Can't apply {infraction.type} to user {infraction.user} because user left from guild."
                    )
                else:
                    log.exception(log_msg)
                failed = True

        if failed:
            log.trace(f"Deleted infraction {infraction.id} from database because applying infraction failed.")
            try:
                await infraction.delete()
            except ResponseCodeError as e:
                confirm_msg += " and failed to delete"
                log_title += " and failed to delete"
                log.error(f"Deletion of {infr_type} infraction #{id_} failed with error code {e.status}.")
            infr_message = ""
        else:
            infr_message = f" **{purge}{' '.join(infr_type.split('_'))}** to {user.mention}{expiry_msg}{end_msg}"

            # Send a confirmation message to the invoking context.
        log.trace(f"Sending infraction #{id_} confirmation message.")
        await ctx.send(f"{dm_result}{confirm_msg}{infr_message}.")

        # Send a log message to the mod log.
        # Don't use ctx.message.author for the actor; antispam only patches ctx.author.
        log.trace(f"Sending apply mod log for infraction #{id_}.")
        await self.mod_log.send_log_message(
            icon_url=icon,
            colour=Colours.soft_red,
            title=f"Infraction {log_title}: {' '.join(infr_type.split('_'))}",
            thumbnail=user.avatar,
            text=textwrap.dedent(f"""
                Member: {messages.format_user(user)}
                Actor: {ctx.author.mention}{dm_log_text}{expiry_log_text}
                Reason: {reason}
                {additional_info}
            """),
            content=log_content,
            footer=f"ID {infraction.id}",
            guild_id=ctx.guild.id
        )

        log.info(f"Applied {purge}{infr_type} infraction #{id_} to {user}.")
        return not failed

    async def pardon_infraction(
            self,
            ctx: Context,
            infr_type: str,
            user: MemberOrUser,
            *,
            send_msg: bool = True,
            notify: bool = True
    ) -> None:
        """
        Prematurely end an infraction for a user and log the action in the mod log.
        If `send_msg` is True, then a pardoning confirmation message will be sent to
        the context channel. Otherwise, no such message will be sent.
        If `notify` is True, notify the user of the pardon via DM where applicable.
        """
        log.trace(f"Pardoning {infr_type} infraction for {user}.")

        # Check the current active infraction
        log.trace(f"Fetching active {infr_type} infractions for {user}.")

        infractions = [
            infraction for infraction in await Infraction.query.where(
                Infraction.type == infr_type,
                Infraction.user == user.id
            ).gino.all() if infraction.active
        ]

        if not infractions:
            log.debug(f"No active {infr_type} infraction found for {user}.")
            await ctx.send(f":x: There's no active {infr_type} infraction for user {user.mention}.")
            return

        # Deactivate the infraction and cancel its scheduled expiration task.
        log_text = await self.deactivate_infraction(infractions[0], send_log=False, notify=notify)

        log_text["Member"] = messages.format_user(user)
        log_text["Actor"] = ctx.author.mention
        log_content = None
        id_ = infractions[0].id
        footer = f"ID: {id_}"

        # Accordingly display whether the user was successfully notified via DM.
        dm_emoji = ""
        if log_text.get("DM") == "Sent":
            dm_emoji = ":incoming_envelope: "
        elif "DM" in log_text:
            dm_emoji = f":warning: "

        # Accordingly display whether the pardon failed.
        if "Failure" in log_text:
            confirm_msg = ":x: failed to pardon"
            log_title = "pardon failed"
            log_content = ctx.author.mention

            log.warning(f"Failed to pardon {infr_type} infraction #{id_} for {user}.")
        else:
            confirm_msg = ":ok_hand: pardoned"
            log_title = "pardoned"

            log.info(f"Pardoned {infr_type} infraction #{id_} for {user}.")

        # Send a confirmation message to the invoking context.
        if send_msg:
            log.trace(f"Sending infraction #{id_} pardon confirmation message.")
            await ctx.send(
                f"{dm_emoji}{confirm_msg} infraction **{' '.join(infr_type.split('_'))}** for {user.mention}. "
                f"{log_text.get('Failure', '')}"
            )

        # Move reason to end of entry to avoid cutting out some keys
        log_text["Reason"] = log_text.pop("Reason")

        # Send a log message to the mod log.
        await self.mod_log.send_log_message(
            icon_url=_utils.INFRACTION_ICONS[infr_type][1],
            colour=Colours.soft_green,
            title=f"Infraction {log_title}: {' '.join(infr_type.split('_'))}",
            thumbnail=user.avatar,
            text="\n".join(f"{k}: {v}" for k, v in log_text.items()),
            footer=footer,
            content=log_content,
            guild_id=ctx.guild.id
        )

    async def deactivate_infraction(
            self,
            infraction: Infraction,
            *,
            send_log: bool = True,
            notify: bool = True
    ) -> t.Dict[str, str]:
        """
        Deactivate an active infraction and return a dictionary of lines to send in a mod log.
        The infraction is removed from Discord, marked as inactive in the database, and has its
        expiration task cancelled. If `send_log` is True, a mod log is sent for the
        deactivation of the infraction.
        If `notify` is True, notify the user of the pardon via DM where applicable.
        Infractions of unsupported types will raise a ValueError.
        """
        user_id = int(infraction.user)
        actor = int(infraction.actor)
        guild = int(infraction.guild)
        type_ = infraction.type
        id_ = infraction.id
        inserted_at = infraction.inserted_at
        expiry = infraction.expiry

        created = time.format_infraction_with_duration(inserted_at, expiry)

        log_content = None
        log_text = {
            "Member": f"<@{user_id}>",
            "Actor": f"<@{actor}>",
            "Reason": infraction.reason,
            "Created": created,
        }

        try:
            returned_log = await self._pardon_action(infraction, notify)

            if returned_log is not None:
                log_text = {**log_text, **returned_log}
            else:
                raise ValueError(
                    f"Attempted to deactivate an unsupported infraction {id_} ({type_})!"
                )

        except discord.Forbidden:
            log.warning(f"Failed to deactivate infraction #{id_} ({type_}): bot lacks permissions.")
            log_text["Failure"] = "the bot lacks permissions to do this (role hierarchy?)"
        except discord.HTTPException as e:
            if e.code == 10007 or e.status == 404:
                log.warning(
                    f"Can't pardon {type_} infraction for user {user_id} because user left the {guild} guild."
                )
                log_text["Failure"] = "User left the guild."
            else:
                log.exception(f"Failed to deactivate infraction #{id_} ({type_})")
                log_text["Failure"] = f"HTTPException with status {e.status} and code {e.code}."

        log.trace(f"Marking infraction {id_} as inactive in the database.")
        await infraction.update(active=False).apply()

        if infraction.expiry:
            self.scheduler.cancel(infraction.id)

        # Cancel the expiration task.
        if infraction.expiry is not None:
            self.scheduler.cancel(infraction.id)

        # Send a log message to the mod log.
        if send_log:
            log_title = "expiration failed" if "Failure" in log_text else "expired"

            user = self.bot.get_user(user_id)
            avatar = user.avatar if user else None

            # Move reason to end so when reason is too long, this is not gonna cut out required items.
            log_text["Reason"] = log_text.pop("Reason")

            log.trace(f"Sending deactivation mod log for infraction #{id_}.")
            await self.mod_log.send_log_message(
                icon_url=_utils.INFRACTION_ICONS[type_][1],
                colour=Colours.soft_green,
                title=f"Infraction {log_title}: {type_}",
                thumbnail=avatar,
                text="\n".join(f"{k}: {v}" for k, v in log_text.items()),
                footer=f"ID: {id_}",
                content=log_content,
                guild_id=guild
            )

        return log_text

    @abstractmethod
    async def _pardon_action(
            self,
            infraction: Infraction,
            notify: bool
    ) -> t.Optional[t.Dict[str, str]]:
        """
        Execute deactivation steps specific to the infraction's type and return a log dict.
        If `notify` is True, notify the user of the pardon via DM where applicable.
        If an infraction type is unsupported, return None instead.
        """
        raise NotImplementedError

    def schedule_expiration(self, infraction: Infraction) -> None:
        """
        Marks an infraction expired after the delay from time of scheduling to time of expiration.
        At the time of expiration, the infraction is marked as inactive on the website and the
        expiration task is cancelled.
        """
        expiry = infraction.expiry
        self.scheduler.schedule_at(expiry, infraction.id, self.deactivate_infraction(infraction))
