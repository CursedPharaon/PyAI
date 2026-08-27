import telebot
import requests
from flask import Flask, request
import os
import json
import time

BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

USERS_FILE = "users.txt"
PORT = 10000

# ============================================
# РАБОТА С ФАЙЛОМ
# ============================================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = {}
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        users[parts[0]] = {"user_id": parts[1], "status": parts[2]}
            return users
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        for username, data in users.items():
            f.write(f"{username}|{data['user_id']}|{data['status']}\n")

def create_user(username, user_id):
    users = load_users()
    if username in users:
        return False
    users[username] = {"user_id": str(user_id), "status": "inactive"}
    save_users(users)
    return True

def get_user_by_id(user_id):
    users = load_users()
    for username, data in users.items():
        if data["user_id"] == str(user_id):
            return username, data["status"]
    return None, None

def give_access(username):
    users = load_users()
    if username not in users:
        return False
    users[username]["status"] = "active"
    save_users(users)
    return True

def list_users():
    users = load_users()
    return [(username, data["status"]) for username, data in users.items()]

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================
@bot.message_handler(commands=['start'])
def start(m):
    user_id = m.from_user.id
    name, status = get_user_by_id(user_id)
    
    if name:
        if status == "active":
            bot.reply_to(m, f"✅ Привет, {name}!")
        else:
            bot.reply_to(m, f"❌ Привет, {name}! Ты не активен. Напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "👋 Отправь /register Имя")

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}!")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        bot.reply_to(m, "❌ Имя занято")

@bot.message_handler(commands=['giveaccess'])
def give(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    parts = m.text.split()
    if len(parts) != 2:
        bot.reply_to(m, "❌ /giveaccess имя")
        return
    
    name = parts[1]
    if give_access(name):
        bot.reply_to(m, f"✅ {name} получил доступ")
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
    for name, status in users:
        emoji = "✅" if status == "active" else "❌"
        text += f"{emoji} {name} | {status}\n"
    
    bot.reply_to(m, text)

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    user_id = m.from_user.id
    name, status = get_user_by_id(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Зарегистрируйся: /register Имя")
        return
    
    if status != "active":
        bot.reply_to(m, "❌ Ты не активен. Напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть."},
                    {"role": "user", "content": m.text}
                ]
            },
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer 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'
            },
            timeout=30
        )
        r.raise_for_status()
        response = r.json()['choices'][0]['message']['content']
        bot.reply_to(m, f"🧠 {response[:4000]}")
    except Exception as e:
        bot.reply_to(m, f"⚠️ Ошибка: {str(e)[:200]}")

# ============================================
# ВЕБ-ХУК
# ============================================
@app.route('/', methods=['GET'])
def index():
    return "PyAI Bot is running! ✅"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json.loads(json_str))
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    # Удаляем старый веб-хук
    try:
        bot.remove_webhook()
        print("✅ Старый webhook удалён")
    except:
        pass
    
    time.sleep(1)
    
    # НОВАЯ ССЫЛКА
    WEBHOOK_URL = "https://pyai-vyzq.onrender.com/webhook"
    
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")
    
    print(f"🚀 Запуск сервера на порту {PORT}")
    app.run(host='0.0.0.0', port=PORT)
