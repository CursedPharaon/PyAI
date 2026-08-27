import telebot
import requests
from flask import Flask
import threading
import os

BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

SUPABASE_URL = "https://sycmhhibqeagzzfvjsdp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN5Y21oaWlicWVhZ3p6ZnZqc2RwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc4NTQ4ODAsImV4cCI6MjEwMzQzMDg4MH0.-isC-BKW5zvywzxTQ_IvUKBdWAONrIVocHbDsiYFaGk"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ============================================
# ПРОВЕРКА ПОДКЛЮЧЕНИЯ
# ============================================
def test_connection():
    """Проверяет подключение к Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/users?limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"🔍 Статус подключения: {r.status_code}")
        print(f"📝 Ответ: {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

def create_user_simple(username, user_id):
    """Простое создание пользователя"""
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
        "status": "inactive"
    }
    try:
        print(f"📤 Отправка: {data}")
        r = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"📥 Статус: {r.status_code}")
        print(f"📥 Ответ: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def list_users_simple():
    """Простой список пользователей"""
    url = f"{SUPABASE_URL}/rest/v1/users?select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"📥 Список пользователей: {r.text}")
        return r.json()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

# ============================================
# КОМАНДЫ БОТА
# ============================================
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "👋 Привет! Отправь /register Имя для регистрации")

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    if create_user_simple(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}!")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        bot.reply_to(m, "❌ Ошибка регистрации. Проверь логи.")

@bot.message_handler(commands=['listusers'])
def listu(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    users = list_users_simple()
    if not users:
        bot.reply_to(m, "📭 Нет пользователей")
        return
    
    text = "📋 Список:\n"
    for user in users:
        text += f"- {user['username']} | {user['status']}\n"
    
    bot.reply_to(m, text)

# ============================================
# ВЕБ-СЕРВЕР
# ============================================
@app.route('/')
def index():
    return "PyAI Bot is running!"

@app.route('/ping')
def ping():
    return "OK", 200

def run_bot():
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    print("🚀 Запуск...")
    
    # Проверяем подключение
    if test_connection():
        print("✅ Подключение к Supabase работает!")
    else:
        print("❌ Проблема с подключением к Supabase")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_web()
