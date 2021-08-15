import logging

import coloredlogs

from bot.bot import Bot

logger = logging.getLogger(__name__)
coloredlogs.install(level="DEBUG", logger=logger)


def setup(bot: Bot):
    logger.warning("Not yet implemented")
