"""
Планировщик для ежедневного анализа
"""
import asyncio
from datetime import datetime, time, timedelta
from loguru import logger
from database_sqlite import db
from analyzer import ChatAnalyzer
from telegram_bot import TelegramBot
from config import config
from aiogram import types

class Scheduler:
    """Простой планировщик"""
    
    def __init__(self):
        self.running = False
        self.telegram_bot = None
    
    def set_telegram_bot(self, telegram_bot: TelegramBot):
        """Устанавливает Telegram бота для отправки уведомлений"""
        self.telegram_bot = telegram_bot
    
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
                target_time = time(17, 9)  # 17:05 МСК
                
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
            logger.info("Starting daily analysis...")
            analyzer = ChatAnalyzer(db)
            results = await analyzer.analyze_all_chats()
            
            if not results:
                logger.error("Daily analysis failed: No results")
                if self.telegram_bot:
                    await self._send_error_notification("Ежедневный анализ завершился с ошибкой: Нет результатов")
            else:
                # Считаем общую статистику
                total_members = sum(len(r.get('filtered_members', [])) for r in results)
                total_messages = sum(len(r.get('filtered_messages', [])) for r in results)
                logger.info(f"Daily analysis completed: {len(results)} chats, {total_members} members, {total_messages} messages")
                
                # Отправляем CSV таблицу
                if self.telegram_bot:
                    await self._send_daily_report(results)
                
        except Exception as e:
            logger.error(f"Failed to run daily analysis: {e}")
            if self.telegram_bot:
                await self._send_error_notification(f"Ошибка ежедневного анализа: {str(e)}")
    
    async def _monitor(self):
        """Мониторинг планировщика"""
        while self.running:
            await asyncio.sleep(60)  # Проверяем каждую минуту
    
    async def _send_daily_report(self, results):
        """Отправляет ежедневный отчет с CSV"""
        try:
            # Получаем статистику из базы данных
            stats = await db.get_stats()
            
            # Создаем CSV с общей статистикой
            csv_content = await self._create_stats_csv(stats)
            
            # Создаем файл
            filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Отправляем CSV файл
            await self.telegram_bot.bot.send_document(
                chat_id=config.TELEGRAM_ADMIN_ID,
                document=types.BufferedInputFile(
                    csv_content.encode('utf-8'),
                    filename=filename
                ),
                caption=f"📊 **Ежедневный отчет VK чатов**\n\n"
                       f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                       f"📁 Файл: {filename}\n\n"
                       f"✅ Анализ завершен автоматически!"
            )
            
            logger.info("Daily report sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")
    
    async def _send_error_notification(self, error_message: str):
        """Отправляет уведомление об ошибке"""
        try:
            await self.telegram_bot.bot.send_message(
                chat_id=config.TELEGRAM_ADMIN_ID,
                text=f"❌ **Ошибка ежедневного анализа**\n\n{error_message}"
            )
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    async def _create_stats_csv(self, stats: dict) -> str:
        """Создает CSV с общей статистикой"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow(["VK Chat Statistics Export"])
        writer.writerow([])
        
        # Общая статистика
        writer.writerow(["1. Общая статистика по всем чатам:"])
        writer.writerow(["Дата:", datetime.now().strftime('%d.%m.%Y %H:%M')])
        writer.writerow(["Обработано чатов:", stats['total_chats']])
        writer.writerow([])
        writer.writerow(["Общая статистика:"])
        writer.writerow(["Участников:", stats['total_unique_members']])
        writer.writerow(["Сообщений (за месяц):", stats['total_unique_messages']])
        writer.writerow([])
        
        # Статистика по чатам
        writer.writerow(["2. Статистика по каждому чату:"])
        
        # Получаем данные по чатам из базы данных
        chats_stats = await db.get_chats_stats()
        for chat in chats_stats:
            writer.writerow([
                f"id группы чата: {chat['group_id']}",
                f"{chat['unique_members']} участников,",
                f"{chat['unique_messages']} сообщений"
            ])
        
        return output.getvalue()
    
    async def stop(self):
        """Остановка планировщика"""
        self.running = False
        logger.info("Scheduler stopped")
