import asyncio
import os
from src.bot import bot
from src.telegram_listener import TelegramListener
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

async def run_telegram_listener():
    """Run Telegram listener as a separate task."""
    try:
        # Create telegram listener using the same trader as the bot
        listener = TelegramListener(bot.trader)
        await listener.start()
    except Exception as e:
        print(f"⚠️ Telegram listener error: {e}")

async def main():
    async with bot:
        # Resume monitoring existing trades
        if hasattr(bot, 'trader'):
             await bot.trader.resume_monitoring()
             # Ears disabled

        # Start Telegram listener as background task
        telegram_task = asyncio.create_task(run_telegram_listener())
        
        # Start Discord bot (this blocks)
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot Stopped manually.")
