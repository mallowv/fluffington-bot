import typing
import textwrap

import discord
from dateutil.relativedelta import relativedelta
from discord.ext import commands

from bot import constants
from bot.bot import Bot
from bot.database.models import Infraction
from bot.utils.converters import Expiry, InfractionConv, MemberOrUser
from bot.exts.moderation.infraction.infractions import Infractions
from bot.exts.moderation.modlog import ModLog
from bot.utils.pagination import LinePaginator
from bot.utils import messages, time
from bot.utils.time import humanize_delta, discord_timestamp

INFRACTION_COLOURS = {
    "ban": discord.Colour.dark_red(),
    "kick": discord.Colour.orange(),
    "mute": constants.Colours.orange,
    "note": discord.Colour.brand_green(),
    "superstar": constants.Colours.yellow,
    "warning": constants.Colours.yellow,
    "voice_ban": discord.Colour.red(),
}


# noinspection PyTypeChecker
class ModManagement(commands.Cog):
    """Management of infractions."""

    category = "Moderation"

    def __init__(self, bot: Bot):
        self.bot = bot

    @property
    def mod_log(self) -> typing.Optional[ModLog]:
        """Get currently loaded ModLog cog instance."""
        return self.bot.get_cog("ModLog")

    @property
    def infractions_cog(self) -> typing.Optional[Infractions]:
        """Get currently loaded Infractions cog instance."""
        return self.bot.get_cog("Infractions")

    @commands.group(name='infraction', aliases=('infr', 'infractions', 'inf', 'i'), invoke_without_command=True)
    async def infraction_group(self, ctx: commands.Context) -> None:
        """Infraction manipulation commands."""
        await ctx.send_help(ctx.command)

    # region: Edit infraction commands

    @infraction_group.command(name="append", aliases=("amend", "add", "a"))
    async def infraction_append(
        self,
        ctx: commands.Context,
        infraction: InfractionConv,
        duration: typing.Union[Expiry, None],   # noqa: F821
        *,
        reason: str = None
    ) -> None:
        """
        Append text and/or edit the duration of an infraction.
        Durations are relative to the time of updating and should be appended with a unit of time.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Use "l", "last", or "recent" as the infraction ID to specify that the most recent infraction
        authored by the command invoker should be edited.
        Use "p" or "permanent" to mark the infraction as permanent. Alternatively, an ISO 8601
        timestamp can be provided for the duration.
        If a previous infraction reason does not end with an ending punctuation mark, this automatically
        adds a period before the amended reason.
        """
        old_reason = infraction.reason

        if old_reason is not None and reason is not None:
            add_period = not old_reason.endswith((".", "!", "?"))
            reason = old_reason + (". " if add_period else " ") + reason

        await self.infraction_edit(ctx, infraction, duration, reason=reason)

    @infraction_group.command(name='edit', aliases=('e',))
    async def infraction_edit(
        self,
        ctx: commands.Context,
        infraction: InfractionConv,
        duration: typing.Union[Expiry, None],   # noqa: F821
        *,
        reason: str = None
    ) -> None:
        """
        Edit the duration and/or the reason of an infraction.
        Durations are relative to the time of updating and should be appended with a unit of time.
        Units (∗case-sensitive):
        \u2003`y` - years
        \u2003`m` - months∗
        \u2003`w` - weeks
        \u2003`d` - days
        \u2003`h` - hours
        \u2003`M` - minutes∗
        \u2003`s` - seconds
        Use "l", "last", or "recent" as the infraction ID to specify that the most recent infraction
        authored by the command invoker should be edited.
        Use "p" or "permanent" to mark the infraction as permanent. Alternatively, an ISO 8601
        timestamp can be provided for the duration.
        """
        if duration is None and reason is None:
            # Unlike UserInputError, the error handler will show a specified message for BadArgument
            raise commands.BadArgument("Neither a new expiry nor a new reason was specified.")

        infraction_id = infraction.id
        prev_expiry = infraction.expiry

        request_data = {}
        confirm_messages = []
        log_text = ""

        if duration is not None and not infraction.active:
            if reason is None:
                await ctx.send(":x: Cannot edit the expiration of an expired infraction.")
                return
            confirm_messages.append("expiry unchanged (infraction already expired)")
        elif isinstance(duration, str):
            request_data['expires_at'] = None
            confirm_messages.append("marked as permanent")
        elif duration is not None:
            request_data['expires_at'] = duration.isoformat()
            expiry = time.format_infraction_with_duration(request_data['expires_at'])
            confirm_messages.append(f"set to expire on {expiry}")
        else:
            confirm_messages.append("expiry unchanged")

        if reason:
            request_data['reason'] = reason
            confirm_messages.append("set a new reason")
            log_text += f"""
                Previous reason: {infraction.reason}
                New reason: {reason}
            """.rstrip()
        else:
            confirm_messages.append("reason unchanged")

        # Update the infraction
        await infraction.update(
            **request_data
        ).apply()

        # Re-schedule infraction if the expiration has been updated
        if 'expires_at' in request_data:
            # A scheduled task should only exist if the old infraction wasn't permanent
            if infraction.expires_at:
                self.infractions_cog.scheduler.cancel(new_infraction['id'])

            # If the infraction was not marked as permanent, schedule a new expiration task
            if request_data['expires_at']:
                self.infractions_cog.schedule_expiration(new_infraction)

            log_text += f"""
                Previous expiry: {until_expiration(prev_expiry) or "Permanent"}
                New expiry: {until_expiration(infraction.expires_at) or "Permanent"}
            """.rstrip()

        changes = ' & '.join(confirm_messages)
        await ctx.send(f":ok_hand: Updated infraction #{infraction_id}: {changes}")

        # Get information about the infraction's user
        user_id = infraction.user
        user = ctx.guild.get_member(user_id)

        if user:
            user_text = messages.format_user(user)
            thumbnail = user.avatar.url
        else:
            user_text = f"<@{user_id}>"
            thumbnail = None

        await self.mod_log.send_log_message(
            icon_url=constants.Icons.pencil,
            colour=discord.Colour.blurple(),
            title="Infraction edited",
            thumbnail=thumbnail,
            text=textwrap.dedent(f"""
                Member: {user_text}
                Actor: <@{infraction.actor}>
                Edited by: {ctx.message.author.mention}{log_text}
            """),
            guild_id=ctx.guild.id
        )

    # endregion
    # region: Search infractions

    @infraction_group.command("get")
    async def get_infraction(self, ctx: commands.Context, infraction: InfractionConv):
        infr_embed = discord.Embed(title="Infraction", colour=INFRACTION_COLOURS[infraction.type])
        user = await self.bot.fetch_user(infraction.user)
        infr_embed.set_thumbnail(url=user.avatar.url)
        desc = await self.infraction_to_string(infraction)
        infr_embed.description = desc
        await ctx.send(embed=infr_embed)

    @infraction_group.group(name="search", aliases=('s',), invoke_without_command=True)
    async def infraction_search_group(self, ctx: commands.Context, query: MemberOrUser) -> None:
        """Searches for infractions in the database."""
        if isinstance(query, int):
            await self.search_user(ctx, discord.Object(query))
        else:
            await self.search_user(ctx, query)

    @infraction_search_group.command(name="user", aliases=("member", "id"))
    async def search_user(self, ctx: commands.Context, user: typing.Union[MemberOrUser, discord.Object]) -> None:
        """Search for infractions by member."""
        infraction_list = await Infraction.query.where(
            Infraction.user == str(user.id)
        ).where(
            Infraction.guild == str(user.guild.id)
        ).gino.all()

        if isinstance(user, (discord.Member, discord.User)):
            user_str = f"{user.name}{user.discriminator} ({user.id})"
        else:
            if infraction_list:
                user = await self.bot.fetch_user(infraction_list[0].user)
                user_str = f"{user.name}{user.discriminator} ({user.id})"
            else:
                user_str = str(user.id)

        embed = discord.Embed(
            title=f"Infractions for {user_str} ({len(infraction_list)} total)",
            colour=discord.Colour.orange()
        )
        await self.send_infraction_list(ctx, embed, infraction_list)

    async def send_infraction_list(
            self,
            ctx: commands.Context,
            embed: discord.Embed,
            infractions: typing.Iterable[Infraction]
    ) -> None:
        """Send a paginated embed of infractions for the specified user."""
        if not infractions:
            await ctx.send(":warning: No infractions could be found for that query.")
            return

        lines = tuple([
                await self.infraction_to_string(infraction)
                for infraction in infractions
            ]
        )

        await LinePaginator.paginate(
            lines,
            ctx=ctx,
            embed=embed,
            empty=True,
            max_lines=3,
        )

    async def infraction_to_string(self, infraction: Infraction) -> str:
        """Convert the infraction object to a string representation."""
        active = infraction.active
        user = infraction.user
        expires_at = infraction.expiry
        created = time.format_infraction(infraction.inserted_at)

        # Format the user string.
        user_obj = await self.bot.fetch_user(user)
        user_str = messages.format_user(user_obj)

        if active:
            remaining = time.until_expiration(expires_at) or "Expired"
        else:
            remaining = "Inactive"

        if expires_at is None:
            duration = "*Permanent*"
        else:
            date_from = infraction.inserted_at
            date_to = expires_at
            duration = humanize_delta(relativedelta(date_to, date_from))

        lines = textwrap.dedent(f"""
            {"**===============**" if active else "==============="}
            Status: {"__**Active**__" if active else "Inactive"}
            User: {user_str}
            Type: **{infraction.type.replace("_", " ").title()}**
            Shadow: {infraction.hidden}
            Created: {created}
            Expires: {remaining}
            Duration: {duration}
            Actor: <@{infraction.actor}>
            ID: `{infraction.id}`
            Reason: {infraction.reason or "*None*"}
            {"**===============**" if active else "==============="}
        """)

        return lines.strip()


def setup(bot: Bot):
    """load the ModManagement cog"""
    bot.add_cog(ModManagement(bot))
