import telebot
import requests
import json
import os
import threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ============================================
# РАБОТА С JSON-ФАЙЛОМ
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

def create_user(username, user_id=None):
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "user_id": user_id,
        "subscription_status": "inactive",
        "subscription_end": None,
        "created_at": datetime.now().isoformat()
    }
    save_users(users)
    return True

def give_access(username, plan):
    users = load_users()
    if username not in users:
        return False
    
    days = {"1": 7, "2": 30, "3": 365, "4": None}.get(plan)
    if days is None:
        users[username]["subscription_status"] = "active"
        users[username]["subscription_end"] = None
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        users[username]["subscription_status"] = "active"
        users[username]["subscription_end"] = end_date
    
    save_users(users)
    return True

def remove_access(username):
    users = load_users()
    if username not in users:
        return False
    users[username]["subscription_status"] = "inactive"
    users[username]["subscription_end"] = None
    save_users(users)
    return True

def get_user_status(username):
    users = load_users()
    if username not in users:
        return None
    
    user = users[username]
    status = user.get("subscription_status", "inactive")
    end_date = user.get("subscription_end")
    
    if status == "active" and end_date:
        if datetime.now().isoformat() > end_date:
            user["subscription_status"] = "inactive"
            user["subscription_end"] = None
            save_users(users)
            return "inactive"
    
    return status

def list_users():
    users = load_users()
    return [(username, data["subscription_status"], data.get("subscription_end")) 
            for username, data in users.items()]

def check_user_exists(username):
    users = load_users()
    return username in users

# ============================================
# OPENROUTER
# ============================================
def ask_openrouter(prompt):
    try:
        r = requests.post(
            OPENROUTER_URL,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть. Ты бесплатна."},
                    {"role": "user", "content": prompt}
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
    
    # Если пользователь уже зарегистрирован
    users = load_users()
    username = None
    for name, data in users.items():
        if data.get("user_id") == user_id:
            username = name
            break
    
    if username:
        status = get_user_status(username)
        if status == "active":
            bot.reply_to(m, f"✅ Привет, {username}! Твоя подписка активна. Задавай любой вопрос!")
        else:
            bot.reply_to(m, f"❌ Привет, {username}! Твоя подписка неактивна. Для продления напиши @cursed_pharaon")
        return
    
    # Если не зарегистрирован
    bot.reply_to(m, 
        "👋 Добро пожаловать в PyAI!\n\n"
        "Чтобы начать пользоваться, зарегистрируйся на сайте или отправь /register Имя\n\n"
        "💡 Подписка активируется администратором.\n"
        "📩 Для продления подписки напишите @cursed_pharaon"
    )

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ Использование: /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    if check_user_exists(username):
        bot.reply_to(m, f"❌ Имя '{username}' уже занято")
        return
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}! Ожидай активации от администратора.\n\n📩 Для продления подписки напишите @cursed_pharaon")
        
        # Уведомляем админа
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username} (ID: {user_id})")
    else:
        bot.reply_to(m, "❌ Ошибка регистрации")

@bot.message_handler(commands=['giveaccess'])
def give(m):
    if m.from_user.id != ADMIN_ID:
        bot.reply_to(m, "⛔ Доступ запрещён.")
        return
    
    parts = m.text.split()
    if len(parts) != 3 or parts[2] not in ["1","2","3","4"]:
        bot.reply_to(m, "❌ /giveaccess имя 1-4\n1-неделя, 2-месяц, 3-год, 4-вечный")
        return
    
    username, plan = parts[1], parts[2]
    if not check_user_exists(username):
        bot.reply_to(m, f"❌ Пользователь '{username}' не найден")
        return
    
    give_access(username, plan)
    plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
    bot.reply_to(m, f"✅ Доступ выдан на {plan_names[plan]} для {username}")
    
    # Уведомляем пользователя
    users = load_users()
    user_id = users.get(username, {}).get("user_id")
    if user_id:
        try:
            bot.send_message(user_id, f"🎉 {username}, твоя подписка активирована на {plan_names[plan]}! Задавай любые вопросы.")
        except:
            pass

@bot.message_handler(commands=['removeaccess'])
def remove(m):
    if m.from_user.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) != 2:
        bot.reply_to(m, "❌ /removeaccess имя")
        return
    
    username = parts[1]
    if remove_access(username):
        bot.reply_to(m, f"✅ Доступ отключён для {username}")
    else:
        bot.reply_to(m, f"❌ Пользователь {username} не найден")

@bot.message_handler(commands=['listusers'])
def listu(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    users = list_users()
    if not users:
        bot.reply_to(m, "📭 Нет пользователей")
        return
    
    text = "📋 Список пользователей:\n\n"
    for username, status, end in users:
        emoji = "✅" if status == 'active' else "❌"
        end_str = f"до {end[:10]}" if end else "бессрочно" if status == 'active' else "-"
        text += f"{emoji} {username} | {status} {end_str}\n"
    
    bot.reply_to(m, text[:4000])

@bot.message_handler(commands=['checkuser'])
def check(m):
    if m.from_user.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) != 2:
        bot.reply_to(m, "❌ /checkuser имя")
        return
    
    username = parts[1]
    status = get_user_status(username)
    if status is None:
        bot.reply_to(m, f"❌ Пользователь '{username}' не найден")
    else:
        bot.reply_to(m, f"📊 Статус '{username}': {status}")

@bot.message_handler(commands=['stats'])
def stats(m):
    if m.from_user.id != ADMIN_ID:
        return
    users = load_users()
    total = len(users)
    active = sum(1 for u in users.values() if u.get("subscription_status") == "active")
    bot.reply_to(m, f"📊 Всего: {total}\n✅ Активных: {active}\n❌ Неактивных: {total - active}")

@bot.message_handler(commands=['ask'])
def ask(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /ask вопрос")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_openrouter(parts[1])
    bot.reply_to(m, f"🧠 PyAI:\n{response[:4000]}")

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    user_id = m.from_user.id
    
    # Проверяем подписку
    users = load_users()
    username = None
    for name, data in users.items():
        if data.get("user_id") == user_id:
            username = name
            break
    
    if not username:
        bot.reply_to(m, "❌ Ты не зарегистрирован. Используй /register Имя")
        return
    
    status = get_user_status(username)
    if status != "active":
        bot.reply_to(m, f"❌ Твоя подписка неактивна. Для продления напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_openrouter(m.text)
    bot.reply_to(m, f"🧠 PyAI:\n{response[:4000]}")

# ============================================
# ВЕБ-СЕРВЕР
# ============================================
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/register', methods=['POST'])
def register_web():
    username = request.form.get('username', '').strip()
    if not username:
        return "Введите имя", 400
    
    if len(username) < 2:
        return "Имя должно быть не менее 2 символов", 400
    
    if check_user_exists(username):
        return "Пользователь с таким именем уже существует", 400
    
    if create_user(username):
        # Уведомляем админа
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username} (зарегистрирован через сайт)")
        return "Регистрация успешна! Ожидайте активации администратора.", 200
    else:
        return "Ошибка регистрации", 500

# ============================================
# ЗАПУСК
# ============================================
def run_bot():
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)

def run_web():
    print("🌐 Веб-сервер запущен на порту 10000")
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    run_web()
