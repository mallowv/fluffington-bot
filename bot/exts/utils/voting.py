import asyncio
from typing import Optional

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.utils.converters import DurationToSeconds


class Voting(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.polls = {}

    @staticmethod
    def get_most_voted_option(poll: dict) -> Optional[tuple[dict, str]]:
        del poll["title"]
        highest_vote = 0
        most_voted_option = {}
        most_voted_emoji = ""
        idx = 0
        for emoji, option in poll["options"].items():
            if idx == 0:
                highest_vote = option["count"]
                idx += 1
                continue

            if option["count"] > highest_vote:
                most_voted_emoji = emoji
                most_voted_option = option
                highest_vote = option["count"]

            idx += 1
        if highest_vote != 0:
            return most_voted_option, most_voted_emoji

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if reaction.message.id not in self.polls.keys():
            return

        if user.bot:
            return

        poll = self.polls.get(reaction.message.id)

        if not poll["active"]:
            return

        options = poll["options"][reaction.emoji]["options"]
        title = poll["title"]
        if reaction.emoji in poll["options"].keys():
            poll["options"][reaction.emoji]["count"] += 1
            self.polls[reaction.message.id] = poll

            opts = [
                f"{option} {poll_item['count']}"
                for poll_item, option in zip(poll["options"].values(), options.values())
            ]
            embed = discord.Embed(title=title, description="\n".join(opts))
            await reaction.message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if reaction.message.id not in self.polls.keys():
            return

        if user.bot:
            return

        poll = self.polls.get(reaction.message.id)

        if not poll["active"]:
            return

        options = poll["options"][reaction.emoji]["options"]
        title = poll["title"]
        if reaction.emoji in poll["options"].keys():
            poll["options"][reaction.emoji]["count"] -= 1
            self.polls[reaction.message.id] = poll

            opts = [
                f"{option} {poll_item['count']}"
                for poll_item, option in zip(poll["options"].values(), options.values())
            ]
            embed = discord.Embed(title=title, description="\n".join(opts))
            await reaction.message.edit(embed=embed)

    @commands.command(aliases=("poll", "choose"))
    async def vote(
        self,
        ctx: commands.Context,
        title: str,
        expiry: DurationToSeconds,
        *options: str,
    ):
        poll = {"title": title, "options": {}}
        if len(options) > 20:
            raise commands.BadArgument(
                "the limit is 20 options, not your imagination, unfortunately"
            )
        if expiry > 1000_000:
            raise commands.BadArgument("that's too long")

        codepoint_start = 127462  # represents "regional_indicator_a" unicode value
        options = {
            chr(i): f"{chr(i)} - {v}"
            for i, v in enumerate(options, start=codepoint_start)
        }
        for emoji, option in options.items():
            opt = {"content": option[4:], "options": options, "count": 0}
            poll["options"][emoji] = opt

        opts = [
            f"{option} {poll_item['count']}"
            for poll_item, option in zip(poll["options"].values(), options.values())
        ]
        embed = discord.Embed(title=title, description="\n".join(opts))
        message = await ctx.send(embed=embed)
        for reaction in options:
            await message.add_reaction(reaction)
        poll["active"] = True
        self.polls[message.id] = poll

        await asyncio.sleep(expiry)
        poll["active"] = False
        del self.polls[message.id]

        won = self.get_most_voted_option(poll)
        if won:
            await ctx.send(f":sparkles: {won[1]} {won[0]['content']} :sparkles: won!1!!1!")

        else:
            await ctx.send("bruh, its a tie")
        await message.clear_reactions()


def setup(bot: Bot):
    """load the Voting cog"""
    bot.add_cog(Voting(bot))
