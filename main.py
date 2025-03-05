import logging
import os
import requests
import json
import asyncio
import io
from datetime import datetime
from telegram import Update, InputFile
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
ALLOWED_CHAT_ID = -1002321217341

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
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
    tokens = []
    page = 1
    page_size = 200
    user_login_norm = user_login.strip().lower()
    while True:
        url = f"{BASE_URL}/sdk/tokens/all-tokens"
        headers = {"Authorization": token, "Content-Type": "application/json"}
        data = {"org_name": ORG_NAME, "page_number": page, "page_size": page_size}
        try:
            resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=True)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("Result") == 0:
                    page_tokens = body.get("Data", [])
                    filtered = [
                        t for t in page_tokens
                        if (t.get("token_owner") or "").strip().lower() == user_login_norm
                    ]
                    tokens.extend(filtered)
                    if len(page_tokens) < page_size or len(tokens) >= count:
                        break
                    page += 1
                else:
                    logger.error("Ошибка запроса /sdk/tokens/all-tokens: %s", body.get("Details", "(нет описания)"))
                    break
            else:
                logger.error("HTTP ошибка /sdk/tokens/all-tokens: %s %s", resp.status_code, resp.text)
                break
        except requests.exceptions.RequestException as e:
            logger.error("Сетевая ошибка при получении токенов: %s", str(e))
            break
    return tokens[:count]

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
                audit_logs.sort(
                    key=lambda x: parse_datetime(x.get("audit_datetime", "01-01-1970 00:00:00")) or datetime.min,
                    reverse=True
                )
                return audit_logs[:limit]
            else:
                logger.error("Ошибка запроса /sdk/audit/audit: %s", body.get("Details", "(нет описания)"))
        else:
            logger.error("HTTP ошибка /sdk/audit/audit: %s %s", resp.status_code, resp.text)
    except requests.exceptions.RequestException as e:
        logger.error("Сетевая ошибка при получении записей аудита: %s", str(e))
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    message = (
        "*Добро пожаловать!*\n\n"
        "Я бот для получения информации о токенах, аудите и получения ID чата.\n\n"
        "*Доступные команды:*\n"
        "• `/tokens <логин>` — получить список токенов для пользователя.\n"
        "• `/audit <логин> [количество]` — получить записи аудита для пользователя. Если указано количество, результаты будут отправлены файлом.\n"
        "• `/getchatid` — получить идентификатор чата.\n"
        "• `/help` — справка по командам.\n\n"
        "Например:\n"
        "• `/tokens ivanova`\n"
        "• `/audit ivanova 5`\n"
        "• `/getchatid`"
    )
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    help_message = (
        "*Справка по командам:*\n\n"
        "• `/start` — Приветственное сообщение с перечнем команд.\n"
        "• `/tokens <логин>` — Получить список токенов для указанного пользователя.\n"
        "   _Пример:_ `/tokens ivanova`\n\n"
        "• `/audit <логин> [количество]` — Получить записи аудита для указанного пользователя.\n"
        "   _Пример:_ `/audit ivanova 5`\n"
        "   Если количество указано, бот отправит текстовый файл с результатами.\n\n"
        "• `/getchatid` — Получить идентификатор чата, из которого отправлено сообщение."
    )
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

async def tokens_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/tokens ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    #await update.message.reply_text(
    #    f"Запрашиваю токены для пользователя: *{user_login}* ...", parse_mode=ParseMode.MARKDOWN
    #)
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
            token_message = (
                "```\n"
                f"ID: {token_id}\n"
                f"Тип: {token_type}\n"
                f"Статус: {state}\n"
                "```"
            )
            response_lines.append(token_message)
        response = "\n".join(response_lines)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Токены не найдены или произошла ошибка.")

async def audit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/audit ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    # Если указан второй аргумент, считаем его количеством записей
    if len(context.args) > 1:
        try:
            count_arg = int(context.args[1])
        except ValueError:
            count_arg = N
        send_file = True
    else:
        count_arg = N
        send_file = False

    #await update.message.reply_text(
    #    f"Запрашиваю записи аудита для пользователя: *{user_login}* ...", parse_mode=ParseMode.MARKDOWN
    #)
    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return
    audit_logs = get_audit_logs(jwt_token, user_login, count_arg)
    if audit_logs:
        if send_file:
            # Формирование результатов в текстовом виде
            audit_text = ""
            for log in audit_logs:
                audit_text += f"Логин: {log.get('audit_login', '')}\n"
                audit_text += f"Время: {log.get('audit_datetime', '')}\n"
                audit_text += f"IP: {log.get('audit_ip_address', '')}\n"
                audit_text += f"Агент: {log.get('audit_agent', '')}\n"
                audit_text += f"Результат: {log.get('audit_result', '')}\n"
                audit_text += f"Номер токена: {log.get('audit_serialnumber', '')}\n"
                audit_text += f"Комментарий: {log.get('audit_comments', '')}\n"
                audit_text += "\n"
            file_obj = io.BytesIO(audit_text.encode('utf-8'))
            file_obj.name = f"audit_{user_login}.txt"
            await update.message.reply_document(
                document=InputFile(file_obj),
                caption=f"Записи аудита для пользователя: {user_login}"
            )
        else:
            response_lines = ["*Записи аудита:*"]
            for log in audit_logs:
                audit_message = (
                    "```\n"
                    f"Логин: {log.get('audit_login', '')}\n"
                    f"Время: {log.get('audit_datetime', '')}\n"
                    f"IP: {log.get('audit_ip_address', '')}\n"
                    f"Агент: {log.get('audit_agent', '')}\n"
                    f"Результат: {log.get('audit_result', '')}\n"
                    f"Номер токена: {log.get('audit_serialnumber', '')}\n"
                    f"Комментарий: {log.get('audit_comments', '')}\n"
                    "```"
                )
                response_lines.append(audit_message)
            response = "\n".join(response_lines)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Записи аудита не найдены или произошла ошибка.")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Chat ID: {chat_id}")

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("tokens", tokens_handler))
    app.add_handler(CommandHandler("audit", audit_handler))
    app.add_handler(CommandHandler("getchatid", get_chat_id))
    logger.info("Бот запущен.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
