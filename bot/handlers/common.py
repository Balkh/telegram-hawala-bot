from telegram import ReplyKeyboardRemove
from bot.services.database import (
    get_admin_by_telegram_id,
    get_agent_by_telegram_id,
    unbind_admin_telegram_id,  # جدید
    unbind_agent_telegram_id,  # جدید
)
from bot.handlers.start import start


async def exit_menu(update, context):
    """خروج از حساب کاربری و بازگشت به منوی اصلی"""

    user_id = update.effective_user.id

    # 1. تشخیص نوع کاربر
    admin = get_admin_by_telegram_id(user_id)
    agent = get_agent_by_telegram_id(user_id)

    # 2. unbind صحیح
    if admin:
        unbind_admin_telegram_id(user_id)  # فقط از ادمین
        print(f"🔍 exit_menu: Admin {user_id} logged out")
    elif agent:
        unbind_agent_telegram_id(user_id)  # فقط از عامل
        print(f"🔍 exit_menu: Agent {user_id} logged out")
    else:
        print(f"🔍 exit_menu: User {user_id} not found in any table")

    # 3. پاک کردن تمام داده‌های کاربر از context
    context.user_data.clear()

    # 4. پیام خروج
    await update.message.reply_text(
        "🚪 شما از حساب کاربری خارج شدید.", reply_markup=ReplyKeyboardRemove()
    )

    # 5. نمایش منوی اصلی ورود
    await start(update, context)
