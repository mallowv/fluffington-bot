import logging

import coloredlogs
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from bot.bot import bot
import bot.constants as constants
from bot.utils.extensions import walk_extensions

sentry_logging = LoggingIntegration(
    level=logging.DEBUG,
    event_level=logging.WARNING
)

sentry_sdk.init(
    dsn=constants.Client.sentry_dsn,
    integrations=[
        sentry_logging
    ]
)

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
