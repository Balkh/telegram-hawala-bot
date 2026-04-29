from telegram.ext import Application
from bot.services.database import init_db
from routes import register_routes
from config import BOT_TOKEN


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Please configure BOT_TOKEN in environment or .env.")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    register_routes(app)

    print("🤖 Hawala Bot is running ...", flush=True)
    app.run_polling()


if __name__ == "__main__":
    main()
