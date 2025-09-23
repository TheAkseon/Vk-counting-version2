"""
Простой анализатор VK чатов
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from loguru import logger
from vk_client import VKClient
from database_sqlite import db
from config import config

class ChatAnalyzer:
    """Простой анализатор чатов"""
    
    def __init__(self):
        self.vk_client = VKClient()
    
    async def analyze_all_chats(self) -> List[Dict[str, Any]]:
        """Анализ всех чатов (как в старом боте)"""
        results = []
        
        logger.info(f"Starting analysis of {len(config.VK_CHATS)} chats")
        
        for i, chat_config in enumerate(config.VK_CHATS):
            group_id = chat_config["group_id"]
            token = chat_config["token"]
            chat_name = f"Chat {i+1}"
            
            try:
                logger.info(f"Analyzing chat {i+1}/{len(config.VK_CHATS)}: {chat_name} (Group ID: {group_id})")
                
                # Создаем VK клиент для этого чата
                vk_client = VKClient(token)
                await vk_client.initialize()
                
                try:
                    # Получаем участников
                    members = await vk_client.get_chat_members()
                    members_count = len(members)
                    
                    # Получаем сообщения
                    messages = await vk_client.get_chat_messages()
                    messages_count = len(messages)
                    
                    # Получаем общее количество сообщений
                    total_messages = await vk_client.get_total_messages_count()
                    
                    # Сохраняем в базу данных
                    chat_id = await db.save_chat(group_id, chat_name, members_count)
                    
                    # Сохраняем пользователей
                    for member_id in members:
                        await db.save_user(str(member_id))
                    
                    # Сохраняем сообщения
                    for message in messages:
                        user_db_id = await db.save_user(str(message.get("from_id", "")))
                        await db.save_message(
                            str(message.get("id", "")),
                            chat_id,
                            user_db_id,
                            message.get("text", ""),
                            datetime.fromtimestamp(message.get("date", 0))
                        )
                    
                    # Сохраняем дневную статистику
                    unique_members = len(set(members))
                    unique_messages = len(set(msg.get("from_id", "") for msg in messages))
                    
                    await db.save_daily_stats(
                        chat_id,
                        datetime.now(),
                        members_count,
                        messages_count,
                        unique_members,
                        unique_messages
                    )
                    
                    result = {
                        "chat_id": group_id,
                        "chat_name": chat_name,
                        "members_count": members_count,
                        "messages_count": messages_count,
                        "total_messages": total_messages,
                        "unique_members": unique_members,
                        "unique_messages": unique_messages,
                        "analysis_date": datetime.now().strftime('%d.%m.%Y %H:%M')
                    }
                    
                    results.append(result)
                    logger.info(f"Chat {group_id} analyzed: {members_count} members, {messages_count} messages")
                    
                finally:
                    await vk_client.close()
                    
            except Exception as e:
                logger.error(f"Failed to analyze chat {group_id}: {e}")
                results.append({
                    "chat_id": group_id,
                    "chat_name": chat_name,
                    "members_count": 0,
                    "messages_count": 0,
                    "total_messages": 0,
                    "unique_members": 0,
                    "unique_messages": 0,
                    "analysis_date": datetime.now().strftime('%d.%m.%Y %H:%M'),
                    "error": str(e)
                })
        
        logger.info(f"Analysis completed: {len(results)} chats processed")
        return results
