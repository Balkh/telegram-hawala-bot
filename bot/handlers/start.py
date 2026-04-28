from telegram import ReplyKeyboardMarkup
from bot.services.database import (
    get_admin_by_telegram_id,
    get_agent_by_telegram_id,
)
from bot.services.localization import _


async def start(update, context):
    user_id = update.effective_user.id

    # زبان پیش‌فرض کاربر در این سشن
    lang = context.user_data.get("lang", "ps")

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
        from bot.handlers.admin import admin_menu
        await update.message.reply_text("👑 خوش آمدید ادمین")
        await admin_menu(update, context)
        return

    # 🎛 عامل لاگین شده
    if agent and agent["is_active"]:
        if not context.user_data.get("agent_id"):
            context.user_data["agent_id"] = agent["id"]
            context.user_data["role"] = "agent"
            
        from bot.handlers.agent import agent_menu
        await update.message.reply_text("🎛 خوش آمدید عامل")
        await agent_menu(update, context)
        return

    # 🔐 کاربر ناشناس - مرحله انتخاب زبان
    keyboard = [
        [
            _("buttons.fa", lang="fa"),
            _("buttons.ps", lang="fa"),
        ]
    ]

    await update.message.reply_text(
        _("start.welcome", lang="fa"),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


async def select_language(update, context):
    text = update.message.text.strip()

    if text in ("دری",):
        lang = "fa"
    elif text in ("پشتو", "پښتو"):
        lang = "ps"
    else:
        await update.message.reply_text("❌ زبان نامعتبر است، لطفاً دوباره انتخاب کنید.")
        return

    context.user_data["lang"] = lang

    keyboard = [
        [_("buttons.admin_login", lang=lang)],
        [_("buttons.agent_login", lang=lang)],
    ]

    await update.message.reply_text(
        _("login.choose_role", lang=lang),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
