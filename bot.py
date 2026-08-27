import telebot
import json
import os
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import threading
import time

# ============================================
# ТОКЕНЫ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# Файл с данными
USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# ============================================
# РАБОТА С JSON
# ============================================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def create_user(username, user_id):
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "user_id": str(user_id),
        "status": "inactive",
        "end_date": None
    }
    save_users(users)
    return True

def get_user_by_id(user_id):
    users = load_users()
    for name, data in users.items():
        if data.get("user_id") == str(user_id):
            return name, data
    return None, None

def give_access(username, plan):
    users = load_users()
    if username not in users:
        return False
    
    days = {"1": 7, "2": 30, "3": 365, "4": None}.get(plan)
    if days is None:
        users[username]["status"] = "active"
        users[username]["end_date"] = None
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        users[username]["status"] = "active"
        users[username]["end_date"] = end_date
    
    save_users(users)
    return True

def get_status(username):
    users = load_users()
    if username not in users:
        return None
    
    status = users[username].get("status", "inactive")
    end_date = users[username].get("end_date")
    
    if status == "active" and end_date:
        if datetime.now().isoformat() > end_date:
            users[username]["status"] = "inactive"
            users[username]["end_date"] = None
            save_users(users)
            return "inactive"
    
    return status

def list_users():
    users = load_users()
    return [(name, data["status"], data.get("end_date")) for name, data in users.items()]

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
        bot.reply_to(m, "❌ Имя занято")

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
# ВЕБ-СЕРВЕР
# ============================================
@app.route('/')
def index():
    return "PyAI Bot is running!"

@app.route('/ping')
def ping():
    return "OK", 200

@app.route('/register-web', methods=['POST'])
def register_web():
    try:
        username = request.form.get('username', '').strip()
        user_id = request.form.get('user_id', '').strip()
        
        if not username:
            return "Введите имя", 400
        
        if len(username) < 2:
            return "Имя должно быть не менее 2 символов", 400
        
        if create_user(username, user_id):
            bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username} (через сайт)")
            return "Регистрация успешна! Ожидайте активации.", 200
        else:
            return "Пользователь с таким именем уже существует", 400
    except Exception as e:
        return f"Ошибка: {str(e)}", 500

# ============================================
# ЗАПУСК
# ============================================
def run_bot():
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)

def run_web():
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Веб-сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем веб-сервер в главном потоке
    run_web()
