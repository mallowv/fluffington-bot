from typing import Optional

import discord
from discord.ext import commands
from discord.ext.commands.converter import TextChannelConverter
from discord import Embed, TextChannel

from bot.bot import Bot
from bot.constants import Roles


class EchoCommands(commands.Cog):
    """
    Echo...stuff
    """

    def __init__(self, bot: Bot) -> None:
        super().__init__()
        self.bot = bot

    @commands.command(name="echo", aliases=("print",))
    @commands.has_any_role(*Roles.moderation_roles)
    async def echo_command(
        self, ctx: commands.Context, channel: Optional[TextChannelConverter], *, text: str
    ) -> None:
        """Repeat the given message in either a specified channel or the current channel."""
        if channel is None:
            await ctx.send(text)
        elif not channel.permissions_for(ctx.author).send_messages:
            await ctx.send("You don't have permission to speak in that channel.")
        else:
            await channel.send(text)

    @commands.command(name="embed")
    @commands.has_any_role(*Roles.moderation_roles)
    async def embed_command(
        self,
        ctx: commands.Context,
        channel: Optional[TextChannel],
        colour: Optional[discord.Colour] = discord.Colour.blurple(),
        *, text: str
    ) -> None:
        """Send the input within an embed to either a specified channel or the current channel."""
        embed = Embed(description=text, colour=colour)

        if channel is None:
            await ctx.send(embed=embed)
        else:
            await channel.send(embed=embed)


def setup(bot: Bot) -> None:
    """load the EchoCommands cog"""
    bot.add_cog(EchoCommands(bot))
