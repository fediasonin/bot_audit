import logging
import os
import shlex

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
        response = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=False)
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
    url = f"{BASE_URL}/sdk/users/user-tokens"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    data = {
        "org_name": ORG_NAME,
        "user_login": user_login
    }
    try:
        resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=False)
        if resp.status_code == 200:
            body = resp.json()
            if body.get("Result") == 0:
                tokens = body.get("Data", [])
                return tokens[:count]
            else:
                logger.error("Ошибка запроса /sdk/users/user-tokens: %s", body.get("Details", "(нет описания)"))
        else:
            logger.error("HTTP ошибка /sdk/users/user-tokens: %s %s", resp.status_code, resp.text)
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
        resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=False)
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
        "• `/enrollments <логин>` — получить список задач активации для пользователя.\n"
        "• `/getchatid` — получить идентификатор чата.\n"
        "• `/help` — справка по командам.\n\n"
        "• `/activelink` — cсылки на задачи активации.\n\n"
        "• `/sshlogs 'логин'` — получить логи через SSH (как на скриншоте).\n\n"
        "Например:\n"
        "• `/enrollments ivanova`\n"
        "• `/tokens ivanova`\n"
        "• `/audit ivanova 5`\n"
        "• `/getchatid`\n"
        "• `/activelink ivanova`"
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
        "• `/sshlogs 'логин'` — Получить логи через SSH в формате как на скриншоте.\n"
        "   _Пример:_ `/sshlogs 'ivanova'`\n\n"
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


