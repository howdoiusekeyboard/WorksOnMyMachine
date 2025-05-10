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
from datetime import datetime, time, timezone
from config import SNOOZE_MINUTES, MAX_SNOOZES

logger = logging.getLogger(__name__)

# States for ConversationHandler
(MED_NAME, DOSAGE, TIMES_A_DAY, SPECIFIC_TIMES, CONFIRMATION, PHONE_NUMBER) = range(6)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:  # Ensure user object exists
        logger.info(f"User {user.id} ({user.username or 'NoUsername'}) started interaction.")
        db.add_user(user.id)  # This should store user.id as telegram_id in your 'users' table
        reply_keyboard = [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']]
        await update.message.reply_text(
            f"Hi {user.first_name}! I'm MediMinder Bot. How can I help you today?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
    else:
        logger.error("start_command: update.effective_user is None. Cannot register user.")

# --- Add Medication Conversation ---
async def add_med_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the medication name."""
    await update.message.reply_text(
        "Let's add a new medication reminder. What's the name of the medication?",
    )
    return MED_NAME

async def med_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the medication name and ask for the dosage."""
    med_name = update.message.text
    context.user_data["med_name"] = med_name
    
    await update.message.reply_text(
        f"Got it! What's the dosage for {med_name}? (e.g., '10mg', '1 tablet', etc.)"
    )
    return DOSAGE

async def dosage_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the dosage and ask for specific times."""
    dosage = update.message.text
    context.user_data["dosage"] = dosage
    
    await update.message.reply_text(
        "At what specific times do you need to take this medication?\n\n"
        "Please enter all times in 24-hour format (HH:MM), separated by commas.\n"
        "For example: '08:00, 20:00' for 8 AM and 8 PM."
    )
    return SPECIFIC_TIMES

async def specific_times_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the specific times and ask for confirmation."""
    times_text = update.message.text
    
    # Basic validation of time format
    times_list = [t.strip() for t in times_text.split(',')]
    valid_times = []
    invalid_times = []
    
    for t in times_list:
        try:
            h, m = map(int, t.split(':'))
            if 0 <= h < 24 and 0 <= m < 60:
                valid_times.append(f"{h:02d}:{m:02d}")
            else:
                invalid_times.append(t)
        except (ValueError, IndexError):
            invalid_times.append(t)
    
    if invalid_times:
        await update.message.reply_text(
            f"Invalid time format(s): {', '.join(invalid_times)}.\n"
            "Please enter all times in 24-hour format (HH:MM), separated by commas."
        )
        return SPECIFIC_TIMES
    
    times_str = ', '.join(valid_times)
    context.user_data["times_of_day"] = times_str
    
    # Summary for confirmation
    await update.message.reply_text(
        f"Please confirm these medication details:\n\n"
        f"Medication: {context.user_data['med_name']}\n"
        f"Dosage: {context.user_data['dosage']}\n"
        f"Times: {times_str}\n\n"
        "Is this correct?",
        reply_markup=ReplyKeyboardMarkup(
            [['✅ Yes, Save!', '✏️ No, Start Over']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return CONFIRMATION

async def confirmation_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the confirmation response and save the medication if confirmed."""
    response = update.message.text
    
    if response == "✅ Yes, Save!":
        user_id = update.effective_user.id
        med_name = context.user_data.get("med_name", "Unknown Medication")
        dosage = context.user_data.get("dosage", "")
        times_of_day = context.user_data.get("times_of_day", "")
        
        # Save to database
        med_id = db.add_medication_db(user_id, med_name, dosage, times_of_day)
        
        if med_id:
            logger.info(f"Medication {med_name} saved for user {user_id} with ID {med_id}")
            await update.message.reply_text(
                f"Great! I've saved your medication reminder for {med_name}.\n"
                f"You'll receive reminders at: {times_of_day}.",
                reply_markup=ReplyKeyboardMarkup(
                    [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
        else:
            logger.error(f"Failed to save medication {med_name} for user {user_id}")
            await update.message.reply_text(
                "Sorry, there was an error saving your medication. Please try again.",
                reply_markup=ReplyKeyboardMarkup(
                    [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
    else:
        await update.message.reply_text(
            "Let's start over. What's the name of the medication?",
        )
        return MED_NAME
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled.",
        reply_markup=ReplyKeyboardMarkup(
            [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    context.user_data.clear()
    return ConversationHandler.END

async def text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback for text messages that don't match expected responses."""
    await update.message.reply_text(
        "I didn't understand that. Please use the buttons or follow the instructions."
    )
    return None  # Stay in the current state

# --- Set Phone Number ---
async def set_phone_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation for setting a phone number."""
    user_id = update.effective_user.id
    current_phone = db.get_user_phone(user_id)
    
    if current_phone:
        await update.message.reply_text(
            f"Your current phone number is: {current_phone}\n"
            "Please enter a new phone number to update it, or /cancel to keep the current one."
        )
    else:
        await update.message.reply_text(
            "Please enter your phone number for call alerts "
            "when you miss medication reminders.\n"
            "Format: Country code + number (e.g., +1234567890)"
        )
    
    return PHONE_NUMBER

async def set_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate and save the phone number."""
    phone_number = update.message.text.strip()
    
    # Basic validation - could be enhanced
    if not (phone_number.startswith('+') and len(phone_number) > 8 and phone_number[1:].isdigit()):
        await update.message.reply_text(
            "Invalid phone number format. Please use: Country code + number (e.g., +1234567890)"
        )
        return PHONE_NUMBER
    
    user_id = update.effective_user.id
    db.add_user(user_id, phone_number)  # This should update the phone number if user exists
    
    await update.message.reply_text(
        f"Thanks! Your phone number {phone_number} has been saved.\n"
        "You'll receive call alerts at this number if you miss medication reminders.",
        reply_markup=ReplyKeyboardMarkup(
            [['💊 Add Medication', '📋 My Medications'], ['📞 Set/Update Call Number']],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    
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
        message += f"   Scheduled for: {med['times_of_day']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# --- Scan Prescription ---
async def scan_rx_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "To scan a prescription, please send a photo of it. "
        "I'll try to extract medication information automatically.\n\n"
        "(This feature is not fully implemented yet - for demonstration purposes only.)"
    )

# --- Handle Reminder Button Callbacks ---
async def handle_reminder_ack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Answer the callback query
    
    callback_data = query.data
    action, log_id = callback_data.split(':')
    log_id = int(log_id)
    
    now = datetime.now(timezone.utc)  # Use timezone-aware datetime
    
    if action == "ack":
        db.update_reminder_log_status(log_id, 'acknowledged', now)
        await query.edit_message_text(
            text="✅ Thanks for confirming you've taken your medication!",
            reply_markup=None  # Remove buttons
        )
    elif action == "snooze":
        # Check if max snoozes reached
        # This would need to read the current snooze count from DB first
        db.update_reminder_log_status(log_id, 'snoozed', None, True)  # Increment snooze count
        await query.edit_message_text(
            text=f"⏰ Reminder snoozed for {SNOOZE_MINUTES} minutes. "
                 f"I'll remind you again soon.",
            reply_markup=None  # Remove buttons
        )
        
        # You should now schedule a new reminder in X minutes
        # For simplicity, this could update the scheduled_time in reminders_log
        # and the scheduler would pick it up

# Add this health check function
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Health check command to confirm the bot is working and can send messages."""
    user = update.effective_user
    user_id = user.id if user else None
    
    if not user_id:
        logger.error("Health check: No user ID found in update.")
        return
        
    logger.info(f"Health check requested by user {user_id}")
    
    # Test message to confirm messaging is working
    await update.message.reply_text("✅ Bot health check: I'm online and working!")
    
    # Send a test reminder-style message with buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Test Button", callback_data=f"test:health"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:health")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        test_msg = await context.bot.send_message(
            chat_id=user_id,
            text="🧪 This is a test notification with buttons.\nIf you see this, notifications should be working!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"Health check test message sent successfully to {user_id}, message_id={test_msg.message_id}")
    except Exception as e:
        logger.error(f"Health check failed to send test message: {e}")
        await update.message.reply_text(f"❌ Error sending test message: {e}")
    
    # Report user and chat information for debugging
    chat_id = update.effective_chat.id if update.effective_chat else None
    await update.message.reply_text(
        f"📊 Debug Info:\n"
        f"• Your user_id: `{user_id}`\n"
        f"• Chat ID: `{chat_id}`\n"
        f"• Username: @{user.username}\n"
        f"Make sure this matches what's in your database.",
        parse_mode='Markdown'
    )