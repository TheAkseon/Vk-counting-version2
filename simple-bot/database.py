"""
Простая база данных для VK бота
"""
import asyncpg
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
from config import config

class Database:
    """Простая база данных"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Инициализация базы данных"""
        try:
            self.pool = await asyncpg.create_pool(
                config.database_url,
                min_size=5,
                max_size=20
            )
            
            # Создаем таблицы
            await self._create_tables()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _create_tables(self):
        """Создание таблиц"""
        async with self.pool.acquire() as conn:
            # Таблица чатов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id SERIAL PRIMARY KEY,
                    group_id VARCHAR(50) UNIQUE NOT NULL,
                    title VARCHAR(255),
                    members_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) UNIQUE NOT NULL,
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица сообщений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    message_id VARCHAR(50) NOT NULL,
                    chat_id INTEGER REFERENCES chats(id),
                    user_id INTEGER REFERENCES users(id),
                    text TEXT,
                    date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, chat_id)
                )
            """)
            
            # Таблица статистики
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id SERIAL PRIMARY KEY,
                    chat_id INTEGER REFERENCES chats(id),
                    date DATE NOT NULL,
                    members_count INTEGER DEFAULT 0,
                    messages_count INTEGER DEFAULT 0,
                    unique_members INTEGER DEFAULT 0,
                    unique_messages INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, date)
                )
            """)
            
            logger.info("Database tables created successfully")
    
    async def save_chat(self, group_id: str, title: str, members_count: int) -> int:
        """Сохранение чата"""
        async with self.pool.acquire() as conn:
            chat_id = await conn.fetchval("""
                INSERT INTO chats (group_id, title, members_count, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (group_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    members_count = EXCLUDED.members_count,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, group_id, title, members_count)
            
            return chat_id
    
    async def save_user(self, user_id: str, first_name: str = "", last_name: str = "", username: str = "") -> int:
        """Сохранение пользователя"""
        async with self.pool.acquire() as conn:
            user_db_id = await conn.fetchval("""
                INSERT INTO users (user_id, first_name, last_name, username)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    username = EXCLUDED.username
                RETURNING id
            """, user_id, first_name, last_name, username)
            
            return user_db_id
    
    async def save_message(self, message_id: str, chat_id: int, user_id: int, text: str, date: datetime):
        """Сохранение сообщения"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO messages (message_id, chat_id, user_id, text, date)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (message_id, chat_id) DO NOTHING
            """, message_id, chat_id, user_id, text, date)
    
    async def save_daily_stats(self, chat_id: int, date: datetime, members_count: int, messages_count: int, unique_members: int, unique_messages: int):
        """Сохранение дневной статистики"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO daily_stats (chat_id, date, members_count, messages_count, unique_members, unique_messages)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (chat_id, date) DO UPDATE SET
                    members_count = EXCLUDED.members_count,
                    messages_count = EXCLUDED.messages_count,
                    unique_members = EXCLUDED.unique_members,
                    unique_messages = EXCLUDED.unique_messages
            """, chat_id, date.date(), members_count, messages_count, unique_members, unique_messages)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получение статистики"""
        async with self.pool.acquire() as conn:
            # Общая статистика
            total_chats = await conn.fetchval("SELECT COUNT(*) FROM chats")
            total_members = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages")
            
            # Статистика за сегодня
            today = datetime.now().date()
            today_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT ds.chat_id) as chats_count,
                    SUM(ds.members_count) as members_count,
                    SUM(ds.messages_count) as messages_count,
                    SUM(ds.unique_members) as unique_members,
                    SUM(ds.unique_messages) as unique_messages
                FROM daily_stats ds
                WHERE ds.date = $1
            """, today)
            
            return {
                "total_chats": total_chats or 0,
                "total_members": total_members or 0,
                "total_messages": total_messages or 0,
                "today_chats": today_stats["chats_count"] or 0,
                "today_members": today_stats["members_count"] or 0,
                "today_messages": today_stats["messages_count"] or 0,
                "today_unique_members": today_stats["unique_members"] or 0,
                "today_unique_messages": today_stats["unique_messages"] or 0
            }
    
    async def close(self):
        """Закрытие соединения"""
        if self.pool:
            await self.pool.close()

# Глобальный экземпляр базы данных
db = Database()
