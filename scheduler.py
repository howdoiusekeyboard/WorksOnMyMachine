import logging
from apscheduler.triggers.interval import IntervalTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.error import TelegramError # Import specific Telegram errors
from datetime import datetime, timezone, timedelta
import asyncio

import database as db
from config import SNOOZE_MINUTES, CALL_ESCALATION_DELAY_MINUTES, MAX_SNOOZES

logger = logging.getLogger(__name__)

async def send_telegram_reminder(bot: Bot, log_id: int, user_telegram_id: int, med_name: str, dosage: str):
    """Sends the medication reminder message via Telegram."""
    logger.info(f"[SEND_ATTEMPT] log_id={log_id}, user_id={user_telegram_id}, med='{med_name}', dosage='{dosage}'")
    
    if not user_telegram_id:
        logger.error(f"[SEND_FAIL] log_id={log_id}: user_telegram_id is missing or invalid: {user_telegram_id}. Cannot send message.")
        return

    message_text = f"💊 Time to take your **{med_name}** ({dosage})!"
    keyboard = [
        [
            InlineKeyboardButton("✅ Taken", callback_data=f"ack:{log_id}"),
            InlineKeyboardButton(f"⏰ Snooze {SNOOZE_MINUTES}min", callback_data=f"snooze:{log_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"[SEND_API_CALL] Attempt {attempt}: bot.send_message(chat_id={user_telegram_id}, text='{message_text}', ...)")
            if not isinstance(bot, Bot):
                logger.error(f"[SEND_FAIL] log_id={log_id}: bot object is not a valid Bot instance: {type(bot)}")
                return
            msg_sent = await bot.send_message(
                chat_id=user_telegram_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            if msg_sent:
                logger.info(f"[SEND_SUCCESS] log_id={log_id} to user {user_telegram_id}. Message ID: {msg_sent.message_id}")
                db.update_reminder_log_status(log_id, 'sent')
                return
            else:
                logger.error(f"[SEND_FAIL_UNEXPECTED] log_id={log_id}: send_message returned None/False without error for user {user_telegram_id}.")
        except TelegramError as te:
            logger.error(f"[SEND_FAIL_TELEGRAM_API_ERROR] log_id={log_id} for user {user_telegram_id}: {te}", exc_info=False)
            logger.error(f"TelegramError details: code={getattr(te, 'error_code', 'N/A')}, message='{getattr(te, 'message', str(te))}'")
            if hasattr(te, 'response') and te.response:
                logger.error(f"TelegramError response: {te.response.text}")
            # Handle specific Telegram API errors
            if "chat not found" in str(te).lower() or (hasattr(te, 'message') and "chat not found" in te.message.lower()):
                logger.error(f"  Specific: Chat ID {user_telegram_id} not found. User might have blocked the bot or wrong ID.")
                # Mark user as inactive in DB
                db.mark_user_inactive(user_telegram_id)
                return
            elif "bot was blocked by the user" in str(te).lower() or (hasattr(te, 'message') and "bot was blocked by the user" in te.message.lower()):
                logger.error(f"  Specific: Bot was blocked by user {user_telegram_id}.")
                db.mark_user_inactive(user_telegram_id)
                return
            # For other Telegram errors, retry
        except Exception as e:
            logger.error(f"[SEND_FAIL_UNKNOWN_ERROR] log_id={log_id} for user {user_telegram_id}: {e}", exc_info=True)
        # Exponential backoff before retrying
        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)
    # If all attempts fail, update DB
    logger.error(f"[SEND_FAIL_FINAL] log_id={log_id}: All attempts to send message failed for user {user_telegram_id}.")
    db.update_reminder_log_status(log_id, 'send_failed')

# --- The rest of scheduler.py (check_and_send_reminders, etc.) remains the same as the previous "Enhanced Debugging" version ---
# Ensure that check_and_send_reminders correctly calls this updated send_telegram_reminder function.
# (The previous version already did this correctly)

async def check_and_send_reminders(bot: Bot):
    logger.info("SCHEDULER JOB: check_and_send_reminders - RUNNING")
    now_utc = datetime.now(timezone.utc) # Explicitly use UTC timezone-aware datetime
    logger.debug(f"Current UTC time: {now_utc.isoformat()}")
    conn = None
    try:
        conn = db.get_db_connection()
        meds_to_check = conn.execute(
            "SELECT id, user_telegram_id, med_name, dosage, times_of_day FROM medications WHERE is_active = TRUE"
        ).fetchall()
        logger.debug(f"Found {len(meds_to_check)} active medications to check.")

        if not meds_to_check:
            logger.info("No active medications found in DB.")
            return

        for med_row in meds_to_check:
            med_id = med_row['id']
            user_telegram_id = med_row['user_telegram_id'] # Make sure this is correctly fetched
            med_name = med_row['med_name']
            dosage = med_row['dosage']
            times_str_list = med_row['times_of_day'].split(',')
            logger.debug(f"Checking Med ID {med_id} ({med_name}) for user {user_telegram_id}. Scheduled times: {times_str_list}")

            # ... (rest of the logic from previous 'Enhanced Debugging' version for time checking and log creation) ...
            # Ensure the user_telegram_id is valid before calling send_telegram_reminder
            if not user_telegram_id:
                logger.error(f"  Med ID {med_id}: Invalid or missing user_telegram_id ({user_telegram_id}). Cannot schedule reminder send.")
                continue

            for time_str in times_str_list:
                time_str = time_str.strip()
                try:
                    h, m = map(int, time_str.split(':'))
                    scheduled_dt_today_utc = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
                    # logger.debug(f"  Med ID {med_id}: Parsed time_str '{time_str}' to scheduled_dt_today_utc: {scheduled_dt_today_utc.isoformat()}")
                    
                    trigger_window = timedelta(minutes=1) 
                    
                    if not (scheduled_dt_today_utc <= now_utc < scheduled_dt_today_utc + trigger_window):
                        continue 

                    # logger.info(f"  Med ID {med_id} at {time_str}: IS IN TRIGGER WINDOW. Scheduled: {scheduled_dt_today_utc}, Now: {now_utc}")

                    date_today_str = scheduled_dt_today_utc.strftime('%Y-%m-%d')
                    time_slot_str = scheduled_dt_today_utc.strftime('%H:%M')

                    existing_log_today = conn.execute(
                        """SELECT id, status FROM reminders_log 
                           WHERE medication_id = ? 
                             AND DATE(scheduled_time, 'utc') = ? 
                             AND STRFTIME('%H:%M', scheduled_time, 'utc') = ? 
                           ORDER BY id DESC LIMIT 1""",
                        (med_id, date_today_str, time_slot_str)
                    ).fetchone()

                    if existing_log_today:
                        # logger.debug(f"  Med ID {med_id} at {time_str}: Found existing log ID {existing_log_today['id']} with status '{existing_log_today['status']}' for today.")
                        if existing_log_today['status'] in ['sent', 'acknowledged', 'call_triggered', 'missed']:
                            # logger.info(f"  Med ID {med_id} at {time_str}: Already handled (status: {existing_log_today['status']}). Skipping.")
                            continue 

                    log_id_to_use = None
                    if existing_log_today and existing_log_today['status'] == 'pending': 
                        log_id_to_use = existing_log_today['id']
                        # logger.info(f"  Med ID {med_id} at {time_str}: Re-using existing PENDING log ID {log_id_to_use}.")
                    else: 
                        # logger.info(f"  Med ID {med_id} at {time_str}: No suitable existing log. Creating new log entry.")
                        cursor = conn.execute(
                            "INSERT INTO reminders_log (medication_id, user_telegram_id, scheduled_time, status) VALUES (?, ?, ?, 'pending')",
                            (med_id, user_telegram_id, scheduled_dt_today_utc) 
                        )
                        log_id_to_use = cursor.lastrowid
                        # logger.info(f"  CREATED new reminder_log ID {log_id_to_use} for med {med_name} ({med_id}) at {time_str} (Scheduled: {scheduled_dt_today_utc.isoformat()})")
                    
                    if log_id_to_use:
                        conn.commit() 
                        logger.info(f"  ==> Med ID {med_id} at {time_str}: Preparing to send reminder via log ID {log_id_to_use} to user_id {user_telegram_id}.")
                        await send_telegram_reminder(bot, log_id_to_use, user_telegram_id, med_name, dosage)
                    # else:
                        # logger.warning(f"  Med ID {med_id} at {time_str}: Could not determine log_id_to_use. This shouldn't happen.")
                        # conn.rollback() 

                except ValueError as ve:
                    logger.error(f"  Med ID {med_id}: Invalid time format '{time_str}': {ve}")
                except Exception as e:
                    logger.error(f"  Med ID {med_id}: Error processing time '{time_str}': {e}", exc_info=True)
        if conn: conn.commit() 
    except Exception as e:
        logger.error(f"SCHEDULER JOB: Major error in check_and_send_reminders: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn:
            conn.close()
        # logger.info("SCHEDULER JOB: check_and_send_reminders - FINISHED") # Keep this if you want end-of-job marker


async def check_missed_reminders_and_escalate(bot: Bot):
    # logger.info("SCHEDULER JOB: check_missed_reminders_and_escalate - RUNNING")
    # ... (Your existing logic for escalation, ensure user_telegram_id is valid before sending) ...
    # Ensure timezone awareness here too.
    now_utc = datetime.now(timezone.utc)
    conn = None
    try:
        conn = db.get_db_connection()
        escalation_window_start_for_sent = now_utc - timedelta(minutes=CALL_ESCALATION_DELAY_MINUTES)
        # logger.debug(f"Escalation check: Looking for 'sent' reminders scheduled before {escalation_window_start_for_sent.isoformat()}")

        missed_reminders_to_escalate = conn.execute(
            """SELECT rl.id as log_id, m.med_name, rl.user_telegram_id, u.phone_number, rl.scheduled_time
               FROM reminders_log rl
               JOIN medications m ON rl.medication_id = m.id
               JOIN users u ON rl.user_telegram_id = u.telegram_id
               WHERE rl.status = 'sent' 
                 AND rl.scheduled_time < ?
            """, (escalation_window_start_for_sent.isoformat(),)
        ).fetchall()
        
        # logger.debug(f"Found {len(missed_reminders_to_escalate)} 'sent' reminders eligible for escalation check.")

        for reminder in missed_reminders_to_escalate:
            log_id = reminder['log_id']
            med_name = reminder['med_name']
            user_telegram_id = reminder['user_telegram_id']
            phone_number = reminder['phone_number']
            
            if not user_telegram_id: # Important check
                logger.error(f"  Escalation: Invalid or missing user_telegram_id for log ID {log_id}. Cannot escalate.")
                continue

            # logger.info(f"  Escalation Candidate: Log ID {log_id} ({med_name}) for user {user_telegram_id}. Phone: {phone_number}")
            
            if phone_number:
                # logger.info(f"    Simulating call escalation to {phone_number} for log ID {log_id}.")
                await bot.send_message(user_telegram_id,
                                       f"🚨 It seems you missed your {med_name} dose. "
                                       f"A call would be made to {phone_number} if fully enabled.")
                db.update_reminder_log_status(log_id, 'call_triggered')
            else:
                # logger.warning(f"    No phone number for user {user_telegram_id} to escalate log ID {log_id}.")
                await bot.send_message(user_telegram_id,
                                       f"🚨 It seems you missed your {med_name} dose. "
                                       "Please set a phone number in settings for call alerts.")
                db.update_reminder_log_status(log_id, 'missed')
            conn.commit()
    except Exception as e:
        logger.error(f"SCHEDULER JOB: Major error in check_missed_reminders_and_escalate: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
    # logger.info("SCHEDULER JOB: check_missed_reminders_and_escalate - FINISHED")


async def schedule_jobs(application):
    scheduler = application.job_queue.scheduler
    logger.info("Attempting to add/update scheduler jobs...") # Changed log message slightly
    scheduler.add_job(
        check_and_send_reminders, 
        IntervalTrigger(seconds=30), 
        args=[application.bot], 
        id="check_reminders_job", 
        replace_existing=True,
        misfire_grace_time=25
    )
    scheduler.add_job(
        check_missed_reminders_and_escalate, 
        IntervalTrigger(minutes=1), 
        args=[application.bot], 
        id="check_escalation_job", 
        replace_existing=True,
        misfire_grace_time=55
    )
    logger.info("APScheduler jobs (check_reminders_job, check_escalation_job) configured in PTB's job queue.")