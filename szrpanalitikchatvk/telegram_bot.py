"""
Простой Telegram бот
"""
import asyncio
import io
from datetime import datetime
from typing import Dict, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from config import config
from database_sqlite import db
from analyzer import ChatAnalyzer
from csv_parser import CSVParser
from export import DataExporter

class TelegramBot:
    """Простой Telegram бот"""
    
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.handle_document, lambda m: m.document is not None)
        self.dp.callback_query.register(self.handle_stats_callback, lambda c: c.data == "stats")
        self.dp.callback_query.register(self.handle_analyze_callback, lambda c: c.data == "analyze")
        self.dp.callback_query.register(self.handle_export_callback, lambda c: c.data == "export")
        self.dp.callback_query.register(self.handle_upload_csv_callback, lambda c: c.data == "upload_csv")
        self.dp.callback_query.register(self.handle_start_callback, lambda c: c.data == "start")
    
    async def start_command(self, message: types.Message):
        """Обработчик команды /start"""
        # Сохраняем пользователя
        await db.save_telegram_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
            [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")]
        ])
        
        await message.answer(
            "🤖 **VK Chat Analyzer Bot**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def handle_stats_callback(self, callback: types.CallbackQuery):
        """Обработчик получения статистики"""
        await callback.answer("📊 Получаю статистику...")
        
        try:
            # Проверяем наличие CSV файла
            csv_parser = CSVParser()
            if not csv_parser.is_csv_available():
                await callback.message.edit_text(
                    "❌ **CSV файл не загружен**\n\n"
                    "Для получения статистики необходимо сначала загрузить CSV файл с данными VK чатов.\n\n"
                    "Нажмите кнопку '📊 Загрузить CSV' и отправьте файл.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
                        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                    ])
                )
                return
            
            # Получаем чаты из CSV
            vk_chats = csv_parser.parse_csv()
            
            # Получаем актуальную статистику из базы данных
            csv_group_ids = {chat['group_id'] for chat in vk_chats}
            csv_chats_count = len(vk_chats)  # Всегда равно количеству чатов в CSV
            
            # Считаем уникальных участников и сообщения (по-чатная дедупликация)
            all_unique_members = set()
            csv_total_messages = 0  # Суммируем по чатам, а не через set()
            chats_stats = await db.get_chats_stats()
            
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
                                csv_total_messages += chat_messages_count  # Суммируем по чатам
            
            csv_total_members = len(all_unique_members)
            csv_total_authors = len(all_unique_members)  # Авторы = участники
            
            # Получаем активность за сегодня из базы данных (по-чатная дедупликация)
            all_today_authors = set()
            csv_today_messages = 0  # Суммируем по чатам, а не через set()
            
            for chat in chats_stats:
                if chat['group_id'] in csv_group_ids:
                    # Получаем активность за сегодня для этого чата
                    chat_id = await db.get_chat_id_by_group_id(chat['group_id'])
                    if chat_id:
                        # Получаем отфильтрованных участников чата
                        members = await db.get_chat_members(chat_id)
                        if members:
                            from datetime import date
                            today = date.today()
                            placeholders = ','.join(['?' for _ in members])
                            
                            # Считаем сообщения за сегодня только от отфильтрованных участников этого чата
                            async with db.connection.execute(f"""
                                SELECT COUNT(DISTINCT m.message_id) 
                                FROM messages m 
                                JOIN users u ON m.user_id = u.id 
                                WHERE m.chat_id = ? AND DATE(m.date) = ? AND u.vk_id IN ({placeholders})
                            """, [chat_id, today] + [str(member) for member in members]) as cursor:
                                chat_today_messages = (await cursor.fetchone())[0] or 0
                                csv_today_messages += chat_today_messages  # Суммируем по чатам
                            
                            # Авторы за сегодня только отфильтрованные участники
                            async with db.connection.execute(f"""
                                SELECT DISTINCT u.vk_id 
                                FROM messages m 
                                JOIN users u ON m.user_id = u.id 
                                WHERE m.chat_id = ? AND DATE(m.date) = ? AND u.vk_id IN ({placeholders})
                            """, [chat_id, today] + [str(member) for member in members]) as cursor:
                                authors = await cursor.fetchall()
                                all_today_authors.update(author[0] for author in authors)
            
            csv_today_authors = len(all_today_authors)
            
            # Проверяем, есть ли данные (проверяем наличие чатов в CSV)
            if len(vk_chats) == 0:
                report = (
                    f"📊 **Статистика VK чатов**\n\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 Чатов в CSV: {len(vk_chats)}\n\n"
                    f"⚠️ **Пока что вы не делали анализ!**\n\n"
                    f"Для получения статистики нажмите кнопку \"🚀 Запустить анализ\""
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            else:
                success_rate = 100.0
                report = (
                    f"📊 **Статистика VK чатов**\n\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 Чатов в CSV: {len(vk_chats)}\n"
                    f"✅ Обработано чатов: {csv_chats_count}\n\n"
                    f"**Общая статистика:**\n"
                    f"• 👥 Уникальных участников: {csv_total_members}\n"
                    f"• 💬 Уникальных сообщений: {csv_total_messages}\n"
                    f"**Активность за сегодня:**\n"
                    f"• 💬 Новых сообщений: {csv_today_messages}\n"
                    f"• 👤 Активных авторов: {csv_today_authors}\n\n"
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            
            await callback.message.edit_text(
                report,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка при получении статистики: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            )
    
    async def handle_analyze_callback(self, callback: types.CallbackQuery):
        """Обработчик запуска анализа"""
        await callback.answer("🚀 Запускаю анализ...")
        
        try:
            # Проверяем наличие CSV файла
            csv_parser = CSVParser()
            if not csv_parser.is_csv_available():
                await callback.message.edit_text(
                    "❌ **CSV файл не загружен**\n\n"
                    "Для запуска анализа необходимо сначала загрузить CSV файл с данными VK чатов.\n\n"
                    "Нажмите кнопку '📊 Загрузить CSV' и отправьте файл.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
                        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                    ])
                )
                return
            
            analyzer = ChatAnalyzer(db)
            results = await analyzer.analyze_all_chats()
            
            # Проверяем, есть ли ошибки
            errors = [r for r in results if "error" in r]
            if errors:
                error_msg = "\n".join([f"• ❌ {r['chat_name']}: {r['error']}" for r in errors])
                await callback.message.edit_text(
                    f"❌ **Ошибки при анализе:**\n\n{error_msg}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
                    ])
                )
            else:
                # Суммируем статистику по всем чатам (используем отфильтрованные данные)
                # Считаем уникальных участников (без дублирования между чатами)
                all_unique_members = set()
                for r in results:
                    all_unique_members.update(r.get('filtered_members', []))
                
                total_members = sum(len(r.get('filtered_members', [])) for r in results)
                total_messages = sum(len(r.get('filtered_messages', [])) for r in results)
                total_unique_members = len(all_unique_members)
                total_unique_messages = sum(len(r.get('filtered_messages', [])) for r in results)
                
                report = (
                    f"✅ **Анализ завершен!**\n\n"
                    f"📅 Дата: {results[0]['analysis_date']}\n"
                    f"📊 Обработано чатов: {len(results)}\n\n"
                    f"**Общая статистика:**\n"
                    f"💬 Сообщений (за месяц): {total_messages}\n"
                    f"🔢 Уникальных участников: {total_unique_members}\n"
                    f"**По чатам:**\n"
                )
                
                # Добавляем статистику по каждому чату (используем отфильтрованные данные)
                for result in results:
                    members_count = len(result.get('filtered_members', []))
                    messages_count = len(result.get('filtered_messages', []))
                    
                    report += f"• {result['chat_name']}: 👥 {members_count} участников, 💬 {messages_count} сообщений\n"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
                    [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
                
                # Получаем чаты из CSV для фильтрации
                csv_parser = CSVParser()
                vk_chats = csv_parser.parse_csv()
                
                # Получаем активность за сегодня только для чатов из CSV
                csv_today_messages = 0
                csv_today_authors = 0
                
                # Получаем статистику из базы данных для чатов из CSV
                chats_stats = await db.get_chats_stats()
                csv_group_ids = {chat['group_id'] for chat in vk_chats}
                
                for chat in chats_stats:
                    if chat['group_id'] in csv_group_ids:
                        # Получаем активность за сегодня для этого чата
                        chat_id = await db.get_chat_id_by_group_id(chat['group_id'])
                        if chat_id:
                            today_stats = await db.get_today_stats_for_chat(chat_id)
                            csv_today_messages += today_stats['messages']
                            csv_today_authors += today_stats['authors']
                
                # Показываем только общую статистику без подробностей по чатам
                general_report = (
                    f"✅ **Анализ завершен!**\n\n"
                    f"📅 Дата: {results[0]['analysis_date']}\n"
                )
                
                await callback.message.edit_text(
                    general_report,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Error running analysis: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка при запуске анализа: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            )
    
    async def handle_export_callback(self, callback: types.CallbackQuery):
        """Обработчик экспорта данных - создает CSV с общей статистикой"""
        await callback.answer("📥 Создаю CSV файл...")
        
        try:
            # Проверяем наличие CSV файла
            csv_parser = CSVParser()
            if not csv_parser.is_csv_available():
                await callback.message.edit_text(
                    "❌ **CSV файл не загружен**\n\n"
                    "Для экспорта данных необходимо сначала загрузить CSV файл с данными VK чатов.\n\n"
                    "Нажмите кнопку '📊 Загрузить CSV' и отправьте файл.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
                        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                    ])
                )
                return
            
            # Получаем статистику из базы данных
            stats = await db.get_stats()
            
            if not stats.get('has_data', False):
                await callback.message.edit_text(
                    "⚠️ **Нет данных для экспорта!**\n\n"
                    "Сначала запустите анализ чатов.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                    ])
                )
                return
            
            # Создаем CSV с общей статистикой (используем данные из CSV файла)
            csv_content = await self._create_stats_csv_from_csv(stats)
            
            # Создаем файл
            filename = f"vk_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            await callback.message.answer_document(
                types.BufferedInputFile(
                    csv_content.encode('utf-8'),
                    filename=filename
                ),
                caption=f"📊 **Экспорт статистики VK чатов**\n\n"
                       f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                       f"📁 Файл: {filename}"
            )
            
        except Exception as e:
            logger.error(f"Error creating export: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка при создании экспорта: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            )
    
    async def _create_stats_csv(self, stats: Dict[str, Any]) -> str:
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
        
        # Добавляем BOM для правильного отображения в Windows Excel
        csv_content = output.getvalue()
        return '\ufeff' + csv_content
    
    async def _create_stats_csv_from_csv(self, stats: Dict[str, Any]) -> str:
        """Создает CSV с общей статистикой используя данные из CSV файла"""
        import csv
        import io
        
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
        processed_chats = len(vk_chats)  # Всегда равно количеству чатов в CSV
        
        # Инициализируем базу данных если не инициализирована
        if not db.connection:
            await db.initialize()
        
        # Считаем уникальных участников и сообщения (по-чатная дедупликация)
        all_unique_members = set()
        total_messages = 0  # Суммируем по чатам, а не через set()
        chats_stats = await db.get_chats_stats()
        
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
    
    async def handle_upload_csv_callback(self, callback: types.CallbackQuery):
        """Обработчик кнопки загрузки CSV"""
        await callback.answer("📊 Ожидаю CSV файл...")
        
        await callback.message.edit_text(
            "📊 **Загрузка CSV файла**\n\n"
            "Отправьте CSV файл с данными VK чатов.\n\n"
            "**Формат CSV:**\n"
            "```\n"
            "group_id,token,chat_name,is_active\n"
            "230351857,vk1.a.token1,Чат 1,1\n"
            "230482562,vk1.a.token2,Чат 2,1\n"
            "```\n\n"
            "**Обязательные поля:**\n"
            "• `group_id` - ID группы VK\n"
            "• `token` - токен доступа VK API\n"
            "• `chat_name` - название чата (опционально)\n"
            "• `is_active` - активен ли чат (1/0)\n\n"
            "Отправьте файл сейчас:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="start")]
            ])
        )
    
    async def handle_document(self, message: types.Message):
        """Обработчик загрузки документа"""
        try:
            if not message.document:
                await message.answer("❌ Пожалуйста, отправьте файл")
                return
            
            # Проверяем расширение файла
            if not message.document.file_name.lower().endswith('.csv'):
                await message.answer("❌ Пожалуйста, отправьте CSV файл")
                return
            
            # Скачиваем файл
            file = await self.bot.get_file(message.document.file_id)
            file_path = f"data/{message.document.file_name}"
            
            # Создаем папку data если её нет
            import os
            os.makedirs("data", exist_ok=True)
            
            # Скачиваем содержимое файла
            await self.bot.download_file(file.file_path, file_path)
            
            # Парсим CSV
            csv_parser = CSVParser(file_path)
            chats = csv_parser.parse_csv()
            
            if not chats:
                await message.answer(
                    "❌ **Ошибка парсинга CSV**\n\n"
                    "Файл не содержит валидных данных или имеет неправильный формат.\n\n"
                    "Проверьте:\n"
                    "• Есть ли заголовки: group_id,token,chat_name,is_active\n"
                    "• Заполнены ли group_id и token\n"
                    "• Правильно ли указан is_active (1/0)",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 Попробовать снова", callback_data="upload_csv")]
                    ])
                )
                return
            
            # Сохраняем в стандартное место
            csv_parser.csv_file_path = "data/vk_chats.csv"
            csv_parser.save_csv(open(file_path, 'r', encoding='utf-8').read())
            
            # Удаляем временный файл
            os.remove(file_path)
            
            await message.answer(
                f"✅ **CSV файл успешно загружен!**\n\n"
                f"📊 Загружено чатов: {len(chats)}\n"
                f"📁 Файл: {message.document.file_name}\n\n"
                f"Теперь можно запускать анализ данных.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="🔙 Главное меню", callback_data="start")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error handling document: {e}")
            await message.answer(
                f"❌ **Ошибка при загрузке файла**\n\n{str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Попробовать снова", callback_data="upload_csv")]
                ])
            )
    
    async def handle_start_callback(self, callback: types.CallbackQuery):
        """Обработчик кнопки 'Главное меню'"""
        await callback.answer("🏠 Возвращаюсь в главное меню...")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
            [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")]
        ])
        
        await callback.message.edit_text(
            "🤖 **VK Chat Analyzer Bot**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def _send_long_message(self, message, text, keyboard=None):
        """Отправляет длинное сообщение, разбивая его на части"""
        MAX_LENGTH = 4000  # Оставляем запас для Markdown разметки
        
        if len(text) <= MAX_LENGTH:
            # Если сообщение короткое, отправляем как обычно
            await message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return
        
        # Разбиваем на части
        parts = []
        current_part = ""
        lines = text.split('\n')
        
        for line in lines:
            # Если добавление строки не превысит лимит
            if len(current_part + line + '\n') <= MAX_LENGTH:
                current_part += line + '\n'
            else:
                # Сохраняем текущую часть и начинаем новую
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
        
        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part.strip())
        
        # Отправляем первую часть с клавиатурой
        await message.edit_text(
            parts[0],
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Отправляем остальные части как новые сообщения
        for i, part in enumerate(parts[1:], 1):
            await message.reply(
                f"**Продолжение {i+1}/{len(parts)}:**\n\n{part}",
                parse_mode="Markdown"
            )
    
    async def start_polling(self):
        """Запуск бота"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        """Остановка бота"""
        await self.bot.session.close()
