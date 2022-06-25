import logging
import typing as t
from datetime import datetime

import discord
from discord.ext import commands

from bot.constants import Colours, Icons
from bot.database.models import Infraction

# apply icon, pardon icon
INFRACTION_ICONS = {
    "ban": (Icons.user_ban, Icons.user_unban),
    "kick": (Icons.sign_out, None),
    "mute": (Icons.user_mute, Icons.user_unmute),
    "note": (Icons.user_warn, None),
    "superstar": (Icons.superstarify, Icons.unsuperstarify),
    "warning": (Icons.user_warn, None),
    "voice_ban": (Icons.voice_state_red, Icons.voice_state_green),
}

INFRACTION_DESCRIPTION_TEMPLATE = (
    "**Type:** {type}\n"
    "**Expires:** {expires}\n"
    "**Reason:** {reason}\n"
)

logger = logging.getLogger(__name__)


async def post_infraction(
        ctx: commands.Context,
        user: discord.Member,
        infr_type: str,
        reason: str,
        expires_at: datetime = None,
        hidden: bool = False,
        active: bool = True
) -> Infraction:
    logger.trace(f"Posting {infr_type} infraction for {user} to the database.")

    infraction = await Infraction.create(
        actor=str(ctx.author.id),
        hidden=hidden,
        reason=reason,
        type=infr_type,
        user=str(user.id),
        guild=str(ctx.guild.id),
        active=active,
        permanent=False if expires_at else True,
        inserted_at=datetime.utcnow(),
        expiry=expires_at
    )

    return infraction


async def get_active_infraction(
        ctx: commands.Context,
        user: discord.Member,
        infr_type: str,
        send_msg: bool = True
) -> Infraction:
    """
    Retrieves an active infraction of the given type for the user.
    If `send_msg` is True and the user has an active infraction matching the `infr_type` parameter,
    then a message for the moderator will be sent to the Context channel letting them know.
    Otherwise, no message will be sent.
    """
    logger.trace(f"Checking if {user} has active infractions of type {infr_type}.")

    active_infractions = [
        infraction for infraction in await Infraction.query.where(
            Infraction.type == infr_type
        ).where(
            Infraction.user == str(user.id)
        ).where(
            Infraction.guild == str(user.guild.id)
        ).gino.all() if infraction.active
    ]

    if active_infractions:
        # Checks to see if the moderator should be told there is an active infraction
        if send_msg:
            logger.trace(f"{user} has active infractions of type {infr_type}.")
            await send_active_infraction_message(ctx, active_infractions[0])
        return active_infractions[0]
    else:
        logger.trace(f"{user} does not have active infractions of type {infr_type}.")


async def send_active_infraction_message(ctx: commands.Context, infraction: Infraction) -> None:
    """Send a message stating that the given infraction is active."""
    await ctx.send(
        f":x: According to my records, this user already has a {infraction.type} infraction. "
        f"See infraction **#{infraction.id}**."
    )


async def notify_infraction(
        user: discord.Member,
        infr_type: str,
        expires_at: t.Optional[str] = None,
        reason: t.Optional[str] = None,
        icon_url: str = Icons.token_removed
) -> bool:
    """DM a user about their new infraction and return True if the DM is successful."""
    logger.trace(f"Sending {user} a DM about their {infr_type} infraction.")

    text = INFRACTION_DESCRIPTION_TEMPLATE.format(
        type=infr_type.title(),
        expires=expires_at or "N/A",
        reason=reason or "No reason provided."
    )

    # For case when other fields than reason is too long and this reach limit, then force-shorten string
    if len(text) > 4096:
        text = f"{text[:4093]}..."

    embed = discord.Embed(
        description=text,
        colour=Colours.soft_red
    )

    embed.set_author(name="Infraction information", icon_url=icon_url)
    embed.title = "You did a bad thing"

    return await send_private_embed(user, embed)


async def notify_pardon(
        user: discord.Member,
        title: str,
        content: str,
        icon_url: str = Icons.user_verified
) -> bool:
    """DM a user about their pardoned infraction and return True if the DM is successful."""
    logger.trace(f"Sending {user} a DM about their pardoned infraction.")

    embed = discord.Embed(
        description=content,
        colour=Colours.soft_green
    )

    embed.set_author(name=title, icon_url=icon_url)

    return await send_private_embed(user, embed)


async def send_private_embed(user: discord.Member, embed: discord.Embed) -> bool:
    """
    A helper method for sending an embed to a user's DMs.
    Returns a boolean indicator of DM success.
    """
    try:
        await user.send(user.mention, embed=embed)
        return True
    except (discord.HTTPException, discord.Forbidden, discord.NotFound):
        logger.debug(
            f"Infraction-related information could not be sent to user {user} ({user.id}). "
            "The user either could not be retrieved or probably disabled their DMs."
        )
        return False
