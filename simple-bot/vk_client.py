"""
Простой VK API клиент
"""
import asyncio
import aiohttp
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
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение запроса к VK API"""
        url = f"{self.base_url}/{method}"
        request_params = {
            "access_token": self.token,
            "v": config.VK_API_VERSION,
            **params
        }
        
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
                    logger.warning(f"Rate limit for {method}: {error_msg}")
                    await asyncio.sleep(1)
                    return await self._make_request(method, params)
                else:
                    logger.error(f"VK API error {error_code}: {error_msg}")
                    return {"response": {"items": []}}
            
            return data
    
    async def get_chat_members(self) -> List[Dict[str, Any]]:
        """Получение участников чата"""
        try:
            response = await self._make_request("messages.getConversationMembers", {
                "peer_id": config.PEER_ID
            })
            
            members = response.get("response", {}).get("items", [])
            real_users = [member["member_id"] for member in members if member.get("member_id", 0) > 0]
            
            logger.info(f"Found {len(real_users)} members")
            return real_users
            
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
                
                # Фильтруем реальные сообщения
                real_messages = [
                    msg for msg in month_messages 
                    if msg.get("from_id", 0) > 0
                ]
                
                all_messages.extend(real_messages)
                
                if len(messages) < batch_size:
                    break
                
                offset += batch_size
                
                # Rate limiting
                await asyncio.sleep(config.RATE_LIMIT_DELAY)
            
            logger.info(f"Found {len(all_messages)} messages")
            return all_messages
            
        except Exception as e:
            logger.error(f"Failed to get chat messages: {e}")
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
