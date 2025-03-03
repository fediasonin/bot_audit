import logging
import os
import requests
import json
import asyncio
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

BASE_URL = os.getenv("BASE_URL")
GUID = os.getenv("GUID")
SIGNATURE = os.getenv("SIGNATURE")
ORG_NAME = os.getenv("ORG_NAME")
N = int(os.getenv("N"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_jwt_token():
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
    limit = min(count, 100)
    url = f"{BASE_URL}/sdk/tokens/all-tokens"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    data = {"org_name": ORG_NAME, "page_number": 1, "page_size": 200}
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
    try:
        return datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
    except Exception as e:
        logger.error("Ошибка преобразования даты '%s': %s", dt_str, e)
        return None

def get_audit_logs(token, user_login, count, start_date="", stop_date=""):
    limit = min(count, 100)
    url = f"{BASE_URL}/sdk/audit/audit"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    data = {"org_name": ORG_NAME, "user_login": user_login, "page_number": 1, "page_size": 200}
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
    message = (
        "*Добро пожаловать!*\n\n"
        "Я бот для получения информации о токенах и аудите.\n\n"
        "*Доступные команды:*\n"
        "• `/tokens <логин>` — получить список токенов для пользователя.\n"
        "• `/audit <логин>` — получить записи аудита для пользователя.\n"
        "• `/help` — справка по командам.\n\n"
        "Например:\n"
        "• `/tokens ivanova`\n"
        "• `/audit ivanova`"
    )
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "*Справка по командам:*\n\n"
        "• `/start` — Приветственное сообщение.\n"
        "• `/tokens <логин>` — Получить список токенов для указанного пользователя.\n"
        "   _Пример:_ `/tokens ivanova`\n\n"
        "• `/audit <логин>` — Получить записи аудита для указанного пользователя.\n"
        "   _Пример:_ `/audit ivanova`"
    )
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

async def tokens_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/tokens ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    await update.message.reply_text(f"Запрашиваю токены для пользователя: *{user_login}* ...", parse_mode=ParseMode.MARKDOWN)
    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return
    tokens = get_tokens_for_user(jwt_token, user_login, N)
    if tokens:
        response_lines = ["*Список токенов:*"]
        for t in tokens:
            token_id = t.get("token_id")
            token_type = t.get("token_type", "Unknown")
            state = "Активен" if t.get("token_activation") else "Не активен"
            response_lines.append(f"• *ID:* `{token_id}`\n  *Тип:* {token_type}\n  *Статус:* {state}\n")
        response = "\n".join(response_lines)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Токены не найдены или произошла ошибка.")

async def audit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/audit ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    await update.message.reply_text(f"Запрашиваю записи аудита для пользователя: *{user_login}* ...", parse_mode=ParseMode.MARKDOWN)
    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return
    audit_logs = get_audit_logs(jwt_token, user_login, N)
    if audit_logs:
        response_lines = ["*Записи аудита:*"]
        for log in audit_logs:
            line = (
                f"*Логин:* `{log.get('audit_login', '')}`\n"
                f"*Время:* `{log.get('audit_datetime', '')}`\n"
                f"*IP:* `{log.get('audit_ip_address', '')}`\n"
                f"*Агент:* `{log.get('audit_agent', '')}`\n"
                f"*Результат:* `{log.get('audit_result', '')}`\n"
                f"*Номер токена:* `{log.get('audit_serialnumber', '')}`\n"
                f"*Комментарий:* `{log.get('audit_comments', '')}`"
            )
            response_lines.append(line)
        response = "\n\n".join(response_lines)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Записи аудита не найдены или произошла ошибка.")

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("tokens", tokens_handler))
    app.add_handler(CommandHandler("audit", audit_handler))
    logger.info("Бот запущен.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
