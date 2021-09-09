import datetime
import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord.utils import get

from bot.bot import Bot
from bot.constants import Roles
from bot.utils.converters import FetchedMember
from bot.utils.time import discord_timestamp


class Infractions(commands.Cog):
    """
    Apply and pardon infractions on users for moderation purposes.
    """

    def __init__(self, bot: commands.bot) -> None:
        super().__init__()
        self.bot = bot

    @staticmethod
    async def apply_ban(
        ctx, member: FetchedMember, reason: Optional[str] = None, **kwargs
    ):
        """
        Apply a ban infarction to a user
        """
        if member is None or member == ctx.author:
            await ctx.send("You cannot ban yourself")
            return
        if reason is None:
            reason = "For being a jerk!"
        message = f"You have been banned from {ctx.guild.name} for {reason}"
        await member.send(message)
        await ctx.guild.ban(member, reason=reason)
        await ctx.channel.send(f"{member.mention} has been banned for {reason}")

    @commands.has_permissions(ban_members=True)
    @commands.command(name="ban")
    async def ban(
        self, ctx: commands.context, member: FetchedMember = None, *, reason: str = None
    ):
        """
        Ban a user
        """
        await self.apply_ban(ctx, member, reason)

    @commands.has_permissions(ban_members=True)
    @commands.command(name="unban")
    async def unban(self, ctx: commands.context, member: FetchedMember):
        """
        Pardon a user from a ban
        """
        await ctx.guild.unban(member)
        await ctx.send(f"{member.mention} has been unbanned :tada:")

    @commands.has_permissions(kick_members=True)
    @commands.command(name="kick")
    async def kick(
        self, ctx: commands.context, member: FetchedMember, *, reason: str = None
    ):
        """
        Kick a user out
        """
        if member is None or member == ctx.author:
            await ctx.send("You cannot kick yourself")
            return
        if reason is None:
            reason = "For being a jerk!"
        message = f"You have been kicked from {ctx.guild.name} for {reason}"
        await member.send(message)
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} has been kicked for {reason}")

    @commands.command(name="mute")
    @commands.has_any_role(*Roles.moderation_roles)
    async def mute(
        self,
        ctx: commands.context,
        member: FetchedMember,
        duration: Optional[int] = 3600,
        *,
        reason: str,
    ):
        muted = get(member.guild.roles, name="Muted")
        await member.add_roles(muted, reason=reason)
        mute_duration = discord_timestamp(
            datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
        )
        mute_message = f"{mute_duration} ({datetime.timedelta(seconds=duration)})"
        await ctx.send(
            f":incoming_envelope: :ok_hand: applied **mute** to {member.mention} until {mute_message}"
        )
        await member.send(f"you have been muted in {member.guild.name} for {reason}")
        await asyncio.sleep(duration)
        await member.remove_roles(muted)
        await ctx.send(
            f":incoming_envelope: :ok_hand: pardoned infraction **mute** for {member.mention}"
        )


def setup(bot: Bot) -> None:
    """load the Infractions cog"""
    bot.add_cog(Infractions(bot))
