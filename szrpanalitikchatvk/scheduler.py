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
        
        # Запускаем ежедневный анализ в 16:15
        asyncio.create_task(self._daily_analysis_task())
        
        # Запускаем мониторинг
        await self._monitor()
    
    async def _daily_analysis_task(self):
        """Ежедневный анализ"""
        while self.running:
            try:
                now = datetime.now()
                target_time = time(6, 27)  
                
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
        """Создает CSV с актуальными результатами анализа в том же формате, что и экспорт"""
        import csv
        import io
        from csv_parser import CSVParser
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow(["VK Chat Statistics Export"])
        writer.writerow([])
        
        # Получаем данные из CSV файла
        csv_parser = CSVParser()
        vk_chats = csv_parser.parse_csv()
        
        # Общая статистика
        writer.writerow(["1. Общая статистика по всем чатам:"])
        writer.writerow(["Дата:", datetime.now().strftime('%d.%m.%Y %H:%M')])
        writer.writerow(["Чатов в CSV:", len(vk_chats)])
        
        # Получаем актуальную статистику только для чатов из CSV
        csv_group_ids = {chat['group_id'] for chat in vk_chats}
        total_members = 0
        total_messages = 0
        processed_chats = len(vk_chats)  # Всегда равно количеству чатов в CSV
        
        # Инициализируем базу данных если не инициализирована
        if not db.connection:
            await db.initialize()
        
        # Считаем статистику только для чатов из CSV (по-чатная дедупликация)
        chats_stats = await db.get_chats_stats()
        all_unique_members = set()
        
        for chat in chats_stats:
            if chat['group_id'] in csv_group_ids:
                # Получаем участников чата из базы данных (уже отфильтрованных)
                chat_id = await db.get_chat_id_by_group_id(chat['group_id'])
                if chat_id:
                    members = await db.get_chat_members(chat_id)
                    all_unique_members.update(members)
                    
                    # Считаем сообщения только от отфильтрованных участников этого чата
                    if members:
                        placeholders = ','.join(['?' for _ in members])
                        async with db.connection.execute(f"""
                            SELECT COUNT(DISTINCT m.message_id) 
                            FROM messages m 
                            JOIN users u ON m.user_id = u.id 
                            WHERE m.chat_id = ? AND u.vk_id IN ({placeholders})
                        """, [chat_id] + [str(member) for member in members]) as cursor:
                            chat_messages_count = (await cursor.fetchone())[0] or 0
                            total_messages += chat_messages_count  # Суммируем по чатам
        
        total_members = len(all_unique_members)
        
        writer.writerow(["Обработано чатов:", processed_chats])
        writer.writerow([])
        
        writer.writerow(["Общая статистика:"])
        writer.writerow(["Участников:", total_members])
        writer.writerow(["Сообщений (за месяц):", total_messages])
        writer.writerow([])
        
        # Статистика по чатам из CSV файла
        writer.writerow(["2. Статистика по каждому чату:"])
        
        # Получаем данные по чатам из базы данных только для чатов из CSV
        chats_stats = await db.get_chats_stats()
        csv_group_ids = {chat['group_id'] for chat in vk_chats}
        
        for chat in chats_stats:
            # Показываем только чаты, которые есть в CSV файле
            if chat['group_id'] in csv_group_ids:
                # Получаем отфильтрованную статистику для этого чата
                chat_id = await db.get_chat_id_by_group_id(chat['group_id'])
                if chat_id:
                    # Получаем участников чата (уже отфильтрованных от дублированных)
                    members = await db.get_chat_members(chat_id)
                    # Получаем сообщения только от этих участников
                    if members:
                        placeholders = ','.join(['?' for _ in members])
                        async with db.connection.execute(f"""
                            SELECT COUNT(DISTINCT m.message_id) 
                            FROM messages m 
                            JOIN users u ON m.user_id = u.id 
                            WHERE m.chat_id = ? AND u.vk_id IN ({placeholders})
                        """, [chat_id] + [str(member) for member in members]) as cursor:
                            messages_count = (await cursor.fetchone())[0] or 0
                    else:
                        messages_count = 0
                    
                    writer.writerow([
                        f"id группы чата: {chat['group_id']}",
                        f"{len(members)} участников,",
                        f"{messages_count} сообщений"
                    ])
                else:
                    # Если чат не найден в базе, показываем нули
                    writer.writerow([
                        f"id группы чата: {chat['group_id']}",
                        f"0 участников,",
                        f"0 сообщений"
                    ])
        
        writer.writerow([])
        
        # Информация о CSV файле
        writer.writerow(["3. Информация о CSV файле:"])
        writer.writerow(["Файл:", "data/vk_chats.csv"])
        writer.writerow(["Загружено чатов:", len(vk_chats)])
        writer.writerow([])
        
        # Список чатов из CSV
        writer.writerow(["4. Список чатов из CSV:"])
        for i, chat in enumerate(vk_chats, 1):
            writer.writerow([
                f"Чат {i}:",
                f"ID: {chat['group_id']}",
                f"Название: {chat.get('chat_name', 'Не указано')}",
                f"Активен: {'Да' if chat.get('is_active', True) else 'Нет'}"
            ])
        
        # Добавляем BOM для правильного отображения в Windows Excel
        csv_content = output.getvalue()
        return '\ufeff' + csv_content
    
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
