import config
from telegram import Bot
import asyncio

async def main():
    bot = Bot(token=config.TELEGRAM_TOKEN)
    user_id = int(input('Enter your Telegram user ID: '))
    msg = input('Enter the test message to send: ')
    try:
        sent = await bot.send_message(chat_id=user_id, text=msg)
        print(f"Message sent! Message ID: {sent.message_id}")
    except Exception as e:
        print(f"Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 