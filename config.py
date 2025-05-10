import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") # For error logging to yourself

# Database configuration
DB_NAME = "mediminder.db"

# Reminder settings
SNOOZE_MINUTES = 5
MAX_SNOOZES = 2
CALL_ESCALATION_DELAY_MINUTES = 10 # After last snooze or initial reminder if no snooze