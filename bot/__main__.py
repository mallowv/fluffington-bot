import discord
from discord.ext import commands
import firebase_admin
from firebase_admin import firestore

import bot.constants as constants
from bot.exts.utils.announcements import Announcements
from bot.exts.moderation.infraction.infractions import Infractions
from bot.exts.utils.echo import EchoCommands
from bot.utils.bot_prefix import BotPrefixHandler

firebase_admin.initialize_app(constants.Client.firebase_creds)
db = firestore.client()
config = [doc.to_dict() for doc in db.collection("config").stream() if doc.id == "main"][0]
prefix: any = constants.Client.prefix if config["fixed_and_single_prefix"] else BotPrefixHandler.get_prefix
bot: commands.bot = commands.Bot(command_prefix=prefix)


@bot.event
async def on_ready():
    print("bot is ready")
    dev_log_embed = discord.Embed(title="", description="", color=discord.Colour.green())
    dev_log_embed.add_field(name="bot status", value="online", inline=False)
    await bot.get_channel(constants.Channels.dev_log_channel).send(embed=dev_log_embed)

bot.add_cog(Announcements(bot))
bot.add_cog(EchoCommands(bot))
bot.add_cog(Infractions(bot))

@bot.event
async def on_message(message):
    if message.content.lower() in ("joe what", "joe who", "who is joe"):
        await message.channel.send("oh god please no, don't please don't")

    elif message.content.lower() in ("joe mama",):
        await message.channel.send("why")

    elif message.content.lower() in ("joe are you still alive", "rusty are you still alive"):
        await message.channel.send("uhh, yes")

    await bot.process_commands(message)

bot.run(constants.Client.token)
