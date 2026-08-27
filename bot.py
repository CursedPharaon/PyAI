


import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from libsql_client import create_client
from datetime import datetime, timedelta
import os
import json
import urllib.request
import urllib.error

# ============================================
# НАСТРОЙКИ
# ============================================
TELEGRAM_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

DB_URL = "libsql://pyai-cursedd.aws-eu-west-1.turso.io"
DB_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODc4Mzg2OTAsImlkIjoiMDFhMDQzN2QtMmQwMS03ZjZmLTk1MDAtNTUzZTI5YzFjNmI1Iiwia2lkIjoicWpYbEhLbElGQmJNX29uRDlaWEkyWFVfazVBT3h3X3JIMF9TcUZ6MmU0ZyIsInJpZCI6IjZhMzk2M2ZkLWYzM2QtNGE2MS1hMTQwLTQyYWU1ZTExZWQ5NCJ9.2pxIFQ_FkjhaNgqU6Adj6pEOaSxRx_rVI6Jc8SdAbvLMYbXWxsyhH8q78TZKcCQ51m7RiitFUzfOGUr-2UalAg"

# ============================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ============================================
conn = create_client(sync_url=DB_URL, auth_token=DB_TOKEN)

# Создаём таблицы
conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    subscription_status TEXT DEFAULT 'inactive',
    subscription_end TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

logging.basicConfig(level=logging.INFO)

# ============================================
# ФУНКЦИИ БАЗЫ
# ============================================
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
        conn.execute("""
            UPDATE users 
            SET subscription_status = 'active', subscription_end = NULL 
            WHERE email = ?
        """, (email,))
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        conn.execute("""
            UPDATE users 
            SET subscription_status = 'active', subscription_end = ? 
            WHERE email = ?
        """, (end_date, email))
    return True

def remove_access(email):
    conn.execute("""
        UPDATE users 
        SET subscription_status = 'inactive', subscription_end = NULL 
        WHERE email = ?
    """, (email,))
    return True

def get_user_status(email):
    result = conn.execute("""
        SELECT subscription_status, subscription_end FROM users WHERE email = ?
    """, (email,))
    row = result.fetchone()
    if not row:
        return None
    status, end_date = row
    if status == 'active' and end_date:
        if datetime.now().isoformat() > end_date:
            conn.execute("UPDATE users SET subscription_status = 'inactive' WHERE email = ?", (email,))
            return 'inactive'
    return status

def list_users():
    result = conn.execute("SELECT email, subscription_status, subscription_end FROM users")
    return result.fetchall()

def register_user(email, password):
    try:
        conn.execute("""
            INSERT INTO users (email, password, subscription_status)
            VALUES (?, ?, 'inactive')
        """, (email, password))
        return True
    except:
        return False

def check_user_exists(email):
    result = conn.execute("SELECT id FROM users WHERE email = ?", (email,))
    return result.fetchone() is not None

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
        
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'HTTP-Referer': 'https://t.me/PyAI_bot',
                'X-Title': 'PyAI Bot'
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    
    except urllib.error.HTTPError as e:
        error_text = e.read().decode('utf-8') if e.fp else str(e)
        return f"⚠️ Ошибка API: {e.code} - {error_text[:200]}"
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
        await update.message.reply_text(f"❌ Пользователь {email} не найден. Сначала зарегистрируйтесь на сайте.")
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
        await update.message.reply_text("📭 Нет зарегистрированных пользователей")
        return
    
    text = "📋 Список пользователей:\n\n"
    for email, status, end_date in users:
        status_emoji = "✅" if status == 'active' else "❌"
        end_str = f"до {end_date[:10]}" if end_date else "бессрочно" if status == 'active' else "-"
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
    
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM users WHERE subscription_status = 'active'").fetchone()[0]
    
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"👥 Всего пользователей: {total}\n"
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
