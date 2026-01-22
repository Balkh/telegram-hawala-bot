# handlers/menu.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get("user")
    if not user:
        return

    if user["role"] == "admin":
        keyboard = [
            ["➕ ایجاد عامل"],
            ["📊 گزارش مالی"],
            ["👥 لیست عامل‌ها"],
            ["🚪 خروج"],
        ]
    else:
        keyboard = [
            ["📌 ثبت حواله"],
            ["✏️ ویرایش حواله"],
            ["🗑 حذف حواله"],
            ["🔎 پیگیری حواله"],
            ["✅ تأیید حواله"],
            ["📋 لیست حواله‌ها"],
            ["⚙️ مدیریت موجودی"],
            ["🚪 خروج"],
        ]

    await update.message.reply_text(
        "📍 منوی اصلی",
        reply_markup=ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=False
        ),
    )
