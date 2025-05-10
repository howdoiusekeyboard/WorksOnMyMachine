import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
import database as db
from datetime import datetime, time
from config import SNOOZE_MINUTES, MAX_SNOOZES

logger = logging.getLogger(__name__)

# States for ConversationHandler
(MED_NAME, DOSAGE, TIMES_A_DAY, SPECIFIC_TIMES, CONFIRMATION, PHONE_NUMBER) = range(6)
# bot_handlers.py (snippet)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user: # Ensure user object exists
        logger.info(f"User {user.id} ({user.username or 'NoUsername'}) started interaction.")
        db.add_user(user.id) # This should store user.id as telegram_id in your 'users' table
        # ... rest of your start_command logic ...
        reply_keyboard = [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']]
        await update.message.reply_text(
            f"Hi {user.first_name}! I'm MediMinder Bot. How can I help you today?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
    else:
        logger.error("start_command: update.effective_user is None. Cannot register user.")
        # Handle this case, perhaps by replying with an error if possible, though without a user, even that is hard.

async def set_phone_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please send me your phone number (e.g., +1234567890) for call reminders. "
                                    "You can type /cancel to stop.")
    return PHONE_NUMBER

async def set_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    phone = update.message.text
    # Basic validation (can be improved)
    if phone.startswith("+") and len(phone) > 7 and phone[1:].isdigit():
        db.add_user(user_id, phone_number=phone) # This will update if user exists
        await update.message.reply_text(f"Phone number {phone} saved for call escalations. "
                                        "You can change it anytime using 'Set/Update Call Number'.")
    else:
        await update.message.reply_text("That doesn't look like a valid phone number. Please try again or type /cancel.")
        return PHONE_NUMBER # Stay in the same state
    return ConversationHandler.END


# --- Add Medication Conversation ---
async def add_med_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to add a new medication."""
    await update.message.reply_text(
        "Okay, let's add a new medication! 😊\n"
        "What is the medication name? (Type /cancel to stop)",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data['med_info'] = {}
    return MED_NAME

async def med_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores medication name and asks for dosage."""
    context.user_data['med_info']['name'] = update.message.text
    await update.message.reply_text(
        f"Got it: {context.user_data['med_info']['name']}.\n"
        "What's the dosage? (e.g., 1 tablet, 50mg, 1 spray)"
    )
    return DOSAGE

async def dosage_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores dosage and asks for times per day."""
    context.user_data['med_info']['dosage'] = update.message.text
    # For simplicity, we'll directly ask for specific times.
    # You could add a "how many times a day" step with buttons first.
    await update.message.reply_text(
        f"Dosage: {context.user_data['med_info']['dosage']}.\n"
        "At what time(s) do you take it? \n"
        "Please enter times in 24-hour HH:MM format, separated by commas if multiple (e.g., 08:00, 14:30, 20:00)."
    )
    return SPECIFIC_TIMES # Skip TIMES_A_DAY for this simplified flow

async def specific_times_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores specific times and asks for confirmation."""
    times_str = update.message.text.strip()
    try:
        parsed_times = []
        for t_str in times_str.split(','):
            t_str = t_str.strip()
            # Validate HH:MM format
            time.fromisoformat(t_str) # Will raise ValueError if invalid
            parsed_times.append(t_str)
        if not parsed_times:
            raise ValueError("No times provided")
        context.user_data['med_info']['times'] = sorted(list(set(parsed_times))) # Store sorted unique times
    except ValueError:
        await update.message.reply_text(
            "Hmm, that doesn't look right. Please use HH:MM format, comma-separated. \n"
            "For example: 09:00 or 08:30,19:00. Try again:"
        )
        return SPECIFIC_TIMES # Stay in this state

    med_info = context.user_data['med_info']
    confirmation_text = (
        f"Great! Please confirm:\n"
        f"💊 Medication: {med_info['name']}\n"
        f"💪 Dosage: {med_info['dosage']}\n"
        f"⏰ Times: {', '.join(med_info['times'])}\n\n"
        "Is this correct?"
    )
    reply_keyboard = [['✅ Yes, Save!', '✏️ No, Start Over']]
    await update.message.reply_text(
        confirmation_text,
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return CONFIRMATION

async def confirmation_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves medication if confirmed, or restarts."""
    choice = update.message.text
    user_id = update.effective_user.id

    if choice == '✅ Yes, Save!':
        med_info = context.user_data['med_info']
        med_id = db.add_medication_db(
            user_telegram_id=user_id,
            med_name=med_info['name'],
            dosage=med_info['dosage'],
            times_of_day=','.join(med_info['times'])
        )
        if med_id:
            await update.message.reply_text(
                f"Reminder for {med_info['name']} saved successfully! 👍\n"
                "I'll remind you. You can see your meds with 'My Medications'.",
                reply_markup=ReplyKeyboardRemove() # Or back to main menu
            )
            # IMPORTANT: Here you'd also populate the reminders_log for the scheduler
            # For each time in med_info['times'], create a 'pending' entry in reminders_log
            # associated with this new med_id and user_id.
            # This is a crucial step for the scheduler to work.
        else:
            await update.message.reply_text(
                "Sorry, there was an error saving your medication. Please try again.",
                reply_markup=ReplyKeyboardRemove()
            )
    elif choice == '✏️ No, Start Over':
        await update.message.reply_text("Okay, let's start over.")
        # Clean up context.user_data if needed, then restart conversation
        return await add_med_start(update, context) # Or directly call the first step's function
    else:
        await update.message.reply_text("Invalid choice. Please use the buttons.")
        return CONFIRMATION

    context.user_data.clear()
    # Consider sending the main menu again after completion
    await start_command(update, context)
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "Okay, I've cancelled the current operation.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    await start_command(update, context) # Show main menu
    return ConversationHandler.END

# --- My Medications ---
async def my_medications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    meds = db.get_active_medications_for_user(user_id)
    if not meds:
        await update.message.reply_text("You don't have any active medications scheduled yet. Use 'Add Medication' to add some!")
        return

    message = "Here are your active medications:\n\n"
    for med in meds:
        message += f"💊 **{med['med_name']}** ({med['dosage']})\n"
        message += f"   Scheduled for: {med['times_of_day']}\n\n" # Consider formatting times nicely
        # Add buttons to edit/delete later
    await update.message.reply_text(message, parse_mode='Markdown')


# --- Reminder Handling (CallbackQueryHandler for buttons on reminder messages) ---
async def handle_reminder_ack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # Acknowledge the button press
    
    action, log_id_str = query.data.split(':') # e.g., "ack:123" or "snooze:123"
    log_id = int(log_id_str)

    if action == "ack":
        db.update_reminder_log_status(log_id, 'acknowledged', acknowledged_at=datetime.utcnow())
        await query.edit_message_text(text=f"{query.message.text}\n\n✅ Marked as Taken at {datetime.now().strftime('%H:%M')}.")
    
    elif action == "snooze":
        # Fetch current snooze count for this log_id from DB
        # For simplicity, let's assume we can get it or it's passed somehow
        # In a real app, you'd query reminders_log for log_id
        current_snoozes = 0 # Placeholder, fetch this
        reminder_log_entry = None # Fetch from DB: db.get_reminder_log_entry(log_id)
        
        # For demo, assume we can find the reminder details
        # This part needs careful implementation to fetch snooze_count and check against MAX_SNOOZES
        # And then to re-schedule or mark as missed.

        # Pseudocode:
        # reminder_details = db.get_reminder_log_details(log_id)
        # if reminder_details and reminder_details['snooze_count'] < MAX_SNOOZES:
        #     new_scheduled_time = datetime.utcnow() + timedelta(minutes=SNOOZE_MINUTES)
        #     db.update_reminder_log_status(log_id, 'pending', snooze_count_increment=True)
        #     db.update_reminder_log_scheduled_time(log_id, new_scheduled_time) # You'd need this DB function
        #     await query.edit_message_text(text=f"{query.message.text}\n\n⏰ Snoozed for {SNOOZE_MINUTES} minutes.")
        # else:
        #     await query.edit_message_text(text=f"{query.message.text}\n\n🚫 Max snoozes reached or reminder not found.")
        #     db.update_reminder_log_status(log_id, 'missed') # Or trigger call escalation logic
        await query.edit_message_text(text=f"{query.message.text}\n\n⏰ Snooze functionality needs full implementation (DB check).")


# Fallback handler for ConversationHandler
async def text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that. If you're in a process, please follow the prompts or type /cancel.")

# --- OCR (Conceptual) ---
async def scan_rx_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Please upload a CLEAR, TYPED image of your prescription. "
        "I'll try my best to read it, but you MUST confirm all details."
        "\n(OCR functionality is a placeholder in this version)"
    )
    # Next step would be a MessageHandler for photos, then OCR processing,
    # then a similar conversation flow as manual add but pre-filled and asking for confirmation.