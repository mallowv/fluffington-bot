from os import getenv

from firebase_admin import credentials
from dotenv import load_dotenv

from bot.utils.get_yaml import get_yaml_val

load_dotenv()

class Client():
    
    name = "Lymba"
    prefix = get_yaml_val("config.yml", "bot")["prefix"]
    token: str = getenv("TOKEN")
    firebase_creds = credentials.Certificate(getenv("FIREBASE_ADMIN_CREDENTIALS_PATH"))
    
class Channels():
    dev_log_channel: int = get_yaml_val("config.yml", "guild")["channels"]["dev_log"]
    
class Roles():
    moderation_roles: list[str] = get_yaml_val("config.yml", "roles")["moderation_roles"]
    