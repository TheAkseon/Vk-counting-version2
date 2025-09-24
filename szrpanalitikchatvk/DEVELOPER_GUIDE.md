# 👨‍💻 Техническая документация для разработчиков

## 🏗️ Архитектура системы

### **Общая схема:**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │   VK API        │    │   SQLite DB     │
│   (aiogram)     │◄──►│   (aiohttp)     │◄──►│   (aiosqlite)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Scheduler     │    │   Analyzer      │    │   CSV Parser    │
│   (asyncio)     │    │   (async)       │    │   (csv)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Структура проекта

```
szrpanalitikchatvk/
├── main.py                 # Точка входа
├── config.py              # Конфигурация
├── database_sqlite.py      # База данных
├── vk_client.py           # VK API клиент
├── analyzer.py            # Анализатор чатов
├── telegram_bot.py        # Telegram бот
├── scheduler.py           # Планировщик
├── csv_parser.py          # Парсер CSV
├── requirements.txt       # Зависимости
├── .env.example          # Пример конфигурации
├── .gitignore            # Git исключения
├── Dockerfile            # Docker образ
├── docker-compose.yml    # Docker Compose
├── start.bat             # Windows запуск
├── install.sh            # Linux установка
└── build_exe.bat         # Создание exe
```

## 🔧 Основные компоненты

### **1. main.py - Точка входа**
```python
class VKSimpleBot:
    def __init__(self):
        self.telegram_bot = TelegramBot()
        self.scheduler = Scheduler()
    
    async def start(self):
        await db.initialize()
        self.scheduler.set_telegram_bot(self.telegram_bot)
        asyncio.create_task(self.scheduler.start())
        await self.telegram_bot.start_polling()
```

**Ответственность:**
- Инициализация всех компонентов
- Управление жизненным циклом
- Обработка сигналов завершения

### **2. config.py - Конфигурация**
```python
class Config:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_ADMIN_CHAT_ID = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID', '1383508355'))
    RATE_LIMIT_DELAY = 0.2
    
    @classmethod
    def get_vk_chats(cls) -> List[Dict[str, Any]]:
        # Динамическая загрузка чатов из CSV
```

**Ответственность:**
- Управление настройками
- Загрузка переменных окружения
- Динамическая конфигурация чатов

### **3. database_sqlite.py - База данных**
```python
class Database:
    async def initialize(self):
        # Создание таблиц
        # chats, users, messages, daily_stats, telegram_users
    
    async def save_telegram_user(self, user_id, username, first_name):
        # Сохранение пользователей Telegram
    
    async def get_chats_stats(self):
        # Получение статистики чатов
```

**Схема БД:**
- `chats` - информация о чатах
- `users` - пользователи VK
- `messages` - сообщения
- `daily_stats` - ежедневная статистика
- `telegram_users` - пользователи Telegram

### **4. vk_client.py - VK API клиент**
```python
class VKClient:
    async def _make_request(self, method, params):
        # HTTP запросы к VK API с обработкой ошибок
    
    async def get_chat_members(self):
        # Получение участников чата
    
    async def get_chat_messages(self):
        # Получение сообщений чата
    
    async def check_users_status(self, user_ids):
        # Проверка статуса пользователей (активен/удален/забанен)
```

**Особенности:**
- Обработка лимитов API (3 запроса/сек)
- Фильтрация удаленных пользователей
- Retry логика для ошибок
- Батчинг запросов

### **5. analyzer.py - Анализатор**
```python
class ChatAnalyzer:
    async def analyze_all_chats(self, batch_size=100):
        # Анализ всех чатов с батчингом
    
    async def _analyze_single_chat(self, group_id, token, chat_name):
        # Анализ одного чата
    
    def _analyze_user_duplication(self):
        # Анализ дублирования пользователей
    
    async def _save_to_database_optimized(self, results):
        # Оптимизированное сохранение в БД
```

**Алгоритм анализа:**
1. Параллельное получение участников и сообщений
2. Фильтрация по статусу пользователей
3. Анализ дублирования между чатами
4. Сохранение результатов в БД

### **6. telegram_bot.py - Telegram бот**
```python
class TelegramBot:
    def __init__(self):
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
    
    async def handle_document(self, message):
        # Обработка загрузки CSV файлов
    
    async def handle_analyze_callback(self, callback):
        # Запуск анализа чатов
    
    async def _create_stats_csv_from_csv(self, stats):
        # Создание CSV отчета
```

**Функции:**
- Загрузка и валидация CSV файлов
- Управление анализом чатов
- Экспорт данных в CSV
- Отображение статистики

### **7. scheduler.py - Планировщик**
```python
class Scheduler:
    async def start(self):
        # Запуск планировщика с ежедневным анализом
    
    async def _run_daily_analysis(self):
        # Ежедневный анализ в 02:00
    
    async def _send_daily_report(self, results):
        # Отправка отчетов пользователям
```

