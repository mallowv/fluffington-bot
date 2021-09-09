import re
from os import getenv

import yaml


env_regex = re.compile(r"\${(\w+)}")


def env_var_constructor(loader, node):
    value = loader.construct_scalar(node)
    key = str(value)
    key = env_regex.search(key)
    return getenv(key.group(1))


yaml.SafeLoader.add_constructor("!ENV", env_var_constructor)
yaml.SafeLoader.add_implicit_resolver("!ENV", env_regex, None)

with open("config-default.yaml", "r") as config:
    _CONFIG_YAML = yaml.safe_load(config)


class YAMLGetter(type):
    """
    Implements a custom metaclass used for accessing
    configuration data by simply accessing class attributes.
    Supports getting configuration from up to two levels
    of nested configuration through `section` and `subsection`.
    `section` specifies the YAML configuration section (or "key")
    in which the configuration lives, and must be set.
    `subsection` is an optional attribute specifying the section
    within the section from which configuration should be loaded.
    Example Usage:
        # config.yaml
        bot:
            prefixes:
                direct_message: ''
                guild: '!'
        # config.py
        class Prefixes(metaclass=YAMLGetter):
            section = "bot"
            subsection = "prefixes"
        # Usage in Python code
        from config import Prefixes
        def get_prefix(bot, message):
            if isinstance(message.channel, PrivateChannel):
                return Prefixes.direct_message
            return Prefixes.guild
    """

    subsection = None

    def __getattr__(cls, name):
        name = name.lower()

        try:
            if cls.subsection is not None:
                return _CONFIG_YAML[cls.section][cls.subsection][name]
            return _CONFIG_YAML[cls.section][name]
        except KeyError as e:
            dotted_path = ".".join(
                (cls.section, cls.subsection, name)
                if cls.subsection is not None
                else (cls.section, name)
            )
            # Only an INFO log since this can be caught through `hasattr` or `getattr`.
            log.info(
                f"Tried accessing configuration variable at `{dotted_path}`, but it could not be found."
            )
            raise AttributeError(repr(name)) from e

    def __getitem__(cls, name):
        return cls.__getattr__(name)

    def __iter__(cls):
        """Return generator of key: value pairs of current constants class' config values."""
        for name in cls.__annotations__:
            yield name, getattr(cls, name)


class Bot(metaclass=YAMLGetter):
    section = "bot"

    name: str
    prefix: str
    token: str
    sentry_dsn: str


class Channels(metaclass=YAMLGetter):
    section = "guild"
    subsection = "channels"

    devlog_channel: int


class Roles(metaclass=YAMLGetter):
    section = "guild"
    subsection = "roles"

    moderation_roles: list[str]


class Database(metaclass=YAMLGetter):
    section = "database"

    username: str
    password: str
    host: str
    port: str
    database: str


class Colours:
    blue = 0x0279FD
    bright_green = 0x01D277
    dark_green = 0x1F8B4C
    orange = 0xE67E22
    pink = 0xCF84E0
    purple = 0xB734EB
    soft_green = 0x68C290
    soft_orange = 0xF9CB54
    soft_red = 0xCD6D6D
    yellow = 0xF9F586
    python_blue = 0x4B8BBE
    python_yellow = 0xFFD43B
    grass_green = 0x66FF00
    gold = 0xE6C200


class Cats:
    cats = ["ᓚᘏᗢ", "ᘡᘏᗢ", "🐈", "ᓕᘏᗢ", "ᓇᘏᗢ", "ᓂᘏᗢ", "ᘣᘏᗢ", "ᕦᘏᗢ", "ᕂᘏᗢ"]


NEGATIVE_REPLIES = [
    "Noooooo!!",
    "Nope.",
    "I'm sorry Dave, I'm afraid I can't do that.",
    "I don't think so.",
    "Not gonna happen.",
    "Out of the question.",
    "Huh? No.",
    "Nah.",
    "Naw.",
    "Not likely.",
    "No way, José.",
    "Not in a million years.",
    "Fat chance.",
    "Certainly not.",
    "NEGATORY.",
    "Nuh-uh.",
    "Not in my house!",
]

POSITIVE_REPLIES = [
    "Yep.",
    "Absolutely!",
    "Can do!",
    "Affirmative!",
    "Yeah okay.",
    "Sure.",
    "Sure thing!",
    "You're the boss!",
    "Okay.",
    "No problem.",
    "I got you.",
    "Alright.",
    "You got it!",
    "ROGER THAT",
    "Of course!",
    "Aye aye, cap'n!",
    "I'll allow it.",
]

ERROR_REPLIES = [
    "Please don't do that.",
    "You have to stop.",
    "Do you mind?",
    "In the future, don't do that.",
    "That was a mistake.",
    "You blew it.",
    "You're bad at computers.",
    "Are you trying to kill me?",
    "Noooooo!!",
    "I can't believe you've done this",
]
