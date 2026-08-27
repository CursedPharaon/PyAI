import telebot
import requests
import json
from datetime import datetime, timedelta
from flask import Flask
import threading
import os
import time

# ============================================
# ТОКЕНЫ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# ============================================
# SUPABASE (ТВОИ ДАННЫЕ)
# ============================================
SUPABASE_URL = "https://sycmhhibqeagzzfvjsdp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN5Y21oaWlicWVhZ3p6ZnZqc2RwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc4NTQ4ODAsImV4cCI6MjEwMzQzMDg4MH0.-isC-BKW5zvywzxTQ_IvUKBdWAONrIVocHbDsiYFaGk"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ============================================
# СОЗДАНИЕ ТАБЛИЦЫ (автоматически)
# ============================================
def init_database():
    """Создаёт таблицу users, если её нет"""
    try:
        # Проверяем, существует ли таблица
        url = f"{SUPABASE_URL}/rest/v1/users?limit=1"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code == 404:
            # Таблицы нет — создаём через SQL (не работает через REST)
            print("⚠️ Таблица users не найдена. Создайте её вручную в Supabase SQL Editor:")
            print("""
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'inactive',
    end_date TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
            """)
        else:
            print("✅ Таблица users существует")
    except Exception as e:
        print(f"Ошибка проверки таблицы: {e}")

# ============================================
# РАБОТА С SUPABASE
# ============================================
def get_user_by_id(user_id):
    """Получает пользователя по Telegram ID"""
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}&select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return data[0]["username"], data[0]
        return None, None
    except Exception as e:
        print(f"get_user_by_id error: {e}")
        return None, None

def create_user(username, user_id):
    """Создаёт нового пользователя"""
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    data = {
        "username": username,
        "user_id": str(user_id),
        "status": "inactive",
        "end_date": None
    }
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"create_user status: {r.status_code}, response: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"create_user error: {e}")
        return False

def give_access(username, plan):
    """Выдаёт доступ"""
    days = {"1": 7, "2": 30, "3": 365, "4": None}.get(plan)
    end_date = None
    if days:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
    
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    data = {"status": "active", "end_date": end_date}
    try:
        r = requests.patch(url, json=data, headers=headers, timeout=10)
        print(f"give_access status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"give_access error: {e}")
        return False

def get_status(username):
    """Проверяет статус подписки"""
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=status,end_date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        
        status = data[0].get("status", "inactive")
        end_date = data[0].get("end_date")
        
        if status == "active" and end_date:
            if datetime.now().isoformat() > end_date:
                # Отключаем, если срок истёк
                update_url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}"
                headers_update = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                }
                requests.patch(update_url, json={"status": "inactive", "end_date": None}, headers=headers_update, timeout=10)
                return "inactive"
        return status
    except Exception as e:
        print(f"get_status error: {e}")
        return None

def list_users():
    """Список всех пользователей"""
    url = f"{SUPABASE_URL}/rest/v1/users?select=username,status,end_date&order=created_at.asc"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [(item["username"], item["status"], item.get("end_date")) for item in data]
    except Exception as e:
        print(f"list_users error: {e}")
        return []

# ============================================
# OPENROUTER
# ============================================
def ask_ai(question):
    try:
        r = requests.post(
            OPENROUTER_URL,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть."},
                    {"role": "user", "content": question}
                ]
            },
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENROUTER_API_KEY}'
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)[:200]}"

# ============================================
# КОМАНДЫ БОТА
# ============================================
@bot.message_handler(commands=['start'])
def start(m):
    user_id = m.from_user.id
    name, data = get_user_by_id(user_id)
    
    if name:
        status = get_status(name)
        if status == "active":
            bot.reply_to(m, f"✅ Привет, {name}! Подписка активна. Задавай вопросы!")
        else:
            bot.reply_to(m, f"❌ Привет, {name}! Подписка неактивна. Напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "👋 Привет! Отправь /register Имя")

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}! Ожидай активации.")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        bot.reply_to(m, "❌ Имя занято или ошибка БД")

@bot.message_handler(commands=['giveaccess'])
def give(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    parts = m.text.split()
    if len(parts) != 3:
        bot.reply_to(m, "❌ /giveaccess имя 1-4")
        return
    
    name, plan = parts[1], parts[2]
    if give_access(name, plan):
        plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
        bot.reply_to(m, f"✅ {name} получил доступ на {plan_names[plan]}")
    else:
        bot.reply_to(m, f"❌ {name} не найден")

@bot.message_handler(commands=['listusers'])
def listu(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    users = list_users()
    if not users:
        bot.reply_to(m, "📭 Нет пользователей")
        return
    
    text = "📋 Список:\n"
    for name, status, end in users:
        emoji = "✅" if status == "active" else "❌"
        end_str = f"до {end[:10]}" if end else "навсегда" if status == "active" else ""
        text += f"{emoji} {name} | {status} {end_str}\n"
    
    bot.reply_to(m, text)

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    user_id = m.from_user.id
    name, data = get_user_by_id(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Зарегистрируйся: /register Имя")
        return
    
    status = get_status(name)
    if status != "active":
        bot.reply_to(m, "❌ Подписка неактивна. Напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_ai(m.text)
    bot.reply_to(m, f"🧠 {response[:4000]}")

# ============================================
# ВЕБ-СЕРВЕР (для Render)
# ============================================
@app.route('/')
def index():
    users = list_users()
    return f"PyAI Bot is running! 👥 Users: {len(users)}"

@app.route('/ping')
def ping():
    return "OK", 200

def run_bot():
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)

def run_web():
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Веб-сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    print("🚀 Запуск PyAI бота...")
    init_database()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_web()
