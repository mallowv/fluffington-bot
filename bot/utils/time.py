import datetime
from typing import Union, Optional
from enum import Enum
import re

from dateutil.relativedelta import relativedelta

ValidTimestamp = Union[
    int, datetime.datetime, datetime.date, datetime.timedelta, relativedelta
]

_DURATION_REGEX = re.compile(
    r"((?P<years>\d+?) ?(years|year|Y|y) ?)?"
    r"((?P<months>\d+?) ?(months|month|m) ?)?"
    r"((?P<weeks>\d+?) ?(weeks|week|W|w) ?)?"
    r"((?P<days>\d+?) ?(days|day|D|d) ?)?"
    r"((?P<hours>\d+?) ?(hours|hour|H|h) ?)?"
    r"((?P<minutes>\d+?) ?(minutes|minute|M) ?)?"
    r"((?P<seconds>\d+?) ?(seconds|second|S|s))?"
)


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


def parse_duration_string(duration: str) -> Optional[relativedelta]:
    """
    Converts a `duration` string to a relativedelta object.
    The function supports the following symbols for each unit of time:
    - years: `Y`, `y`, `year`, `years`
    - months: `m`, `month`, `months`
    - weeks: `w`, `W`, `week`, `weeks`
    - days: `d`, `D`, `day`, `days`
    - hours: `H`, `h`, `hour`, `hours`
    - minutes: `M`, `minute`, `minutes`
    - seconds: `S`, `s`, `second`, `seconds`
    The units need to be provided in descending order of magnitude.
    If the string does represent a durationdelta object, it will return None.
    """
    match = _DURATION_REGEX.fullmatch(duration)
    if not match:
        return None

    duration_dict = {
        unit: int(amount) for unit, amount in match.groupdict(default=0).items()
    }
    delta = relativedelta(**duration_dict)

    return delta


def _stringify_time_unit(value: int, unit: str) -> str:
    """
    Returns a string to represent a value and time unit, ensuring that it uses the right plural form of the unit.
    >>> _stringify_time_unit(1, "seconds")
    "1 second"
    >>> _stringify_time_unit(24, "hours")
    "24 hours"
    >>> _stringify_time_unit(0, "minutes")
    "less than a minute"
    """
    if unit == "seconds" and value == 0:
        return "0 seconds"
    elif value == 1:
        return f"{value} {unit[:-1]}"
    elif value == 0:
        return f"less than a {unit[:-1]}"
    else:
        return f"{value} {unit}"


def humanize_delta(delta: relativedelta, precision: str = "seconds", max_units: int = 6) -> str:
    """
    Returns a human-readable version of the relativedelta.
    precision specifies the smallest unit of time to include (e.g. "seconds", "minutes").
    max_units specifies the maximum number of units of time to include (e.g. 1 may include days but not hours).
    """
    if max_units <= 0:
        raise ValueError("max_units must be positive")

    units = (
        ("years", delta.years),
        ("months", delta.months),
        ("days", delta.days),
        ("hours", delta.hours),
        ("minutes", delta.minutes),
        ("seconds", delta.seconds),
    )

    # Add the time units that are >0, but stop at accuracy or max_units.
    time_strings = []
    unit_count = 0
    for unit, value in units:
        if value:
            time_strings.append(_stringify_time_unit(value, unit))
            unit_count += 1

        if unit == precision or unit_count >= max_units:
            break

    # Add the 'and' between the last two units, if necessary
    if len(time_strings) > 1:
        time_strings[-1] = f"{time_strings[-2]} and {time_strings[-1]}"
        del time_strings[-2]

    # If nothing has been found, just make the value 0 precision, e.g. `0 days`.
    if not time_strings:
        humanized = _stringify_time_unit(0, precision)
    else:
        humanized = ", ".join(time_strings)

    return humanized


def format_infraction(timestamp: datetime.datetime) -> str:
    """Format an infraction timestamp to a discord timestamp."""
    return discord_timestamp(timestamp)


def format_infraction_with_duration(
    date_to: Optional[datetime.datetime],
    date_from: Optional[datetime.datetime] = None,
    max_units: int = 2,
    absolute: bool = True
) -> Optional[str]:
    """
    Return `date_to` formatted as a discord timestamp with the timestamp duration since `date_from`.
    `max_units` specifies the maximum number of units of time to include in the duration. For
    example, a value of 1 may include days but not hours.
    If `absolute` is True, the absolute value of the duration delta is used. This prevents negative
    values in the case that `date_to` is in the past relative to `date_from`.
    """
    if not date_to:
        return None

    date_to_formatted = format_infraction(date_to)

    date_from = date_from or datetime.datetime.utcnow()
    date_to = date_to

    delta = relativedelta(date_to, date_from)
    if absolute:
        delta = abs(delta)

    duration = humanize_delta(delta, max_units=max_units)
    duration_formatted = f" ({duration})" if duration else ""

    return f"{date_to_formatted}{duration_formatted}"


def until_expiration(
    expiry: datetime
) -> Optional[str]:
    """
    Get the remaining time until infraction's expiration, in a discord timestamp.
    Returns a human-readable version of the remaining duration between datetime.utcnow() and an expiry.
    Similar to time_since, except that this function doesn't error on a null input
    and return null if the expiry is in the paste
    """
    if not expiry:
        return None

    now = datetime.datetime.utcnow()
    since = expiry

    if since < now:
        return None

    return discord_timestamp(since, TimestampFormats.RELATIVE)

