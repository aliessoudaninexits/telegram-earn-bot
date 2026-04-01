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
    referrer INTEGER,
    last_watch INTEGER DEFAULT 0
)
""")
conn.commit()

REWARD_VIDEO = 0.2
REWARD_REF = 0.5
MIN_WITHDRAW = 20
WATCH_COOLDOWN = 30

# Helper: Main Menu
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Profile", "🎬 Watch")
    markup.row("👥 Invite", "💰 Balance")
    markup.row("💸 Withdraw")
    return markup

# START + REFERRAL
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name

    args = message.text.split()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referrer = None

        # Check referral
        if len(args) > 1:
            referrer = int(args[1])

        cursor.execute(
            "INSERT INTO users (user_id, name, referrer) VALUES (?, ?, ?)",
            (user_id, name, referrer)
        )
        conn.commit()

        # Give referral reward
        if referrer:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?",
                           (REWARD_REF, referrer))
            conn.commit()

    bot.send_message(message.chat.id,
        f"Welcome {name} 👋\nEarn money by watching videos!",
        reply_markup=main_menu()
    )

# PROFILE
@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile(message):
    user_id = message.from_user.id

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    bot.send_message(message.chat.id,
        f"👤 Name: {message.from_user.first_name}\n💰 Balance: {balance:.2f} DT")

# WATCH
@bot.message_handler(func=lambda m: m.text == "🎬 Watch")
def watch(message):
    user_id = message.from_user.id

    cursor.execute("SELECT last_watch FROM users WHERE user_id=?", (user_id,))
    last_watch = cursor.fetchone()[0]

    if time.time() - last_watch < WATCH_COOLDOWN:
        bot.send_message(message.chat.id, "⏳ Wait before next video")
        return

    video_link = "https://www.facebook.com/reel/XXXXXXXX"

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("▶️ Watch Video", url=video_link),
        telebot.types.InlineKeyboardButton("✅ Done", callback_data="done")
    )

    bot.send_message(message.chat.id,
        "Watch the video then click DONE",
        reply_markup=markup)

# CONFIRM WATCH
@bot.callback_query_handler(func=lambda call: call.data == "done")
def done(call):
    user_id = call.from_user.id

    cursor.execute("SELECT last_watch FROM users WHERE user_id=?", (user_id,))
    last_watch = cursor.fetchone()[0]

    if time.time() - last_watch < WATCH_COOLDOWN:
        bot.answer_callback_query(call.id, "Too fast ❌")
        return

    cursor.execute("UPDATE users SET balance = balance + ?, last_watch=? WHERE user_id=?",
                   (REWARD_VIDEO, int(time.time()), user_id))
    conn.commit()

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    bot.send_message(call.message.chat.id,
        f"✅ +{REWARD_VIDEO} DT\n💰 Balance: {balance:.2f} DT")

# INVITE
@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username

    link = f"https://t.me/{bot_username}?start={user_id}"

    bot.send_message(message.chat.id,
        f"👥 دعوت أصحابك و اربح {REWARD_REF} DT لكل واحد\n\n🔗 Link:\n{link}")

# BALANCE
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    user_id = message.from_user.id

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    bot.send_message(message.chat.id,
        f"💰 Your balance: {balance:.2f} DT")

# WITHDRAW
@bot.message_handler(func=lambda m: m.text == "💸 Withdraw")
def withdraw(message):
    user_id = message.from_user.id

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = cursor.fetchone()[0]

    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id,
            f"❌ Minimum withdraw: {MIN_WITHDRAW} DT")
        return

    bot.send_message(message.chat.id,
        "💸 Send your payment info (D17 / Bank)")

bot.infinity_polling()

