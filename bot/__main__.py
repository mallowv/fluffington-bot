from bot.bot import Bot
from bot.log import setup_sentry
import bot.constants as constants
from bot.utils.extensions import walk_extensions

setup_sentry()

bot = Bot.create()

for ext in walk_extensions():
    bot.load_extension(ext)

bot.run(constants.Bot.token)
