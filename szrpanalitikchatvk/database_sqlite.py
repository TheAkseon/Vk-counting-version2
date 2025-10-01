"""
База данных SQLite 
"""
import asyncio
import aiosqlite
from datetime import datetime, date
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

        async with self.connection.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            from datetime import datetime, date
            
            # Получаем количество чатов
            async with self.connection.execute("SELECT COUNT(*) FROM chats") as cursor:
                total_chats = (await cursor.fetchone())[0] or 0

            # Получаем количество УНИКАЛЬНЫХ участников (из chat_members)
            async with self.connection.execute("SELECT COUNT(DISTINCT vk_id) FROM chat_members WHERE is_active = 1") as cursor:
                total_unique_members = (await cursor.fetchone())[0] or 0

            # Получаем количество УНИКАЛЬНЫХ сообщений
            async with self.connection.execute("SELECT COUNT(DISTINCT message_id) FROM messages") as cursor:
                total_unique_messages = (await cursor.fetchone())[0] or 0

            # Получаем количество уникальных авторов сообщений (из messages)
            async with self.connection.execute("SELECT COUNT(DISTINCT user_id) FROM messages") as cursor:
                unique_authors = (await cursor.fetchone())[0] or 0

            # Получаем статистику за сегодня (только для информации)
            today = date.today()
            async with self.connection.execute("""
                SELECT COUNT(DISTINCT message_id) FROM messages 
                WHERE DATE(date) = ?
            """, (today,)) as cursor:
                today_unique_messages = (await cursor.fetchone())[0] or 0

            # Получаем уникальных авторов сообщений за сегодня
            async with self.connection.execute("""
                SELECT COUNT(DISTINCT user_id) FROM messages 
                WHERE DATE(date) = ?
            """, (today,)) as cursor:
                today_unique_authors = (await cursor.fetchone())[0] or 0

            # Проверяем, есть ли данные
            has_data = total_chats > 0 or total_unique_members > 0 or total_unique_messages > 0

            return {
                'total_chats': total_chats,
                'total_unique_members': total_unique_members,  # Общее количество уникальных участников
                'total_unique_messages': total_unique_messages,  # Общее количество уникальных сообщений
                'unique_authors': unique_authors,  # Общее количество уникальных авторов
                'has_data': has_data,
                'today_unique_messages': today_unique_messages,  # Сообщения за сегодня
                'today_unique_authors': today_unique_authors  # Авторы за сегодня
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                'total_chats': 0,
                'total_unique_members': 0,
                'total_unique_messages': 0,
                'unique_authors': 0,
                'has_data': False,
                'today_unique_messages': 0,
                'today_unique_authors': 0
            }
    
    async def get_chats_stats(self) -> List[Dict[str, Any]]:
        """Получает статистику по каждому чату"""
        try:
            async with self.connection.execute("""
                SELECT 
                    c.group_id,
                    c.title,
                    c.members_count,
                    COUNT(DISTINCT cm.vk_id) as unique_members,
                    COUNT(DISTINCT m.message_id) as unique_messages,
                    COUNT(DISTINCT m.user_id) as unique_authors
                FROM chats c
                LEFT JOIN chat_members cm ON c.id = cm.chat_id AND cm.is_active = 1
                LEFT JOIN messages m ON c.id = m.chat_id
                GROUP BY c.id, c.group_id, c.title, c.members_count
                ORDER BY c.id
            """) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'group_id': row[0],
                        'title': row[1],
                        'members_count': row[2],
                        'unique_members': row[3] or 0,
                        'unique_messages': row[4] or 0,
                        'unique_authors': row[5] or 0
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get chats stats: {e}")
            return []

    async def get_chat_id_by_group_id(self, group_id: str) -> Optional[int]:
        """Получает ID чата по group_id"""
        try:
            async with self.connection.execute("SELECT id FROM chats WHERE group_id = ?", (group_id,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get chat_id by group_id {group_id}: {e}")
            return None

    async def get_today_stats_for_chat(self, chat_id: int) -> Dict[str, int]:
        """Получает статистику за сегодня для конкретного чата"""
        try:
            today = date.today()
            
            # Сообщения за сегодня
            async with self.connection.execute("""
                SELECT COUNT(DISTINCT message_id) FROM messages 
                WHERE chat_id = ? AND DATE(date) = ?
            """, (chat_id, today)) as cursor:
                messages = (await cursor.fetchone())[0] or 0
            
            # Авторы за сегодня
            async with self.connection.execute("""
                SELECT COUNT(DISTINCT user_id) FROM messages 
                WHERE chat_id = ? AND DATE(date) = ?
            """, (chat_id, today)) as cursor:
                authors = (await cursor.fetchone())[0] or 0
            
            return {
                'messages': messages,
                'authors': authors
            }
        except Exception as e:
            logger.error(f"Failed to get today stats for chat {chat_id}: {e}")
            return {'messages': 0, 'authors': 0}

    async def get_chat_members(self, chat_id: int) -> List[int]:
        """Получает список участников чата"""
        try:
            async with self.connection.execute("""
                SELECT DISTINCT vk_id FROM chat_members 
                WHERE chat_id = ? AND is_active = 1
            """, (chat_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0] is not None]
        except Exception as e:
            logger.error(f"Failed to get chat members for chat {chat_id}: {e}")
            return []

    async def save_telegram_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Сохраняет пользователя Telegram"""
        try:
            async with self.connection.execute("""
                INSERT OR REPLACE INTO telegram_users (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, first_name, last_name)):
                pass
        except Exception as e:
            logger.error(f"Failed to save telegram user {user_id}: {e}")

    async def get_all_telegram_users(self) -> List[Dict[str, Any]]:
        """Получает всех пользователей Telegram"""
        try:
            async with self.connection.execute("SELECT user_id, username, first_name, last_name FROM telegram_users") as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get telegram users: {e}")
            return []

# Глобальный экземпляр базы данных
db = Database()
