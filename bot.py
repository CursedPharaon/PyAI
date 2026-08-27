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
# ФУНКЦИИ РАБОТЫ С SUPABASE
# ============================================
def create_user(username, user_id):
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    data = {"username": username, "user_id": str(user_id), "status": "inactive"}
    try:
        r = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"create_user: {r.status_code} - {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"create_user error: {e}")
        return False

def get_user(user_id):
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}&select=username,status"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0]["username"], data[0]["status"]
        return None, None
    except:
        return None, None

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
        return r.status_code == 200
    except:
        return False

def get_status(username):
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=status"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0].get("status", "inactive")
        return None
    except:
        return None

def list_users():
    url = f"{SUPABASE_URL}/rest/v1/users?select=username,status"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return [(item["username"], item["status"]) for item in r.json()]
        return []
    except:
        return []

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================
@bot.message_handler(commands=['start'])
def start(m):
    user_id = m.from_user.id
    name, status = get_user(user_id)
    
    if name:
        if status == "active":
            bot.reply_to(m, f"✅ Привет, {name}! Подписка активна!")
        else:
            bot.reply_to(m, f"❌ Привет, {name}! Подписка неактивна. Напиши @cursed_pharaon")
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
    
    # Проверяем, не существует ли пользователь с таким именем
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}&select=username"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            bot.reply_to(m, f"❌ Имя '{username}' уже занято")
            return
    except:
        pass
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}! Ожидай активации.")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        bot.reply_to(m, "❌ Ошибка регистрации. Проверь логи.")

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
    for name, status in users:
        emoji = "✅" if status == "active" else "❌"
        text += f"{emoji} {name} | {status}\n"
    
    bot.reply_to(m, text)

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    user_id = m.from_user.id
    name, status = get_user(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Зарегистрируйся: /register Имя")
        return
    
    if status != "active":
        bot.reply_to(m, "❌ Подписка неактивна. Напиши @cursed_pharaon")
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

@app.route('/ping', methods=['GET'])
def ping():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update_dict = json.loads(json_str)
        update = telebot.types.Update.de_json(update_dict)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    # Удаляем старый webhook и ставим новый
    try:
        bot.remove_webhook()
        print("✅ Старый webhook удалён")
    except:
        pass
    
    WEBHOOK_URL = "https://pyai-7edz.onrender.com/webhook"
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")
    
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
