from sys import prefix
import typing as t
import logging

import coloredlogs
import discord
from discord.ext.commands import (
    BadArgument,
    Bot,
    Context,
    Converter,
    IDConverter,
    UserConverter,
)

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)


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


FetchedMember = t.Union[discord.Member, FetchedUser]
