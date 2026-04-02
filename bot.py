import telebot
import sqlite3
import time
import os

API_TOKEN = "8431392986:AAEqjmix7p6UJvGjHXawmzZiubz5Gp7XdPM"  # replace with your bot token
bot = telebot.TeleBot(API_TOKEN)

# --- Database ---
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    balance REAL DEFAULT 0,
    earned REAL DEFAULT 0,
    referrer INTEGER,
    last_watch INTEGER DEFAULT 0,
    video_index INTEGER DEFAULT 0
)
""")
conn.commit()

# --- Settings ---
REWARD_VIDEO = 0.2
REWARD_REF = 0.5
MIN_WITHDRAW = 20
WATCH_COOLDOWN = 30  # seconds
VIDEOS = [
    {"id": 1, "file": "video1.mp4", "title": "Video 1"},
    {"id": 2, "file": "video2.mp4", "title": "Video 2"},
    {"id": 3, "file": "video3.mp4", "title": "Video 3"}
]

# --- Main Menu ---
def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👤 Profile", "🎬 Watch")
    markup.row("👥 Invite", "💰 Balance")
    markup.row("💸 Withdraw")
    return markup

# --- Withdraw Menu ---
def withdraw_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💳 Bank", "📱 Mobile Money")
    markup.row("🏦 D17", "🔙 Back to Menu")
    return markup

# --- Back to Main Menu ---
@bot.message_handler(func=lambda m: m.text == "🔙 Back to Menu")
def back_to_menu(message):
    bot.send_message(message.chat.id, "Back to main menu:", reply_markup=main_menu())

# --- Start / Referral ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    args = message.text.split()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referrer = None
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
        
        cursor.execute(
            "INSERT INTO users (user_id, name, referrer) VALUES (?, ?, ?)",
            (user_id, name, referrer)
        )
        conn.commit()
        
        if referrer and referrer != user_id:
            cursor.execute(
                "UPDATE users SET balance = balance + ?, earned = earned + ? WHERE user_id=?",
                (REWARD_REF, REWARD_REF, referrer)
            )
            conn.commit()
            bot.send_message(referrer, f"🎉 Your friend {name} joined using your link! You earned {REWARD_REF} DT!")

    bot.send_message(message.chat.id,
        f"Welcome {name} 👋\nEarn money by watching videos!",
        reply_markup=main_menu()
    )

# --- Profile ---
@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance, earned FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        balance, earned = result
        bot.send_message(message.chat.id,
            f"👤 Name: {message.from_user.first_name}\n💰 Balance: {balance:.2f} DT\n🏆 Total Earned: {earned:.2f} DT")
    else:
        bot.send_message(message.chat.id, "User not found. Please use /start command.")

# --- Watch Video ---
@bot.message_handler(func=lambda m: m.text == "🎬 Watch")
def watch(message):
    user_id = message.from_user.id
    cursor.execute("SELECT last_watch, video_index FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        bot.send_message(message.chat.id, "Please use /start command first.")
        return
    
    last_watch, video_index = result

    if time.time() - last_watch < WATCH_COOLDOWN:
        remaining = int(WATCH_COOLDOWN - (time.time() - last_watch))
        bot.send_message(message.chat.id,
            f"⏳ Please wait {remaining} seconds before watching next video")
        return

    # Reset to first video if finished
    if video_index >= len(VIDEOS):
        video_index = 0

    video = VIDEOS[video_index]
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Watched & Next", callback_data=f"next_{video_index}"))

    # Check if video file exists
    if os.path.exists(video["file"]):
        try:
            with open(video["file"], "rb") as video_file:
                bot.send_video(message.chat.id, video=video_file,
                               caption=f"🎬 {video['title']}\nWatch the video and click 'Watched & Next' to earn {REWARD_VIDEO} DT!",
                               reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id,
                f"❌ Error sending video. Please contact support.\nError: {str(e)}")
    else:
        bot.send_message(message.chat.id,
            f"⚠️ Video file '{video['file']}' not found. Please check if the file exists.")

# --- Handle Next Video / Reward ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("next_"))
def next_video(call):
    user_id = call.from_user.id
    index = int(call.data.split("_")[1])

    # Reward for watching the video
    cursor.execute(
        "UPDATE users SET balance = balance + ?, earned = earned + ?, last_watch=?, video_index=? WHERE user_id=?",
        (REWARD_VIDEO, REWARD_VIDEO, int(time.time()), index + 1, user_id)
    )
    conn.commit()

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 0

    # Send next video if exists
    if index + 1 < len(VIDEOS):
        video = VIDEOS[index + 1]
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✅ Watched & Next", callback_data=f"next_{index + 1}"))
        
        if os.path.exists(video["file"]):
            try:
                with open(video["file"], "rb") as video_file:
                    bot.send_video(call.message.chat.id, video=video_file,
                                   caption=f"🎬 {video['title']}\nWatch the video and click 'Watched & Next' to earn {REWARD_VIDEO} DT!",
                                   reply_markup=markup)
            except Exception as e:
                bot.send_message(call.message.chat.id, f"❌ Error sending video: {video['file']}")
        else:
            bot.send_message(call.message.chat.id, f"⚠️ Video file '{video['file']}' not found.")
    else:
        # All videos completed
        bot.send_message(call.message.chat.id,
            f"✅ Congratulations! You've completed all videos!\n💰 Your current balance: {balance:.2f} DT\n\n🎬 Use the 'Watch' button again to start over!")
        
        # Reset video index for next session
        cursor.execute("UPDATE users SET video_index = 0 WHERE user_id=?", (user_id,))
        conn.commit()

# --- Invite ---
@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={user_id}"
    
    # Get referral count
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer=?", (user_id,))
    referral_count = cursor.fetchone()[0]
    
    bot.send_message(message.chat.id,
        f"👥 Invite your friends and earn {REWARD_REF} DT per friend!\n\n"
        f"📊 Your referrals: {referral_count}\n"
        f"💰 You earn: {REWARD_REF} DT per referral\n\n"
        f"🔗 Your invite link:\n{link}\n\n"
        f"💡 Share this link with your friends!")

# --- Balance ---
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        balance = result[0]
        bot.send_message(message.chat.id, f"💰 Your balance: {balance:.2f} DT")
    else:
        bot.send_message(message.chat.id, "User not found. Please use /start command.")

# --- Withdraw ---
@bot.message_handler(func=lambda m: m.text == "💸 Withdraw")
def withdraw(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()

    if not result:
        bot.send_message(message.chat.id, "User not found. Please use /start command.")
        return

    balance = result[0]

    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ Minimum withdraw amount is {MIN_WITHDRAW} DT\nYour current balance: {balance:.2f} DT")
        return

    bot.send_message(message.chat.id, f"💰 Your balance: {balance:.2f} DT\nPlease choose a withdrawal method:", reply_markup=withdraw_menu())

# --- Handle Withdraw Methods ---
@bot.message_handler(func=lambda m: m.text in ["💳 Bank", "📱 Mobile Money", "🏦 D17"])
def process_withdraw(message):
    user_id = message.from_user.id
    method = message.text
    
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        bot.send_message(message.chat.id, "User not found. Please use /start command.", reply_markup=main_menu())
        return
    
    balance = result[0]
    
    if balance < MIN_WITHDRAW:
        bot.send_message(message.chat.id, f"❌ Minimum withdraw amount is {MIN_WITHDRAW} DT", reply_markup=main_menu())
        return
    
    # Process withdrawal (in real implementation, you would integrate with payment API)
    bot.send_message(message.chat.id, 
        f"📝 Withdrawal request received!\n"
        f"Method: {method}\n"
        f"Amount: {balance:.2f} DT\n\n"
        f"✅ Your request has been submitted. The admin will process it within 24-48 hours.\n"
        f"💡 Note: This is a demo. In production, integrate with actual payment gateway.",
        reply_markup=main_menu())

# --- Error Handler ---
@bot.message_handler(func=lambda m: True)
def handle_unknown(message):
    bot.send_message(message.chat.id, "Please use the menu buttons to interact with the bot.", reply_markup=main_menu())

# --- Run Bot with error handling ---
if __name__ == "__main__":
    print("Bot is starting...")
    print(f"Bot username: @{bot.get_me().username}")
    print("Bot is running... Press Ctrl+C to stop")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Error occurred: {e}")
            print("Restarting polling in 5 seconds...")
            time.sleep(5)
