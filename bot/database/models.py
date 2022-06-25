import uuid

from .database import db
from bot.constants import Bot


class Guild(db.Model):
    __tablename__ = "guilds"

    id = db.Column(db.String(), primary_key=True)
    server_log_channel = db.Column(db.String(), nullable=True)
    muted_role = db.Column(db.String())
    voiceban_role = db.Column(db.String())
    prefix = db.Column(db.String(), default=Bot.prefix)


class Infraction(db.Model):
    __tablename__ = "infractions"

    id = db.Column(db.String(), primary_key=True, default=lambda: str(uuid.uuid4().hex))
    actor = db.Column(db.String())
    hidden = db.Column(db.Boolean())
    reason = db.Column(db.String())
    type = db.Column(db.String())
    user = db.Column(db.String())
    guild = db.Column(db.String())
    active = db.Column(db.Boolean())
    permanent = db.Column(db.Boolean())
    inserted_at = db.Column(db.DateTime())
    expiry = db.Column(db.DateTime(), nullable=True)


class Reminder(db.Model):
    __tablename__ = "reminders"

    id = db.Column(db.String(), primary_key=True, default=lambda: str(uuid.uuid4().hex))
    author = db.Column(db.String())
    channel_id = db.Column(db.String())
    guild_id = db.Column(db.String())
    jump_url = db.Column(db.String())
    content = db.Column(db.String())
    expiration = db.Column(db.DateTime())
    mentions = db.Column(db.String())


class MessageLog(db.Model):
    __tablename__ = "message_logs"
    id = db.Column(db.String(), primary_key=True, default=lambda: str(uuid.uuid4().hex))
    actor = db.Column(db.String())
    guild = db.Column(db.String())
    inserted_at = db.Column(db.DateTime())
    messages = db.Column(db.String())  # JSON: {"msgs":[MSG_OBJ]}

