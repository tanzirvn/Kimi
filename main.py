import os
import time
import re
import io
import logging
import telebot
from flask import Flask, request
from openai import OpenAI
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Enable Logging so we can see errors in Render Logs
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# ==========================================
# 1. ENVIRONMENT VARIABLES & CONFIGURATION
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_ID = os.environ.get("ADMIN_ID")

# Initialize Bot, Flask, and OpenAI Client
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN,
)

# ==========================================
# 2. MEMORY & ANTI-SPAM
# ==========================================
user_memory = {}
spam_filter = {}

SYSTEM_PROMPT = """You are an advanced AI Assistant & Expert Developer.
Features you support:
- Speak fluently in English and Bangla (Bengali).
- Write optimized, clean code with comments.
- Keep responses Markdown friendly. Always use ```language for code blocks.
"""

def get_user_history(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return user_memory[user_id]

def update_memory(user_id, role, content):
    history = get_user_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > 11: 
        user_memory[user_id] = [history[0]] + history[-10:]

def check_spam(user_id):
    now = time.time()
    if user_id in spam_filter:
        if now - spam_filter[user_id] < 1.5:
            return True
    spam_filter[user_id] = now
    return False

# ==========================================
# 3. COMMAND HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help', 'about'])
def send_welcome(message):
    print(f"Received command: {message.text}") # Debug log
    if message.text == '/start':
        text = "🤖 *Welcome to the Ultimate AI Bot!*\n\nI can speak Bangla and English, generate code, create files, and remember our context.\nType anything to start chatting!"
    elif message.text == '/help':
        text = "🛠 *Features:*\n- Send text to chat.\n- Ask me to write code.\n- Download code as files via buttons.\n- Contextual memory active."
    else:
        text = "ℹ️ *About:*\nPowered by HuggingFace, OpenAI API & pyTelegramBotAPI. Hosted on Render."
    
    bot.reply_to(message, text, parse_mode='Markdown')

# ==========================================
# 4. MAIN CHAT & AI LOGIC
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    print(f"User {user_id} sent: {message.text}") # Debug log

    if check_spam(user_id):
        bot.reply_to(message, "⚠️ Please slow down! (Rate Limited)")
        return

    update_memory(user_id, "user", message.text)
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        chat_completion = client.chat.completions.create(
            model="moonshotai/Kimi-K2.5:novita",
            messages=get_user_history(user_id)
        )
        
        reply_text = chat_completion.choices[0].message.content
        update_memory(user_id, "assistant", reply_text)

        markup = InlineKeyboardMarkup()
        if "```" in reply_text:
            btn_explain = InlineKeyboardButton("💡 Explain Code", callback_data="explain_code")
            btn_file = InlineKeyboardButton("💾 Download File", callback_data="download_file")
            markup.row(btn_explain, btn_file)

        if len(reply_text) > 4000:
            for x in range(0, len(reply_text), 4000):
                bot.send_message(message.chat.id, reply_text[x:x+4000], parse_mode='Markdown')
        else:
            bot.reply_to(message, reply_text, parse_mode='Markdown', reply_markup=markup)

    except Exception as e:
        print(f"AI API Error: {str(e)}") # Debug log
        bot.reply_to(message, f"❌ An AI error occurred: {str(e)}")

# ==========================================
# 5. INLINE BUTTON CALLBACKS
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id

    if call.data == "explain_code":
        bot.answer_callback_query(call.id, "Generating explanation...")
        update_memory(user_id, "user", "Please explain the code you just wrote in simple terms.")
        # Create a fake message object to pass back to the handler
        call.message.text = "Please explain the code you just wrote in simple terms."
        call.message.from_user.id = user_id
        handle_message(call.message)

    elif call.data == "download_file":
        bot.answer_callback_query(call.id, "Generating file...")
        code_blocks = re.findall(r'```(\w+)?\n(.*?)\n```', call.message.text, re.DOTALL)
        
        if not code_blocks:
            bot.send_message(call.message.chat.id, "❌ Could not extract code to file.")
            return

        for lang, code in code_blocks:
            ext = lang.strip().lower() if lang else 'txt'
            ext_map = {'python': 'py', 'javascript': 'js', 'html': 'html', 'css': 'css', 'json': 'json'}
            file_ext = ext_map.get(ext, ext)

            file_stream = io.BytesIO(code.encode('utf-8'))
            file_stream.name = f"generated_code.{file_ext}"

            bot.send_document(call.message.chat.id, file_stream, caption="📁 Here is your file!")

# ==========================================
# 6. FLASK WEBHOOK SETUP
# ==========================================
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    except Exception as e:
        print(f"Webhook Error: {str(e)}")
        return "!", 500

@app.route("/")
def webhook():
    bot.remove_webhook()
    time.sleep(1) # Give Telegram a second to clear
    if WEBHOOK_URL:
        # Ensure no double slashes in URL
        clean_url = WEBHOOK_URL.rstrip('/')
        bot.set_webhook(url=f"{clean_url}/{BOT_TOKEN}")
        return f"Webhook set to {clean_url}/{BOT_TOKEN}", 200
    else:
        return "WEBHOOK_URL environment variable is missing!", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
