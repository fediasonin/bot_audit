FROM python:3-slim

# Установка зависимостей для SSH
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя appuser
RUN useradd -m appuser && \
    mkdir -p /home/appuser/.ssh && \
    chown -R appuser:appuser /home/appuser/.ssh && \
    chmod 700 /home/appuser/.ssh

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем SSH-ключи (права сохранятся из-за COPY --chown)
COPY --chown=appuser:appuser id_ed25519 /home/appuser/.ssh/id_ed25519
COPY --chown=appuser:appuser known_hosts /home/appuser/.ssh/known_hosts

# Устанавливаем правильные права
RUN chmod 600 /home/appuser/.ssh/id_ed25519 && \
    chmod 644 /home/appuser/.ssh/known_hosts

# Копируем основной код (владельцем будет root)
COPY . .

# Переключаемся на appuser (для безопасности)
USER appuser

CMD ["python", "main.py"]