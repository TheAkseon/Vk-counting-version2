"""
Анализатор чатов 
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from loguru import logger

from config import config
from database_sqlite import db
from vk_client import VKClient

class ChatAnalyzer:
    """Анализатор чатов"""
    
    def __init__(self, db_instance=None):
        self.db = db_instance or db
        self.total_members = 0
        self.total_messages = 0
        self.duplicated_users = 0
        self.filtered_messages = 0
        self.all_results = []
        self.user_chats = {}  # user_id -> [chat_names]
        self.duplicated_users_set = set()
    
    async def analyze_all_chats(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Анализ всех чатов с логикой старого бота"""
        # Получаем чаты из CSV или fallback на статический список
        vk_chats = config.get_vk_chats()
        
        if not vk_chats:
            logger.error("No VK chats available for analysis. Please upload CSV file first.")
            return []
        
        logger.info(f"Starting parallel analysis of {len(vk_chats)} chats with old logic")
        
        # Если чатов много, обрабатываем пакетами
        if len(vk_chats) > batch_size:
            return await self._analyze_chats_in_batches(batch_size)
        
        # Шаг 1: Анализируем чаты параллельно (по 20 одновременно)
        semaphore = asyncio.Semaphore(20)  # Максимум 20 параллельных чатов
        
        async def analyze_chat_with_semaphore(chat_config, index):
            async with semaphore:
                group_id = chat_config["group_id"]
                token = chat_config["token"]
                chat_name = f"Chat {index+1}"
                
                try:
                    logger.info(f"Analyzing chat {index+1}/{len(config.VK_CHATS)}: {chat_name} (Group ID: {group_id})")
                    return await self._analyze_single_chat(group_id, token, chat_name)
                except Exception as e:
                    logger.error(f"Failed to analyze chat {group_id}: {e}")
                    return None
        
        # Создаем задачи для всех чатов
        tasks = [
            analyze_chat_with_semaphore(chat_config, i) 
            for i, chat_config in enumerate(vk_chats)
        ]
        
        # Обрабатываем все чаты параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем успешные результаты
        self.all_results = [r for r in results if r is not None and not isinstance(r, Exception)]
        
        logger.info(f"Successfully analyzed {len(self.all_results)} out of {len(vk_chats)} chats")
        
        # Шаг 2: Анализируем дублирование пользователей
        duplication_info = self._analyze_user_duplication()
        logger.info(f"Duplication analysis: {duplication_info['duplication_stats']}")
        
        # Шаг 3: Фильтруем данные (исключаем дублированных пользователей)
        filtered_results = self._filter_duplicated_data(duplication_info['duplicated_users'])
        
        # Шаг 4: Сохраняем в базу данных 
        await self._save_to_database_optimized(filtered_results)
        
        # Шаг 5: Возвращаем итоговую статистику
        return self._calculate_final_stats(filtered_results)
    
    async def _analyze_single_chat(self, group_id: str, token: str, chat_name: str) -> Dict[str, Any]:
        """Анализ одного чата"""
        try:
            vk_client = VKClient(token)
            await vk_client.initialize()
            
            # Параллельно получаем участников и общее количество сообщений
            members_task = asyncio.create_task(vk_client.get_chat_members())
            total_task = asyncio.create_task(vk_client.get_total_messages_count())
            
            # Получаем участников и общее количество параллельно
            members, total_messages = await asyncio.gather(members_task, total_task)
            
            # Участники уже отфильтрованы в VK Client (удалены неактивные пользователи)
            real_users = members
            members_count = len(real_users)
            
            # Получаем сообщения за последний месяц
            messages = await vk_client.get_chat_messages()
            month_ago = int((datetime.now() - timedelta(days=30)).timestamp())
            current_time = int(datetime.now().timestamp())
            
            month_messages = [
                msg for msg in messages 
                if month_ago <= msg.get('date', 0) <= current_time
            ]
            # Сообщения уже отфильтрованы в VK Client (удалены от неактивных пользователей)
            real_month_messages = month_messages
            
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
        """Анализирует дублирование пользователей между чатами"""
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
            if len(chats) > 1:  # Дублированный если в более чем 1 чате
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
        """Фильтрует данные, оставляя только пользователей из одного чата"""
        filtered_results = []
        
        for result in self.all_results:
            # Фильтруем участников (исключаем только дублированных, удаленные уже отфильтрованы)
            filtered_members = [
                user_id for user_id in result['all_members'] 
                if user_id not in duplicated_users
            ]
            
            # Фильтруем сообщения (исключаем только от дублированных пользователей, удаленные уже отфильтрованы)
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
    
    async def _save_to_database_optimized(self, filtered_results: List[Dict[str, Any]]):
        """Сохранение отфильтрованных данных в базу данных"""
        try:
            # Убеждаемся, что база данных инициализирована
            if not hasattr(self.db, 'connection') or self.db.connection is None:
                await self.db.initialize()
            # Собираем все данные для batch операций
            all_users = set()
            all_messages = []
            all_stats = []
            
            # Предварительно собираем всех пользователей
            for result in filtered_results:
                all_users.update(str(user_id) for user_id in result['filtered_members'])
                all_users.update(str(msg.get("from_id", "")) for msg in result['filtered_messages'])
            
            # Batch сохранение пользователей
            user_id_map = {}
            logger.info(f"Saving {len(all_users)} users to database")
            for user_id in all_users:
                if user_id:
                    db_user_id = await self.db.save_user(user_id)
                    user_id_map[user_id] = db_user_id
            
            # Обрабатываем каждый чат
            logger.info(f"Processing {len(filtered_results)} chats for database saving")
            for result in filtered_results:
                # Сохраняем чат
                logger.info(f"Saving chat {result['chat_name']} with {len(result['filtered_members'])} members")
                chat_id = await self.db.save_chat(
                    result['group_id'], 
                    result['chat_name'], 
                    len(result['filtered_members'])
                )
                
                # Сохраняем участников чата
                for user_id in result['filtered_members']:
                    if str(user_id) in user_id_map:
                        await self.db.save_chat_member(
                            chat_id, user_id_map[str(user_id)], str(user_id), "", "", ""
                        )
                
                # Собираем сообщения для batch сохранения
                for message in result['filtered_messages']:
                    user_vk_id = str(message.get("from_id", ""))
                    if user_vk_id in user_id_map:
                        all_messages.append((
                            str(message.get("id", "")),
                            chat_id,
                            user_id_map[user_vk_id],
                            message.get("text", ""),
                            datetime.fromtimestamp(message.get("date", 0))
                        ))
                
                # Собираем статистику
                unique_members = len(set(result['filtered_members']))
                unique_messages = len(set(msg.get("from_id", "") for msg in result['filtered_messages']))
                
                all_stats.append((
                    chat_id,
                    datetime.now(),
                    len(result['filtered_members']),
                    len(result['filtered_messages']),
                    unique_members,
                    unique_messages
                ))
            
            # Batch сохранение сообщений
            for message_data in all_messages:
                await self.db.save_message(*message_data)
            
            # Batch сохранение статистики
            for stats_data in all_stats:
                await self.db.save_daily_stats(*stats_data)
            
            # Коммитим все изменения
            await self.db.connection.commit()
            logger.info(f"Saved {len(all_messages)} messages and {len(all_stats)} stats records")
                
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
    
    def _calculate_final_stats(self, filtered_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Вычисляет итоговую статистику"""
        # Считаем уникальных участников (без дублирования между чатами)
        all_unique_members = set()
        for result in filtered_results:
            all_unique_members.update(result['filtered_members'])
        
        total_unique_members = len(all_unique_members)
        total_messages = sum(len(result['filtered_messages']) for result in filtered_results)
        total_excluded_members = sum(result['excluded_members'] for result in filtered_results)
        total_excluded_messages = sum(result['excluded_messages'] for result in filtered_results)
        
        logger.info(f"Final stats: {len(filtered_results)} chats, {total_unique_members} unique members, {total_messages} messages")
        logger.info(f"Excluded: {total_excluded_members} members, {total_excluded_messages} messages")
        
        return filtered_results
    
    async def _analyze_chats_in_batches(self, batch_size: int) -> List[Dict[str, Any]]:
        """Анализ чатов пакетами для больших объемов"""
        vk_chats = config.get_vk_chats()
        logger.info(f"Processing {len(vk_chats)} chats in batches of {batch_size}")
        
        all_results = []
        total_batches = (len(vk_chats) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(vk_chats))
            batch_chats = vk_chats[start_idx:end_idx]
            
            logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_chats)} chats)")
            
            try:
                # Анализируем текущий пакет
                batch_results = await self._analyze_single_batch(batch_chats)
                all_results.extend(batch_results)
                
                # Сохраняем промежуточные результаты
                await self._save_batch_results(batch_results, batch_num)
            except Exception as e:
                logger.error(f"Error processing batch {batch_num + 1}: {e}")
            
            # Небольшая пауза между пакетами
            if batch_num < total_batches - 1:
                await asyncio.sleep(2)
        
        logger.info(f"Completed processing all {len(vk_chats)} chats")
        return all_results
    
    async def _analyze_single_batch(self, batch_chats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Анализ одного пакета чатов"""
        semaphore = asyncio.Semaphore(20)  # Максимум 20 параллельных чатов
        
        async def analyze_chat_with_semaphore(chat_config, index):
            async with semaphore:
                group_id = chat_config["group_id"]
                token = chat_config["token"]
                chat_name = chat_config.get("chat_name", f"Chat {index+1}")
                
                try:
                    logger.info(f"Analyzing chat {index+1}/{len(batch_chats)}: {chat_name} (Group ID: {group_id})")
                    return await self._analyze_single_chat(group_id, token, chat_name)
                except Exception as e:
                    logger.error(f"Failed to analyze chat {group_id}: {e}")
                    return None
        
        # Создаем задачи для всех чатов в пакете
        tasks = [
            analyze_chat_with_semaphore(chat_config, i) 
            for i, chat_config in enumerate(batch_chats)
        ]
        
        # Обрабатываем все чаты параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем успешные результаты
        return [r for r in results if r is not None and not isinstance(r, Exception)]
    
    async def _save_batch_results(self, batch_results: List[Dict[str, Any]], batch_num: int):
        """Сохранение результатов пакета"""
        try:
            logger.info(f"Saving batch {batch_num + 1} results ({len(batch_results)} chats)")
            
            # Анализируем дублирование для текущего пакета
            duplication_info = self._analyze_user_duplication_for_batch(batch_results)
            
            # Фильтруем данные
            filtered_results = self._filter_duplicated_data(duplication_info['duplicated_users'])
            
            # Сохраняем в базу данных
            await self._save_to_database_optimized(filtered_results)
            
            logger.info(f"Batch {batch_num + 1} saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save batch {batch_num + 1}: {e}")
    
    def _analyze_user_duplication_for_batch(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализирует дублирование пользователей для пакета"""
        user_chats = {}
        
        for result in batch_results:
            chat_name = result['chat_name']
            for user_id in result['all_members']:
                if user_id not in user_chats:
                    user_chats[user_id] = []
                user_chats[user_id].append(chat_name)
        
        duplicated_users = []
        unique_users = []
        
        for user_id, chats in user_chats.items():
            if len(chats) > 1:  # Дублированный если в более чем 1 чате
                duplicated_users.append(user_id)
            else:
                unique_users.append(user_id)
        
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
