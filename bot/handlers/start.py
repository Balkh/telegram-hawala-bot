from telegram import ReplyKeyboardMarkup
from bot.services.database import (
    get_admin_by_telegram_id,
    get_agent_by_telegram_id,
)


async def start(update, context):
    user_id = update.effective_user.id

    admin = get_admin_by_telegram_id(user_id)
    agent = get_agent_by_telegram_id(user_id)

    # 👑 ادمین لاگین شده
    if admin and admin["is_active"]:
        # منوی اصلی ادمین - بدون انتخاب
        keyboard = [
            ["➕ ایجاد عامل", "📋 لیست عامل‌ها"],
            ["⛔ فعال / غیرفعال عامل", "📊 گزارش مالی"],
            ["🚪 خروج"],
        ]

        await update.message.reply_text(
            "👑 خوش آمدید ادمین",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    # 🎛 عامل لاگین شده
    if agent and agent["is_active"]:
        keyboard = [
            ["💸 ارسال حواله جدید"],
            ["📋 حواله‌های من"],
            ["🔍 پیگیری با کد حواله"],
            ["💰 موجودی و گزارش"],
            ["🎛 منوی عامل"],  # 🔴 دکمه جدید برای ناوبری
            ["🚪 خروج"],
        ]
        await update.message.reply_text(
            "🎛 خوش آمدید عامل",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    # 🔐 کاربر ناشناس
    keyboard = [
        ["👑 ورود ادمین"],
        ["🔐 ورود عامل"],
    ]

    await update.message.reply_text(
        "🔐 لطفاً نوع ورود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
