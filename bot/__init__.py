try:
    from dotenv import load_dotenv

    print("Found .env file, loading environment variables from it.")
    load_dotenv()
except ImportError:
    print("Nevermind")
    pass

__version__ = "0.1.0"
