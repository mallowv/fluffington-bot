import random
from typing import Optional
import re

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Colours, Cats


class Catify(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command(name="catify")
    async def catify(self, ctx: commands.context, *, text: Optional[str]):
        if not text:
            display_name = ctx.author.display_name

            if len(display_name) > 26:
                embed = discord.Embed(
                    title=random.choice(NEGATIVE_REPLIES),
                    description=(
                        "Your display name is too long to be catified! "
                        "Please change it to be under 26 characters."
                    ),
                    color=Colours.soft_red,
                )
                await ctx.send(embed=embed)
                return

            display_name += f" | {random.choice(Cats.cats)}"

            await ctx.send(f"Your catified nickname is: `{display_name}`")

            await ctx.author.edit(nick=display_name)
            return

        text = re.sub(
            r"cat|kitten",
            random.choice(Cats.cats),
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        await ctx.send(f"Your catified text is: `{text}`")


def setup(bot: Bot):
    """load the Catify cog"""
    bot.add_cog(Catify(bot))
