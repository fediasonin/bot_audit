FROM python:3-slim

# Установка зависимостей для SSH
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код, включая .env и SSH-ключи
COPY . .

CMD ["python", "main.py"]
