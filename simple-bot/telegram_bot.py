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
        self.dp.callback_query.register(self.handle_export_all_callback, lambda c: c.data == "export_all")
        self.dp.callback_query.register(self.handle_export_chats_callback, lambda c: c.data == "export_chats")
        self.dp.callback_query.register(self.handle_export_users_callback, lambda c: c.data == "export_users")
        self.dp.callback_query.register(self.handle_export_messages_callback, lambda c: c.data == "export_messages")
        self.dp.callback_query.register(self.handle_export_stats_callback, lambda c: c.data == "export_stats")
        self.dp.callback_query.register(self.handle_upload_csv_callback, lambda c: c.data == "upload_csv")
        self.dp.callback_query.register(self.handle_start_callback, lambda c: c.data == "start")
    
    async def start_command(self, message: types.Message):
        """Обработчик команды /start"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Загрузить CSV", callback_data="upload_csv")],
            [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
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
            stats = await db.get_stats()
            
            # Проверяем, есть ли данные
            if not stats.get('has_data', False):
                report = (
                    f"📊 **Статистика VK чатов**\n\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"⚠️ **Пока что вы не делали анализ!**\n\n"
                    f"Для получения статистики нажмите кнопку \"🚀 Запустить анализ\""
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
                ])
            else:
                report = (
                    f"📊 **Статистика VK чатов**\n\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"**Общая статистика:**\n"
                    f"• 💬 Чатов: {stats['total_chats']}\n"
                    f"• 👥 Уникальных участников: {stats['total_unique_members']}\n"
                    f"• 💬 Уникальных сообщений: {stats['total_unique_messages']}\n"
                    f"• 👤 Уникальных авторов: {stats['unique_authors']}\n\n"
                    f"**Активность за сегодня:**\n"
                    f"• 💬 Новых сообщений: {stats['today_unique_messages']}\n"
                    f"• 👤 Активных авторов: {stats['today_unique_authors']}"
                )
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")]
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
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
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
                    report += f"• 💬 {result['chat_name']}: 👥 {len(result.get('filtered_members', []))} участников, 💬 {len(result.get('filtered_messages', []))} сообщений\n"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Получить статистику", callback_data="stats")],
                    [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")]
                ])
                
                await callback.message.edit_text(
                    report,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
        except Exception as e:
            logger.error(f"Error running analysis: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка при запуске анализа: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
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
                        [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
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
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")]
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
            writer.writerow([
                f"id группы чата: {chat['group_id']}",
                f"{chat['unique_members']} участников,",
                f"{chat['unique_messages']} сообщений"
            ])
        
        return output.getvalue()
    
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
        writer.writerow(["Обработано чатов:", len(vk_chats)])
        writer.writerow([])
        writer.writerow(["Общая статистика:"])
        writer.writerow(["Участников:", stats['total_unique_members']])
        writer.writerow(["Сообщений (за месяц):", stats['total_unique_messages']])
        writer.writerow([])
        
        # Статистика по чатам из CSV файла
        writer.writerow(["2. Статистика по каждому чату:"])
        
        # Получаем данные по чатам из базы данных
        chats_stats = await db.get_chats_stats()
        for chat in chats_stats:
            writer.writerow([
                f"id группы чата: {chat['group_id']}",
                f"{chat['unique_members']} участников,",
                f"{chat['unique_messages']} сообщений"
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
        
        return output.getvalue()
    
    async def handle_export_all_callback(self, callback: types.CallbackQuery):
        """Экспорт всех данных"""
        await callback.answer("Экспортирую все данные...")
        await self._export_data(callback, "all", "Все данные (сводный отчет)")
    
    async def handle_export_chats_callback(self, callback: types.CallbackQuery):
        """Экспорт чатов"""
        await callback.answer("Экспортирую чаты...")
        await self._export_data(callback, "chats", "Чаты")
    
    async def handle_export_users_callback(self, callback: types.CallbackQuery):
        """Экспорт пользователей"""
        await callback.answer("Экспортирую пользователей...")
        await self._export_data(callback, "users", "Пользователи")
    
    async def handle_export_messages_callback(self, callback: types.CallbackQuery):
        """Экспорт сообщений"""
        await callback.answer("Экспортирую сообщения...")
        await self._export_data(callback, "messages", "Сообщения")
    
    async def handle_export_stats_callback(self, callback: types.CallbackQuery):
        """Экспорт статистики"""
        await callback.answer("Экспортирую статистику...")
        await self._export_data(callback, "stats", "Дневная статистика")
    
    async def _export_data(self, callback: types.CallbackQuery, export_type: str, description: str):
        """Общий метод для экспорта данных"""
        try:
            exporter = DataExporter()
            
            # Выбираем метод экспорта
            if export_type == "all":
                csv_data = await exporter.export_all_data_to_csv()
            elif export_type == "chats":
                csv_data = await exporter.export_chats_to_csv()
            elif export_type == "users":
                csv_data = await exporter.export_users_to_csv()
            elif export_type == "messages":
                csv_data = await exporter.export_messages_to_csv()
            elif export_type == "stats":
                csv_data = await exporter.export_daily_stats_to_csv()
            else:
                csv_data = ""
            
            if not csv_data:
                await callback.message.edit_text(
                    f"**Ошибка экспорта {description}**\n\n"
                    "Не удалось получить данные для экспорта.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                        [InlineKeyboardButton(text="📥 Меню экспорта", callback_data="export")]
                    ])
                )
                return
            
            # Создаем файл
            filename = f"vk_{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Отправляем файл
            await callback.message.answer_document(
                types.FSInputFile(
                    io.BytesIO(csv_data.encode('utf-8-sig')),  # UTF-8 BOM для корректного отображения в Excel
                    filename=filename
                ),
                caption=(
                    f"📥 **Экспорт: {description}**\n\n"
                    f"📅 Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 Формат: CSV\n"
                    f"📁 Файл: {filename}"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Меню экспорта", callback_data="export")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error creating export {export_type}: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка при экспорте {description}: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Запустить анализ", callback_data="analyze")],
                    [InlineKeyboardButton(text="📥 Меню экспорта", callback_data="export")]
                ])
            )
    
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
            [InlineKeyboardButton(text="📥 Экспорт данных", callback_data="export")]
        ])
        
        await callback.message.edit_text(
            "🤖 **VK Chat Analyzer Bot**\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def start_polling(self):
        """Запуск бота"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        """Остановка бота"""
        await self.bot.session.close()
