# bot/handlers/keyboards.py
from telegram import ReplyKeyboardMarkup


def agent_keyboard():
    keyboard = [
        ["➕ ثبت حواله", "📋 لیست حواله‌ها"],
        ["💰 موجودی من"],
        ["🚪 خروج"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )
