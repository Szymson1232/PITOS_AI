
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
from core.scanner import scan_sports


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("PITOS_AI")

POLAND_TIMEZONE = "Europe/Warsaw"


async def main():
    validate_config()

    api = None
    app = None
    scheduler = AsyncIOScheduler(timezone=POLAND_TIMEZONE)

    try:
        logger.info("STARTING PITOS AI | QUALITY FIRST")

        await init_db()
        logger.info("POSTGRESQL CONNECTION OK")

        api = OddsAPI(api_key=ODDS_API_KEY)

        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("help", help_command))

        async def quality_scan(session_name):
            logger.info("STARTING %s SESSION", session_name)

            try:
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"🔎 PITOS AI | Rozpoczynam sesję {session_name}.",
                )

                published = await scan_sports(
                    api=api,
                    bot=app.bot,
                    chat_id=TELEGRAM_CHAT_ID,
                )

                logger.info(
                    "%s SESSION FINISHED | Published: %s",
                    session_name,
                    published,
                )

                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=(
                        f"✅ PITOS AI | Koniec sesji {session_name}\n"
                        f"Opublikowane propozycje: {published}/10\n\n"
                        "QUALITY FIRST: brak dobrych okazji oznacza brak typu."
                    ),
                )

            except Exception:
                logger.exception("%s SESSION FAILED", session_name)

        # RAPORT DZIENNY — 06:00 czasu polskiego
        scheduler.add_job(
            quality_scan,
            "cron",
            hour=6,
            minute=0,
            args=["DZIENNA"],
            id="daily_quality_scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        # RAPORT NOCNY — 22:00 czasu polskiego
        scheduler.add_job(
            quality_scan,
            "cron",
            hour=22,
            minute=0,
            args=["NOCNA"],
            id="night_quality_scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        await app.initialize()
        await app.start()

        if app.updater:
            await app.updater.start_polling()

        scheduler.start()

        logger.info("PITOS AI ONLINE | SCHEDULE: 06:00 / 22:00")

        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🚀 PITOS AI | QUALITY FIRST ONLINE\n\n"
                "✅ Telegram: ACTIVE\n"
                "✅ PostgreSQL: ACTIVE\n"
                "✅ The Odds API: ACTIVE\n\n"
                "🎟️ AKO2\n"
                "📈 VALUE SINGLE\n\n"
                "🕕 Sesja dzienna: 06:00\n"
                "🌙 Sesja nocna: 22:00\n"
                "🔟 Maksymalnie 10 publikacji na sesję\n\n"
                "💰 Budżet testowy: 400 zł\n"
                "🪙 1j = 25 zł\n\n"
                "Brak dobrych okazji = brak publikacji."
            ),
        )

        # Nie uruchamiamy skanowania przy restarcie.
        while True:
            await asyncio.sleep(3600)

    except Exception:
        logger.exception("FATAL PITOS AI ERROR")
        raise

    finally:
        logger.info("PITOS AI SHUTTING DOWN")

        if scheduler.running:
            scheduler.shutdown(wait=False)

        if api is not None:
            await api.close()

        if app is not None:
            if app.updater and app.updater.running:
                await app.updater.stop()

            if app.running:
                await app.stop()

            await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
