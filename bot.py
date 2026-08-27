import telebot
import requests
import json
import time
import threading
from flask import Flask

# ============================================
# НАСТРОЙКИ (ВСЁ ВСТАВЛЕНО)
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

# JSONBin.io - данные сохраняются в ОБЛАКЕ (НЕ ПРОПАДАЮТ)
JSONBIN_KEY = "$2a$10$3T6Ssc3MDy8btFzOD4PTjOzciiAlCszOrB4zJDiorULg2BRrdPWRS"
BIN_ID = "6a90a8efda38895dfe19be69"  # Твой ID

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
PORT = 10000

# ============================================
# ФУНКЦИИ РАБОТЫ С JSONBin (ОБЛАКО)
# ============================================
def load_users():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    headers = {"X-Access-Key": JSONBIN_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("record", {})
        return {}
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        return {}

def save_users(users):
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    headers = {
        "X-Access-Key": JSONBIN_KEY,
        "Content-Type": "application/json"
    }
    try:
        r = requests.put(url, json=users, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return False

def create_user(username, user_id):
    users = load_users()
    if username in users:
        return False
    users[username] = {"user_id": str(user_id), "status": "inactive"}
    return save_users(users)

def get_user_by_id(user_id):
    users = load_users()
    for username, data in users.items():
        if data.get("user_id") == str(user_id):
            return username, data.get("status")
    return None, None

def give_access(username):
    users = load_users()
    if username not in users:
        return False
    users[username]["status"] = "active"
    return save_users(users)

def list_users():
    users = load_users()
    return [(username, data.get("status")) for username, data in users.items()]

# ============================================
# OPENROUTER (ИИ)
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

@bot.message_handler(commands=['ask'])
def ask(m):
    user_id = m.from_user.id
    name, status = get_user_by_id(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Зарегистрируйся: /register Имя")
        return
    
    if status != "active":
        bot.reply_to(m, "❌ Ты не активен. Напиши @cursed_pharaon")
        return
    
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /ask вопрос")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_ai(parts[1])
    bot.reply_to(m, f"🧠 {response[:4000]}")

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
    response = ask_ai(m.text)
    bot.reply_to(m, f"🧠 {response[:4000]}")

# ============================================
# АВТО-ПИНГ
# ============================================
def keep_alive():
    url = f"http://localhost:{PORT}/ping"
    while True:
        try:
            requests.get(url, timeout=5)
            print(f"🔄 Пинг")
        except:
            pass
        time.sleep(300)

@app.route('/')
def index():
    return "PyAI Bot is running! ✅"

@app.route('/ping')
def ping():
    return "OK", 200

def run_bot():
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)

def run_web():
    app.run(host='0.0.0.0', port=PORT)

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    print("🚀 Запуск...")
    
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    run_web()
