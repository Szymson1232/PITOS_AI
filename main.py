
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
from telegram_bot.commands import (
    start,
    status,
    help_command,
)
from core.scanner import scan_sports


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("PITOS_AI")


async def main():
    validate_config()

    logger.info("STARTING PITOS AI V2 | QUALITY FIRST")

    api = None
    app = None
    scheduler = AsyncIOScheduler(timezone="UTC")

    try:
        # DATABASE
        await init_db()
        logger.info("POSTGRESQL CONNECTION OK")

        # ODDS API
        api = OddsAPI(api_key=ODDS_API_KEY)

        # TELEGRAM
        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("help", help_command))

        async def health_check():
            try:
                sports = await api.get_sports()
                logger.info(
                    "ODDS API OK | Available sport keys: %s",
                    len(sports),
                )
            except Exception:
                logger.exception("ODDS API HEALTH CHECK FAILED")

        async def quality_scan():
            try:
                logger.info("STARTING PITOS AI QUALITY SCAN")

                count = await scan_sports(
                    api=api,
                    bot=app.bot,
                    chat_id=TELEGRAM_CHAT_ID,
                )

                logger.info(
                    "QUALITY SCAN COMPLETE | Published: %s",
                    count,
                )

            except Exception:
                logger.exception("QUALITY SCAN FAILED")

        scheduler.add_job(
            health_check,
            "interval",
            minutes=30,
            id="health_check",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.add_job(
            quality_scan,
            "interval",
            minutes=60,
            id="quality_scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        await app.initialize()
        await app.start()

        if app.updater:
            await app.updater.start_polling()

        scheduler.start()

        logger.info("PITOS AI V2 ONLINE")

        await health_check()

        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🚀 PITOS AI V2 ONLINE\n\n"
                "✅ Telegram: ACTIVE\n"
                "✅ PostgreSQL: ACTIVE\n"
                "✅ The Odds API: ACTIVE\n"
                "✅ QUALITY FIRST: ACTIVE\n\n"
                "🏆 PEWNIACZKI\n"
                "💎 PEREŁKI\n"
                "📈 VALUE SINGLE\n"
                "🎟️ AKO2 | min. 1.20 na zdarzenie\n\n"
                "💰 Budżet testowy: 400 zł\n"
                "🪙 Jednostka: 25 zł\n\n"
                "Pierwszy skan rozpoczyna się teraz."
            ),
        )

        await quality_scan()

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
