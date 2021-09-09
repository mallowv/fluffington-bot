import discord
from discord.ext import commands

from bot.bot import Bot
import bot.constants as constants


class Announcements(commands.Cog):
    """
    commands to subscribe and unsubscribe from the announcement notifications
    """

    name = constants.Bot.name

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    @commands.command(name="subscribe")
    async def subscribe_command(
        self, ctx: commands.Context, *_
    ) -> None:  # We don't actually care about the args
        """
        Subscribe to announcement notifications by assigning yourself the role.
        """
        has_role = False

        for role in ctx.author.roles:
            if role.id == constants.Roles.announcements:
                has_role = True
                break

        if has_role:
            await ctx.send(f"{ctx.author.mention} You're already subscribed!")
            return

        print(
            f"{ctx.author} called {constants.Bot.prefix}subscribe. Assigning the 'Announcements' role."
        )
        await ctx.author.add_roles(
            discord.Object(constants.Roles.announcements),
            reason="Subscribed to announcements",
        )

        await ctx.send(
            f"{ctx.author.mention} Subscribed to <#{constants.Channels.announcements}> notifications.",
        )

    @commands.command(name="unsubscribe")
    async def unsubscribe_command(
        self, ctx: commands.Context, *_
    ) -> None:  # We don't actually care about the args
        """
        Unsubscribe from announcement notifications by removing the role from yourself.
        """
        has_role = False

        for role in ctx.author.roles:
            if role.id == constants.Roles.announcements:
                has_role = True
                break

        if not has_role:
            await ctx.send(f"{ctx.author.mention} You're already unsubscribed!")
            return

        print(
            f"{ctx.author} called {constants.Bot.prefix}unsubscribe. Removing the 'Announcements' role."
        )
        await ctx.author.remove_roles(
            discord.Object(constants.Roles.announcements),
            reason="Unsubscribed from announcements",
        )

        await ctx.send(
            f"{ctx.author.mention} Unsubscribed from <#{constants.Channels.announcements}> notifications."
        )


def setup(bot: Bot) -> None:
    """load the Announcements cog"""
    bot.add_cog(Announcements(bot))
