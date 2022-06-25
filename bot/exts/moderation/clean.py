import logging
import random
import re
import typing
from typing import Iterable, Optional

import discord
from discord.ext import commands

from bot.bot import Bot
from bot.constants import Colours, CleanMessages, Roles, Icons
from bot.database.models import Guild

log = logging.getLogger(__name__)


class Clean(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.cleaning = False

    @property
    def mod_log(self) -> typing.Optional[commands.Cog]:
        """Get currently loaded ModLog cog instance."""
        return self.bot.get_cog("ModLog")

    async def _clean_messages(
            self,
            amount: int,
            ctx: commands.Context,
            channels: Iterable[discord.TextChannel],
            bots_only: bool = False,
            user: discord.User = None,
            regex: Optional[str] = None,
            until_message: Optional[discord.Message] = None,
    ) -> None:
        """A helper function that does the actual message cleaning."""

        def predicate_bots_only(message: discord.Message) -> bool:
            """Return True if the message was sent by a bot."""
            return message.author.bot

        def predicate_specific_user(message: discord.Message) -> bool:
            """Return True if the message was sent by the user provided in the _clean_messages call."""
            return message.author == user

        def predicate_regex(message: discord.Message) -> bool:
            """Check if the regex provided in _clean_messages matches the message content or any embed attributes."""
            content = [message.content]

            # Add the content for all embed attributes
            for embed in message.embeds:
                content.append(embed.title)
                content.append(embed.description)
                content.append(embed.footer.text)
                content.append(embed.author.name)
                for field in embed.fields:
                    content.append(field.name)
                    content.append(field.value)

            # Get rid of empty attributes and turn it into a string
            content = [attr for attr in content if attr]
            content = "\n".join(content)

            # Now let's see if there's a regex match
            if not content:
                return False
            else:
                return bool(re.search(regex.lower(), content.lower()))

        # Is this an acceptable amount of messages to clean?
        if amount > CleanMessages.message_limit:
            embed = discord.Embed(
                color=discord.Colour(Colours.soft_red),
                title=random.choice(NEGATIVE_REPLIES),
                description=f"You cannot clean more than {CleanMessages.message_limit} messages."
            )
            await ctx.send(embed=embed)
            return

        # Are we already performing a clean?
        if self.cleaning:
            embed = discord.Embed(
                color=discord.Colour(Colours.soft_red),
                title=random.choice(NEGATIVE_REPLIES),
                description="Please wait for the currently ongoing clean operation to complete."
            )
            await ctx.send(embed=embed)
            return

        # Set up the correct predicate
        if bots_only:
            predicate = predicate_bots_only  # Delete messages from bots
        elif user:
            predicate = predicate_specific_user  # Delete messages from specific user
        elif regex:
            predicate = predicate_regex  # Delete messages that match regex
        else:
            predicate = lambda m: True  # Delete all messages

        # Default to using the invoking context's channel
        if not channels:
            channels = [ctx.channel]

        # Delete the invocation first
        # self.mod_log.ignore(Event.message_delete, ctx.message.id)
        try:
            await ctx.message.delete()
        except errors.NotFound:
            # Invocation message has already been deleted
            log.info("Tried to delete invocation message, but it was already deleted.")

        messages = []
        message_ids = []
        guilds = await Guild.query.gino.all()
        server_log_channels = {guild.id: guild.server_log_channel for guild in guilds}
        server_logs_channel: int = int(server_log_channels.get(str(ctx.guild.id)))
        self.cleaning = True

        # Find the IDs of the messages to delete. IDs are needed in order to ignore mod log events.
        for channel in channels:
            async for message in channel.history(limit=amount):

                # If at any point the cancel command is invoked, we should stop.
                if not self.cleaning:
                    return

                # If we are looking for specific message.
                if until_message:

                    # we could use ID's here however in case if the message we are looking for gets deleted,
                    # we won't have a way to figure that out thus checking for datetime should be more reliable
                    if message.created_at < until_message.created_at:
                        # means we have found the message until which we were supposed to be deleting.
                        break

                    # Since we will be using `delete_messages` method of a TextChannel and we need message objects to
                    # use it as well as to send logs we will start appending messages here instead adding them from
                    # purge.
                    messages.append(message)

                # If the message passes predicate, let's save it.
                if predicate is None or predicate(message):
                    message_ids.append(message.id)

        self.cleaning = False

        # Now let's delete the actual messages with purge.
        # self.mod_log.ignore(Event.message_delete, *message_ids)
        for channel in channels:
            if until_message:
                for i in range(0, len(messages), 100):
                    # while purge automatically handles the amount of messages
                    # delete_messages only allows for up to 100 messages at once
                    # thus we need to paginate the amount to always be <= 100
                    await channel.delete_messages(messages[i:i + 100])
            else:
                messages += await channel.purge(limit=amount, check=predicate)

        # Reverse the list to restore chronological order
        if messages:
            messages = reversed(messages)
        else:
            # Can't build an embed, nothing to clean!
            embed = discord.Embed(
                color=discord.Colour(Colours.soft_red),
                description="No matching messages could be found."
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        # Build the embed and send it
        target_channels = ", ".join(channel.mention for channel in channels)
        msglogs = b""
        for message in messages:
            a = f"{message.author.display_name} ({message.author.id}) {message.created_at} -> {message.content}\n"
            msglogs += bytes(a, "utf8")

        b=""

        async with self.bot.http_session.post("https://www.toptal.com/developers/hastebin/documents", data=msglogs) as res:
            b = await res.json()
        #   Temporarily using Hastebin :| TODO: Uh make ur own web thing
        #     msglogs.append(
        #         {
        #             'id': message.id,
        #             'author': message.author.id,
        #             'channel_id': message.channel.id,
        #             'content': message.content.replace("\0", ""),  # Null chars cause 400.
        #             'embeds': [embed.to_dict() for embed in message.embeds],
        #             'attachments': [attachment.url for attachment in message.attachments]
        #         }
        #     )
        #
        # msglogs = json.dumps({"logs": msglogs})
        # msglog = await MessageLog.create(
        #     actor=str(ctx.author.id),
        #     guild=str(ctx.guild.id),
        #     inserted_at=datetime.utcnow(),
        #     messages=msglogs
        # )

        message = (
            f"**{len(message_ids)}** messages deleted in {target_channels} by "
            f"{ctx.author.mention}\n\n"
            f"[Message Log](https://www.toptal.com/developers/hastebin/{b['key']})"
        )

        await self.mod_log.send_log_message(
            icon_url=Icons.message_bulk_delete,
            colour=discord.Colour(Colours.soft_red),
            title="Bulk message delete",
            text=message,
            channel_id=server_logs_channel
        )

    @commands.group(invoke_without_command=True, name="clean", aliases=["clear", "purge"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_group(self, ctx: commands.Context) -> None:
        """Commands for cleaning messages in channels."""
        await ctx.send_help(ctx.command)

    @clean_group.command(name="user", aliases=["users"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_user(
            self,
            ctx: commands.Context,
            user: discord.User,
            amount: Optional[int] = 10,
            channels: commands.Greedy[discord.TextChannel] = None
    ) -> None:
        """Delete messages posted by the provided user, stop cleaning after traversing `amount` messages."""
        await self._clean_messages(amount, ctx, user=user, channels=channels)

    @clean_group.command(name="all", aliases=["everything"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_all(
            self,
            ctx: commands.Context,
            amount: Optional[int] = 10,
            channels: commands.Greedy[discord.TextChannel] = None
    ) -> None:
        """Delete all messages, regardless of poster, stop cleaning after traversing `amount` messages."""
        await self._clean_messages(amount, ctx, channels=channels)

    @clean_group.command(name="bots", aliases=["bot"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_bots(
            self,
            ctx: commands.Context,
            amount: Optional[int] = 10,
            channels: commands.Greedy[discord.TextChannel] = None
    ) -> None:
        """Delete all messages posted by a bot, stop cleaning after traversing `amount` messages."""
        await self._clean_messages(amount, ctx, bots_only=True, channels=channels)

    @clean_group.command(name="regex", aliases=["word", "expression"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_regex(
            self,
            ctx: commands.Context,
            regex: str,
            amount: Optional[int] = 10,
            channels: commands.Greedy[discord.TextChannel] = None
    ) -> None:
        """Delete all messages that match a certain regex, stop cleaning after traversing `amount` messages."""
        await self._clean_messages(amount, ctx, regex=regex, channels=channels)

    @clean_group.command(name="message", aliases=["messages"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_message(self, ctx: commands.Context, message: discord.Message) -> None:
        """Delete all messages until certain message, stop cleaning after hitting the `message`."""
        await self._clean_messages(
            CleanMessages.message_limit,
            ctx,
            channels=[message.channel],
            until_message=message
        )

    @clean_group.command(name="stop", aliases=["cancel", "abort"])
    @commands.has_any_role(*Roles.moderation_roles)
    async def clean_cancel(self, ctx: commands.Context) -> None:
        """If there is an ongoing cleaning process, attempt to immediately cancel it."""
        self.cleaning = False

        embed = Embed(
            color=discord.Colour.blurple(),
            description="Clean interrupted."
        )
        await ctx.send(embed=embed, delete_after=10)


def setup(bot: Bot):
    """load the Clean cog"""
    bot.add_cog(Clean(bot))
