import telebot
import requests
import json
import os
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = "8790410681:AAH8fYqJ0XYljg2QuPTVAorhew_qNN38rDk"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# Turso
TURSO_URL = "https://pyai-cursedd.aws-eu-west-1.turso.io/v1/query"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODc4Mzg2OTAsImlkIjoiMDFhMDQzN2QtMmQwMS03ZjZmLTk1MDAtNTUzZTI5YzFjNmI1Iiwia2lkIjoicWpYbEhLbElGQmJNX29uRDlaWEkyWFVfazVBT3h3X3JIMF9TcUZ6MmU0ZyIsInJpZCI6IjZhMzk2M2ZkLWYzM2QtNGE2MS1hMTQwLTQyYWU1ZTExZWQ5NCJ9.2pxIFQ_FkjhaNgqU6Adj6pEOaSxRx_rVI6Jc8SdAbvLMYbXWxsyhH8q78TZKcCQ51m7RiitFUzfOGUr-2UalAg"

PORT = 10000

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# ============================================
# TURSO (данные не пропадают)
# ============================================
def turso_query(sql, params=[]):
    payload = {
        "requests": [{
            "type": "execute",
            "stmt": {"sql": sql, "args": params}
        }]
    }
    try:
        r = requests.post(
            TURSO_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {TURSO_TOKEN}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Turso error: {e}")
        return None

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        user_id TEXT,
        subscription_status TEXT DEFAULT 'inactive',
        subscription_end TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """
    turso_query(sql)

def create_user(username, user_id=None):
    result = turso_query(
        "INSERT INTO users (username, user_id, subscription_status) VALUES (?, ?, 'inactive')",
        [username, user_id]
    )
    return result is not None

def get_user_by_username(username):
    r = turso_query("SELECT username, subscription_status, subscription_end FROM users WHERE username = ?", [username])
    if not r or not r.get('results'):
        return None
    rows = r['results'][0].get('rows', [])
    if not rows:
        return None
    return {"username": rows[0][0], "status": rows[0][1], "end_date": rows[0][2] if len(rows[0]) > 2 else None}

def get_user_by_id(user_id):
    r = turso_query("SELECT username, subscription_status, subscription_end FROM users WHERE user_id = ?", [str(user_id)])
    if not r or not r.get('results'):
        return None
    rows = r['results'][0].get('rows', [])
    if not rows:
        return None
    return {"username": rows[0][0], "status": rows[0][1], "end_date": rows[0][2] if len(rows[0]) > 2 else None}

def get_user_status(username):
    user = get_user_by_username(username)
    if not user:
        return None
    
    status = user["status"]
    end_date = user["end_date"]
    
    if status == "active" and end_date:
        if datetime.now().isoformat() > end_date:
            turso_query("UPDATE users SET subscription_status = 'inactive' WHERE username = ?", [username])
            return "inactive"
    
    return status

def give_access(username, plan):
    user = get_user_by_username(username)
    if not user:
        return False
    
    days = {"1": 7, "2": 30, "3": 365, "4": None}.get(plan)
    if days is None:
        turso_query("UPDATE users SET subscription_status = 'active', subscription_end = NULL WHERE username = ?", [username])
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        turso_query("UPDATE users SET subscription_status = 'active', subscription_end = ? WHERE username = ?", [end_date, username])
    return True

def remove_access(username):
    turso_query("UPDATE users SET subscription_status = 'inactive', subscription_end = NULL WHERE username = ?", [username])
    return True

def list_users():
    r = turso_query("SELECT username, subscription_status, subscription_end FROM users")
    if not r or not r.get('results'):
        return []
    rows = r['results'][0].get('rows', [])
    return [(row[0], row[1], row[2] if len(row) > 2 else None) for row in rows]

def check_user_exists(username):
    return get_user_by_username(username) is not None

# ============================================
# АВТО-ПИНГ (ЧТОБЫ НЕ ЗАСЫПАЛ)
# ============================================
def keep_alive():
    url = f"http://localhost:{PORT}/ping"
    while True:
        try:
            requests.get(url, timeout=5)
            print(f"🔄 Пинг в {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")
        time.sleep(300)

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
    user_id = str(m.from_user.id)
    user = get_user_by_id(user_id)
    
    if user:
        username = user["username"]
        status = get_user_status(username)
        if status == "active":
            bot.reply_to(m, f"✅ Привет, {username}! Твоя подписка активна. Задавай любой вопрос!")
        else:
            bot.reply_to(m, f"❌ Привет, {username}! Твоя подписка неактивна. Для продления напиши @cursed_pharaon")
        return
    
    bot.reply_to(m, 
        "👋 Добро пожаловать в PyAI!\n\n"
        "Чтобы начать пользоваться, отправь /register Имя\n\n"
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
    user_id = str(m.from_user.id)
    
    if check_user_exists(username):
        bot.reply_to(m, f"❌ Имя '{username}' уже занято")
        return
    
    if create_user(username, user_id):
        bot.reply_to(m, f"✅ Регистрация успешна, {username}! Ожидай активации от администратора.\n\n📩 Для продления подписки напишите @cursed_pharaon")
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
    
    user = get_user_by_username(username)
    if user:
        # Пытаемся найти user_id в базе
        r = turso_query("SELECT user_id FROM users WHERE username = ?", [username])
        if r and r.get('results'):
            rows = r['results'][0].get('rows', [])
            if rows and rows[0][0]:
                try:
                    bot.send_message(int(rows[0][0]), f"🎉 {username}, твоя подписка активирована на {plan_names[plan]}! Задавай любые вопросы.")
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
    r = turso_query("SELECT COUNT(*) FROM users")
    total = r['results'][0]['rows'][0][0] if r and r.get('results') else 0
    r = turso_query("SELECT COUNT(*) FROM users WHERE subscription_status = 'active'")
    active = r['results'][0]['rows'][0][0] if r and r.get('results') else 0
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
    user_id = str(m.from_user.id)
    user = get_user_by_id(user_id)
    
    if not user:
        bot.reply_to(m, "❌ Ты не зарегистрирован. Используй /register Имя")
        return
    
    username = user["username"]
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

@app.route('/ping')
def ping():
    return "OK", 200

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    username = data.get('username', '').strip()
    message = data.get('message', '').strip()
    
    if not username or not message:
        return jsonify({'error': 'Введите имя и вопрос'}), 400
    
    status = get_user_status(username)
    if status is None:
        return jsonify({'error': 'Пользователь не найден. Зарегистрируйтесь.'}), 404
    
    if status != 'active':
        return jsonify({'error': 'Подписка неактивна. Напишите @cursed_pharaon для продления.'}), 403
    
    response = ask_openrouter(message)
    return jsonify({'response': response})

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
    print(f"🌐 Веб-сервер запущен на порту {PORT}")
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    init_db()
    
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    run_web()
