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
        self.dp.callback_query.register(self.handle_stats_callback, lambda c: c.data == "stats")
        self.dp.callback_query.register(self.handle_analyze_callback, lambda c: c.data == "analyze")
        self.dp.callback_query.register(self.handle_export_callback, lambda c: c.data == "export")
        self.dp.callback_query.register(self.handle_export_all_callback, lambda c: c.data == "export_all")
        self.dp.callback_query.register(self.handle_export_chats_callback, lambda c: c.data == "export_chats")
        self.dp.callback_query.register(self.handle_export_users_callback, lambda c: c.data == "export_users")
        self.dp.callback_query.register(self.handle_export_messages_callback, lambda c: c.data == "export_messages")
        self.dp.callback_query.register(self.handle_export_stats_callback, lambda c: c.data == "export_stats")
    
    async def start_command(self, message: types.Message):
        """Обработчик команды /start"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
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
                total_members = sum(len(r.get('filtered_members', [])) for r in results)
                total_messages = sum(len(r.get('filtered_messages', [])) for r in results)
                total_unique_members = sum(len(r.get('filtered_members', [])) for r in results)
                total_unique_messages = sum(len(r.get('filtered_messages', [])) for r in results)
                
                report = (
                    f"✅ **Анализ завершен!**\n\n"
                    f"📅 Дата: {results[0]['analysis_date']}\n"
                    f"📊 Обработано чатов: {len(results)}\n\n"
                    f"**Общая статистика:**\n"
                    f"👥 Участников: {total_members}\n"
                    f"💬 Сообщений (за месяц): {total_messages}\n"
                    f"🔢 Уникальных участников: {total_unique_members}\n"
                    f"🔢 Уникальных сообщений: {total_unique_messages}\n\n"
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
        """Обработчик экспорта данных - показывает меню"""
        await callback.answer("📥 Выберите тип экспорта...")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Все данные (сводный отчет)", callback_data="export_all")],
            [InlineKeyboardButton(text="💬 Чаты", callback_data="export_chats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="export_users")],
            [InlineKeyboardButton(text="💬 Сообщения", callback_data="export_messages")],
            [InlineKeyboardButton(text="📈 Статистика", callback_data="export_stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="stats")]
        ])
        
        await callback.message.edit_text(
            "📥 **Экспорт данных**\n\n"
            "Выберите тип данных для экспорта:",
            reply_markup=keyboard
        )
    
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
    
    async def start_polling(self):
        """Запуск бота"""
        logger.info("Starting Telegram bot...")
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        """Остановка бота"""
        await self.bot.session.close()
