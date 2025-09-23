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
                target_time = time(00, 14)  
                
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
        """Отправляет ежедневный отчет с CSV всем пользователям"""
        try:
            # Создаем CSV с актуальными результатами анализа
            csv_content = await self._create_daily_report_csv(results)
            
            # Создаем файл
            filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Получаем всех пользователей Telegram
            users = await db.get_all_telegram_users()
            
            # Отправляем отчет всем пользователям
            for user in users:
                try:
                    await self.telegram_bot.bot.send_document(
                        chat_id=user['user_id'],
                        document=types.BufferedInputFile(
                            csv_content.encode('utf-8-sig'),
                            filename=filename
                        ),
                        caption=f"📊 **Ежедневный отчет VK чатов**\n\n"
                               f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                               f"📁 Файл: {filename}\n\n"
                               f"✅ Анализ завершен автоматически!"
                    )
                    logger.info(f"Daily report sent to user {user['user_id']}")
                except Exception as e:
                    logger.error(f"Failed to send report to user {user['user_id']}: {e}")
            
            logger.info(f"Daily report sent to {len(users)} users")
            
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")
    
    async def _create_daily_report_csv(self, results):
        """Создает CSV с актуальными результатами анализа"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow(["VK Chat Statistics Export"])
        writer.writerow([])
        
        # Общая статистика
        total_members = sum(len(r.get('filtered_members', [])) for r in results)
        total_messages = sum(len(r.get('filtered_messages', [])) for r in results)
        
        writer.writerow(["1. Общая статистика по всем чатам:"])
        writer.writerow([f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
        writer.writerow([f"Обработано чатов: {len(results)}"])
        writer.writerow([f"Общая статистика:"])
        writer.writerow([f"Участников: {total_members}"])
        writer.writerow([f"Сообщений (за месяц): {total_messages}"])
        writer.writerow([])
        
        # Статистика по чатам
        writer.writerow(["2. Статистика по каждому чату:"])
        for result in results:
            group_id = result.get('group_id', 'Unknown')
            members_count = len(result.get('filtered_members', []))
            messages_count = len(result.get('filtered_messages', []))
            writer.writerow([f"id группы чата: {group_id}"])
            writer.writerow([f"{members_count} участников, {messages_count} сообщений"])
        
        writer.writerow([])
        
        # Информация о CSV файле
        writer.writerow(["3. Информация о CSV файле:"])
        writer.writerow([f"Файл: data/vk_chats.csv"])
        writer.writerow([f"Загружено чатов: {len(results)}"])
        
        # Список чатов из CSV
        writer.writerow([])
        writer.writerow(["4. Список чатов из CSV:"])
        vk_chats = config.get_vk_chats()
        for i, chat in enumerate(vk_chats, 1):
            writer.writerow([f"Чат {i}: ID: {chat['group_id']} Название: {chat['chat_name']} Активен: {'Да' if chat['is_active'] else 'Нет'}"])
        
        csv_content = output.getvalue()
        return '\ufeff' + csv_content  # Добавляем BOM для Windows Excel
    
    async def _send_error_notification(self, error_message: str):
        """Отправляет уведомление об ошибке"""
        try:
            await self.telegram_bot.bot.send_message(
                chat_id=config.TELEGRAM_ADMIN_CHAT_ID,
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
