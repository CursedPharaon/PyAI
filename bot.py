import logging
import requests
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ============================================
# НАСТРОЙКИ
# ============================================
TELEGRAM_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"  # ВСТАВЬ СВОЙ ТОКЕН
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# Turso HTTP API
TURSO_URL = "https://pyai-cursedd.aws-eu-west-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODc4Mzg2OTAsImlkIjoiMDFhMDQzN2QtMmQwMS03ZjZmLTk1MDAtNTUzZTI5YzFjNmI1Iiwia2lkIjoicWpYbEhLbElGQmJNX29uRDlaWEkyWFVfazVBT3h3X3JIMF9TcUZ6MmU0ZyIsInJpZCI6IjZhMzk2M2ZkLWYzM2QtNGE2MS1hMTQwLTQyYWU1ZTExZWQ5NCJ9.2pxIFQ_FkjhaNgqU6Adj6pEOaSxRx_rVI6Jc8SdAbvLMYbXWxsyhH8q78TZKcCQ51m7RiitFUzfOGUr-2UalAg"

logging.basicConfig(level=logging.INFO)

# ============================================
# ФУНКЦИИ РАБОТЫ С TURSO ЧЕРЕЗ HTTP
# ============================================
def turso_query(sql, params=None):
    """Выполняет SQL-запрос к Turso через HTTP API"""
    url = f"{TURSO_URL}/v1/query"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Параметры для запроса
    data = {
        "sql": sql,
        "params": params or {}
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Turso error: {e}")
        return None

def init_db():
    """Создаёт таблицу пользователей"""
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        subscription_status TEXT DEFAULT 'inactive',
        subscription_end TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """
    turso_query(sql)

def get_subscription_days(plan):
    plans = {
        "1": 7,
        "2": 30,
        "3": 365,
        "4": None
    }
    return plans.get(plan)

def give_access(email, plan):
    days = get_subscription_days(plan)
    if days is None:
        sql = """
            UPDATE users 
            SET subscription_status = 'active', subscription_end = NULL 
            WHERE email = ?
        """
        params = [email]
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        sql = """
            UPDATE users 
            SET subscription_status = 'active', subscription_end = ? 
            WHERE email = ?
        """
        params = [end_date, email]
    
    result = turso_query(sql, params)
    return result is not None

def remove_access(email):
    sql = """
        UPDATE users 
        SET subscription_status = 'inactive', subscription_end = NULL 
        WHERE email = ?
    """
    result = turso_query(sql, [email])
    return result is not None

def get_user_status(email):
    sql = "SELECT subscription_status, subscription_end FROM users WHERE email = ?"
    result = turso_query(sql, [email])
    if not result or not result.get('results'):
        return None
    
    rows = result['results'][0].get('rows', [])
    if not rows:
        return None
    
    status = rows[0][0]
    end_date = rows[0][1] if len(rows[0]) > 1 else None
    
    if status == 'active' and end_date:
        if datetime.now().isoformat() > end_date:
            turso_query("UPDATE users SET subscription_status = 'inactive' WHERE email = ?", [email])
            return 'inactive'
    return status

def list_users():
    sql = "SELECT email, subscription_status, subscription_end FROM users"
    result = turso_query(sql)
    if not result or not result.get('results'):
        return []
    
    rows = result['results'][0].get('rows', [])
    return [(row[0], row[1], row[2] if len(row) > 2 else None) for row in rows]

def register_user(email, password):
    sql = """
        INSERT INTO users (email, password, subscription_status)
        VALUES (?, ?, 'inactive')
    """
    result = turso_query(sql, [email, password])
    return result is not None

def check_user_exists(email):
    sql = "SELECT id FROM users WHERE email = ?"
    result = turso_query(sql, [email])
    if not result or not result.get('results'):
        return False
    rows = result['results'][0].get('rows', [])
    return len(rows) > 0

# ============================================
# ФУНКЦИЯ ЗАПРОСА К OPENROUTER
# ============================================
def ask_openrouter(prompt):
    try:
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть. Отвечай полезно и понятно. Ты полностью бесплатна для всех пользователей."},
                {"role": "user", "content": prompt}
            ]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'HTTP-Referer': 'https://t.me/PyAI_bot',
            'X-Title': 'PyAI Bot'
        }
        
        response = requests.post(OPENROUTER_URL, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)[:200]}"

# ============================================
# КОМАНДЫ БОТА
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    await update.message.reply_text(
        "👋 Привет, админ!\n\n"
        "📌 Команды:\n"
        "/giveaccess email 1-4 - дать доступ (1-неделя, 2-месяц, 3-год, 4-вечный)\n"
        "/removeaccess email - отключить доступ\n"
        "/listusers - список пользователей\n"
        "/checkuser email - проверить статус\n"
        "/stats - статистика\n"
        "/ask вопрос - спросить у PyAI"
    )

async def give_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Использование: /giveaccess email@example.com 1-4")
        return
    
    email, plan = context.args[0], context.args[1]
    if plan not in ["1", "2", "3", "4"]:
        await update.message.reply_text("❌ План: 1-неделя, 2-месяц, 3-год, 4-вечный")
        return
    
    if not check_user_exists(email):
        await update.message.reply_text(f"❌ Пользователь {email} не найден.")
        return
    
    give_access(email, plan)
    plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
    await update.message.reply_text(f"✅ Доступ выдан на {plan_names[plan]} для {email}")

async def remove_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /removeaccess email@example.com")
        return
    
    email = context.args[0]
    remove_access(email)
    await update.message.reply_text(f"✅ Доступ отключён для {email}")

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    users = list_users()
    if not users:
        await update.message.reply_text("📭 Нет пользователей")
        return
    
    text = "📋 Список пользователей:\n\n"
    for email, status, end_date in users:
        status_emoji = "✅" if status == 'active' else "❌"
        end_str = f"до {end_date[:10]}" if end_date else "бессрочно"
        text += f"{status_emoji} {email} | {status} {end_str}\n"
    
    await update.message.reply_text(text[:4000])

async def check_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /checkuser email@example.com")
        return
    
    email = context.args[0]
    status = get_user_status(email)
    if status is None:
        await update.message.reply_text(f"❌ Пользователь {email} не найден")
    else:
        await update.message.reply_text(f"📊 Статус {email}: {status}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    result = turso_query("SELECT COUNT(*) FROM users")
    total = result['results'][0]['rows'][0][0] if result and result.get('results') else 0
    
    result = turso_query("SELECT COUNT(*) FROM users WHERE subscription_status = 'active'")
    active = result['results'][0]['rows'][0][0] if result and result.get('results') else 0
    
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"👥 Всего: {total}\n"
        f"✅ Активных: {active}\n"
        f"❌ Неактивных: {total - active}"
    )

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /ask вопрос")
        return
    
    question = ' '.join(context.args)
    await update.message.reply_text("🤔 Думаю...")
    response = ask_openrouter(question)
    await update.message.reply_text(f"🧠 PyAI:\n{response[:4000]}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён. Обратитесь к администратору.")
        return
    
    await update.message.reply_text("🤔 Думаю...")
    response = ask_openrouter(update.message.text)
    await update.message.reply_text(f"🧠 PyAI:\n{response[:4000]}")

# ============================================
# ЗАПУСК
# ============================================
def main():
    # Инициализируем БД
    init_db()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("giveaccess", give_access_command))
    app.add_handler(CommandHandler("removeaccess", remove_access_command))
    app.add_handler(CommandHandler("listusers", list_users_command))
    app.add_handler(CommandHandler("checkuser", check_user_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
