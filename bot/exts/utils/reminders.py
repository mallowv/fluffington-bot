from datetime import datetime
import logging
import typing as t
import random
import asyncio
import textwrap

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.utils.messages import send_denial
from bot.utils.scheduling import Scheduler
from bot.utils.pagination import LinePaginator
from bot.database.models import Reminder
from bot.utils.converters import Duration
from bot.constants import POSITIVE_REPLIES, Icons
from bot.utils.time import discord_timestamp, TimestampFormats

log = logging.getLogger(__name__)
MAXIMUM_REMINDERS = 100


class Reminders(commands.Cog):
    """Provide in-channel reminder functionality."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

        self.scheduler = Scheduler(self.__class__.__name__)

        self.bot.loop.create_task(self.reschedule_reminders())

    def cog_unload(self) -> None:
        """Cancel scheduled tasks."""
        self.scheduler.cancel_all()

    async def reschedule_reminders(self):
        """Get all reminders from the database then reschedule them"""
        await self.bot.wait_until_database_ready()
        reminders = await Reminder.query.gino.all()

        now = datetime.utcnow()

        for reminder in reminders:
            is_valid, *_ = await self.ensure_valid_reminder(reminder)

            if not is_valid:
                continue

            #if the reminder is already overdue
            if reminder.expiration < now:
                await self.send_reminder(reminder)

            else:
                self.schedule_reminder(reminder)

    async def get_mentionables(self, reminder: Reminder):
        guild = await self.bot.fetch_guild(reminder.guild_id)

        if reminder.mentions:
            for mention in reminder.mentions.split(","):
                if mentionable := (await guild.fetch_member(int(mention)) or await guild.get_role(int(mention))):
                    yield mentionable

    def schedule_reminder(self, reminder: Reminder):
        """A coroutine which sends the reminder once the time is reached, and cancels the running task."""
        self.scheduler.schedule_at(reminder.expiration, reminder.id, self.send_reminder(reminder))

    async def ensure_valid_reminder(self, reminder: Reminder) -> t.Tuple[bool, discord.User, discord.TextChannel]:
        """Ensure reminder author and channel can be fetched otherwise delete the reminder."""
        user = await self.bot.fetch_user(reminder.author)
        channel = await self.bot.fetch_channel(reminder.channel_id)
        is_valid = True
        if not user or not channel:
            is_valid = False
            log.info(
                f"Reminder {reminder.id} invalid: "
                f"User {reminder.author}={user}, Channel {reminder.channel_id}={channel}."
            )
            asyncio.create_task(reminder.delete())

        return is_valid, user, channel

    @staticmethod
    async def _send_confirmation(
        ctx: commands.Context,
        on_success: str,
        reminder_id: t.Union[str, int]
    ) -> None:
        """Send an embed confirming the reminder change was made successfully."""
        embed = discord.Embed(
            description=on_success,
            colour=discord.Colour.green(),
            title=random.choice(POSITIVE_REPLIES)
        )

        footer_str = f"ID: {reminder_id}"

        embed.set_footer(text=footer_str)

        await ctx.send(embed=embed)

    @staticmethod
    async def _edit_reminder(reminder_id: str, **updated_reminder: dict) -> Reminder:
        """
        Edits a reminder in the database given the ID and payload.
        Returns the edited reminder.
        """

        reminder = await Reminder.get(reminder_id)
        await reminder.update(**updated_reminder).apply()
        return reminder

    async def _reschedule_reminder(self, reminder: Reminder) -> None:
        """Reschedule a reminder object."""
        log.trace(f"Cancelling old task #{reminder.id}")
        self.scheduler.cancel(reminder.id)

        log.trace(f"Scheduling new task #{reminder.id}")
        self.schedule_reminder(reminder)

    async def send_reminder(self, reminder: Reminder, expected_time: datetime = None) -> None:
        """Send the reminder."""
        is_valid, user, channel = await self.ensure_valid_reminder(reminder)
        if not is_valid:
            # No need to cancel the task too; it'll simply be done once this coroutine returns.
            return
        embed = discord.Embed()
        if expected_time:
            embed.colour = discord.Colour.red()
            embed.set_author(
                icon_url=Icons.remind_red,
                name="Sorry, your reminder should have arrived earlier!"
            )
        else:
            embed.colour = discord.Colour.blurple()
            embed.set_author(
                icon_url=Icons.remind_blurple,
                name="It has arrived!"
            )

        # Let's not use a codeblock to keep emojis and mentions working. Embeds are safe anyway.
        embed.description = f"Here's your reminder: {reminder.content}"

        mentions = []
        async for mentionables in self.get_mentionables(reminder):
            mentions.append(mentionables.mention)
        mentions = ", ".join(mentions)

        jump_url = reminder.jump_url
        embed.description += f"\n[Jump back to when you created the reminder]({jump_url})"
        partial_message = channel.get_partial_message(int(jump_url.split("/")[-1]))
        try:
            await partial_message.reply(content=f"{mentions}", embed=embed)
        except discord.HTTPException as e:
            log.info(
                f"There was an error when trying to reply to a reminder invocation message, {e}, "
                "fall back to using jump_url"
            )
            await channel.send(content=f"{user.mention} {mentions}", embed=embed)

        log.debug(f"Deleting reminder #{reminder.id} (the user has been reminded).")
        await reminder.delete()

    @commands.group(name="remind", aliases=("reminder", "reminders", "remindme"), invoke_without_command=True)
    async def remind_group(
        self, ctx: commands.Context,
        mentions: commands.Greedy[t.Union[discord.Member, discord.Role]],
        expiration: Duration,
        *,
        content: str
    ) -> None:
        """
        Commands for managing your reminders.
        The `expiration` duration of `!remind new` supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `m`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `M`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        For example, to set a reminder that expires in 3 days and 1 minute, you can do `!remind new 3d1M Do something`.
        """
        await self.new_reminder(ctx, mentions=mentions, expiration=expiration, content=content)

    @remind_group.command(name="new", aliases=("add", "create"))
    async def new_reminder(
        self, ctx: commands.Context,
        mentions: commands.Greedy[t.Union[discord.Member, discord.Role]],
        expiration: Duration,
        *,
        content: str
    ) -> None:
        """
        Set yourself a simple reminder.
        The `expiration` duration supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `m`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `M`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        For example, to set a reminder that expires in 3 days and 1 minute, you can do `!remind new 3d1M Do something`.
        """

        active_reminders = await Reminder.query.gino.all()

        # Let's limit this, so we don't get 10 000
        # reminders from joe or something like that :P
        if len(active_reminders) > MAXIMUM_REMINDERS:
            await send_denial(ctx, "You have too many active reminders!")
            return

        mentions = set(mentions)
        mentions.discard(ctx.author)

        mention_ids = [str(mention.id) for mention in mentions]

        reminder = await Reminder.create(
            author=str(ctx.author.id),
            channel_id=str(ctx.channel.id),
            guild_id=str(ctx.guild.id),
            jump_url=ctx.message.jump_url,
            content=content,
            expiration=expiration,
            mentions=",".join(mention_ids) if mention_ids else ""
        )

        mention_string = f"Your reminder will arrive on {discord_timestamp(expiration, TimestampFormats.DAY_TIME)}"

        if mentions:
            mention_string += f" and will mention {len(mentions)} other(s)"
        mention_string += "!"

        # Confirm to the user that it worked.
        await self._send_confirmation(
            ctx,
            on_success=mention_string,
            reminder_id=reminder.id
        )

        self.schedule_reminder(reminder)

    @remind_group.command(name="list")
    async def list_reminders(self, ctx: commands.Context):
        """View a paginated embed of all reminders for your user."""

        reminders = await Reminder.query.order_by(Reminder.expiration).where(
            Reminder.author == str(ctx.author.id)
        ).gino.all()

        lines = []

        for reminder in reminders:
            # Parse and humanize the time, make it pretty :D
            remind_datetime = reminder.expiration
            time = discord_timestamp(remind_datetime, TimestampFormats.RELATIVE)

            mentions = []
            async for mentionables in self.get_mentionables(reminder):
                mentions.append(mentionables.mention)
            mentions = ", ".join(mentions)
            mention_string = f"\n**Mentions:** {mentions}" if mentions else ""

            text = textwrap.dedent(f"""
            **Reminder #{reminder.id}:** *expires {time}* {mention_string}
            {reminder.content}
            """).strip()

            lines.append(text)

        embed = discord.Embed()
        embed.colour = discord.Colour.blurple()
        embed.title = f"Reminders for {ctx.author}"

        # Remind the user that they have no reminders :^)
        if not lines:
            embed.description = "No active reminders could be found."
            await ctx.send(embed=embed)
            return

        # Construct the embed and paginate it.
        embed.colour = discord.Colour.blurple()

        await LinePaginator.paginate(
            lines,
            ctx, embed,
            max_lines=3,
            empty=True
        )

    @remind_group.group(name="edit", aliases=("change", "modify"), invoke_without_command=True)
    async def edit_reminder_group(self, ctx: commands.Context) -> None:
        """
        Commands for modifying your current reminders.
        The `expiration` duration supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `m`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `M`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        For example, to edit a reminder to expire in 3 days and 1 minute, you can do `!remind edit duration 1234 3d1M`.
        """
        await ctx.send_help(ctx.command)

    @edit_reminder_group.command(name="duration", aliases=("time",))
    async def edit_reminder_duration(self, ctx: commands.Context, id_: str, expiration: Duration) -> None:
        """
        Edit one of your reminder's expiration.
        The `expiration` duration supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `m`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `M`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        For example, to edit a reminder to expire in 3 days and 1 minute, you can do `!remind edit duration 1234 3d1M`.
        """
        await self.edit_reminder(ctx, id_, {'expiration': expiration})

    @edit_reminder_group.command(name="content", aliases=("reason",))
    async def edit_reminder_content(self, ctx: commands.Context, id_: str, *, content: str) -> None:
        """Edit one of your reminder's content."""
        await self.edit_reminder(ctx, id_, {"content": content})

    @edit_reminder_group.command(name="mentions", aliases=("pings",))
    async def edit_reminder_mentions(
        self,
        ctx: commands.Context,
        id_: str,
        mentions: commands.Greedy[t.Union[discord.Member, discord.Role]]
    ) -> None:
        """Edit one of your reminder's mentions."""
        # Remove duplicate mentions
        mentions = set(mentions)
        mentions.discard(ctx.author)

        mention_ids = [str(mention.id) for mention in mentions]
        await self.edit_reminder(ctx, id_, {"mentions": ",".join(mention_ids) if mention_ids else ""})

    async def edit_reminder(self, ctx: commands.Context, id_: str, payload: dict) -> None:
        """Edits a reminder with the given payload, then sends a confirmation message."""
        if not await self._can_modify(ctx, id_):
            return
        reminder = await self._edit_reminder(id_, **payload)

        # Send a confirmation message to the channel
        await self._send_confirmation(
            ctx,
            on_success="That reminder has been edited successfully!",
            reminder_id=id_,
        )
        await self._reschedule_reminder(reminder)

    @remind_group.command("delete", aliases=("remove", "cancel"))
    async def delete_reminder(self, ctx: commands.Context, id_: str) -> None:
        """Delete one of your active reminders."""
        if not await self._can_modify(ctx, id_):
            return

        reminder = await Reminder.get(id_)
        await reminder.delete()
        self.scheduler.cancel(id_)

        await self._send_confirmation(
            ctx,
            on_success="That reminder has been deleted successfully!",
            reminder_id=id_
        )

    @staticmethod
    async def _can_modify(ctx: commands.Context, reminder_id: str) -> bool:
        """
        Check whether the reminder can be modified by the ctx author.
        The check passes when the user is an admin, or if they created the reminder.
        """

        if ctx.author.guild_permissions.administrator:
            return True

        reminder = await Reminder.get(reminder_id)
        if not reminder.author == ctx.author.id:
            log.debug(f"{ctx.author} is not the reminder author and does not pass the check.")
            await send_denial(ctx, "You can't modify reminders of other users!")
            return False

        log.debug(f"{ctx.author} is the reminder author and passes the check.")
        return True


def setup(bot: Bot):
    """load the Reminders cog"""
    bot.add_cog(Reminders(bot))
