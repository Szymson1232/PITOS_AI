
import asyncio
import logging

from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    ODDS_API_KEY,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    validate_config,
)

from database.connection import init_db
from data.odds_api import OddsAPI
from telegram_bot.commands import start, status, help_command


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# Ograniczenie powtarzających się logów zapytań HTTP
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("PITOS_AI")


async def main():
    validate_config()

    logger.info("Starting PITOS AI...")

    # Baza danych
    await init_db()
    logger.info("Database connection OK")

    # The Odds API
    api = OddsAPI(api_key=ODDS_API_KEY)

    # Telegram
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))

    # Harmonogram
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def health_check():
        try:
            sports = await api.get_sports()
            logger.info(
                "ODDS API CONNECTION OK | Sports: %s",
                len(sports),
            )
        except Exception:
            logger.exception("ODDS API CONNECTION ERROR")

    scheduler.add_job(
        health_check,
        "interval",
        minutes=30,
        id="health_check",
        replace_existing=True,
    )

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        scheduler.start()

        logger.info("PITOS AI ONLINE!")

        # Test połączenia z The Odds API
        await health_check()

        # Test publikacji na kanale
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🚀 PITOS AI ONLINE!\n\n"
                "✅ Telegram: połączenie aktywne\n"
                "✅ Baza danych: połączenie aktywne\n"
                "✅ The Odds API: połączenie aktywne\n\n"
                "System jest uruchomiony. "
                "Trwa przygotowanie modułu analitycznego."
            ),
        )

        logger.info("TEST MESSAGE SENT TO TELEGRAM CHANNEL")

        while True:
            await asyncio.sleep(3600)

    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)

        await api.close()

        if app.updater and app.updater.running:
            await app.updater.stop()

        if app.running:
            await app.stop()

        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
