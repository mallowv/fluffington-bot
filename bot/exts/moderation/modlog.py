from datetime import datetime
import typing
import difflib
import itertools

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Colours, Icons, Event
from bot.database.models import Guild


class ModLog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self._ignored = {event: [] for event in Event}

    def ignore(self, event: Event, *items: int) -> None:
        """Add event to ignored events to suppress log emission."""
        for item in items:
            if item not in self._ignored[event]:
                self._ignored[event].append(item)

    async def send_log_message(
        self,
        icon_url: typing.Optional[str],
        colour: typing.Union[discord.Colour, int],
        title: typing.Optional[str],
        text: str,
        channel_id: typing.Optional[int] = None,
        guild_id: typing.Optional[int] = None,
        thumbnail: typing.Optional[typing.Union[str, discord.Asset]] = None,
        ping_everyone: bool = False,
        files: typing.Optional[typing.List[discord.File]] = None,
        content: typing.Optional[str] = None,
        additional_embeds: typing.Optional[typing.List[discord.Embed]] = None,
        timestamp_override: typing.Optional[datetime] = None,
        footer: typing.Optional[str] = None,
    ) -> typing.Optional[commands.Context]:
        """Generate log embed and send to logging channel."""
        # Truncate string directly here to avoid removing newlines

        if not channel_id:
            guilds = await Guild.query.gino.all()
            server_log_channels = {guild.id: guild.server_log_channel for guild in guilds}
            server_logs_channel: int = int(server_log_channels.get(str(guild_id), 0))
            if server_logs_channel <= 0:
                return
            channel_id = server_logs_channel

        embed = discord.Embed(
            description=text[:4093] + "..." if len(text) > 4096 else text
        )

        if title and icon_url:
            embed.set_author(name=title, icon_url=icon_url)

        embed.colour = colour
        embed.timestamp = timestamp_override or datetime.utcnow()

        if footer:
            embed.set_footer(text=footer)

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        if ping_everyone:
            if content:
                content = f"everyone ping attempt detected\n{content}"
            else:
                content = f"everyone ping attempt detected"

        # Truncate content to 2000 characters and append an ellipsis.
        if content and len(content) > 2000:
            content = content[: 2000 - 3] + "..."

        channel = self.bot.get_channel(channel_id)
        log_message = await channel.send(content=content, embed=embed, files=files)

        if additional_embeds:
            for additional_embed in additional_embeds:
                await channel.send(embed=additional_embed)

        return await self.bot.get_context(
            log_message
        )  # Optionally return for use with antispam

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        channel = message.channel
        author = message.author

        if not message.guild:
            return

        if message.author.bot:
            return

        if message.id in self._ignored[Event.message_delete]:
            self._ignored[Event.message_delete].remove(message.id)
            return

        log = message.content
        footer = f"Author id: {message.author.id} | Message id: {message.id}"
        log_msg = f"""
            **Message deleted by {author.mention} in <#{channel.id}>**
            {log}
            """

        await self.send_log_message(
            Icons.message_delete,
            Colours.soft_red,
            message.author.name,
            log_msg,
            guild_id=message.guild.id,
            thumbnail=message.author.avatar,
            footer=footer,
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self, msg_before: discord.Message, msg_after: discord.Message
    ):
        if (
            not msg_before.guild
            or msg_before.author.bot
        ):
            return

        channel = msg_before.channel
        channel_name = (
            f"{channel.category}/<#{channel.id}>"
            if channel.category
            else f"#{channel.name}"
        )

        cleaned_contents = (
            discord.utils.escape_markdown(str(msg.clean_content)).split()
            for msg in (msg_before, msg_after)
        )
        # Getting the difference per words and group them by type - add, remove, same
        # Note that this is intended grouping without sorting
        diff = difflib.ndiff(*cleaned_contents)
        diff_groups = tuple(
            (diff_type, tuple(s[2:] for s in diff_words))
            for diff_type, diff_words in itertools.groupby(diff, key=lambda s: s[0])
        )

        content_before: t.List[str] = []
        content_after: t.List[str] = []

        for index, (diff_type, words) in enumerate(diff_groups):
            sub = ' '.join(words)
            if diff_type == '-':
                content_before.append(f"[{sub}](http://o.hi)")
            elif diff_type == '+':
                content_after.append(f"[{sub}](http://o.hi)")
            elif diff_type == ' ':
                if len(words) > 2:
                    sub = (
                        f"{words[0] if index > 0 else ''}"
                        " ... "
                        f"{words[-1] if index < len(diff_groups) - 1 else ''}"
                    )
                content_before.append(sub)
                content_after.append(sub)

        # print(" ".join(content_before))
        # print(" ".join(content_after))

        log = (
            f"**before**: {' '.join(content_before)}\n"
            f"**after**: {' '.join(content_after)}\n"
            "\n"
            f"[jump url]({msg_after.jump_url})\n"
        )
        footer = f"Author id: {msg_after.author.id} | Message id: {msg_after.id}"
        log_msg = f"""
              **Message edited by {msg_after.author.mention} in {channel_name}**
              {log}
              """

        await self.send_log_message(
            Icons.message_edit,
            Colours.orange,
            msg_after.author.name,
            log_msg,
            guild_id=msg_before.guild.id,
            thumbnail=msg_after.author.avatar,
            footer=footer,
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        """Log role create event to mod log."""

        await self.send_log_message(
            Icons.crown_green, Colours.soft_green,
            "Role created", f"`{role.id}`",
            guild_id=role.guild.id,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        """Log role delete event to mod log."""

        # to prevent a 403 error when removed from guild
        if role.name == self.bot.user.name:
            return

        await self.send_log_message(
            Icons.crown_red, Colours.soft_red,
            "Role removed", f"{role.name} (`{role.id}`)",
            guild_id=role.guild.id,
        )


def setup(bot: Bot):
    """load the ModLog cog"""
    bot.add_cog(ModLog(bot))
