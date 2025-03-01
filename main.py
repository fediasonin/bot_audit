import logging
import requests
import json
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()  # Позволяет запускать вложенные циклы событий

# === Константы (настроить под вашу среду) ===
BASE_URL = "https://mgmt-kr01.mfa.mosreg.ru"
GUID = "7bd7a2b75b8a0db9a5dd8cba946d49bc"  # GUID сервисной учётной записи
SIGNATURE = "MLWQQj5OK2bqgaLEtmiIGe5sMrQdIptyBTJ8GheX5AbnN0zjAkNUlV2dHQafol7CsybZQM8jW95QLmQBYRvCXPjqSm7LLaChQOFlxLp7vKWNIiEQAdZMq7lVXDUJKVeS0KrPol2CjoSJrqeQOqWVQ1HFvWYl5505JCkrFdAOjf8AN241dsY1InKqx/iUOSO8+GgmKJPjF9B050Xo19ArnG/Y9XFYb9OxVBk5kUh2otsCiOutg6feaLR3JDStgaeEw/HKRZuUc+EnuIDmGbLccBEko6+76Kz0+a+UhtQm6SCBgVHsB1MOkBJPw0JV6wm7W5upYVJ1msG0KAdb8SV6bw=="
ORG_NAME = "MFA-MOSREG"
N = 2  # Число последних записей (не более 100)

TELEGRAM_BOT_TOKEN = "8129371386:AAFHpa6ZhLOyAYMZxOtKhR4hOCb-RqEOAZs"  # Замените на токен вашего бота
# --------------------------------------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_jwt_token():
    """
    Авторизация (GET /sdk/login). JSON-тело:
      { "guid": GUID, "signature": SIGNATURE }
    Возвращает JWT-токен или None при ошибке.
    """
    url = f"{BASE_URL}/sdk/login"
    headers = {"Content-Type": "application/json"}
    data = {"guid": GUID, "signature": SIGNATURE}
    try:
        response = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=True)
        if response.status_code == 200:
            body = response.json()
            if body.get("Result") == 0:
                logger.info("Успешная авторизация в SAS.")
                return body.get("Token")
            else:
                logger.error("Ошибка авторизации: %s", body.get("Details", "(нет описания)"))
        else:
            logger.error("HTTP ошибка при авторизации: %s %s", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        logger.error("Сетевая ошибка при авторизации: %s", str(e))
    return None


def get_tokens_for_user(token, user_login, count):
    """
    Получает список токенов для аккаунта (GET /sdk/tokens/all-tokens).
    Фильтрует по полю token_owner равному user_login,
    сортирует по убыванию token_id и возвращает не более count записей.
    """
    limit = min(count, 100)
    url = f"{BASE_URL}/sdk/tokens/all-tokens"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "org_name": ORG_NAME,
        "page_number": 1,
        "page_size": 200
    }
    try:
        resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=True)
        if resp.status_code == 200:
            body = resp.json()
            if body.get("Result") == 0:
                all_tokens = body.get("Data", [])
                filtered = [t for t in all_tokens if t.get("token_owner") == user_login]
                filtered.sort(key=lambda x: x.get("token_id", 0), reverse=True)
                return filtered[:limit]
            else:
                logger.error("Ошибка запроса /sdk/tokens/all-tokens: %s", body.get("Details", "(нет описания)"))
        else:
            logger.error("HTTP ошибка /sdk/tokens/all-tokens: %s %s", resp.status_code, resp.text)
    except requests.exceptions.RequestException as e:
        logger.error("Сетевая ошибка при получении токенов: %s", str(e))
    return []


def parse_datetime(dt_str):
    """
    Преобразует строку даты/времени из формата "дд-мм-гггг чч:мм:сс" в объект datetime.
    """
    try:
        return datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
    except Exception as e:
        logger.error("Ошибка преобразования даты '%s': %s", dt_str, e)
        return None


def get_audit_logs(token, user_login, count, start_date="", stop_date=""):
    """
    Получает записи аудита (GET /sdk/audit/audit).
    Параметры:
      org_name: название аккаунта (ORG_NAME)
      user_login: логин (опционально)
      start_date и stop_date: диапазон дат (формат "2025-02-06")
      page_number: 1, page_size: достаточно большое число для получения нужного количества записей
    Возвращает не более count записей аудита.
    """
    limit = min(count, 100)
    url = f"{BASE_URL}/sdk/audit/audit"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "org_name": ORG_NAME,
        "user_login": user_login,
        "page_number": 1,
        "page_size": 200  # берем достаточно записей
    }
    if start_date:
        data["start_date"] = start_date
    if stop_date:
        data["stop_date"] = stop_date

    try:
        resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=True)
        if resp.status_code == 200:
            body = resp.json()
            if body.get("Result") == 0:
                audit_logs = body.get("Data", [])
                # Сортировка по убыванию даты (если необходимо)
                audit_logs.sort(key=lambda x: parse_datetime(x.get("audit_datetime", "01-01-1970 00:00:00")) or datetime.min, reverse=True)
                return audit_logs[:limit]
            else:
                logger.error("Ошибка запроса /sdk/audit/audit: %s", body.get("Details", "(нет описания)"))
        else:
            logger.error("HTTP ошибка /sdk/audit/audit: %s %s", resp.status_code, resp.text)
    except requests.exceptions.RequestException as e:
        logger.error("Сетевая ошибка при получении записей аудита: %s", str(e))
    return []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет!\n"
        "Используй команду /tokens <логин>, чтобы получить список токенов,\n"
        "или /audit <логин>, чтобы получить записи аудита.\n"
        "Например: /tokens LevandovskiyGeG\n"
        "           /audit LevandovskiyGeG"
    )


async def tokens_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: /tokens LevandovskiyGeG")
        return

    user_login = context.args[0]
    await update.message.reply_text(f"Запрашиваю токены для пользователя: {user_login} ...")

    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return

    tokens = get_tokens_for_user(jwt_token, user_login, N)
    if tokens:
        response_lines = []
        for t in tokens:
            token_id = t.get("token_id")
            token_type = t.get("token_type", "Unknown")
            state = "Активен" if t.get("token_activation") else "Не активен"
            response_lines.append(f"{token_id}: {token_type}: {state}")
        response = "\n".join(response_lines)
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Токены не найдены или произошла ошибка.")


async def audit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: /audit LevandovskiyGeG")
        return

    user_login = context.args[0]
    await update.message.reply_text(f"Запрашиваю записи аудита для пользователя: {user_login} ...")

    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return

    # Если нужно, можно указать start_date и stop_date, например, за сегодня или за нужный период
    # Для примера оставим их пустыми, чтобы получить все записи
    audit_logs = get_audit_logs(jwt_token, user_login, N)
    if audit_logs:
        response_lines = []
        for log in audit_logs:
            # Формат: логин: время: ip-адрес: агент: результат: номер_токена: сообщение
            line = (
                f"{log.get('audit_login', '')}: "
                f"{log.get('audit_datetime', '')}: "
                f"{log.get('audit_ip_address', '')}: "
                f"{log.get('audit_agent', '')}: "
                f"{log.get('audit_result', '')}: "
                f"{log.get('audit_serialnumber', '')}: "
                f"{log.get('audit_comments', '')}"
            )
            response_lines.append(line)
        response = "\n".join(response_lines)
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Записи аудита не найдены или произошла ошибка.")


async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tokens", tokens_handler))
    app.add_handler(CommandHandler("audit", audit_handler))

    logger.info("Бот запущен.")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())