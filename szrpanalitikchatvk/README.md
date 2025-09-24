# VK Simple Bot

Простой VK бот для анализа чатов с 5 основными функциями:

## 🎯 Основные функции

1. **Асинхронный алгоритм** - переделан из линейного в асинхронный
2. **PostgreSQL** - хранение данных в базе данных вместо оперативной памяти
3. **Серверное хранение** - данные сохраняются на сервере
4. **Telegram бот** - кнопка для выгрузки статистики
5. **Автоподсчет** - ежедневный автоматический анализ в 02:00

## 🚀 Быстрый старт

### 1. Настройка конфигурации

**Создайте файл `.env` на основе примера:**

```bash
# Скопируйте пример файла
cp env.example .env

# Отредактируйте .env файл
nano .env
```

**Заполните переменные в `.env`:**
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота (получите у @BotFather)
- `TELEGRAM_ADMIN_CHAT_ID` - ID вашего чата (узнайте у @userinfobot)

**⚠️ ВАЖНО: Файл `.env` содержит секретные данные и НЕ должен попадать в Git!**

### 2. Запуск

#### **Способ 1: Docker (рекомендуется)**
```bash
# 1. Создайте файл .env с переменными:
# TELEGRAM_BOT_TOKEN=your_token
# TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# 2. Запустите:
docker-compose up -d

# 3. Проверьте логи:
docker-compose logs -f
```

#### **Способ 2: Linux сервер (systemd)**
```bash
# 1. Запустите скрипт установки:
chmod +x install.sh
sudo ./install.sh

# 2. Создайте .env файл:
sudo nano /opt/vk-bot/.env

# 3. Запустите сервис:
sudo systemctl start vk-bot
sudo systemctl status vk-bot
```

#### **Способ 3: Windows**
```bash
# 1. Дважды кликните start.bat
# 2. Создайте .env файл с переменными
# 3. Бот запустится автоматически
```

#### **Способ 4: Создание exe файла**
```bash
# 1. Запустите build_exe.bat
# 2. exe файл будет в папке dist/
# 3. Запустите VK-Counting-Bot.exe
```

#### **Способ 5: Ручная установка**
```bash
# 1. Установите Python 3.8+
# 2. pip install -r requirements.txt
# 3. Создайте .env файл
# 4. python main.py
```

## 📊 Функции бота

- **📊 Получить статистику** - показывает текущую статистику
- **🚀 Запустить анализ** - запускает анализ чата
- **📥 Экспорт данных** - экспорт данных 

## 🗄️ База данных

Автоматически создаются таблицы:
- `chats` - информация о чатах
- `users` - пользователи
- `messages` - сообщения
- `daily_stats` - ежедневная статистика

## ⏰ Планировщик

Автоматически запускает анализ каждый день в 02:00.

## 📝 Логи

Логи сохраняются в папке `logs/` с ротацией каждый день.



# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=7948828146:AAFJg3tKJidUADzrAwNmhpIHsvqrPtJI0cM
TELEGRAM_ADMIN_CHAT_ID=1383508355

# VK API Configuration
VK_ACCESS_TOKEN_GROUP_ID_1=your_vk_token_here
VK_GROUP_ID_1=your_group_id_here

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vk_simple_bot
POSTGRES_USER=vkuser
POSTGRES_PASSWORD=secure_password_123

# Application Configuration
VK_API_VERSION=5.131
PEER_ID=2000000001
MAX_MESSAGES=10000
RATE_LIMIT_DELAY=0.34

