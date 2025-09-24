@echo off
echo 🔨 Создание exe файла...

REM Устанавливаем PyInstaller
pip install pyinstaller

REM Создаем exe файл
pyinstaller --onefile --name "VK-Counting-Bot" --add-data "data;data" --add-data "logs;logs" main.py

echo ✅ exe файл создан в папке dist/
pause
