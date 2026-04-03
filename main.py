import os
import threading
from flask import Flask
import telebot
from openai import OpenAI

# 1. Environment Variables (Set these in Render Dashboard)
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# 2. Initialize Clients
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

# 3. Flask Server Setup (To keep Render alive)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# 4. Telegram Bot Handlers
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hello! I am your AI Chatbot powered by Hugging Face. How can I help you today?")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    try:
        # Send a typing indicator
        bot.send_chat_action(message.chat.id, 'typing')

        # Call Hugging Face API (Moonshot Kimi model)
        chat_completion = client.chat.completions.create(
            model="moonshotai/Kimi-K2.5:novita",
            messages=[
                {"role": "user", "content": message.text}
            ],
            max_tokens=500
        )

        # Get response text
        response_text = chat_completion.choices[0].message.content
        
        # Send response back to Telegram
        bot.reply_to(message, response_text)

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "Sorry, I encountered an error processing your request.")

# 5. Run Flask and Bot together
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    # Start the bot in a separate thread
    threading.Thread(target=run_bot).start()
    # Start the Flask server
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
