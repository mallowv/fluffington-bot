import logging

from gino import Gino

from bot.constants import Database as DatabaseConfig

db = Gino()
log = logging.getLogger(__name__)


def build_db_uri() -> str:
    """Use information from the config file to build a PostgreSQL URI."""

    return (
        f"postgresql://{DatabaseConfig.username}:{DatabaseConfig.password}"
        f"@{DatabaseConfig.host}:{DatabaseConfig.port}/{DatabaseConfig.database}"
    )


async def connect() -> None:
    """Initiate a connection to the database."""
    log.info("Initiating connection to the database")
    await db.set_bind(build_db_uri())
    log.info("Database connection established")
