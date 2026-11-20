
import asyncio
import logging

from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    ODDS_API_KEY,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    validate_config,
)

from database.connection import init_db
from data.odds_api import OddsAPI
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

        # DATABASE
        await init_db()
        logger.info("POSTGRESQL CONNECTION OK")

        # ODDS API
        api = OddsAPI(api_key=ODDS_API_KEY)

        # TELEGRAM — outbound messages only
        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        await app.initialize()
        await app.start()

        logger.info("TELEGRAM SENDER READY")

        async def health_check():
            try:
                sports = await api.get_sports()
                logger.info(
                    "ODDS API CONNECTION OK | Sport keys: %s",
                    len(sports),
                )
            except Exception:
                logger.exception("ODDS API HEALTH CHECK FAILED")

        async def quality_scan(session_name):
            logger.info(
                "STARTING %s QUALITY SESSION",
                session_name,
            )

            try:
                published = await scan_sports(
                    api=api,
                    bot=app.bot,
                    chat_id=TELEGRAM_CHAT_ID,
                )

                logger.info(
                    "%s SESSION FINISHED | Published: %s/10",
                    session_name,
                    published,
                )

            except Exception:
                logger.exception(
                    "%s QUALITY SESSION FAILED",
                    session_name,
                )

        # DAILY SESSION — 06:00
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

        # NIGHT SESSION — 22:00
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

        # API HEALTH CHECK — EVERY 30 MINUTES
        scheduler.add_job(
            health_check,
            "interval",
            minutes=30,
            id="health_check",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.start()

        logger.info(
            "PITOS AI ONLINE | 06:00 / 22:00 | POLLING DISABLED"
        )

        # STARTUP MESSAGE
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🚀 PITOS AI | QUALITY FIRST ONLINE\n\n"
                "✅ PostgreSQL: ACTIVE\n"
                "✅ The Odds API: ACTIVE\n"
                "✅ Telegram sender: ACTIVE\n\n"
                "🎟️ AKO2\n"
                "📈 VALUE SINGLE\n\n"
                "🕕 Raport dzienny: 06:00\n"
                "🌙 Raport nocny: 22:00\n"
                "🔟 Maksymalnie 10 publikacji na sesję\n\n"
                "Brak dobrych okazji = brak publikacji."
            ),
        )

        # DAY 0 — ONE-TIME STARTUP TEST
        logger.info("DAY 0 TEST STARTING")

        await quality_scan("DZIEN 0 | TEST STARTOWY")

        logger.info("DAY 0 TEST FINISHED")

        # NORMAL OPERATION
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
            if app.running:
                await app.stop()

            await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
