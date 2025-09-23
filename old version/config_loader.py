import json
from functools import lru_cache

@lru_cache(maxsize=1)
def load_config(config_file="config.json"):
    """
    Загружает конфигурацию из JSON файла с кэшированием
    
    Args:
        config_file (str): Путь к файлу конфигурации
        
    Returns:
        dict: Словарь с настройками или None при ошибке
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Файл конфигурации {config_file} не найден!")
        return None
    except json.JSONDecodeError as e:
        print(f"Ошибка в JSON файле: {e}")
        return None

def get_vk_chats():
    """
    Получает список всех чатов VK из конфигурации
    
    Returns:
        list: Список словарей с данными чатов или пустой список при ошибке
    """
    config = load_config()
    return config.get("vk_chats", []) if config else []

def get_vk_chat_config(chat_index=0):
    """
    Получает настройки VK API для конкретного чата
    
    Args:
        chat_index (int): Индекс чата в списке (по умолчанию 0)
    
    Returns:
        tuple: (peer_id, token, api_version) или (None, None, None) при ошибке
    """
    # Используем get_vk_chats() чтобы избежать двойной загрузки конфигурации
    chats = get_vk_chats()
    if not chats or chat_index >= len(chats):
        return None, None, None
    
    chat = chats[chat_index]
    group_id = chat.get("group_id")
    peer_id = 2000000001  
    token = chat.get("token")
    
    # Получаем api_version из кэшированной конфигурации
    config = load_config()
    api_version = config.get("api_version", "5.131") if config else "5.131"
    
    return group_id, peer_id, token, api_version
