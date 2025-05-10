import logging
import asyncio 
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)
import config
import database as db
from bot_handlers import (
    start_command,
    add_med_start, med_name_received, dosage_received,
    specific_times_received, confirmation_received, cancel_conversation,
    my_medications_command, scan_rx_command, text_fallback,
    MED_NAME, DOSAGE, SPECIFIC_TIMES, CONFIRMATION,
    set_phone_start, set_phone_received, PHONE_NUMBER,
    handle_reminder_ack
)
from scheduler import schedule_jobs

# Enable logging - SET TO DEBUG FOR DETAILED OUTPUT
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG # CHANGED TO DEBUG
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.DEBUG) # Get APScheduler's own debug logs
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    logger.info("Bot initialized. Running post_init setup...")
    await schedule_jobs(application) 
    logger.info("post_init setup complete. Scheduler jobs should be configured.")


def main() -> None:
    db.init_db()
    logger.info("Database initialized by main.")

    application = Application.builder().token(config.TELEGRAM_TOKEN).post_init(post_init).build()
    logger.info("Telegram Application built.")

    add_med_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^💊 Add Medication$'), add_med_start),
                      CommandHandler('addmed', add_med_start)],
        states={
            MED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, med_name_received)],
            DOSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dosage_received)],
            SPECIFIC_TIMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, specific_times_received)],
            CONFIRMATION: [MessageHandler(filters.Regex('^(✅ Yes, Save!|✏️ No, Start Over)$'), confirmation_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation), MessageHandler(filters.TEXT, text_fallback)],
        per_message=False
    )

    set_phone_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📞 Set/Update Call Number$'), set_phone_start),
                      CommandHandler('setphone', set_phone_start)],
        states={
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_phone_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_message=False
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(set_phone_conv_handler)
    application.add_handler(add_med_conv_handler)
    application.add_handler(MessageHandler(filters.Regex('^📋 My Medications$'), my_medications_command))
    application.add_handler(CommandHandler("mylist", my_medications_command))
    application.add_handler(CommandHandler("scanrx", scan_rx_command))
    application.add_handler(CallbackQueryHandler(handle_reminder_ack, pattern=r"^(ack|snooze):"))
    logger.info("All handlers added to the application.")
    
    logger.info("Starting bot polling...")
    application.run_polling()
    logger.info("Bot polling stopped.")

if __name__ == "__main__":
    main()