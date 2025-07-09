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

# Устанавливаем права для SSH
RUN chmod 700 /home/appuser/.ssh && \
    chmod 600 /home/appuser/.ssh/id_ed25519 && \
    chmod 644 /home/appuser/.ssh/known_hosts || true

CMD ["python", "main.py"]
