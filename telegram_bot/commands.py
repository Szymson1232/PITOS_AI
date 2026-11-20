
from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 PITOS AI ONLINE!\n"
        "System analizy sportowej uruchomiony."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟢 PITOS AI działa."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Dostępne komendy:\n"
        "/start - uruchomienie\n"
        "/status - status systemu\n"
        "/help - pomoc"
    )
