from .database import db


class Guild(db.Model):
    __tablename__ = "guilds"

    id = db.Column(db.String(), primary_key=True)
    server_log_channel = db.Column(db.String(), nullable=True)
    prefix = db.Column(db.String())
