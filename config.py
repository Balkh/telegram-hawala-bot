# bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# لیست آیدی‌های تلگرام ادمین‌ها (از .env یا لیست پیش‌فرض)
admin_ids_str = os.getenv("ADMIN_IDS", "6458047080")
ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(",") if i.strip()]
