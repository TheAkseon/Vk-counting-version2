"""
Простой VK API клиент
"""
import asyncio
import aiohttp
import ssl
from datetime import datetime, timedelta
from typing import List, Dict, Any
from loguru import logger
from config import config

class VKClient:
    """Простой VK API клиент"""
    
    def __init__(self, token: str = None):
        self.session: aiohttp.ClientSession = None
        self.base_url = "https://api.vk.com/method"
        self.token = token or config.VK_CHATS[0]["token"]  # Используем первый токен по умолчанию
    
    async def initialize(self):
        """Инициализация HTTP сессии"""
        # Создаем SSL контекст для обхода проблем с сертификатами
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
    
    async def close(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, params: Dict[str, Any], max_retries: int = 5) -> Dict[str, Any]:
        """Выполнение запроса к VK API с retry логикой"""
        url = f"{self.base_url}/{method}"
        request_params = {
            "access_token": self.token,
            "v": config.VK_API_VERSION,
            **params
        }
        
        for attempt in range(max_retries):
            try:
                async with self.session.get(url, params=request_params) as response:
                    data = await response.json()
                    
                    if "error" in data:
                        error = data["error"]
                        error_code = error.get("error_code", 0)
                        error_msg = error.get("error_msg", "Unknown error")
                        
                        if error_code == 15:  # Access denied
                            logger.warning(f"Access denied for {method}: {error_msg}")
                            return {"response": {"items": []}}
                        elif error_code == 6:  # Too many requests
                            logger.warning(f"Rate limit for {method}: {error_msg} (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1, 2, 4 seconds
                                continue
                            else:
                                logger.error(f"Rate limit exceeded after {max_retries} attempts for {method}")
                                return {"response": {"items": []}}
                        elif error_code == 9:  # Flood control
                            logger.warning(f"Flood control for {method}: {error_msg} (attempt {attempt + 1}/{max_retries})")
                            if attempt < max_retries - 1:
                                # Увеличиваем задержку для Flood control: 10, 15, 20, 25 секунд
                                await asyncio.sleep(10 + (5 * attempt))
                                continue
                            else:
                                logger.error(f"Flood control exceeded after {max_retries} attempts for {method}")
                                return {"response": {"items": []}}
                        else:
                            logger.error(f"VK API error {error_code}: {error_msg}")
                            return {"response": {"items": []}}
                    
                    return data
                    
            except Exception as e:
                logger.error(f"Request failed for {method} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(f"Request failed after {max_retries} attempts for {method}")
                    return {"response": {"items": []}}
        
        return {"response": {"items": []}}
    
    async def get_chat_members(self) -> List[Dict[str, Any]]:
        """Получение участников чата с проверкой удаленных страниц"""
        try:
            response = await self._make_request("messages.getConversationMembers", {
                "peer_id": config.PEER_ID
            })
            
            members = response.get("response", {}).get("items", [])
            # Сначала получаем всех пользователей с положительными ID
            candidate_users = [member["member_id"] for member in members if member.get("member_id", 0) > 0]
            
            if not candidate_users:
                logger.info("No candidate users found")
                return []
            
            # Проверяем статус пользователей через официальный API
            user_statuses = await self.check_users_status(candidate_users)
            
            # Фильтруем только активных пользователей
            active_users = []
            deleted_count = 0
            banned_count = 0
            
            for user_id in candidate_users:
                status = user_statuses.get(user_id, "unknown")
                if status == "active":
                    active_users.append(user_id)
                elif status == "deleted":
                    deleted_count += 1
                elif status == "banned":
                    banned_count += 1
            
            logger.info(f"Found {len(active_users)} active members, {deleted_count} deleted, {banned_count} banned")
            return active_users
            
        except Exception as e:
            logger.error(f"Failed to get chat members: {e}")
            return []
    
    async def get_chat_messages(self, max_messages: int = None) -> List[Dict[str, Any]]:
        """Получение сообщений чата"""
        try:
            if max_messages is None:
                max_messages = config.MAX_MESSAGES
            
            all_messages = []
            offset = 0
            batch_size = 200
            
            while len(all_messages) < max_messages:
                response = await self._make_request("messages.getHistory", {
                    "peer_id": config.PEER_ID,
                    "count": batch_size,
                    "offset": offset
                })
                
                messages = response.get("response", {}).get("items", [])
                if not messages:
                    break
                
                # Фильтруем сообщения за последние 30 дней
                month_ago = int((datetime.now() - timedelta(days=30)).timestamp())
                current_time = int(datetime.now().timestamp())
                
                month_messages = [
                    msg for msg in messages 
                    if month_ago <= msg.get("date", 0) <= current_time
                ]
                
                # Фильтруем сообщения от пользователей с положительными ID
                candidate_messages = [
                    msg for msg in month_messages 
                    if msg.get("from_id", 0) > 0
                ]
                
                all_messages.extend(candidate_messages)
                
                if len(messages) < batch_size:
                    break
                
                offset += batch_size
                
                # Rate limiting
                await asyncio.sleep(config.RATE_LIMIT_DELAY)
            
            # Фильтруем сообщения от удаленных пользователей
            if all_messages:
                # Получаем уникальных авторов сообщений
                unique_authors = list(set(msg.get("from_id", 0) for msg in all_messages if msg.get("from_id", 0) > 0))
                
                if unique_authors:
                    # Проверяем статус авторов
                    author_statuses = await self.check_users_status(unique_authors)
                    
                    # Фильтруем только сообщения от активных пользователей
                    filtered_messages = []
                    deleted_messages = 0
                    banned_messages = 0
                    
                    for msg in all_messages:
                        from_id = msg.get("from_id", 0)
                        if from_id > 0:
                            status = author_statuses.get(from_id, "unknown")
                            if status == "active":
                                filtered_messages.append(msg)
                            elif status == "deleted":
                                deleted_messages += 1
                            elif status == "banned":
                                banned_messages += 1
                    
                    logger.info(f"Found {len(filtered_messages)} messages from active users, {deleted_messages} from deleted, {banned_messages} from banned")
                    return filtered_messages
            
            logger.info(f"Found {len(all_messages)} messages")
            return all_messages
            
        except Exception as e:
            logger.error(f"Failed to get chat messages: {e}")
            return []
    
    async def get_chat_members_from_messages(self) -> List[int]:
        """Получение участников из авторов сообщений (fallback метод)"""
        try:
            messages = await self.get_chat_messages()
            if not messages:
                return []
            
            # Получаем уникальных авторов сообщений
            unique_authors = list(set(msg.get("from_id", 0) for msg in messages if msg.get("from_id", 0) > 0))
            
            if not unique_authors:
                return []
            
            # Проверяем статус авторов
            author_statuses = await self.check_users_status(unique_authors)
            
            # Возвращаем только активных авторов
            active_authors = [user_id for user_id in unique_authors if author_statuses.get(user_id) == "active"]
            
            logger.info(f"Found {len(active_authors)} active members from message authors")
            return active_authors
            
        except Exception as e:
            logger.error(f"Failed to get members from messages: {e}")
            return []
    
    async def get_chat_members_with_fallback(self) -> List[int]:
        """Получение участников с fallback на сообщения"""
        try:
            # Основной метод - получение участников чата
            members = await self.get_chat_members()
            if members:
                return members
        except Exception as e:
            logger.warning(f"Failed to get chat members: {e}")
        
        try:
            # Fallback: участники из авторов сообщений
            logger.info("Using fallback: getting members from message authors")
            members_from_messages = await self.get_chat_members_from_messages()
            if members_from_messages:
                return members_from_messages
        except Exception as e:
            logger.warning(f"Failed to get members from messages: {e}")
        
        return []
    
    async def get_total_messages_count(self) -> int:
        """Получение общего количества сообщений"""
        try:
            response = await self._make_request("messages.getHistory", {
                "peer_id": config.PEER_ID,
                "count": 0
            })
            
            total_count = response.get("response", {}).get("count", 0)
            logger.info(f"Total messages in chat: {total_count}")
            return total_count
            
        except Exception as e:
            logger.error(f"Failed to get total messages count: {e}")
            return 0
    
    async def check_users_status(self, user_ids: List[int]) -> Dict[int, str]:
        """Проверяет статус пользователей через VK API (официальный способ)"""
        try:
            if not user_ids:
                return {}
            
            # VK API позволяет запрашивать до 1000 пользователей за раз
            batch_size = 1000
            all_statuses = {}
            
            for i in range(0, len(user_ids), batch_size):
                batch_ids = user_ids[i:i + batch_size]
                
                response = await self._make_request("users.get", {
                    "user_ids": ",".join(map(str, batch_ids)),
                    "fields": "deactivated"
                })
                
                users = response.get("response", [])
                
                for user in users:
                    user_id = user.get("id")
                    deactivated = user.get("deactivated")
                    # "active" если поле deactivated отсутствует, иначе статус из API
                    status = "active" if not deactivated else deactivated
                    all_statuses[user_id] = status
                
                # Небольшая задержка между запросами
                await asyncio.sleep(0.1)
            
            logger.info(f"Checked status for {len(user_ids)} users, found {len(all_statuses)} responses")
            return all_statuses
            
        except Exception as e:
            logger.error(f"Failed to check users status: {e}")
            return {}
