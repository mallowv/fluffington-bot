from typing import Optional

from discord.ext import commands
from discord.ext.commands.bot import Bot
from discord.ext.commands.converter import TextChannelConverter
from discord import Embed, TextChannel

import bot.constants as constants

class EchoCommands(commands.Cog):
    """
    Apply and pardon infractions on users for moderation purposes.
    """
    
    def __init__(self, bot: commands.bot) -> None:
        super().__init__()
        self.bot = bot
        
    @commands.command(name='echo', aliases=('print',))
    @commands.has_any_role(*constants.Roles.moderation_roles)
    async def echo_command(self, ctx: commands.Context, channel: Optional[TextChannelConverter], *, text: str) -> None:
        """Repeat the given message in either a specified channel or the current channel."""
        if channel is None:
            await ctx.send(text)
        elif not channel.permissions_for(ctx.author).send_messages:
            await ctx.send("You don't have permission to speak in that channel.")
        else:
            await channel.send(text)

    @commands.command(name='embed')
    @commands.has_any_role(*constants.Roles.moderation_roles)
    async def embed_command(self, ctx: commands.Context, channel: Optional[TextChannel], *, text: str) -> None:
        """Send the input within an embed to either a specified channel or the current channel."""
        embed = Embed(description=text)

        if channel is None:
            await ctx.send(embed=embed)
        else:
            await channel.send(embed=embed)
