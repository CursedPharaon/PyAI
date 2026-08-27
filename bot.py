import telebot
import requests
import json
import os
from datetime import datetime, timedelta

# ============================================
# НАСТРОЙКИ
# ============================================
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"
ADMIN_ID = 8549857532

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# РАБОТА С JSON-ФАЙЛОМ
# ============================================
def load_users():
    """Загружает пользователей из JSON-файла"""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """Сохраняет пользователей в JSON-файл"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def get_user(username):
    """Получает данные пользователя"""
    users = load_users()
    return users.get(username)

def create_user(username):
    """Создаёт нового пользователя"""
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "subscription_status": "inactive",
        "subscription_end": None,
        "created_at": datetime.now().isoformat()
    }
    save_users(users)
    return True

def give_access(username, plan):
    """Выдаёт доступ"""
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
    """Отключает доступ"""
    users = load_users()
    if username not in users:
        return False
    users[username]["subscription_status"] = "inactive"
    users[username]["subscription_end"] = None
    save_users(users)
    return True

def get_user_status(username):
    """Проверяет статус пользователя"""
    users = load_users()
    if username not in users:
        return None
    
    user = users[username]
    status = user.get("subscription_status", "inactive")
    end_date = user.get("subscription_end")
    
    # Проверяем, не истёк ли срок
    if status == "active" and end_date:
        if datetime.now().isoformat() > end_date:
            user["subscription_status"] = "inactive"
            user["subscription_end"] = None
            save_users(users)
            return "inactive"
    
    return status

def list_users():
    """Список всех пользователей"""
    users = load_users()
    return [(username, data["subscription_status"], data.get("subscription_end")) 
            for username, data in users.items()]

def check_user_exists(username):
    """Проверяет, существует ли пользователь"""
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
# КОМАНДЫ
# ============================================
@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id != ADMIN_ID:
        bot.reply_to(m, "⛔ Доступ запрещён.")
        return
    bot.reply_to(m, 
        "👋 Админ!\n\n"
        "/giveaccess имя 1-4 - дать доступ\n"
        "/removeaccess имя - отключить\n"
        "/listusers - список\n"
        "/checkuser имя - статус\n"
        "/stats - статистика\n"
        "/ask вопрос - спросить PyAI"
    )

@bot.message_handler(commands=['giveaccess'])
def give(m):
    if m.from_user.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) != 3 or parts[2] not in ["1","2","3","4"]:
        bot.reply_to(m, "❌ /giveaccess имя 1-4")
        return
    
    username, plan = parts[1], parts[2]
    if not check_user_exists(username):
        bot.reply_to(m, f"❌ Пользователь '{username}' не найден")
        return
    
    give_access(username, plan)
    plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
    bot.reply_to(m, f"✅ Доступ выдан на {plan_names[plan]} для {username}")

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
    
    bot.reply_to(m,
        f"📊 Статистика:\n"
        f"👥 Всего: {total}\n"
        f"✅ Активных: {active}\n"
        f"❌ Неактивных: {total - active}"
    )

@bot.message_handler(commands=['ask'])
def ask(m):
    if m.from_user.id != ADMIN_ID:
        return
    
    parts = m.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(m, "❌ /ask вопрос")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_openrouter(parts[1])
    bot.reply_to(m, f"🧠 PyAI:\n{response[:4000]}")

@bot.message_handler(func=lambda m: True)
def all_messages(m):
    if m.from_user.id != ADMIN_ID:
        bot.reply_to(m, "⛔ Доступ запрещён.")
        return
    
    bot.reply_to(m, "🤔 Думаю...")
    response = ask_openrouter(m.text)
    bot.reply_to(m, f"🧠 PyAI:\n{response[:4000]}")

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    print("🤖 Бот запущен!")
    bot.polling(non_stop=True)
