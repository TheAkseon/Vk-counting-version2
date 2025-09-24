#!/bin/bash

# Скрипт установки VK Counting Bot на Linux сервер

echo "🚀 Установка VK Counting Bot..."

# Обновляем систему
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# Создаем пользователя для бота
sudo useradd -m -s /bin/bash vkbot
sudo usermod -aG sudo vkbot

# Создаем директорию для бота
sudo mkdir -p /opt/vk-bot
sudo chown vkbot:vkbot /opt/vk-bot

# Переходим в директорию
cd /opt/vk-bot

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Создаем папки
mkdir -p data logs

# Создаем systemd сервис
sudo tee /etc/systemd/system/vk-bot.service > /dev/null <<EOF
[Unit]
Description=VK Counting Bot
After=network.target

[Service]
Type=simple
User=vkbot
Group=vkbot
WorkingDirectory=/opt/vk-bot
Environment=PATH=/opt/vk-bot/venv/bin
ExecStart=/opt/vk-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
sudo systemctl daemon-reload
sudo systemctl enable vk-bot

echo "✅ Установка завершена!"
echo "📝 Создайте файл .env с переменными:"
echo "   TELEGRAM_BOT_TOKEN=your_token"
echo "   TELEGRAM_ADMIN_CHAT_ID=your_chat_id"
echo ""
echo "🚀 Запуск: sudo systemctl start vk-bot"
echo "📊 Статус: sudo systemctl status vk-bot"
echo "📋 Логи: sudo journalctl -u vk-bot -f"
