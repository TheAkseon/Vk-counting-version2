"""
Модуль для экспорта данных в CSV
"""
import csv
import io
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger
from database_sqlite import db

class DataExporter:
    """Экспортер данных в CSV"""
    
    def __init__(self):
        self.db = db
    
    async def export_chats_to_csv(self) -> str:
        """Экспорт чатов в CSV"""
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow([
                'Chat ID', 'Title', 'Members Count', 'Created At', 'Updated At'
            ])
            
            # Получаем данные из базы
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT group_id, title, members_count, created_at, updated_at
                    FROM chats
                    ORDER BY created_at DESC
                """)
                
                for row in rows:
                    writer.writerow([
                        row['group_id'],
                        row['title'],
                        row['members_count'],
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                        row['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export chats: {e}")
            return ""
    
    async def export_users_to_csv(self) -> str:
        """Экспорт пользователей в CSV"""
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow([
                'User ID', 'First Name', 'Last Name', 'Username', 'Created At'
            ])
            
            # Получаем данные из базы
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT user_id, first_name, last_name, username, created_at
                    FROM users
                    ORDER BY created_at DESC
                """)
                
                for row in rows:
                    writer.writerow([
                        row['user_id'],
                        row['first_name'] or '',
                        row['last_name'] or '',
                        row['username'] or '',
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export users: {e}")
            return ""
    
    async def export_messages_to_csv(self) -> str:
        """Экспорт сообщений в CSV"""
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow([
                'Message ID', 'Chat ID', 'User ID', 'Text', 'Date', 'Created At'
            ])
            
            # Получаем данные из базы
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT m.message_id, m.chat_id, m.user_id, m.text, m.date, m.created_at
                    FROM messages m
                    ORDER BY m.date DESC
                    LIMIT 10000
                """)
                
                for row in rows:
                    writer.writerow([
                        row['message_id'],
                        row['chat_id'],
                        row['user_id'],
                        (row['text'] or '')[:500],  # Ограничиваем длину текста
                        row['date'].strftime('%Y-%m-%d %H:%M:%S') if row['date'] else '',
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export messages: {e}")
            return ""
    
    async def export_daily_stats_to_csv(self) -> str:
        """Экспорт дневной статистики в CSV"""
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            writer.writerow([
                'Chat ID', 'Date', 'Members Count', 'Messages Count', 
                'Unique Members', 'Unique Messages', 'Created At'
            ])
            
            # Получаем данные из базы
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT ds.chat_id, ds.date, ds.members_count, ds.messages_count,
                           ds.unique_members, ds.unique_messages, ds.created_at,
                           c.group_id
                    FROM daily_stats ds
                    JOIN chats c ON ds.chat_id = c.id
                    ORDER BY ds.date DESC, ds.chat_id
                """)
                
                for row in rows:
                    writer.writerow([
                        row['group_id'],
                        row['date'].strftime('%Y-%m-%d'),
                        row['members_count'],
                        row['messages_count'],
                        row['unique_members'],
                        row['unique_messages'],
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export daily stats: {e}")
            return ""
    
    async def export_all_data_to_csv(self) -> str:
        """Экспорт всех данных в один CSV файл"""
        try:
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки для сводного отчета
            writer.writerow([
                'Data Type', 'Chat ID', 'Title', 'Members Count', 'Messages Count',
                'Unique Members', 'Unique Messages', 'Date', 'Created At'
            ])
            
            # Получаем сводные данные
            async with self.db.pool.acquire() as conn:
                # Статистика по чатам
                chat_stats = await conn.fetch("""
                    SELECT 
                        c.group_id,
                        c.title,
                        c.members_count,
                        COUNT(DISTINCT m.id) as messages_count,
                        COUNT(DISTINCT m.user_id) as unique_members,
                        COUNT(DISTINCT m.message_id) as unique_messages,
                        MAX(m.date) as last_message_date,
                        c.created_at
                    FROM chats c
                    LEFT JOIN messages m ON c.id = m.chat_id
                    GROUP BY c.id, c.group_id, c.title, c.members_count, c.created_at
                    ORDER BY c.created_at DESC
                """)
                
                for row in chat_stats:
                    writer.writerow([
                        'Chat Summary',
                        row['group_id'],
                        row['title'],
                        row['members_count'],
                        row['messages_count'],
                        row['unique_members'],
                        row['unique_messages'],
                        row['last_message_date'].strftime('%Y-%m-%d %H:%M:%S') if row['last_message_date'] else '',
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
                
                # Дневная статистика
                daily_stats = await conn.fetch("""
                    SELECT 
                        c.group_id,
                        ds.date,
                        ds.members_count,
                        ds.messages_count,
                        ds.unique_members,
                        ds.unique_messages,
                        ds.created_at
                    FROM daily_stats ds
                    JOIN chats c ON ds.chat_id = c.id
                    ORDER BY ds.date DESC, c.group_id
                """)
                
                for row in daily_stats:
                    writer.writerow([
                        'Daily Stats',
                        row['group_id'],
                        '',
                        row['members_count'],
                        row['messages_count'],
                        row['unique_members'],
                        row['unique_messages'],
                        row['date'].strftime('%Y-%m-%d'),
                        row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export all data: {e}")
            return ""
