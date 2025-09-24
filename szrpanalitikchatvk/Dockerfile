# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем папки для данных
RUN mkdir -p data logs

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1

# Запускаем приложение
CMD ["python", "main.py"]
