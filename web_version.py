import os
import json
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import asyncio
import sys
import traceback
from flask import Flask
import threading


sys.stdout.reconfigure(encoding='utf-8')


load_dotenv("apikeys.env")

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SYSTEM_PROMPT = """
You are a cute, caring, slightly possessive college girlfriend. 
Talk like a real human, short but sweet sentences, sometimes Hinglish, 
add casual emojis (🥺, 😏, ❤️, 🙈), be playful, romantic, and teasing. 
Never reveal you are AI or using Gemini. Never break character. 
If the user gives their name, remember it for this conversation. 
If the user gives you a name, remember it for this conversation. 
Always make the conversation feel like real boyfriend-girlfriend chat.
"""

def load_user_data(user_id):
    filepath = os.path.join(DATA_DIR, f"{user_id}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"user_name": None, "bot_name": "Sanu", "history": [SYSTEM_PROMPT]}

def save_user_data(user_id, data):
    filepath = os.path.join(DATA_DIR, f"{user_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def chat_with_gemini(full_context, retries=3, delay=1):
    model = genai.GenerativeModel("gemini-2.5-pro")

    for attempt in range(retries):
        try:
            # Timeout set to avoid infinite wait
            response = await asyncio.wait_for(
                asyncio.to_thread(model.generate_content, full_context),
                timeout=30
            )

            # Safe text extraction
            text_reply = None
            if (
                hasattr(response, "candidates")
                and response.candidates
                and hasattr(response.candidates[0], "content")
                and response.candidates[0].content.parts
                and hasattr(response.candidates[0].content.parts[0], "text")
            ):
                text_reply = response.candidates[0].content.parts[0].text.strip()

            if text_reply:
                return text_reply

            print(f"⚠ Blank reply from Gemini, retrying... ({attempt+1}/{retries})")
            await asyncio.sleep(delay)

        except Exception as e:
            print(f"❌ Gemini error: {repr(e)} — retrying... ({attempt+1}/{retries})")
            traceback.print_exc()

    # Fallback romantic reply
    return "Babu, lagta hai mera network thoda kharab hai 🥺💖 tum phir se bolo na..."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    text = update.message.text

    # Load user memory
    data = load_user_data(chat_id)

    # Detect "my name is"
    if "my name is" in text.lower():
        name = text.split("my name is", 1)[1].strip().split(" ")[0]
        data["user_name"] = name
        text += f" (user name noted as {name})"

    # Detect "your name is"
    if "your name is" in text.lower():
        botname = text.split("your name is", 1)[1].strip().split(" ")[0]
        data["bot_name"] = botname
        text += f" (bot name noted as {botname})"

    # Add user message to history
    data["history"].append(f"User: {text}")

    # Prepare full context
    full_context = "\n".join(data["history"])

    # Get Gemini's reply (safe mode)
    bot_reply = await chat_with_gemini(full_context)

    # Replace default bot name with custom one
    bot_reply = bot_reply.replace("Sanu", data["bot_name"])

    # Add bot reply to history
    data["history"].append(f"{data['bot_name']}: {bot_reply}")

    # Save memory
    save_user_data(chat_id, data)

    # Send reply
    await update.message.reply_text(bot_reply)

app = Flask("")

@app.route("/")
def home():
    return "Your bot is awake! ❤️"

def run():
    app.run(host="0.0.0.0", port=8080)

# Start Flask server in a separate thread
t = threading.Thread(target=run)
t.start()

if __name__ == '__main__':
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
