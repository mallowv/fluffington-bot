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
    async def what_should_i_do(self, ctx: commands.Context, *, seed: typing.Optional[str] = ""):
        seed = seed.replace(" ", "")
        seed_num = 0
        verb = random.choice(VERBS)
        noun = random.choice(NOUNS)
        if seed:
            for char in seed:
                seed_num += ord(char)

            random.seed(seed_num)
            verb = random.choice(VERBS)
            random.seed(seed_num)
            noun = random.choice(NOUNS)

        msg = f"You should {verb} {noun}."
        await ctx.reply(msg)


def setup(bot: Bot):
    """load the Fun cog"""
    bot.add_cog(Fun(bot))
