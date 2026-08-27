import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import libsql_experimental as libsql
from datetime import datetime, timedelta
import asyncio
import http.server
import socketserver
import threading
import os

# ============================================
# НАСТРОЙКИ
# ============================================
TELEGRAM_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"
ADMIN_ID = 8549857532  # Твой Telegram ID

# Turso DB
DB_URL = "libsql://pyai-cursedd.aws-eu-west-1.turso.io"
DB_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODc4Mzg2OTAsImlkIjoiMDFhMDQzN2QtMmQwMS03ZjZmLTk1MDAtNTUzZTI5YzFjNmI1Iiwia2lkIjoicWpYbEhLbElGQmJNX29uRDlaWEkyWFVfazVBT3h3X3JIMF9TcUZ6MmU0ZyIsInJpZCI6IjZhMzk2M2ZkLWYzM2QtNGE2MS1hMTQwLTQyYWU1ZTExZWQ5NCJ9.2pxIFQ_FkjhaNgqU6Adj6pEOaSxRx_rVI6Jc8SdAbvLMYbXWxsyhH8q78TZKcCQ51m7RiitFUzfOGUr-2UalAg"

# ============================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ============================================
conn = libsql.connect("pyai.db", sync_url=DB_URL, auth_token=DB_TOKEN)
cursor = conn.cursor()

# Создаём таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    subscription_status TEXT DEFAULT 'inactive',
    subscription_end TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

logging.basicConfig(level=logging.INFO)

# ============================================
# ФУНКЦИИ БАЗЫ
# ============================================
def get_subscription_days(plan):
    plans = {
        "1": 7,   # неделя
        "2": 30,  # месяц
        "3": 365, # год
        "4": None # вечный
    }
    return plans.get(plan)

def give_access(email, plan):
    days = get_subscription_days(plan)
    if days is None:
        cursor.execute("""
            UPDATE users 
            SET subscription_status = 'active', subscription_end = NULL 
            WHERE email = ?
        """, (email,))
    else:
        end_date = (datetime.now() + timedelta(days=days)).isoformat()
        cursor.execute("""
            UPDATE users 
            SET subscription_status = 'active', subscription_end = ? 
            WHERE email = ?
        """, (end_date, email))
    conn.commit()
    return cursor.rowcount > 0

def remove_access(email):
    cursor.execute("""
        UPDATE users 
        SET subscription_status = 'inactive', subscription_end = NULL 
        WHERE email = ?
    """, (email,))
    conn.commit()
    return cursor.rowcount > 0

def get_user_status(email):
    cursor.execute("""
        SELECT subscription_status, subscription_end FROM users WHERE email = ?
    """, (email,))
    row = cursor.fetchone()
    if not row:
        return None
    status, end_date = row
    if status == 'active' and end_date:
        if datetime.now().isoformat() > end_date:
            cursor.execute("UPDATE users SET subscription_status = 'inactive' WHERE email = ?", (email,))
            conn.commit()
            return 'inactive'
    return status

def list_users():
    cursor.execute("SELECT email, subscription_status, subscription_end FROM users")
    return cursor.fetchall()

def register_user(email, password):
    try:
        cursor.execute("""
            INSERT INTO users (email, password, subscription_status)
            VALUES (?, ?, 'inactive')
        """, (email, password))
        conn.commit()
        return True
    except:
        return False

def check_user_exists(email):
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    return cursor.fetchone() is not None

# ============================================
# КОМАНДЫ ТЕЛЕГРАМ-БОТА
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён. Только для администратора.")
        return
    
    await update.message.reply_text(
        "👋 Привет, админ!\n\n"
        "📌 Команды:\n"
        "/giveaccess email@example.com 1 - дать доступ (1-неделя, 2-месяц, 3-год, 4-вечный)\n"
        "/removeaccess email@example.com - отключить доступ\n"
        "/listusers - список пользователей\n"
        "/checkuser email@example.com - проверить статус\n"
        "/stats - статистика"
    )

async def give_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ Использование: /giveaccess email@example.com 1-4")
        return
    
    email, plan = context.args[0], context.args[1]
    if plan not in ["1", "2", "3", "4"]:
        await update.message.reply_text("❌ План: 1-неделя, 2-месяц, 3-год, 4-вечный")
        return
    
    if not check_user_exists(email):
        await update.message.reply_text(f"❌ Пользователь {email} не найден. Сначала зарегистрируйтесь на сайте.")
        return
    
    if give_access(email, plan):
        plan_names = {"1": "неделя", "2": "месяц", "3": "год", "4": "вечный"}
        await update.message.reply_text(f"✅ Доступ выдан на {plan_names[plan]} для {email}")
    else:
        await update.message.reply_text("❌ Ошибка при выдаче доступа")

async def remove_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /removeaccess email@example.com")
        return
    
    email = context.args[0]
    if remove_access(email):
        await update.message.reply_text(f"✅ Доступ отключён для {email}")
    else:
        await update.message.reply_text(f"❌ Пользователь {email} не найден")

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    users = list_users()
    if not users:
        await update.message.reply_text("📭 Нет зарегистрированных пользователей")
        return
    
    text = "📋 Список пользователей:\n\n"
    for email, status, end_date in users:
        status_emoji = "✅" if status == 'active' else "❌"
        end_str = f"до {end_date[:10]}" if end_date else "бессрочно" if status == 'active' else "-"
        text += f"{status_emoji} {email} | {status} {end_str}\n"
    
    await update.message.reply_text(text[:4000])

async def check_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /checkuser email@example.com")
        return
    
    email = context.args[0]
    status = get_user_status(email)
    if status is None:
        await update.message.reply_text(f"❌ Пользователь {email} не найден")
    else:
        await update.message.reply_text(f"📊 Статус {email}: {status}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_status = 'active'")
    active = cursor.fetchone()[0]
    
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"👥 Всего пользователей: {total}\n"
        f"✅ Активных: {active}\n"
        f"❌ Неактивных: {total - active}"
    )

# ============================================
# ВЕБ-СЕРВЕР ДЛЯ HTML
# ============================================
class MyHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        if self.path == '/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            import urllib.parse
            data = urllib.parse.parse_qs(post_data)
            email = data.get('email', [''])[0]
            password = data.get('password', [''])[0]
            
            if not email or not password:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Email and password required')
                return
            
            if check_user_exists(email):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'User already exists')
                return
            
            if register_user(email, password):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Registration successful! Wait for admin to activate your access.')
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'Registration failed')
    
    def log_message(self, format, *args):
        pass  # Отключаем логи

def start_web_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with socketserver.TCPServer(("", 8000), MyHTTPHandler) as httpd:
        print("🌐 Веб-сервер запущен на http://localhost:8000")
        httpd.serve_forever()

# ============================================
# ЗАПУСК
# ============================================
def main():
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Запускаем Telegram-бота
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("giveaccess", give_access_command))
    app.add_handler(CommandHandler("removeaccess", remove_access_command))
    app.add_handler(CommandHandler("listusers", list_users_command))
    app.add_handler(CommandHandler("checkuser", check_user_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
