"""
Анализатор чатов с логикой старого бота
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from loguru import logger

from config import config
from database_sqlite import db
from vk_client import VKClient

class OldLogicChatAnalyzer:
    """Анализатор чатов с логикой старого бота"""
    
    def __init__(self):
        self.db = db
        self.total_members = 0
        self.total_messages = 0
        self.duplicated_users = 0
        self.filtered_messages = 0
        self.all_results = []
        self.user_chats = {}  # user_id -> [chat_names]
        self.duplicated_users_set = set()
    
    async def analyze_all_chats(self) -> List[Dict[str, Any]]:
        """Анализ всех чатов с логикой старого бота"""
        logger.info(f"Starting analysis of {len(config.VK_CHATS)} chats with old logic")
        
        # Шаг 1: Анализируем каждый чат отдельно
        for i, chat_config in enumerate(config.VK_CHATS):
            group_id = chat_config["group_id"]
            token = chat_config["token"]
            chat_name = f"Chat {i+1}"
            
            try:
                logger.info(f"Analyzing chat {i+1}/{len(config.VK_CHATS)}: {chat_name} (Group ID: {group_id})")
                
                result = await self._analyze_single_chat(group_id, token, chat_name)
                if result:
                    self.all_results.append(result)
                    
            except Exception as e:
                logger.error(f"Failed to analyze chat {group_id}: {e}")
        
        # Шаг 2: Анализируем дублирование пользователей
        duplication_info = self._analyze_user_duplication()
        logger.info(f"Duplication analysis: {duplication_info['duplication_stats']}")
        
        # Шаг 3: Фильтруем данные (исключаем дублированных пользователей)
        filtered_results = self._filter_duplicated_data(duplication_info['duplicated_users'])
        
        # Шаг 4: Сохраняем в базу данных
        await self._save_to_database(filtered_results)
        
        # Шаг 5: Возвращаем итоговую статистику
        return self._calculate_final_stats(filtered_results)
    
    async def _analyze_single_chat(self, group_id: str, token: str, chat_name: str) -> Dict[str, Any]:
        """Анализ одного чата (как в старом боте)"""
        try:
            vk_client = VKClient(token)
            await vk_client.initialize()
            
            # Получаем участников
            members = await vk_client.get_chat_members()
            real_users = [user_id for user_id in members if user_id > 0]
            members_count = len(real_users)
            
            # Получаем сообщения за последний месяц
            messages = await vk_client.get_chat_messages()
            month_ago = int((datetime.now() - timedelta(days=30)).timestamp())
            current_time = int(datetime.now().timestamp())
            
            month_messages = [
                msg for msg in messages 
                if month_ago <= msg.get('date', 0) <= current_time
            ]
            real_month_messages = [
                msg for msg in month_messages 
                if msg.get('from_id', 0) > 0
            ]
            
            # Получаем общее количество сообщений
            total_messages = await vk_client.get_total_messages_count()
            
            result = {
                "chat_name": chat_name,
                "group_id": group_id,
                "peer_id": 2000000001,
                "all_members": real_users,
                "all_messages": real_month_messages,
                "members_count": members_count,
                "messages_last_month": len(real_month_messages),
                "total_messages": total_messages,
                "analysis_date": datetime.now().strftime('%d.%m.%Y %H:%M')
            }
            
            logger.info(f"Chat {group_id} analyzed: {members_count} members, {len(real_month_messages)} messages")
            
            await vk_client.close()
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing chat {group_id}: {e}")
            return None
    
    def _analyze_user_duplication(self) -> Dict[str, Any]:
        """Анализирует дублирование пользователей между чатами (как в старом боте)"""
        user_chats = {}
        
        for result in self.all_results:
            chat_name = result['chat_name']
            for user_id in result['all_members']:
                if user_id not in user_chats:
                    user_chats[user_id] = []
                user_chats[user_id].append(chat_name)
        
        duplicated_users = []
        unique_users = []
        
        for user_id, chats in user_chats.items():
            if len(chats) > 2:  # Дублированный если в более чем 2 чатах
                duplicated_users.append(user_id)
            else:
                unique_users.append(user_id)
        
        self.user_chats = user_chats
        self.duplicated_users_set = set(duplicated_users)
        
        return {
            'user_chats': user_chats,
            'duplicated_users': duplicated_users,
            'unique_users': unique_users,
            'duplication_stats': {
                'total_users': len(user_chats),
                'duplicated_count': len(duplicated_users),
                'unique_count': len(unique_users)
            }
        }
    
    def _filter_duplicated_data(self, duplicated_users: List[int]) -> List[Dict[str, Any]]:
        """Фильтрует данные, исключая дублированных пользователей (как в старом боте)"""
        filtered_results = []
        
        for result in self.all_results:
            # Фильтруем участников
            filtered_members = [
                user_id for user_id in result['all_members'] 
                if user_id not in duplicated_users
            ]
            
            # Фильтруем сообщения
            filtered_messages = [
                msg for msg in result['all_messages']
                if msg.get('from_id', 0) not in duplicated_users
            ]
            
            # Создаем отфильтрованный результат
            filtered_result = {
                "chat_name": result['chat_name'],
                "group_id": result['group_id'],
                "peer_id": result['peer_id'],
                "members_count": len(filtered_members),
                "messages_last_month": len(filtered_messages),
                "total_messages": result['total_messages'],
                "analysis_date": result['analysis_date'],
                "excluded_members": len(result['all_members']) - len(filtered_members),
                "excluded_messages": len(result['all_messages']) - len(filtered_messages),
                "filtered_members": filtered_members,
                "filtered_messages": filtered_messages
            }
            
            filtered_results.append(filtered_result)
        
        return filtered_results
    
    async def _save_to_database(self, filtered_results: List[Dict[str, Any]]):
        """Сохраняет отфильтрованные данные в базу данных"""
        try:
            for result in filtered_results:
                # Сохраняем чат
                chat_id = await db.save_chat(
                    result['group_id'], 
                    result['chat_name'], 
                    result['members_count']
                )
                
                # Сохраняем пользователей
                for user_id in result['filtered_members']:
                    user_db_id = await db.save_user(str(user_id))
                    await db.save_chat_member(
                        chat_id, user_db_id, str(user_id), "", "", ""
                    )
                
                # Сохраняем сообщения
                for message in result['filtered_messages']:
                    user_vk_id = str(message.get("from_id", ""))
                    user_db_id = await db.save_user(user_vk_id)
                    await db.save_message(
                        str(message.get("id", "")),
                        chat_id,
                        user_db_id,
                        message.get("text", ""),
                        datetime.fromtimestamp(message.get("date", 0))
                    )
                
                # Сохраняем дневную статистику
                unique_members = len(set(result['filtered_members']))
                unique_messages = len(set(msg.get("from_id", "") for msg in result['filtered_messages']))
                
                await db.save_daily_stats(
                    chat_id,
                    datetime.now(),
                    result['members_count'],
                    result['messages_last_month'],
                    unique_members,
                    unique_messages
                )
                
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
    
    def _calculate_final_stats(self, filtered_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Вычисляет итоговую статистику (как в старом боте)"""
        total_members = sum(result['members_count'] for result in filtered_results)
        total_messages = sum(result['messages_last_month'] for result in filtered_results)
        total_excluded_members = sum(result['excluded_members'] for result in filtered_results)
        total_excluded_messages = sum(result['excluded_messages'] for result in filtered_results)
        
        logger.info(f"Final stats: {len(filtered_results)} chats, {total_members} unique members, {total_messages} messages")
        logger.info(f"Excluded: {total_excluded_members} members, {total_excluded_messages} messages")
        
        return filtered_results
