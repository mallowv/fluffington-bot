import pathlib
import random

import discord
from discord.ext import commands
import yaml

from bot.bot import Bot

FORM_URL = "https://forms.gle/sb2jNbvVcTorNPTX6"

with pathlib.Path("bot/resources/fun/starters.yaml").open("r", encoding="utf8") as f:
    STARTERS = yaml.load(f, Loader=yaml.FullLoader)


class ConversationStarters(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command(name="topic")
    async def topic(self, ctx: commands.Context):
        random_topic = random.choice(STARTERS)
        topic_embed = discord.Embed(
            description=f"you want to suggest a new topic? [click here]({FORM_URL})"
        )
        topic_embed.title = random_topic
        await ctx.send(embed=topic_embed)


def setup(bot: Bot):
    """load the ConversationStarters cog"""
    bot.add_cog(ConversationStarters(bot))
