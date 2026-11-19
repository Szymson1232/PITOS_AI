
async def start(update, context):
    await update.message.reply_text(
        "🤖 PITOS AI ONLINE!\n"
        "System uruchomiony.\n"
        "Moduł analityczny jest w przygotowaniu."
    )


async def status(update, context):
    await update.message.reply_text(
        "🟢 PITOS AI działa.\n"
        "Tryb: DATA COLLECTION"
    )


async def help_command(update, context):
    await update.message.reply_text(
        "/start - uruchomienie\n"
        "/status - status systemu\n"
        "/help - pomoc"
    )
