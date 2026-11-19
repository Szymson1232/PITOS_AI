
import os
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

ODDS_REGIONS = os.getenv("ODDS_REGIONS", "eu")
ODDS_MARKET = os.getenv("ODDS_MARKET", "h2h")

LOOKAHEAD_HOURS = int(os.getenv("LOOKAHEAD_HOURS", "48"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

ALLOWED_SPORT_GROUPS = {
    "Soccer",
    "Basketball",
    "Tennis",
    "Ice Hockey",
    "Baseball",
}

def validate_config():
    required = {
        "ODDS_API_KEY": ODDS_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "DATABASE_URL": DATABASE_URL,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing Railway Variables: " + ", ".join(missing)
        )
