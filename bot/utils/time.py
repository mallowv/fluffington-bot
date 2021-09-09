import datetime
from typing import Union
from enum import Enum

from dateutil.relativedelta import relativedelta

ValidTimestamp = Union[
    int, datetime.datetime, datetime.date, datetime.timedelta, relativedelta
]


class TimestampFormats(Enum):
    """
    Represents the different formats possible for Discord timestamps.
    Examples are given in epoch time.
    """

    DATE_TIME = "f"  # January 1, 1970 1:00 AM
    DAY_TIME = "F"  # Thursday, January 1, 1970 1:00 AM
    DATE_SHORT = "d"  # 01/01/1970
    DATE = "D"  # January 1, 1970
    TIME = "t"  # 1:00 AM
    TIME_SECONDS = "T"  # 1:00:00 AM
    RELATIVE = "R"  # 52 years ago


def discord_timestamp(
    timestamp: ValidTimestamp,
    time_format: TimestampFormats = TimestampFormats.DATE_TIME,
) -> str:
    """Create and format a Discord flavored markdown timestamp."""
    if time_format not in TimestampFormats:
        raise ValueError(
            f"Format can only be one of {', '.join(TimestampFormats.args)}, not {time_format}."
        )

    # Convert each possible timestamp class to an integer.
    if isinstance(timestamp, datetime.datetime):
        timestamp = (
            timestamp.replace(tzinfo=None) - datetime.datetime.utcfromtimestamp(0)
        ).total_seconds()
    elif isinstance(timestamp, datetime.date):
        timestamp = (timestamp - datetime.date.fromtimestamp(0)).total_seconds()
    elif isinstance(timestamp, datetime.timedelta):
        timestamp = timestamp.total_seconds()
    elif isinstance(timestamp, relativedelta):
        timestamp = timestamp.seconds

    return f"<t:{int(timestamp)}:{time_format.value}>"
