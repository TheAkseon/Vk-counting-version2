"""
Конфигурация для VK бота 
"""
import json
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from csv_parser import CSVParser

# Загружаем переменные окружения
load_dotenv('.env')

class Config:
    """Конфигурация"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_ADMIN_CHAT_ID = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID', '1383508355'))
    
    # VK API - используем данные из старого config.json + новые чаты
    VK_CHATS = [
        {
            "group_id": "230351857",
            "token": "vk1.a.BF2mzPzhp-1ScgnxeS0BpUhJkuUTXV-ym3lteHFO2BEV6IKy_RmgB7-vVnJWu85UvZXlOljUfkdrrlH-C8bHotjLQ92Gzuhj87rUM_GBw1zZ7In2RlBbt8KQ5Jr-lLOd4yYpDTzBWGZBpEUcHUGkz-T1DJCM3e6ruyTAjaujSnTd8e-d5CjI_R5FlfFiFN7yiFSTvxQrrgeIo0dvzoxqaQ"
        },
        {
            "group_id": "230482562",
            "token": "vk1.a.ipopqLr7oMJgUxShdy07MS0uMArlkf7boNGGqFIX9r1bTCy4fKKEGZm2RRahyhwBSb4u4WSdfzsk0SlLgGbNY313XNOeeFdQAAUwpzjotAWdgOtGAAFva67lVhxuV1msojzr0vwsVMVKlmsDiZ88wWMKhdsz-uphqM9-esxJL6sSqTsMmQVK0sJidujt1Kq5jz04DnlP0sf12ESz5NiGng"
        },
        {
            "group_id": "230482521",
            "token": "vk1.a.Hu6ng24HJBCidlhDjDx5vnxQJObmzo4oApiSsEehiUxShBfu-Q794HQBPWMqApHardJQh-v5z4vysOI5D-4ezkeEP1Wm5A2c5YpXf5pjKLsV-8Udaj3IjKPsmH2gzj2ejWeIlNzYtuSkjPFwQQGNLtZGkX8VK-WoN0MkXp7ATCnlr87cmSPVeGYtq2ar2NZLCp767oeZ1orMi_BcCKUTCQ"
        },
        {
            "group_id": "230547891",
            "token": "vk1.a.wDymbjGGGUuQbHnWqsRpf91Foj2suL3T2505dEhlCEe1ZM3avl0nnxXVdlYETZE6cfxGpd4GlyL_qCsmKL4WaRL4I8NT8jcsme_j_fI_EMqxbQS3CVXVaReB8l3Zcz04ISD1FJ6uRtdwjlSYtuobCqrNibvXZWYhoMplp7fu02wz6vGV5ODP2aiAwD0lEeaIcnfkjcQSFpy8jrwrfB3DkQ"
        }
    ]
    
    VK_API_VERSION = "5.131"
    PEER_ID = 2000000001
    MAX_MESSAGES = 10000
    RATE_LIMIT_DELAY = 0.2  # Уменьшено для множественных токенов
    
    # Database
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'vk_simple_bot')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'vk_user')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'vk_password')
    
    @property
    def database_url(self):
        """URL для подключения к базе данных"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    def get_vk_chats(self) -> List[Dict[str, Any]]:
        """Получает список VK чатов из CSV или fallback на статический список"""
        csv_parser = CSVParser()
        
        # Пытаемся загрузить из CSV
        if csv_parser.is_csv_available():
            chats = csv_parser.parse_csv()
            if chats:
                return chats
        
        # Если CSV недоступен или пустой, возвращаем пустой список
        # Это заставит пользователя загрузить правильный CSV файл
        return []

# Глобальный экземпляр конфигурации
config = Config()