async def ssh_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        logger.warning(f"Доступ запрещен для chat_id: {update.effective_chat.id}")
        return

    if not context.args:
        logger.warning("Не указан логин пользователя")
        await update.message.reply_text(
            "Пожалуйста, укажите логин: `/sshlogs 'логин'`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    user_login = context.args[0].strip("'\"")
    logger.info(f"Запрошены логи для пользователя: {user_login}")

    ssh_key_path = "/app/ssh/id_ed25519"
    ssh_host = "10.4.96.65"
    ssh_user = "tgbot"

    if not os.path.exists(ssh_key_path):
        error_msg = f"SSH ключ не найден по пути: {ssh_key_path}"
        logger.error(error_msg)
        await update.message.reply_text(f"Ошибка конфигурации: {error_msg}")
        return

    try:
        safe_login = shlex.quote(user_login)

        ssh_command = [
            "ssh",
            "-i", ssh_key_path,
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=/app/ssh/known_hosts",
            "-o", "LogLevel=ERROR",
            f"{ssh_user}@{ssh_host}",
            safe_login
        ]

        logger.debug(f"Формируемая SSH команда: {' '.join(ssh_command)}")

        process = await asyncio.create_subprocess_exec(
            *ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        logger.info(f"Запущен SSH процесс (PID: {process.pid}) для пользователя: {user_login}")

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error(f"Таймаут SSH соединения для {user_login}")
            await update.message.reply_text("Превышено время ожидания ответа от сервера")
            return

        exit_code = process.returncode
        logger.debug(f"SSH процесс завершен с кодом: {exit_code}")

        if exit_code == 0:
            logs = stdout.decode().strip()
            if logs:
                logger.info(f"Успешно получены логи для {user_login} (длина: {len(logs)} символов)")
                if len(logs) <= 4000:
                    await update.message.reply_text(
                        f"<b>Логи для {user_login}:</b>\n\n<pre>{logs}</pre>",
                        parse_mode=ParseMode.HTML
                    )
                else:
                    file_obj = io.BytesIO(logs.encode('utf-8'))
                    file_obj.name = f"logs_{user_login}.txt"
                    await update.message.reply_document(
                        document=InputFile(file_obj),
                        caption=f"Логи для {user_login} (вложением, т.к. длинные)"
                    )
            else:
                logger.warning(f"Пустой ответ от сервера для {user_login}")
                await update.message.reply_text("Сервер вернул пустой ответ")
        else:
            error_msg = stderr.decode().strip()
            logger.error(f"SSH ошибка (код {exit_code}): {error_msg}")

            if "Permission denied" in error_msg:
                error_msg = "Ошибка доступа: неверный SSH ключ или права"
            elif "Connection timed out" in error_msg:
                error_msg = "Таймаут соединения с сервером"

            await update.message.reply_text(f"Ошибка SSH:\n{error_msg}")

    except FileNotFoundError as e:
        logger.error(f"Не найден SSH клиент: {str(e)}")
        await update.message.reply_text("Ошибка: SSH клиент не установлен в системе")
    except Exception as e:
        logger.exception(f"Неожиданная ошибка при обработке запроса для {user_login}")
        await update.message.reply_text(f"Произошла непредвиденная ошибка: {str(e)}")


def generate_login_variants(login: str) -> list:
    login = login.strip()
    if not login:
        return []
    # Вариант 1 – весь логин в нижнем регистре
    variant1 = login.lower()
    # Вариант 2 – первая буква и две последние буквы в верхнем регистре (если длина позволяет)
    if len(login) >= 3:
        variant2 = login[0].upper() + login[1:-2].lower() + login[-2:].upper()
    else:
        variant2 = login.upper()
    return list({variant1, variant2})


def get_enrollment_tasks_universal(token, user_login):
    variants = generate_login_variants(user_login)
    logger.info("Генерируем варианты логина для '%s': %s", user_login, variants)
    all_tasks = []
    errors = []
    for variant in variants:
        url = f"{BASE_URL}/sdk/users/enrollments"
        headers = {"Authorization": token, "Content-Type": "application/json"}
        data = {"org_name": ORG_NAME, "user_login": variant}
        try:
            resp = requests.get(url, headers=headers, data=json.dumps(data), timeout=10, verify=False)
            logger.info("Запрос для логина '%s': HTTP %s, ответ: %s", variant, resp.status_code, resp.text)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("Result") == 0:
                    all_tasks.extend(body.get("Data", []))
                else:
                    errors.append(f"Логин '{variant}': {body.get('Details', 'Нет описания')}")
            else:
                errors.append(f"Логин '{variant}': HTTP {resp.status_code}: {resp.text}")
        except requests.exceptions.RequestException as e:
            errors.append(f"Логин '{variant}': Сетевая ошибка: {str(e)}")
    # Убираем дубли по enrollment_id
    unique_tasks = {task.get("enrollment_id"): task for task in all_tasks}.values()
    return list(unique_tasks), errors

async def enrollments_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/enrollments ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return
    enrollment_tasks, errors = get_enrollment_tasks_universal(jwt_token, user_login)
    if errors:
        error_text = "\n".join(errors)
        await update.message.reply_text(f"Ошибка при получении задач активации:\n{error_text}", parse_mode=ParseMode.MARKDOWN)
    else:
        if enrollment_tasks:
            response_lines = ["*Список задач активации:*"]
            for task in enrollment_tasks:
                enrollment_id = task.get("enrollment_id")
                enrollment_stop_date = task.get("enrollment_stop_date", "")
                enrollment_url = task.get("enrollment_url", "")
                task_message = (
                    "```\n"
                    f"ID: {enrollment_id}\n"
                    f"Дата окончания: {enrollment_stop_date}\n"
                    "```"
                )
                response_lines.append(task_message)
            response = "\n".join(response_lines)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("У пользователя отсутствуют задачи активации.", parse_mode=ParseMode.MARKDOWN)


async def active_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите логин. Пример: `/activelink ivanova`", parse_mode=ParseMode.MARKDOWN)
        return
    user_login = context.args[0]
    jwt_token = get_jwt_token()
    if not jwt_token:
        await update.message.reply_text("Ошибка авторизации. Попробуйте позже.")
        return
    enrollment_tasks, errors = get_enrollment_tasks_universal(jwt_token, user_login)
    if errors:
        error_text = "\n".join(errors)
        await update.message.reply_text(f"Ошибка при получении задач:\n{error_text}", parse_mode=ParseMode.MARKDOWN)
    else:
        links = [t.get("enrollment_url") for t in enrollment_tasks if t.get("enrollment_url")]
        if links:
            link_text = "*Ссылки на задачи активации:*\n\n"
            link_text += "\n".join([f"{i+1}. {link}" for i, link in enumerate(links)])
            await update.message.reply_text(link_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("Активных ссылок на задачи не найдено.", parse_mode=ParseMode.MARKDOWN)


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #if update.effective_chat.id != ALLOWED_CHAT_ID:
    #    return
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Chat ID: {chat_id}")


async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Список команд с описаниями для подсказок
    commands = [
        ("start", "Начальное сообщение"),
        ("help", "Показать справку"),
        ("tokens", "Получить токены пользователя"),
        ("audit", "Получить записи аудита"),
        ("enrollments", "Задачи активации"),
        ("getchatid", "Узнать ID чата"),
        ("activelink", "Ссылки на активации"),
        ("sshlogs", "Получить логи через SSH")
    ]

    # Устанавливаем команды для отображения в подсказках
    await app.bot.set_my_commands(commands)

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("tokens", tokens_handler))
    app.add_handler(CommandHandler("audit", audit_handler))
    app.add_handler(CommandHandler("getchatid", get_chat_id))
    app.add_handler(CommandHandler("enrollments", enrollments_handler))
    app.add_handler(CommandHandler("activelink", active_link_handler))
    app.add_handler(CommandHandler("sshlogs", ssh_logs_handler))
    logger.info("Бот запущен.")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
