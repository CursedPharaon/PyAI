import telebot
import requests
import json
from datetime import datetime, timedelta
import time

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"  # ВСТАВЬ СВОЙ ТОКЕН
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# Turso HTTP API
TURSO_URL = "https://pyai-cursedd.aws-eu-west-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODc4Mzg2OTAsImlkIjoiMDFhMDQzN2QtMmQwMS03ZjZmLTk1MDAtNTUzZTI5YzFjNmI1Iiwia2lkIjoicWpYbEhLbElGQmJNX29uRDlaWEkyWFVfazVBT3h3X3JIMF9TcUZ6MmU0ZyIsInJpZCI6IjZhMzk2M2ZkLWYzM2QtNGE2MS1hMTQwLTQyYWU1ZTExZWQ5NCJ9.2pxIFQ_FkjhaNgqU6Adj6pEOaSxRx_rVI6Jc8SdAbvLMYbXWxsyhH8q78TZKcCQ51m7RiitFUzfOGUr-2UalAg"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# ФУНКЦИИ TURSO
# ============================================
def turso_query(sql, params=[]):
    url = f"{TURSO_URL}/v1/query"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Формат для Turso
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": params
                }
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Turso error: {e}")
        return None

def init_db():
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
    plans = {"1": 7, "2": 30, "3": 365, "4": None}
    return plans.get(plan)

def give_access(email, plan):
    days = get_subscription_days(plan)
    if days is None:
        sql = "UPDATE users SET subscription_status = 'active', subscription_end = NULL WHERE email = ?"
        params = [email]
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        sql = "UPDATE users SET subscription_status = 'active', subscription_end = ? WHERE email = ?"
        params = [end_date, email]
    
    result = turso_query(sql, params)
    return result is not None

def remove_access(email):
    sql = "UPDATE users SET subscription_status = 'inactive', subscription_end = NULL WHERE email = ?"
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

def check_user_exists(email):
    sql = "SELECT id FROM users WHERE email = ?"
    result = turso_query(sql, [email])
    if not result or not result.get('results'):
        return False
    rows = result['results'][0].get('rows', [])
    return len(rows) > 0

def register_user(email, password):
    sql = "INSERT INTO users (email, password, subscription_status) VALUES (?, ?, 'inactive')"
    result = turso_query(sql, [email, password])
    return result is not None

# ============================================
# ФУНКЦИЯ OPENROUTER
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
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    bot.reply_to(message, 
        "👋 Привет, админ!\n\n"
        "📌 Команды:\n"
        "/giveaccess email 1-4 - дать доступ\n"
        "/removeaccess email - отключить\n"
        "/listusers - список\n"
        "/checkuser email - статус\n"
        "/stats - статистика"
    )

@bot.message_handler(commands=['giveaccess'])
def give_access_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "❌ Использование: /giveaccess email@example.com 1-4")
        return
    
    email, plan = parts[1], parts[2]
    if plan not in ["1", "2", "3", "4"]:
        bot.reply_to(message, "❌ План: 1-неделя, 2-месяц, 3-год, 4-вечный")
        return
    
    if not check_user_exists(email):
        bot.reply_to(message, f"❌ Пользователь {email} не найден.")
        return
    
    give_access(email, plan)
    plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
    bot.reply_to(message, f"✅ Доступ выдан на {plan_names[plan]} для {email}")

@bot.message_handler(commands=['removeaccess'])
def remove_access_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /removeaccess email@example.com")
        return
    
    email = parts[1]
    remove_access(email)
    bot.reply_to(message, f"✅ Доступ отключён для {email}")

@bot.message_handler(commands=['listusers'])
def list_users_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    users = list_users()
    if not users:
        bot.reply_to(message, "📭 Нет пользователей")
        return
    
    text = "📋 Список:\n\n"
    for email, status, end_date in users:
        status_emoji = "✅" if status == 'active' else "❌"
        end_str = f"до {end_date[:10]}" if end_date else "бессрочно"
        text += f"{status_emoji} {email} | {status} {end_str}\n"
    
    bot.reply_to(message, text[:4000])

@bot.message_handler(commands=['checkuser'])
def check_user_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /checkuser email@example.com")
        return
    
    email = parts[1]
    status = get_user_status(email)
    if status is None:
        bot.reply_to(message, f"❌ Пользователь {email} не найден")
    else:
        bot.reply_to(message, f"📊 Статус {email}: {status}")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    result = turso_query("SELECT COUNT(*) FROM users")
    total = result['results'][0]['rows'][0][0] if result and result.get('results') else 0
    
    result = turso_query("SELECT COUNT(*) FROM users WHERE subscription_status = 'active'")
    active = result['results'][0]['rows'][0][0] if result and result.get('results') else 0
    
    bot.reply_to(message,
        f"📊 Статистика:\n"
        f"👥 Всего: {total}\n"
        f"✅ Активных: {active}\n"
        f"❌ Неактивных: {total - active}"
    )

@bot.message_handler(commands=['ask'])
def ask_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /ask вопрос")
        return
    
    question = parts[1]
    bot.reply_to(message, "🤔 Думаю...")
    response = ask_openrouter(question)
    bot.reply_to(message, f"🧠 PyAI:\n{response[:4000]}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Доступ запрещён.")
        return
    
    bot.reply_to(message, "🤔 Думаю...")
    response = ask_openrouter(message.text)
    bot.reply_to(message, f"🧠 PyAI:\n{response[:4000]}")

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    init_db()
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)
