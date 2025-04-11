
Copy
# Telegram Bot for MFA Management

Бот для работы с системой многофакторной аутентификации (MFA) через Telegram. Позволяет получать информацию о токенах пользователей, просматривать записи аудита и управлять задачами активации.

## Функционал

- Получение списка токенов пользователя
- Просмотр записей аудита
- Управление задачами активации
- Получение ID чата

## Установка и настройка

1. Клонировать репозиторий:
```bash
git clone <repository-url>
cd <repository-folder>
Установить зависимости:

bash
Copy
pip install -r requirements.txt
Создать файл .env и заполнить его по образцу:

ini
Copy
BASE_URL=your_base_url
GUID=your_guid
SIGNATURE=your_signature
ORG_NAME=your_org_name
N=5  # Количество возвращаемых записей по умолчанию
TELEGRAM_BOT_TOKEN=your_bot_token
ALLOWED_CHAT_ID=-1002321217341  # ID разрешенного чата
Запустить бота:

bash
Copy
python main.py
Доступные команды
При вводе / в чате с ботом будут отображаться следующие команды:

/start - Начальное сообщение

/help - Показать справку

/tokens <логин> - Получить токены пользователя

/audit <логин> [количество] - Получить записи аудита

/enrollments <логин> - Задачи активации пользователя

/getchatid - Узнать ID чата

Примеры использования
Получить токены пользователя:

Copy
/tokens ivanova
Получить 5 последних записей аудита:

Copy
/audit ivanova 5
Просмотреть задачи активации:

Copy
/enrollments petrov
Технологии
Python 3.9+

python-telegram-bot 20.0+

Requests

python-dotenv

Лицензия
Проект распространяется под лицензией MIT.

