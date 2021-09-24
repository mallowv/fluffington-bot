from datetime import datetime
import typing as t
import logging

import discord
from dateutil.relativedelta import relativedelta
from discord.ext.commands import (
    BadArgument,
    Context,
    Converter,
    UserConverter,
)

from bot import exts
from bot.utils.time import parse_duration_string
from bot.utils.extensions import EXTENSIONS, unqualify

logger = logging.getLogger(__name__)


class FetchedUser(UserConverter):
    """
    Converts to a `discord.User` or, if it fails, a `discord.Object`.
    Unlike the default `UserConverter`, which only does lookups via the global user cache, this
    converter attempts to fetch the user via an API call to Discord when the using the cache is
    unsuccessful.
    If the fetch also fails and the error doesn't imply the user doesn't exist, then a
    `discord.Object` is returned via the `user_proxy` converter.
    The lookup strategy is as follows (in order):
    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name#discrim
    4. Lookup by name
    5. Lookup via API
    6. Create a proxy user with discord.Object
    """

    async def convert(
        self, ctx: Context, arg: str
    ) -> t.Union[discord.User, discord.Object]:
        """Convert the `arg` to a `discord.User` or `discord.Object`."""
        try:
            return await super().convert(ctx, arg)
        except BadArgument:
            pass

        try:
            user_id = int(arg)
            logger.debug(f"Fetching user {user_id}...")
            return await ctx.bot.fetch_user(user_id)
        except ValueError:
            logger.debug(f"Failed to fetch user {arg}: could not convert to int.")
            raise BadArgument(
                f"The provided argument can't be turned into integer: `{arg}`"
            )
        except discord.HTTPException as e:
            # If the Discord error isn't `Unknown user`, return a proxy instead
            if e.code != 10013:
                logger.info(
                    f"Failed to fetch user, returning a proxy instead: status {e.status}"
                )
                return proxy_user(arg)

            logger.debug(f"Failed to fetch user {arg}: user does not exist.")
            raise BadArgument(f"User `{arg}` does not exist")


def proxy_user(user_id: str) -> discord.Object:
    """
    Create a proxy user object from the given id.
    Used when a Member or User object cannot be resolved.
    """
    logger.debug(f"Attempting to create a proxy user for the user id {user_id}.")

    try:
        user_id = int(user_id)
    except ValueError:
        logger.debug(
            f"Failed to create proxy user {user_id}: could not convert to int."
        )
        raise BadArgument(
            f"User ID `{user_id}` is invalid - could not convert to an integer."
        )

    user = discord.Object(user_id)
    user.mention = user.id
    user.display_name = f"<@{user.id}>"
    user.avatar_url_as = lambda static_format: None
    user.bot = False

    return user


class DurationToSeconds(Converter):
    async def convert(self, ctx, argument: str) -> int:
        delta = parse_duration_string(argument)
        if delta is None:
            raise BadArgument("that's not a duration")
        return int((datetime.utcnow() + delta - datetime.utcnow()).total_seconds())


class DurationDelta(Converter):
    """Convert duration strings into dateutil.relativedelta.relativedelta objects."""

    async def convert(self, ctx: Context, duration: str) -> relativedelta:
        """
        Converts a `duration` string to a relativedelta object.
        The converter supports the following symbols for each unit of time:
        - years: `Y`, `y`, `year`, `years`
        - months: `m`, `month`, `months`
        - weeks: `w`, `W`, `week`, `weeks`
        - days: `d`, `D`, `day`, `days`
        - hours: `H`, `h`, `hour`, `hours`
        - minutes: `M`, `minute`, `minutes`
        - seconds: `S`, `s`, `second`, `seconds`
        The units need to be provided in descending order of magnitude.
        """
        if not (delta := parse_duration_string(duration)):
            raise BadArgument(f"`{duration}` is not a valid duration string.")

        return delta


class Duration(DurationDelta):
    """Convert duration strings into UTC datetime.datetime objects."""

    async def convert(self, ctx: Context, duration: str) -> datetime:
        """
        Converts a `duration` string to a datetime object that's `duration` in the future.
        The converter supports the same symbols for each unit of time as its parent class.
        """
        delta = await super().convert(ctx, duration)
        now = datetime.utcnow()

        try:
            return now + delta
        except (ValueError, OverflowError):
            raise BadArgument(f"`{duration}` results in a datetime outside the supported range.")


class ISODateTime(Converter):
    """Converts an ISO-8601 datetime string into a datetime.datetime."""

    async def convert(self, ctx: Context, datetime_string: str) -> datetime:
        """
        Converts a ISO-8601 `datetime_string` into a `datetime.datetime` object.
        The converter is flexible in the formats it accepts, as it uses the `isoparse` method of
        `dateutil.parser`. In general, it accepts datetime strings that start with a date,
        optionally followed by a time. Specifying a timezone offset in the datetime string is
        supported, but the `datetime` object will be converted to UTC and will be returned without
        `tzinfo` as a timezone-unaware `datetime` object.
        See: https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.isoparse
        Formats that are guaranteed to be valid by our tests are:
        - `YYYY-mm-ddTHH:MM:SSZ` | `YYYY-mm-dd HH:MM:SSZ`
        - `YYYY-mm-ddTHH:MM:SS±HH:MM` | `YYYY-mm-dd HH:MM:SS±HH:MM`
        - `YYYY-mm-ddTHH:MM:SS±HHMM` | `YYYY-mm-dd HH:MM:SS±HHMM`
        - `YYYY-mm-ddTHH:MM:SS±HH` | `YYYY-mm-dd HH:MM:SS±HH`
        - `YYYY-mm-ddTHH:MM:SS` | `YYYY-mm-dd HH:MM:SS`
        - `YYYY-mm-ddTHH:MM` | `YYYY-mm-dd HH:MM`
        - `YYYY-mm-dd`
        - `YYYY-mm`
        - `YYYY`
        Note: ISO-8601 specifies a `T` as the separator between the date and the time part of the
        datetime string. The converter accepts both a `T` and a single space character.
        """
        try:
            dt = dateutil.parser.isoparse(datetime_string)
        except ValueError:
            raise BadArgument(f"`{datetime_string}` is not a valid ISO-8601 datetime string")

        if dt.tzinfo:
            dt = dt.astimezone(dateutil.tz.UTC)
            dt = dt.replace(tzinfo=None)

        return dt


class Extension(Converter):
    """
    Fully qualify the name of an extension and ensure it exists.
    The * and ** values bypass this when used with the reload command.
    """

    async def convert(self, ctx: Context, argument: str) -> str:
        """Fully qualify the name of an extension and ensure it exists."""
        # Special values to reload all extensions
        if argument == "*" or argument == "**":
            return argument

        argument = argument.lower()

        if argument in EXTENSIONS:
            return argument
        elif (qualified_arg := f"{exts.__name__}.{argument}") in EXTENSIONS:
            return qualified_arg

        matches = []
        for ext in EXTENSIONS:
            if argument == unqualify(ext):
                matches.append(ext)

        if len(matches) > 1:
            matches.sort()
            names = "\n".join(matches)
            raise BadArgument(
                f":x: `{argument}` is an ambiguous extension name. "
                f"Please use one of the following fully-qualified names.```\n{names}```"
            )
        elif matches:
            return matches[0]
        else:
            raise BadArgument(f":x: Could not find the extension `{argument}`.")


FetchedMember = t.Union[discord.Member, FetchedUser]
MemberOrUser = t.Union[discord.Member, discord.User]
Expiry = t.Union[Duration, ISODateTime]
