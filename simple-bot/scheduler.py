"""
Планировщик для ежедневного анализа
"""
import asyncio
from datetime import datetime, time, timedelta
from loguru import logger
from database_sqlite import db
from analyzer import ChatAnalyzer

class Scheduler:
    """Простой планировщик"""
    
    def __init__(self):
        self.running = False
    
    async def start(self):
        """Запуск планировщика"""
        self.running = True
        logger.info("Scheduler started")
        
        # Запускаем ежедневный анализ в 02:00
        asyncio.create_task(self._daily_analysis_task())
        
        # Запускаем мониторинг
        await self._monitor()
    
    async def _daily_analysis_task(self):
        """Ежедневный анализ"""
        while self.running:
            try:
                now = datetime.now()
                target_time = time(2, 0)  # 02:00
                
                # Вычисляем время до следующего запуска
                next_run = datetime.combine(now.date(), target_time)
                if next_run <= now:
                    next_run = datetime.combine(now.date() + timedelta(days=1), target_time)
                
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"Next daily analysis scheduled for {next_run}")
                
                await asyncio.sleep(wait_seconds)
                
                if self.running:
                    logger.info("Starting daily analysis...")
                    await self._run_daily_analysis()
                    
            except Exception as e:
                logger.error(f"Error in daily analysis task: {e}")
                await asyncio.sleep(3600)  # Ждем час при ошибке
    
    async def _run_daily_analysis(self):
        """Выполнение ежедневного анализа"""
        try:
            analyzer = ChatAnalyzer()
            result = await analyzer.analyze_chat()
            
            if "error" in result:
                logger.error(f"Daily analysis failed: {result['error']}")
            else:
                logger.info(f"Daily analysis completed: {result['members_count']} members, {result['messages_count']} messages")
                
        except Exception as e:
            logger.error(f"Failed to run daily analysis: {e}")
    
    async def _monitor(self):
        """Мониторинг планировщика"""
        while self.running:
            await asyncio.sleep(60)  # Проверяем каждую минуту
    
    async def stop(self):
        """Остановка планировщика"""
        self.running = False
        logger.info("Scheduler stopped")
