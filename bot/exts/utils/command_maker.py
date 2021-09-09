import asyncio
import typing

import discord
from discord.ext import commands

from bot.bot import Bot


class CommandMaker(commands.Cog):
    """tools to create commands"""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group(aliases=("cmdmaker",))
    async def commands_maker(self, ctx: commands.Context):
        """tools to create commands"""
        if not ctx.subcommand_passed:
            await ctx.send_help(ctx.command)

    @commands_maker.command()
    async def make(
        self,
        ctx: commands.Context,
        name: str,
        *,
        code: typing.Optional[str],
        lifetime: typing.Optional[int] = 60
    ):
        """make a temporary command"""
        if not code:
            code = await ctx.message.attachments[0].read()
            code = code.decode("utf8")
        code = code.replace("```py", "").replace("```", "")
        exec(code, globals(), locals())
        self.bot.add_command(locals()[name])
        await ctx.send("command added!")

        await asyncio.sleep(lifetime)
        self.bot.remove_command(name)


def setup(bot: Bot):
    """load the CommandMaker cog"""
    bot.add_cog(CommandMaker(bot))
