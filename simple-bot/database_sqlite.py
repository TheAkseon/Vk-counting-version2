"""
База данных SQLite 
"""
import asyncio
import aiosqlite
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from config import config

class Database:
    """Класс для работы с базой данных SQLite"""
    def __init__(self):
        self.db_path = "vk_simple_bot.db"
        self.connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Инициализация базы данных"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            await self._create_indexes()
            logger.info("SQLite database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("SQLite database connection closed")

    async def _create_tables(self):
        """Создание таблиц"""
        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                title TEXT,
                members_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """):
            pass

        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """):
            pass

        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS chat_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER REFERENCES chats(id),
                user_id INTEGER REFERENCES users(id),
                vk_id TEXT,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, user_id),
                UNIQUE(vk_id)
            )
        """):
            pass

        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                chat_id INTEGER REFERENCES chats(id),
                user_id INTEGER REFERENCES users(id),
                text TEXT,
                date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id, chat_id)
            )
        """):
            pass

        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER REFERENCES chats(id),
                stat_date DATE NOT NULL,
                total_members INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                unique_members INTEGER DEFAULT 0,
                unique_messages INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, stat_date)
            )
        """):
            pass

        await self.connection.commit()

    async def _create_indexes(self):
        """Создание индексов"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_chats_group_id ON chats(group_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_vk_id ON users(vk_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_members_chat_id ON chat_members(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_members_user_id ON chat_members(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_chat_id ON daily_stats(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(stat_date)"
        ]

        for index_sql in indexes:
            async with self.connection.execute(index_sql):
                pass

        await self.connection.commit()

    async def save_chat(self, group_id: str, title: str, members_count: int) -> int:
        """Сохраняет или обновляет информацию о чате"""
        async with self.connection.execute("""
            INSERT OR REPLACE INTO chats (group_id, title, members_count, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (group_id, title, members_count)):
            pass

        async with self.connection.execute("""
            SELECT id FROM chats WHERE group_id = ?
        """, (group_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def save_user(self, vk_id: str, first_name: str = "", last_name: str = "", username: str = "") -> int:
        """Сохраняет или обновляет информацию о пользователе"""
        async with self.connection.execute("""
            INSERT OR REPLACE INTO users (vk_id, first_name, last_name, username, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (vk_id, first_name, last_name, username)):
            pass

        async with self.connection.execute("""
            SELECT id FROM users WHERE vk_id = ?
        """, (vk_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def save_chat_member(self, chat_id: int, user_id: int, vk_id: str, first_name: str, last_name: str, username: str):
        """Сохраняет или обновляет участника чата"""
        async with self.connection.execute("""
            INSERT OR REPLACE INTO chat_members (chat_id, user_id, vk_id, first_name, last_name, username, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (chat_id, user_id, vk_id, first_name, last_name, username)):
            pass

    async def save_message(self, message_id: str, chat_id: int, user_id: int, text: str, date: datetime):
        """Сохраняет сообщение"""
        async with self.connection.execute("""
            INSERT OR IGNORE INTO messages (message_id, chat_id, user_id, text, date)
            VALUES (?, ?, ?, ?, ?)
        """, (message_id, chat_id, user_id, text, date)):
            pass

    async def save_daily_stats(self, chat_id: int, stat_date: datetime, total_members: int, total_messages: int, unique_members: int, unique_messages: int):
        """Сохраняет ежедневную статистику"""
        async with self.connection.execute("""
            INSERT OR REPLACE INTO daily_stats (chat_id, stat_date, total_members, total_messages, unique_members, unique_messages)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, stat_date.date(), total_members, total_messages, unique_members, unique_messages)):
            pass

    async def get_latest_stats(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получает последнюю статистику по чату или по всем чатам"""
        if chat_id:
            async with self.connection.execute("""
                SELECT 
                    ds.stat_date,
                    ds.total_members,
                    ds.total_messages,
                    ds.unique_members,
                    ds.unique_messages,
                    c.title as chat_name,
                    c.group_id
                FROM daily_stats ds
                JOIN chats c ON ds.chat_id = c.id
                WHERE ds.chat_id = ?
                ORDER BY ds.stat_date DESC
                LIMIT 1
            """, (chat_id,)) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self.connection.execute("""
                SELECT 
                    ds.stat_date,
                    ds.total_members,
                    ds.total_messages,
                    ds.unique_members,
                    ds.unique_messages,
                    c.title as chat_name,
                    c.group_id
                FROM daily_stats ds
                JOIN chats c ON ds.chat_id = c.id
                WHERE ds.stat_date = (SELECT MAX(stat_date) FROM daily_stats)
                ORDER BY c.title
            """) as cursor:
                rows = await cursor.fetchall()

        return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Получает общую статистику"""
        try:
            # Получаем количество чатов
            async with self.connection.execute("SELECT COUNT(*) FROM chats") as cursor:
                total_chats = (await cursor.fetchone())[0] or 0

            # Получаем общее количество участников
            async with self.connection.execute("SELECT SUM(members_count) FROM chats") as cursor:
                total_members = (await cursor.fetchone())[0] or 0

            # Получаем общее количество сообщений
            async with self.connection.execute("SELECT COUNT(*) FROM messages") as cursor:
                total_messages = (await cursor.fetchone())[0] or 0

            # Получаем количество уникальных пользователей
            async with self.connection.execute("SELECT COUNT(DISTINCT user_id) FROM messages") as cursor:
                unique_users = (await cursor.fetchone())[0] or 0

            return {
                'total_chats': total_chats,
                'total_members': total_members,
                'total_messages': total_messages,
                'unique_users': unique_users
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                'total_chats': 0,
                'total_members': 0,
                'total_messages': 0,
                'unique_users': 0
            }

# Глобальный экземпляр базы данных
db = Database()
