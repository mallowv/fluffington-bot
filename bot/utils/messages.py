import typing
import random
import logging

import discord
from bot.utils.converters import MemberOrUser
from discord.ext import commands

from bot.constants import NEGATIVE_REPLIES


log = logging.getLogger(__name__)


def reaction_check(
    reaction: discord.Reaction,
    user: discord.User,
    *,
    message_id: int,
    allowed_emoji: typing.Sequence[str],
    allowed_users: typing.Sequence[int],
) -> bool:
    """
    Check if a reaction's emoji and author are allowed and the message is `message_id`.
    If the user is not allowed, remove the reaction. Ignore reactions made by the bot.
    If `allow_mods` is True, allow users with moderator roles even if they're not in `allowed_users`.
    """
    right_reaction = (
        not user.bot
        and reaction.message.id == message_id
        and str(reaction.emoji) in allowed_emoji
    )
    if not right_reaction:
        return False

    if user.id in allowed_users:
        log.trace(f"Allowed reaction {reaction} by {user} on {reaction.message.id}.")
        return True
    else:
        log.trace(f"Removing reaction {reaction} by {user} on {reaction.message.id}: disallowed user.")
        scheduling.create_task(
            reaction.message.remove_reaction(reaction.emoji, user),
            suppressed_exceptions=(discord.HTTPException,),
            name=f"remove_reaction-{reaction}-{reaction.message.id}-{user}"
        )
        return False


def format_user(user: MemberOrUser) -> str:
    """Return a string for `user` which has their mention and ID."""
    return f"{user.mention} (`{user.id}`)"


async def send_denial(ctx: commands.Context, reason: str) -> discord.Message:
    embed = discord.Embed()
    embed.colour = discord.Colour.red()
    embed.title = random.choice(NEGATIVE_REPLIES)
    embed.description = reason

    return await ctx.send(embed=embed)
