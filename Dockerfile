FROM python:3-slim

# SSH-клиент (чтобы внутри контейнера была команда ssh)
RUN apt-get update && apt-get install -y openssh-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# копируем только исходники проекта (без секретов)
COPY . .

CMD ["python", "main.py"]
