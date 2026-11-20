
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


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("PITOS_AI")


# ==========================================
# MAIN
# ==========================================

async def main():

    validate_config()

    logger.info("STARTING PITOS AI")

    api = None
    app = None
    scheduler = AsyncIOScheduler(timezone="UTC")

    try:

        # DATABASE
        await init_db()
        logger.info("DATABASE CONNECTION OK")

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

        # ==================================
        # HEALTH CHECK
        # ==================================

        async def health_check():

            try:
                sports = await api.get_sports()

                logger.info(
                    "ODDS API CONNECTION OK | Sports: %s",
                    len(sports),
                )

            except Exception:
                logger.exception("ODDS API CONNECTION ERROR")

        # ==================================
        # VALUE SCANNER
        # ==================================

        async def value_scan():

            try:

                logger.info("STARTING VALUE HUNTER")

                candidates = await scan_sports(
                    api=api,
                    bot=app.bot,
                    chat_id=TELEGRAM_CHAT_ID,
                )

                logger.info(
                    "VALUE HUNTER FINISHED | Candidates: %s",
                    candidates,
                )

            except Exception:
                logger.exception("VALUE SCAN FAILED")

        # ==================================
        # SCHEDULER
        # ==================================

        scheduler.add_job(
            health_check,
            "interval",
            minutes=30,
            id="health_check",
            replace_existing=True,
            max_instances=1,
        )

        scheduler.add_job(
            value_scan,
            "interval",
            minutes=60,
            id="value_scan",
            replace_existing=True,
            max_instances=1,
        )

        # ==================================
        # START APPLICATION
        # ==================================

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        scheduler.start()

        logger.info("PITOS AI ONLINE")

        # FIRST CONNECTION TEST
        await health_check()

        # TELEGRAM TEST MESSAGE
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "🚀 PITOS AI ONLINE!\n\n"
                "✅ Telegram: ACTIVE\n"
                "✅ PostgreSQL: ACTIVE\n"
                "✅ The Odds API: ACTIVE\n"
                "🔎 Value Hunter: STARTING\n\n"
                "Pierwsza analiza właśnie rusza."
            ),
        )

        # FIRST SCAN IMMEDIATELY
        await value_scan()

        # KEEP ALIVE
        while True:
            await asyncio.sleep(3600)

    except Exception:

        logger.exception("FATAL PITOS AI ERROR")
        raise

    finally:

        logger.info("SHUTTING DOWN PITOS AI")

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
