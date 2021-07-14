import datetime

import discord
from discord.ext import commands

import bot.constants as constants

class Infractions(commands.Cog):
    """
    Apply and pardon infractions on users for moderation purposes.
    """
    
    def __init__(self, bot: commands.bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.has_permissions(ban_members = True)
    @commands.command(name="ban")
    async def ban(self, ctx: commands.context, member: discord.User = None, *, reason: str = None):
        if member is None or member == ctx.author:
            await ctx.send("You cannot ban yourself")
            return
        if reason is None:
            reason = "For being a jerk!"
        message = f"You have been banned from {ctx.guild.name} for {reason}"
        await member.send(message)
        await ctx.guild.ban(member, reason=reason)
        await ctx.channel.send(f"{member.mention} has been banned for {reason}")