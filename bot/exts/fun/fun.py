import random
import typing

import discord
from discord.ext import commands

from bot.bot import Bot

VERBS = ("Pet", "Eat", "Get", "See", "Go to", "Talk to", "Touch")
NOUNS = ("your Cat", "some Food", "your Toys", "the Stars", "Sleep", "Someone", "Grass")


class Fun(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command(aliases=("wsid", "what"))
    async def what_should_i_do(
        self, ctx: commands.Context, *, seed: typing.Optional[str] = ""
    ):
        seed = seed.replace(" ", "")
        verb = random.choice(VERBS)
        noun = random.choice(NOUNS)
        if seed:
            rng = random.Random(seed)
            verb = rng.choice(VERBS)
            noun = rng.choice(NOUNS)

        msg = f"You should {verb} {noun}."
        await ctx.reply(msg)


def setup(bot: Bot):
    """load the Fun cog"""
    bot.add_cog(Fun(bot))
