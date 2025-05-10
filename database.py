import sqlite3
import logging
from datetime import datetime
from config import DB_NAME

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            phone_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Medications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_telegram_id INTEGER NOT NULL,
            med_name TEXT NOT NULL,
            dosage TEXT,
            schedule_type TEXT DEFAULT 'daily', -- e.g., 'daily', 'specific_days'
            times_of_day TEXT NOT NULL, -- Comma-separated HH:MM, e.g., "08:00,20:00"
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_telegram_id) REFERENCES users (telegram_id)
        )
    ''')
    # Reminders Log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            user_telegram_id INTEGER NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, sent, acknowledged, snoozed, missed, call_triggered
            snooze_count INTEGER DEFAULT 0,
            acknowledged_at TIMESTAMP,
            call_triggered_at TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id),
            FOREIGN KEY (user_telegram_id) REFERENCES users (telegram_id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

# --- User Functions ---
def add_user(telegram_id, phone_number=None):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, phone_number) VALUES (?, ?)",
            (telegram_id, phone_number)
        )
        conn.commit()
        logger.info(f"User {telegram_id} added or already exists.")
        return True
    except sqlite3.Error as e:
        logger.error(f"DB Error adding user {telegram_id}: {e}")
        return False
    finally:
        conn.close()

def get_user_phone(telegram_id):
    conn = get_db_connection()
    user = conn.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return user['phone_number'] if user and user['phone_number'] else None

# --- Medication Functions ---
def add_medication_db(user_telegram_id, med_name, dosage, times_of_day):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO medications (user_telegram_id, med_name, dosage, times_of_day) VALUES (?, ?, ?, ?)",
            (user_telegram_id, med_name, dosage, times_of_day)
        )
        conn.commit()
        med_id = cursor.lastrowid
        logger.info(f"Medication {med_name} (ID: {med_id}) added for user {user_telegram_id}.")
        return med_id
    except sqlite3.Error as e:
        logger.error(f"DB Error adding medication for user {user_telegram_id}: {e}")
        return None
    finally:
        conn.close()

def get_active_medications_for_user(user_telegram_id):
    conn = get_db_connection()
    meds = conn.execute(
        "SELECT id, med_name, dosage, times_of_day FROM medications WHERE user_telegram_id = ? AND is_active = TRUE",
        (user_telegram_id,)
    ).fetchall()
    conn.close()
    return meds

def get_due_reminders(): # To be called by scheduler
    conn = get_db_connection()
    # This query needs refinement. It should find medications whose scheduled times are due
    # and for which a reminder hasn't been sent or needs to be re-sent (snooze).
    # For simplicity, we'll focus on creating reminder log entries when a med is added.
    # The scheduler will then pick up 'pending' reminders from reminders_log.
    now_utc = datetime.utcnow()
    # Get pending reminders that are due
    reminders = conn.execute(
        """SELECT rl.id as log_id, rl.medication_id, m.med_name, m.dosage, rl.user_telegram_id, rl.scheduled_time, u.phone_number
           FROM reminders_log rl
           JOIN medications m ON rl.medication_id = m.id
           JOIN users u ON rl.user_telegram_id = u.telegram_id
           WHERE rl.status = 'pending' AND rl.scheduled_time <= ?
        """, (now_utc,) # Make sure scheduled_time is stored in UTC
    ).fetchall()
    conn.close()
    return reminders


def update_reminder_log_status(log_id, status, acknowledged_at=None, snooze_count_increment=False):
    conn = get_db_connection()
    try:
        query = f"UPDATE reminders_log SET status = ?"
        params = [status]
        if acknowledged_at:
            query += ", acknowledged_at = ?"
            params.append(acknowledged_at)
        if snooze_count_increment:
            query += ", snooze_count = snooze_count + 1"

        query += " WHERE id = ?"
        params.append(log_id)
        conn.execute(query, tuple(params))
        conn.commit()
        logger.info(f"Reminder log ID {log_id} updated to status {status}.")
    except sqlite3.Error as e:
        logger.error(f"DB Error updating reminder log {log_id}: {e}")
    finally:
        conn.close()

def mark_user_inactive(user_telegram_id):
    conn = get_db_connection()
    try:
        # Set is_active=FALSE for all medications for this user
        conn.execute("UPDATE medications SET is_active=FALSE WHERE user_telegram_id=?", (user_telegram_id,))
        # Optionally, you can add an 'is_active' column to users table if not present
        # For now, just log the event
        conn.commit()
        logger.info(f"User {user_telegram_id} marked as inactive (all medications disabled).")
    except Exception as e:
        logger.error(f"Error marking user {user_telegram_id} as inactive: {e}")
    finally:
        conn.close()

# More functions for CRUD operations on medications, reminders_log etc. as needed.
# For example, creating entries in reminders_log when a medication is added,
# for each scheduled time for the next X days.