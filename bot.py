import os
import logging
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    GROQ_API_KEY = os.environ["GROQ_API_KEY"]
except KeyError as e:
    print(f"CRITICAL ERROR: Missing environment variable {e}", flush=True)
    logger.critical(f"Missing environment variable {e}")
    raise e


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

    def log_message(self, format, *args):
        # Suppress logging every ping request to keep the logs clean
        return

def run_ping_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    logger.info(f"Ping server listening on port {port}")
    server.serve_forever()

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"CRITICAL ERROR: Failed to initialize Groq client: {e}", flush=True)
    logger.critical(f"Failed to initialize Groq client: {e}")
    raise e
user_histories = {}

async def start(update, context):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("👋 Hello! I am your AI assistant. Ask me anything!")

async def clear(update, context):
    user_histories[update.effective_user.id] = []
    await update.message.reply_text("🗑️ History cleared!")

async def handle_message(update, context):
    user = update.effective_user
    text = update.message.text
    if user.id not in user_histories:
        user_histories[user.id] = []
    user_histories[user.id].append({"role": "user", "content": text})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful assistant."}] + user_histories[user.id],
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
        user_histories[user.id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Error. Please try again.")

try:
    # Explicitly create and set an event loop for Python 3.12/3.13/3.14 compatibility
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the ping server in a background daemon thread
    threading.Thread(target=run_ping_server, daemon=True).start()

    logger.info("Bot is running...")
    print("Bot is running...", flush=True)
    app.run_polling()
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: {e}", flush=True)
    logger.critical(f"Critical startup error: {e}")
    raise e