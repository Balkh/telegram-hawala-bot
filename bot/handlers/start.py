from telegram import ReplyKeyboardMarkup
from bot.services.database import (
    get_admin_by_telegram_id,
    get_agent_by_telegram_id,
)


async def start(update, context):
    user_id = update.effective_user.id

    # بررسی نقش از طریق سشن (برای تست با اکانت مشترک)
    role = context.user_data.get("role")
    
    if role == "admin":
        from bot.handlers.admin import admin_menu
        await update.message.reply_text("👑 خوش آمدید ادمین")
        await admin_menu(update, context)
        return
    elif role == "agent":
        from bot.handlers.agent import agent_menu
        await update.message.reply_text("🎛 خوش آمدید عامل")
        await agent_menu(update, context)
        return

    # اگر در سشن نبود، از دیتابیس چک کن
    admin = get_admin_by_telegram_id(user_id)
    agent = get_agent_by_telegram_id(user_id)

    # 👑 ادمین لاگین شده
    if admin and admin["is_active"]:
        # منوی اصلی ادمین - بدون انتخاب
        from bot.handlers.admin import admin_menu
        
        # ارسال خوشامدگویی و سپس منوی کامل
        await update.message.reply_text("👑 خوش آمدید ادمین")
        
        # فراخوانی منوی کامل ادمین
        await admin_menu(update, context)
        return

    # 🎛 عامل لاگین شده
    if agent and agent["is_active"]:
        # تنظیم اطلاعات در سشن اگر نیست
        if not context.user_data.get("agent_id"):
            context.user_data["agent_id"] = agent["id"]
            context.user_data["role"] = "agent"
            
        from bot.handlers.agent import agent_menu
        await update.message.reply_text("🎛 خوش آمدید عامل")
        await agent_menu(update, context)
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
