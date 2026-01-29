"""
هندلرهای عامل (نسخه مینیمال برای تست)
"""

from telegram import Update
from telegram.ext import ContextTypes

from bot.database import db


class AgentHandlers:
    # ---------- شروع ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        دستور /start
        اگر کاربر در دیتابیس نبود، به عنوان agent ثبت می‌شود
        """
        user = update.effective_user
        message = update.message

        # چک ایمنی (برای Pylance و runtime)
        if not user or not message:
            return

        # اگر کاربر وجود نداشت، اضافه کن
        if not db.user_exists(user.id):
            db.add_user(user.id, "agent")
            await message.reply_text("👋 خوش آمدید! شما به عنوان عامل ثبت شدید")
        else:
            await message.reply_text("👋 خوش آمدید دوباره")

    # ---------- بررسی موجودی ----------
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        دستور /balance
        نمایش موجودی عامل
        """
        user = update.effective_user
        message = update.message

        if not user or not message:
            return

        balance = db.get_balance(user.id)

        await message.reply_text(f"💰 موجودی شما: {balance}")

    async def my_transactions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        نمایش تراکنش‌های عامل (نسخه مینیمال – فعلاً فقط پیام)
        """
        message = update.message

        if not message:
            return

        await message.reply_text(
            "📄 هنوز تراکنشی ثبت نشده.\n" "این بخش در مرحله بعدی تکمیل می‌شود."
        )
