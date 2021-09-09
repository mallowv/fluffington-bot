import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Roles

UNLOAD_BLACKLIST = (
    "bot.exts.moderation.defcon",
    "bot.exts.moderation.infraction.infractions",
)


class Extensions(commands.Cog):
    """tools to manage extensions"""
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group(aliases=("cogs", "ext"))
    async def extensions(self, ctx: commands.Context):
        """tools to manage extensions"""
        if not ctx.subcommand_passed:
            await ctx.send_help(ctx.command)

    @extensions.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def list(self, ctx: commands.Context):
        """list all loaded extensions"""
        exts = []
        for ext in self.bot.extensions:
            exts.append(ext)
        exts = "\n".join(exts)
        await ctx.send(f"```{exts}```")

    @extensions.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def list_cogs(self, ctx: commands.Context):
        """list all loaded cogs"""
        cogs = []
        for cog in self.bot.cogs:
            cogs.append(cog)
        cogs = "\n".join(cogs)
        await ctx.send(f"```{cogs}```")

    @extensions.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def load(self, ctx: commands.Context, *exts):
        """load extensions"""
        exts_list = []
        for ext in exts:
            self.bot.load_extension(ext)
            exts_list.append(ext)

        exts_list = "\n".join(exts_list)
        await ctx.send(f"```loaded:\n{exts_list}```")

    @extensions.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def unload(self, ctx: commands.Context, *exts):
        """unload extensions"""
        exts_list = []
        unload = True
        for ext in exts:
            if ext in UNLOAD_BLACKLIST:
                await ctx.send("that cog is in the unload blacklist!")
                unload = False
                continue
            self.bot.unload_extension(ext)
            exts_list.append(ext)

        exts_list = "\n".join(exts_list)
        if unload or len(exts) > 1:
            await ctx.send(f"```unloaded:\n{exts_list}```")

    @extensions.command()
    @commands.has_any_role(*Roles.moderation_roles)
    async def reload(self, ctx: commands.Context, *exts):
        """reload extensions"""
        exts_list = []
        for ext in exts:
            self.bot.reload_extension(ext)
            exts_list.append(ext)

        exts_list = "\n".join(exts_list)
        await ctx.send(f"```reloaded:\n{exts_list}```")


def setup(bot: Bot):
    """load the Extensions cog"""
    bot.add_cog(Extensions(bot))
