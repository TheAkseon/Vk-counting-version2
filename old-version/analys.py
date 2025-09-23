import vk_api
import time
from datetime import datetime, timedelta
from config_loader import get_vk_chats, get_vk_chat_config

# Скрипт для анализа чатов VK: участники и сообщения за месяц

def analyze_chat(group_id, peer_id, token, api_version, chat_name=""):
    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api() 
        
        print(f"\n{'='*60}")
        print(f"Анализ чата: {chat_name} (Group ID: {group_id})")  # ← Логируем group_id
        print(f"{'='*60}")
        
        # 1. Участники
        try:
            members_response = vk.messages.getConversationMembers(peer_id=int(peer_id), v=api_version)
            members = members_response.get('items', [])

            real_users = [member['member_id'] for member in members if member['member_id'] > 0]
            members_count = len(real_users)

            print(f"Участников в чате: {members_count}")
            print(f"ID пользователей: {real_users}")
        except vk_api.exceptions.ApiError as e:
            print(f"Ошибка получения участников: {e.code} {e.message}")
            members_count = 0
        except Exception as e:
            print(f"Неизвестная ошибка участников: {e}")
            members_count = 0
        
        # 2. Сообщения за месяц
        try:
            month_ago = int((datetime.now() - timedelta(days=30)).timestamp())
            current_time = int(time.time())
            
            print(f"Анализируем сообщения с {datetime.fromtimestamp(month_ago).strftime('%d.%m.%Y')} по {datetime.fromtimestamp(current_time).strftime('%d.%m.%Y')}")
            
            messages_count = 0
            all_messages = []
            offset = 0
            batch_size = 200
            
            while True:
                try:
                    history_response = vk.messages.getHistory(
                        peer_id=int(peer_id),
                        count=batch_size,
                        offset=offset,
                        v=api_version  # ← Добавлено
                    )
                    
                    messages = history_response.get('items', [])
                    if not messages:
                        break
                    
                    month_messages = [msg for msg in messages if month_ago <= msg.get('date', 0) <= current_time]
                    
                    real_month_messages = [msg for msg in month_messages if msg.get('from_id', 0) > 0]
                    all_messages.extend(real_month_messages)
                    messages_count += len(real_month_messages)
                    
                    oldest_message_date = min((msg.get('date', 0) for msg in messages), default=0)
                    if oldest_message_date < month_ago:
                        break
                    
                    offset += batch_size
                    
                    if offset > 10000:
                        break
                    
                    time.sleep(0.34)  # ← Rate limit
                    
                except vk_api.exceptions.ApiError as e:
                    print(f"Ошибка получения сообщений (offset {offset}): {e.code} {e.message}")
                    break
                except Exception as e:
                    print(f"Неизвестная ошибка сообщений: {e}")
                    break
            
            print(f"Сообщений за месяц: {messages_count}")
            
        except Exception as e:
            print(f"Ошибка анализа сообщений: {e}")
            all_messages = []
            messages_count = 0
        
        # 3. Общее количество
        try:
            total_response = vk.messages.getHistory(peer_id=int(peer_id), count=0, v=api_version)
            total_messages = total_response.get('count', 0)
            print(f"Всего сообщений в чате: {total_messages}")
        except vk_api.exceptions.ApiError as e:
            print(f"Не удалось получить общее количество: {e.code} {e.message}")
            total_messages = 0
        except Exception as e:
            print(f"Неизвестная ошибка общего счёта: {e}")
            total_messages = 0
        
        results = {
            "chat_name": chat_name,
            "group_id": group_id,  
            "peer_id": peer_id,
            "all_members": real_users,
            "all_messages": all_messages,
            "members_count": members_count,
            "messages_last_month": messages_count,
            "total_messages": total_messages,
            "analysis_date": datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        print(f"{'='*60}")
        return results
        
    except Exception as e:
        print(f"Критическая ошибка для чата {chat_name} (Group ID: {group_id}, Peer ID: {peer_id}): {e}")
        return None

def analyze_user_duplication(results):
    """
    Анализирует дублирование пользователей между чатами
    
    Args:
        results: Список результатов анализа чатов
    
    Returns:
        dict: Словарь с информацией о дублировании
    """

    user_chats = {}

    for result in results:
        chat_name = result['chat_name']
        for user_id in result['all_members']:
            if user_id not in user_chats:
                user_chats[user_id] = []
            user_chats[user_id].append(chat_name)
    
    duplicated_users = []
    unique_users = []
    
    for user_id, chats in user_chats.items():
        if len(chats) > 2:
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

def filter_duplicated_data(results, duplicated_users):
    """
    Фильтрует данные, исключая дублированных пользователей
    
    Args:
        results: Список результатов анализа чатов
        duplicated_users: Список ID дублированных пользователей
    
    Returns:
        list: Отфильтрованные результаты
    """
    filtered_results = []
    
    for result in results:
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


if __name__ == "__main__":
    print("Анализ чатов VK: участники и сообщения за месяц")
    print("=" * 60)
    
    # Загружаем все чаты из конфигурации
    chats = get_vk_chats()
    
    if not chats:
        print("Чаты не найдены в файле config.json!")
        exit(1)
    
    print(f"Найдено чатов: {len(chats)}")
    print(f"Используем API версии: 5.131")
    
    results = []
    total_members = 0
    total_messages = 0
    
    # Анализируем каждый чат
    for i in range(len(chats)):
        group_id, peer_id, token, api_version = get_vk_chat_config(i)
        chat_name = chats[i].get("name", f"Чат {i+1}")
        
        
        if peer_id and token:
            print(f"\nОбрабатываем {i+1}/{len(chats)}: {chat_name}")
            result = analyze_chat(group_id, peer_id, token, api_version, chat_name)
            
            if result:
                results.append(result)
            else:
                print(f"Пропускаем {chat_name}: ошибка анализа")
        else:
            print(f"Пропускаем {chat_name}: отсутствуют peer_id или token")
    
    duplication_info = analyze_user_duplication(results)
    # Анализируем дублирование пользователей
    print(f"Всего пользователей: {duplication_info['duplication_stats']['total_users']}")
    print(f"Уникальных пользователей: {duplication_info['duplication_stats']['unique_count']}")
    print(f"Дублированных пользователей: {duplication_info['duplication_stats']['duplicated_count']}")
    
    if duplication_info['duplicated_users']:
        print("\nДублированные пользователи:")
        for user_id in duplication_info['duplicated_users']:
            chats = duplication_info['user_chats'][user_id]
            print(f"- ID {user_id}: {', '.join(chats)}")
    else:
        print("Дублированных пользователей не найдено")


    # Фильтруем данные
    filtered_results = filter_duplicated_data(results, duplication_info['duplicated_users'])

    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА (после фильтрации)")
    print("=" * 80)

    total_members = sum(result['members_count'] for result in filtered_results)
    total_messages = sum(result['messages_last_month'] for result in filtered_results)
    total_excluded_members = sum(result['excluded_members'] for result in filtered_results)
    total_excluded_messages = sum(result['excluded_messages'] for result in filtered_results)

    print(f"Проанализировано чатов: {len(filtered_results)}")
    print(f"Уникальных участников: {total_members}")
    print(f"Сообщений за месяц: {total_messages}")
    print(f"Исключено участников: {total_excluded_members}")
    print(f"Исключено сообщений: {total_excluded_messages}")
    print(f"Среднее сообщений на чат: {total_messages/len(filtered_results) if filtered_results else 0:.1f}")

    if filtered_results:
        print("\nДетальная статистика по чатам:")
        for result in filtered_results:
            print(f"- {result['chat_name']}:")
            print(f"  - Участников: {result['members_count']}")
            print(f"  - Сообщений за месяц: {result['messages_last_month']}")
            print(f"  - Исключено участников: {result['excluded_members']}")
            print(f"  - Исключено сообщений: {result['excluded_messages']}")
            print(f"  - Всего сообщений: {result['total_messages']}")
            if result['filtered_members']:
                print(f"  - ID участников: {result['filtered_members']}")

    print("\n" + "=" * 80)
    print("Анализ завершен!")
    