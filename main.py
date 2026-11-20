
import asyncio
import logging

from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    TELEGRAM_BOT_TOKEN,
    ODDS_API_KEY,
    validate_config,
)

from database.connection import init_db
from data.odds_api import OddsAPI

from telegram_bot.commands import (
    start,
    status,
    help_command,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("PITOS_AI")


async def main():
    # Sprawdzenie konfiguracji
    validate_config()

    logger.info("Starting PITOS AI...")

    # Inicjalizacja bazy danych
    await init_db()
    logger.info("Database connection OK")

    # Połączenie z The Odds API
    api = OddsAPI(api_key=ODDS_API_KEY)

    # Inicjalizacja Telegrama
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

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
        trigger="interval",
        minutes=30,
        id="health_check",
        replace_existing=True,
    )

    # Uruchomienie aplikacji
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    scheduler.start()

    logger.info("PITOS AI ONLINE!")

    # Pierwszy test API
    await health_check()

    try:
        while True:
            await asyncio.sleep(3600)

    finally:
        logger.info("Stopping PITOS AI...")

        scheduler.shutdown(wait=False)

        await api.close()

        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
