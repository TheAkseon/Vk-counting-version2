"""
Главный файл простого VK бота
"""
import asyncio
import signal
from loguru import logger
from config import config
from database_sqlite import db
from telegram_bot import TelegramBot
from scheduler import Scheduler

class VKSimpleBot:
    """Простой VK бот"""
    
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.scheduler = Scheduler()
        self.running = False
    
    async def start(self):
        """Запуск бота"""
        try:
            logger.info("Starting VK Simple Bot...")
            
            # Инициализируем базу данных
            await db.initialize()
            
            # Запускаем планировщик
            asyncio.create_task(self.scheduler.start())
            
            # Запускаем Telegram бота
            self.running = True
            await self.telegram_bot.start_polling()
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise
    
    async def stop(self):
        """Остановка бота"""
        logger.info("Stopping VK Simple Bot...")
        self.running = False
        
        # Останавливаем планировщик
        await self.scheduler.stop()
        
        # Закрываем базу данных
        await db.close()
        
        logger.info("VK Simple Bot stopped")

async def main():
    """Главная функция"""
    # Настройка логирования
    logger.add("logs/bot.log", rotation="1 day", retention="7 days")
    
    # Создаем экземпляр бота
    bot = VKSimpleBot()
    
    # Обработчик сигналов для graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
