import telebot
import requests
from flask import Flask, request
import os
import json

BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

SUPABASE_URL = "https://sycmhhibqeagzzfvjsdp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN5Y21oaWlicWVhZ3p6ZnZqc2RwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc4NTQ4ODAsImV4cCI6MjEwMzQzMDg4MH0.-isC-BKW5zvywzxTQ_IvUKBdWAONrIVocHbDsiYFaGk"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ============================================
# ФУНКЦИИ БАЗЫ С ЛОГАМИ
# ============================================
def log(msg):
    print(f"[LOG] {msg}")

def user_exists(username):
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=username"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        log(f"user_exists: статус {r.status_code}, ответ: {r.text}")
        if r.status_code == 200:
            data = r.json()
            return len(data) > 0
        return False
    except Exception as e:
        log(f"user_exists ошибка: {e}")
        return False

def create_user(username, user_id):
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
        log(f"create_user: отправка {json.dumps(data)}")
        r = requests.post(url, json=data, headers=headers, timeout=10)
        log(f"create_user: статус {r.status_code}, ответ: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        log(f"create_user ошибка: {e}")
        return False

def get_user_by_id(user_id):
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}&select=username,status,end_date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        log(f"get_user_by_id: статус {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0]["username"], data[0]
        return None, None
    except Exception as e:
        log(f"get_user_by_id ошибка: {e}")
        return None, None

def get_status(username):
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=status,end_date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        log(f"get_status: статус {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0].get("status", "inactive")
        return None
    except Exception as e:
        log(f"get_status ошибка: {e}")
        return None

def give_access(username, plan):
    from datetime import datetime, timedelta
    days = {"1": 7, "2": 30, "3": 365, "4": None}.get(plan)
    end_date = (datetime.now() + timedelta(days=days)).isoformat() if days else None
    
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    data = {"status": "active", "end_date": end_date}
    try:
        r = requests.patch(url, json=data, headers=headers, timeout=10)
        log(f"give_access: статус {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"give_access ошибка: {e}")
        return False

def list_users():
    url = f"{SUPABASE_URL}/rest/v1/users?select=username,status,end_date"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return [(item["username"], item["status"], item.get("end_date")) for item in r.json()]
        return []
    except:
        return []

# ============================================
# OPENROUTER
# ============================================
def ask_ai(question):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть."},
                    {"role": "user", "content": question}
                ]
            },
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer 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'
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
            bot.reply_to(m, f"✅ Привет, {name}! Подписка активна!")
        else:
            bot.reply_to(m, f"❌ Привет, {name}! Подписка неактивна. Напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "👋 Отправь /register Имя для регистрации")

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ Использование: /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    log(f"===== РЕГИСТРАЦИЯ: {username} (user_id: {user_id}) =====")
    
    # Проверяем, существует ли пользователь
    if user_exists(username):
        log(f"Имя {username} уже занято")
        bot.reply_to(m, f"❌ Имя '{username}' уже занято")
        return
    
    # Создаём пользователя
    if create_user(username, user_id):
        log(f"✅ Регистрация успешна: {username}")
        bot.reply_to(m, f"✅ Регистрация успешна, {username}! Ожидай активации.")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        log(f"❌ Ошибка регистрации: {username}")
        bot.reply_to(m, "❌ Ошибка регистрации. Попробуй позже.")

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
        text += f"{emoji} {name} | {status}\n"
    
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
# ВЕБ-ХУК
# ============================================
@app.route('/', methods=['GET'])
def index():
    return "PyAI Bot is running! ✅"

@app.route('/ping', methods=['GET'])
def ping():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    # Устанавливаем веб-хук
    WEBHOOK_URL = f"https://pyai-7edz.onrender.com/webhook"
    
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")
    
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
