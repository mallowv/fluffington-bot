try:
    from dotenv import load_dotenv

    print("Found .env file, loading environment variables from it.")
    load_dotenv()
except ImportError:
    print("Nevermind")
    pass

from os import getenv

import firebase_admin
firebase_admin.initialize_app(firebase_admin.credentials.Certificate(getenv("FIREBASE_ADMIN_CREDENTIALS_PATH")))

from bot.constants import Client

__version__ = "0.1.0"