**Функции:**
- Ежедневный анализ в 16:15
- Отправка отчетов всем пользователям
- Обработка ошибок и уведомления

### **8. csv_parser.py - Парсер CSV**
```python
class CSVParser:
    def parse_csv(self) -> List[Dict[str, Any]]:
        # Парсинг CSV файла с валидацией
    
    def save_csv(self, csv_content: str) -> bool:
        # Сохранение CSV файла
    
    def is_csv_available(self) -> bool:
        # Проверка доступности файла
```

**Особенности:**
- Обработка BOM (Byte Order Mark)
- Валидация обязательных полей
- Поддержка UTF-8 кодировки

## 🔄 Потоки данных

### **1. Загрузка CSV:**
```
User → Telegram → CSV Parser → File System
```

### **2. Анализ чатов:**
```
CSV Parser → Analyzer → VK Client → VK API
                ↓
            Database ← Results
```

### **3. Экспорт данных:**
```
Database → Telegram Bot → CSV Generator → User
```

### **4. Автоматический анализ:**
```
Scheduler → Analyzer → VK API → Database → Telegram Users
```

## ⚡ Производительность

### **Оптимизации:**
- **Параллельная обработка** - до 20 чатов одновременно
- **Батчинг запросов** - группировка API вызовов
- **Кэширование** - сохранение промежуточных результатов
- **Фильтрация** - исключение неактивных пользователей

### **Лимиты:**
- **VK API** - 3 запроса/сек на токен
- **Память** - ~50MB для 1000 чатов
- **Время** - ~1 сек на чат с 1000 участников

## 🛠️ Разработка

### **Добавление новых функций:**

#### 1. Новый тип анализа:
```python
# В analyzer.py
async def _analyze_custom_metric(self, chat_data):
    # Ваша логика анализа
    return custom_result
```

#### 2. Новая команда Telegram:
```python
# В telegram_bot.py
@self.dp.message(Command("new_command"))
async def handle_new_command(message):
    # Обработка новой команды
```

#### 3. Новое поле в БД:
```python
# В database_sqlite.py
async def initialize(self):
    await self.connection.execute("""
        ALTER TABLE chats ADD COLUMN new_field TEXT
    """)
```

### **Тестирование:**
```bash
# Запуск тестов
pytest test_bot.py -v

# Тестирование конкретного компонента
pytest test_bot.py::TestCSVParser -v

# Покрытие кода
pytest --cov=. --cov-report=html
```

### **Отладка:**
```python
# Логирование
from loguru import logger
logger.info("Debug message")
logger.error(f"Error: {e}")

# Проверка состояния
logger.debug(f"Current state: {state}")
```

## 🚀 Развертывание

### **Docker:**
```bash
# Сборка образа
docker build -t vk-bot .

# Запуск контейнера
docker run -d --name vk-bot vk-bot

# Логи
docker logs -f vk-bot
```

### **Systemd (Linux):**
```bash
# Установка сервиса
sudo systemctl enable vk-bot
sudo systemctl start vk-bot

# Статус
sudo systemctl status vk-bot

# Логи
sudo journalctl -u vk-bot -f
```

### **Windows Service:**
```bash
# Установка как служба
sc create "VK Bot" binPath="C:\path\to\python.exe C:\path\to\main.py"
sc start "VK Bot"
```

## 🔧 Конфигурация

### **Переменные окружения:**
```env
# Обязательные
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Опциональные
RATE_LIMIT_DELAY=0.2
BATCH_SIZE=100
SCHEDULE_TIME=02:00
```

### **Настройка производительности:**
```python
# В config.py
RATE_LIMIT_DELAY = 0.2  # Задержка между запросами
BATCH_SIZE = 100        # Размер батча для обработки
MAX_CONCURRENT = 20     # Максимум параллельных чатов
```

## 📊 Мониторинг

### **Метрики:**
- Количество обработанных чатов
- Время выполнения анализа
- Количество ошибок API
- Использование памяти

### **Логи:**
```python
# Структура логов
2024-01-01 02:00:01 | INFO | Starting daily analysis
2024-01-01 02:00:05 | INFO | Chat 123456 analyzed: 100 members
2024-01-01 02:00:10 | ERROR | VK API error: Rate limit exceeded
```

### **Алерты:**
- Превышение лимитов API
- Ошибки подключения к БД
- Недоступность VK API
- Критические ошибки анализа

## 🔒 Безопасность

### **Защита токенов:**
- Хранение в переменных окружения
- Исключение из Git (.gitignore)
- Шифрование в production

### **Валидация данных:**
- Проверка формата CSV
- Валидация токенов VK API
- Санитизация пользовательского ввода

### **Ограничения доступа:**
- Только авторизованные пользователи Telegram
- Проверка прав доступа к чатам
- Логирование всех операций
