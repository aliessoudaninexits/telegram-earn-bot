import telebot
import sqlite3
import time

API_TOKEN = "8431392986:AAEqjmix7p6UJvGjHXawmzZiubz5Gp7XdPM"
bot = telebot.TeleBot(API_TOKEN)

# Database
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    balance REAL DEFAULT 0,
    earned REAL DEFAULT 0,
    referrer INTEGER,
    last_watch INTEGER DEFAULT 0
)
""")
conn.commit()

# Settings
REWARD_VIDEO = 0.2
REWARD_REF = 0.5
MIN_WITHDRAW = 20
WATCH_COOLDOWN = 30
MIN_WATCH_DURATION = 20  # seconds to watch video

VIDEOS = [
    {"id": 1, "title": "Facebook Video 1", "link": "https://www.facebook.com/reel/XXXXXXXX"},
    {"id": 2, "title": "Facebook Video 2", "link": "https://www.facebook.com/reel/YYYYYYYY"},
]

# Main Menu
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Profile", "🎬 Watch")
    markup.row("👥 Invite", "💰 Balance")
    markup.row("💸 Withdraw")
    return markup

# Start + referral
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name

    args = message.text.split()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referrer = int(args[1]) if len(args) > 1 else None
        cursor.execute(
            "INSERT INTO users (user_id, name, referrer) VALUES (?, ?, ?)",
            (user_id, name, referrer)
        )
        conn.commit()
        if referrer:
            cursor.execute("UPDATE users SET balance = balance + ?, earned = earned + ? WHERE user_id=?",
                           (REWARD_REF, REWARD_REF, referrer))
            conn.commit()

    bot.send_message(message.chat.id,
        f"Welcome {name} 👋\nEarn money by watching videos!",
        reply_markup=main_menu()
    )

# Profile
@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance, earned FROM users WHERE user_id=?", (user_id,))
    balance, earned = cursor.fetchone()
    bot.send_message(message.chat.id,
        f"👤 Name: {message.from_user.first_name}\n💰 Balance: {balance:.2f} DT\n🏆 Total Earned: {earned:.2f} DT")

# Watch video
@bot.message_handler(func=lambda m: m.text == "🎬 Watch")
def watch(message):
    user_id = message.from_user.id
    cursor.execute("SELECT last_watch FROM users WHERE user_id=?", (user_id,))
    last_watch = cursor.fetchone()[0]

    if time.time() - last_watch < WATCH_COOLDOWN:
        bot.send_message(message.chat.id, f"⏳ Wait {WATCH_COOLDOWN} seconds between videos")
        return

    # Display video options
    markup = telebot.types.InlineKeyboardMarkup()
    for v in VIDEOS:
        markup.add(
            telebot.types.InlineKeyboardButton(f"{v['title']}", url=v['link']),
            telebot.types.InlineKeyboardButton("✅ Watched", callback_data=f"watched_{v['id']}")
        )
    bot.send_message(message.chat.id, "Choose a video and watch at least 20 sec then click ✅ Watched", reply_markup=markup)

# Confirm watch
@bot.callback_query_handler(func=lambda call: call.data.startswith("watched_"))
def watched(call):
    user_id = call.from_user.id
    video_id = int(call.data.split("_")[1])

    cursor.execute("SELECT last_watch FROM users WHERE user_id=?", (user_id,))
    last_watch = cursor.fetchone()[0]

    if time.time() - last_watch < WATCH_COOLDOWN:
        bot.answer_callback_query(call.id, "Too fast ❌")
        return

    # Reward user
    cursor.execute("UPDATE users SET balance = balance + ?, earned = earned + ?, last_watch=? WHERE user_id=?",
                   (REWARD_VIDEO, REWARD_VIDEO, int(time.time()), user_id))
    conn.commit()

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    bot.send_message(call.message.chat.id,
        f"✅ You earned {REWARD_VIDEO} DT!\n💰 Balance: {balance:.2f} DT")

# Invite
@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={user_id}"
    bot.send_message(message.chat.id,
        f"👥 Invite your friends and earn {REWARD_REF} DT per friend!\n🔗 Link:\n{link}")

# Balance
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"💰 Your balance: {balance:.2f} DT")

# Withdraw
@bot.message_handler(func=lambda m: m.text == "💸 Withdraw")
def withdraw(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ Minimum withdraw is {MIN_WITHDRAW} DT")
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💳 Bank", "📱 Mobile Money")
    markup.row("🏦 D17")
    bot.send_message(message.chat.id, "Choose a withdraw method:", reply_markup=markup)

# Run bot
bot.infinity_polling()
