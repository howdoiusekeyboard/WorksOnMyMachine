# Pill-Pal Telegram Bot

A medication reminder bot that sends notifications via Telegram.

## Setup Instructions

1. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Set up your Telegram bot token**:
   - Get a bot token from [@BotFather](https://t.me/botfather) on Telegram
   - Create a file named `.env` in the project directory with the following content:
     ```
     TELEGRAM_TOKEN=your_bot_token_here
     ```
   - Replace `your_bot_token_here` with the token you received from BotFather

3. **Run the bot**:
   ```
   python main.py
   ```

4. **Start a chat with your bot** on Telegram and send `/start`

## Debugging Notifications

If you're not receiving notifications:

1. Use the `/health` command in your chat with the bot to run a diagnostic test
2. Check your bot logs for any error messages
3. Make sure you've added medications with upcoming reminder times
4. Verify that your user ID is correctly registered in the database

## Database

The bot uses SQLite locally to store:
- User information (Telegram user ID)
- Medications and dosage schedules
- Reminder logs and statuses

## Commands

- `/start` - Initialize the bot and display the main menu
- `/addmed` - Add a new medication
- `/mylist` - View your active medications
- `/setphone` - Set a phone number for call escalations
- `/health` - Check if the bot is functioning correctly
- `/scanrx` - (Demo) Scan a prescription image

## Troubleshooting

- **ModuleNotFoundError**: Make sure you've installed all requirements
- **No notifications**: Check whether the bot is running and has the correct permissions
- **Bot not responding**: Ensure the TELEGRAM_TOKEN is set correctly
