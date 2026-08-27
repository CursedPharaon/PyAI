import telebot
import requests
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

# JSONBin.io
JSONBIN_KEY = "$2a$10$3T6Ssc3MDy8btFzOD4PTjOzciiAlCszOrB4zJDiorULg2BRrdPWRS"
BIN_ID = "6a90a8efda38895dfe19be69"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
PORT = 10000

# Удаляем веб-хук
try:
    bot.remove_webhook()
    print("✅ Веб-хук удалён")
except:
    pass
time.sleep(1)

# ============================================
# ПЛАНЫ ПОДПИСОК
# ============================================
PLANS = {
    "1": {"name": "Неделя", "days": 7, "price": "100 ₽"},
    "2": {"name": "Месяц", "days": 30, "price": "300 ₽"},
    "3": {"name": "Год", "days": 365, "price": "1000 ₽"},
    "4": {"name": "Вечная", "days": None, "price": "2000 ₽"}
}

# ============================================
# ФУНКЦИИ РАБОТЫ С JSONBin
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

def get_user(username):
    users = load_users()
    return users.get(username)

def create_user(username, user_id):
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "user_id": str(user_id),
        "status": "inactive",
        "plan": None,
        "end_date": None,
        "created_at": datetime.now().isoformat()
    }
    return save_users(users)

def get_user_by_id(user_id):
    users = load_users()
    for username, data in users.items():
        if data.get("user_id") == str(user_id):
            return username, data
    return None, None

def give_access(username, plan_key):
    users = load_users()
    if username not in users:
        return False
    
    plan = PLANS.get(plan_key)
    if not plan:
        return False
    
    users[username]["plan"] = plan_key
    users[username]["status"] = "active"
    
    if plan["days"] is None:
        users[username]["end_date"] = None  # Вечная
    else:
        end_date = datetime.now() + timedelta(days=plan["days"])
        users[username]["end_date"] = end_date.isoformat()
    
    return save_users(users)

def remove_access(username):
    users = load_users()
    if username not in users:
        return False
    users[username]["status"] = "inactive"
    users[username]["plan"] = None
    users[username]["end_date"] = None
    return save_users(users)

def check_subscription(username):
    users = load_users()
    if username not in users:
        return None
    
    user = users[username]
    status = user.get("status", "inactive")
    end_date = user.get("end_date")
    
    if status == "active" and end_date:
        if datetime.now().isoformat() > end_date:
            user["status"] = "inactive"
            user["plan"] = None
            user["end_date"] = None
            save_users(users)
            return "inactive"
    
    return status

def get_subscription_info(username):
    users = load_users()
    if username not in users:
        return None
    
    user = users[username]
    status = user.get("status", "inactive")
    plan_key = user.get("plan")
    end_date = user.get("end_date")
    
    plan_name = PLANS.get(plan_key, {}).get("name", "Нет") if plan_key else "Нет"
    
    if status == "active" and end_date:
        end = datetime.fromisoformat(end_date)
        days_left = (end - datetime.now()).days
        if days_left < 0:
            days_left = 0
        return {
            "status": status,
            "plan": plan_name,
            "days_left": days_left,
            "end_date": end_date
        }
    elif status == "active" and not end_date:
        return {
            "status": status,
            "plan": "Вечная",
            "days_left": "∞",
            "end_date": None
        }
    else:
        return {
            "status": "inactive",
            "plan": "Нет",
            "days_left": 0,
            "end_date": None
        }

def list_users():
    users = load_users()
    result = []
    for username, data in users.items():
        plan_key = data.get("plan")
        plan_name = PLANS.get(plan_key, {}).get("name", "Нет") if plan_key else "Нет"
        result.append({
            "username": username,
            "status": data.get("status", "inactive"),
            "plan": plan_name,
            "end_date": data.get("end_date")
        })
    return result

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
                    {"role": "system", "content": "Ты — PyAI, дружелюбная нейросеть. Отвечай полезно и понятно."},
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
        info = get_subscription_info(name)
        if info["status"] == "active":
            if info["days_left"] == "∞":
                days_text = "♾️ Вечная"
            else:
                days_text = f"⏳ {info['days_left']} дн."
            bot.reply_to(m, 
                f"✅ Привет, {name}!\n"
                f"📊 Подписка: {info['plan']}\n"
                f"{days_text}\n\n"
                f"Просто напиши мне сообщение, и я отвечу!"
            )
        else:
            bot.reply_to(m, 
                f"❌ Привет, {name}!\n"
                f"Твоя подписка неактивна.\n\n"
                f"📌 Для продления напиши @cursed_pharaon\n"
                f"💳 Тарифы:\n"
                f"1 - Неделя (100 ₽)\n"
                f"2 - Месяц (300 ₽)\n"
                f"3 - Год (1000 ₽)\n"
                f"4 - Вечная (2000 ₽)"
            )
        return
    
    bot.reply_to(m, 
        "👋 Добро пожаловать в PyAI!\n\n"
        "📝 Для регистрации отправь:\n"
        "/register Имя\n\n"
        "💡 После регистрации напиши @cursed_pharaon для покупки подписки."
    )

