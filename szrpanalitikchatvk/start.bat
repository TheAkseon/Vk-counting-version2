@echo off
echo 🚀 Запуск VK Counting Bot...

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

REM Проверяем наличие pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip не найден! Переустановите Python
    pause
    exit /b 1
)

REM Создаем виртуальное окружение если его нет
if not exist "venv" (
    echo 📦 Создание виртуального окружения...
    python -m venv venv
)

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Устанавливаем зависимости
echo 📦 Установка зависимостей...
pip install --upgrade pip
pip install -r requirements.txt

REM Создаем папки
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ⚠️  Создайте файл .env с переменными:
    echo    TELEGRAM_BOT_TOKEN=your_token
    echo    TELEGRAM_ADMIN_CHAT_ID=your_chat_id
    pause
)

REM Запускаем бота
echo 🚀 Запуск бота...
python main.py

pause
