"""
Парсер CSV файла с данными VK чатов
"""
import csv
import os
from typing import List, Dict, Any
from loguru import logger

class CSVParser:
    """Простой парсер CSV файла с чатами"""
    
    def __init__(self, csv_file_path: str = "data/vk_chats.csv"):
        self.csv_file_path = csv_file_path
        self.data_dir = "data"
    
    def ensure_data_dir(self):
        """Создает папку data если её нет"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"Created data directory: {self.data_dir}")
    
    def parse_csv(self) -> List[Dict[str, Any]]:
        """Парсит CSV файл и возвращает список чатов"""
        try:
            if not os.path.exists(self.csv_file_path):
                logger.warning(f"CSV file not found: {self.csv_file_path}")
                return []
            
            chats = []
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row_num, row in enumerate(reader, start=2):  # Начинаем с 2 (пропускаем заголовок)
                    try:
                        # Валидация обязательных полей
                        if not row.get('group_id') or not row.get('token'):
                            logger.warning(f"Row {row_num}: Missing group_id or token, skipping")
                            continue
                        
                        # Создаем объект чата в том же формате что и config.py
                        chat = {
                            "group_id": str(row['group_id']).strip(),
                            "token": str(row['token']).strip(),
                            "chat_name": str(row.get('chat_name', f"Chat {len(chats) + 1}")).strip(),
                            "is_active": str(row.get('is_active', '1')).strip() == '1'
                        }
                        
                        # Проверяем что чат активен
                        if chat['is_active']:
                            chats.append(chat)
                            logger.debug(f"Added chat: {chat['chat_name']} (ID: {chat['group_id']})")
                        else:
                            logger.debug(f"Skipped inactive chat: {chat['chat_name']}")
                            
                    except Exception as e:
                        logger.error(f"Error parsing row {row_num}: {e}")
                        continue
            
            logger.info(f"Successfully parsed {len(chats)} active chats from CSV")
            return chats
            
        except Exception as e:
            logger.error(f"Failed to parse CSV file: {e}")
            return []
    
    def save_csv(self, csv_content: str) -> bool:
        """Сохраняет CSV контент в файл"""
        try:
            self.ensure_data_dir()
            
            with open(self.csv_file_path, 'w', encoding='utf-8-sig') as file:
                file.write(csv_content)
            
            logger.info(f"CSV file saved: {self.csv_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save CSV file: {e}")
            return False
    
    def get_csv_template(self) -> str:
        """Возвращает шаблон CSV файла"""
        template = """group_id,token,chat_name,is_active
230351857,vk1.a.example_token_1,Чат 1,1
230482562,vk1.a.example_token_2,Чат 2,1
230482521,vk1.a.example_token_3,Чат 3,1"""
        return template
    
    def is_csv_available(self) -> bool:
        """Проверяет, доступен ли CSV файл"""
        return os.path.exists(self.csv_file_path)
