import logging

import coloredlogs

from bot.bot import bot
import bot.constants as constants
from bot.utils.bot_prefix import BotPrefixHandler
from bot.utils.extensions import walk_extensions

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)
logging.basicConfig(
    filename="bot/logs/app.log",
    filemode="w",
    format="%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s",
)

for ext in walk_extensions():
    bot.load_extension(ext)

bot.run(constants.Client.token)
