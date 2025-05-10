import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Bot Token (CRITICAL - must be set in environment or .env file)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set. Please set it in .env file or environment.")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") # For error logging to yourself

# Database config
DB_NAME = "mediminder.db"

# Reminder settings
SNOOZE_MINUTES = 5  # Time to snooze a reminder in minutes
CALL_ESCALATION_DELAY_MINUTES = 30  # Time after a reminder is sent before escalating to a call
MAX_SNOOZES = 3  # Maximum number of times a user can snooze a reminder

# You can add more configuration variables as needed