import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Roles


class DefCon(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ...

    @commands.group(name="defcon", aliases=("dc",))
    async def defcon_group(self, ctx: commands.Context):
        if not ctx.subcommand_passed:
            await ctx.send_help(ctx.command)

    @defcon_group.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def shutdown(self, ctx: commands.Context):
        """Shut down the server by setting send permissions of everyone to False."""
        role = ctx.guild.default_role
        permissions = role.permissions

        permissions.update(send_messages=False, add_reactions=False, connect=False)
        await role.edit(reason="DEFCON shutdown", permissions=permissions)
        await ctx.send(":white_check_mark::lock:  server locked down")

    @defcon_group.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def unshutdown(self, ctx: commands.Context) -> None:
        """Open up the server again by setting send permissions of everyone to None."""
        role = ctx.guild.default_role
        permissions = role.permissions

        permissions.update(send_messages=True, add_reactions=True, connect=True)
        await role.edit(reason="DEFCON unshutdown", permissions=permissions)
        await ctx.send(":white_check_mark::unlock: server reopened")


def setup(bot: Bot):
    """load the DefCon cog"""
    bot.add_cog(DefCon(bot))