@bot.message_handler(commands=['register'])
def register(m):
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ Использование: /register Имя")
        return
    
    username = parts[1].strip()
    user_id = m.from_user.id
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}!\n\nДля покупки подписки напиши @cursed_pharaon")
        bot.send_message(ADMIN_ID, f"📝 Новый пользователь: {username}")
    else:
        bot.reply_to(m, "❌ Имя уже занято")

@bot.message_handler(commands=['my'])
def my_subscription(m):
    user_id = m.from_user.id
    name, data = get_user_by_id(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Ты не зарегистрирован. Используй /register Имя")
        return
    
    info = get_subscription_info(name)
    if info["status"] == "active":
        if info["days_left"] == "∞":
            days_text = "♾️ Вечная"
        else:
            days_text = f"⏳ {info['days_left']} дн."
        bot.reply_to(m,
            f"📊 Статус подписки:\n"
            f"👤 Пользователь: {name}\n"
            f"📋 План: {info['plan']}\n"
            f"{days_text}"
        )
    else:
        bot.reply_to(m,
            f"❌ Подписка неактивна.\n\n"
            f"📌 Для продления напиши @cursed_pharaon\n"
            f"💳 Тарифы:\n"
            f"1 - Неделя (100 ₽)\n"
            f"2 - Месяц (300 ₽)\n"
            f"3 - Год (1000 ₽)\n"
            f"4 - Вечная (2000 ₽)"
        )

@bot.message_handler(commands=['giveaccess'])
def give(m):
    if m.from_user.id != ADMIN_ID:
        bot.reply_to(m, "⛔ Доступ запрещён")
        return
    
    parts = m.text.split()
    if len(parts) != 3:
        bot.reply_to(m, "❌ /giveaccess имя 1-4\n1-Неделя, 2-Месяц, 3-Год, 4-Вечная")
        return
    
    name, plan_key = parts[1], parts[2]
    if plan_key not in PLANS:
        bot.reply_to(m, "❌ Неверный план. Доступно: 1-4")
        return
    
    if give_access(name, plan_key):
        plan_name = PLANS[plan_key]["name"]
        bot.reply_to(m, f"✅ {name} получил доступ на {plan_name}")
        
        # Уведомляем пользователя
        user_data = load_users().get(name, {})
        user_id = user_data.get("user_id")
        if user_id:
            try:
                bot.send_message(int(user_id), 
                    f"🎉 Поздравляю, {name}!\n"
                    f"Твоя подписка на {plan_name} активирована!"
                )
            except:
                pass
    else:
        bot.reply_to(m, f"❌ Пользователь {name} не найден")

@bot.message_handler(commands=['removeaccess'])
def remove(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    parts = m.text.split()
    if len(parts) != 2:
        bot.reply_to(m, "❌ /removeaccess имя")
        return
    
    name = parts[1]
    if remove_access(name):
        bot.reply_to(m, f"✅ Доступ отключён для {name}")
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
    
    text = "📋 Список пользователей:\n\n"
    for user in users:
        status_emoji = "✅" if user["status"] == "active" else "❌"
        end_str = f"до {user['end_date'][:10]}" if user["end_date"] else "бессрочно" if user["status"] == "active" else "-"
        text += f"{status_emoji} {user['username']} | {user['plan']} | {end_str}\n"
    
    bot.reply_to(m, text[:4000])

@bot.message_handler(commands=['stats'])
def stats(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    users = list_users()
    total = len(users)
    active = sum(1 for u in users if u["status"] == "active")
    
    bot.reply_to(m,
        f"📊 Статистика:\n"
        f"👥 Всего: {total}\n"
        f"✅ Активных: {active}\n"
        f"❌ Неактивных: {total - active}"
    )

@bot.message_handler(commands=['help'])
def help_cmd(m):
    user_id = m.from_user.id
    if user_id == ADMIN_ID:
        bot.reply_to(m,
            "🤖 Команды админа:\n"
            "/giveaccess имя 1-4 - выдать доступ\n"
            "/removeaccess имя - отключить\n"
            "/listusers - список пользователей\n"
            "/stats - статистика\n\n"
            "👤 Пользовательские:\n"
            "/register имя - регистрация\n"
            "/my - моя подписка\n"
            "/help - помощь"
        )
    else:
        bot.reply_to(m,
            "👤 Команды:\n"
            "/register имя - регистрация\n"
            "/my - моя подписка\n"
            "/help - помощь\n\n"
            "💬 Просто пиши сообщения, и я отвечу!"
        )

# ============================================
# ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ
# ============================================
@bot.message_handler(func=lambda m: True)
def all_messages(m):
    # Если сообщение начинается с "/" - не отвечаем (это команда)
    if m.text and m.text.startswith('/'):
        return
    
    user_id = m.from_user.id
    name, data = get_user_by_id(user_id)
    
    if not name:
        bot.reply_to(m, "❌ Ты не зарегистрирован. Используй /register Имя")
        return
    
    status = check_subscription(name)
    if status != "active":
        bot.reply_to(m, "❌ Подписка неактивна. Напиши @cursed_pharaon для продления")
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
    users = load_users()
    return f"PyAI Bot is running! 👥 Users: {len(users)}"

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
    print("🚀 Запуск PyAI Bot...")
    
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    run_web()
