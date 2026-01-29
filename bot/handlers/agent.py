from telegram.ext import ConversationHandler


from bot.services.database import (
    get_agent_by_telegram_id,
    get_agent_by_phone,
    bind_agent_telegram_id,
)
from bot.services.security import verify_password
from bot.services.auth import require_agent

from bot.handlers.keyboards import agent_keyboard


LOGIN_PHONE, LOGIN_PASSWORD = range(2)


@require_agent
async def agent_menu(update, context):
    """
    منوی اصلی عامل
    فقط عامل لاگین‌شده + فعال اجازه دسترسی دارد
    """

    user_id = update.effective_user.id

    # 🔍 گرفتن عامل از دیتابیس بر اساس telegram_id
    agent = get_agent_by_telegram_id(user_id)

    # ❌ عامل لاگین نکرده یا وجود ندارد
    if not agent:
        await update.message.reply_text(
            "❌ شما وارد سیستم نشده‌اید\n🔐 لطفاً ابتدا وارد شوید"
        )
        return

    # ⛔ عامل غیرفعال شده
    if not agent["is_active"]:
        await update.message.reply_text(
            "⛔ حساب شما غیرفعال شده\n📞 با ادمین تماس بگیرید"
        )
        return

    # ✅ عامل معتبر
    await update.message.reply_text(
        "🎛 منوی عامل",
        reply_markup=agent_keyboard(),
    )


async def agent_login_start(update, context):
    await update.message.reply_text("📞 شماره تماس خود را وارد کنید:")
    return LOGIN_PHONE


async def agent_login_phone(update, context):
    phone = update.message.text.strip()
    agent = get_agent_by_phone(phone)

    if not agent:
        await update.message.reply_text("❌ عامل با این شماره یافت نشد")
        return ConversationHandler.END

    agent_id, password_hash, telegram_id, is_active = agent

    if not is_active:
        await update.message.reply_text("⛔ حساب شما غیرفعال است")
        return ConversationHandler.END

    if telegram_id:
        await update.message.reply_text("❌ این عامل قبلاً لاگین شده")
        return ConversationHandler.END

    context.user_data["login_agent_id"] = agent_id
    context.user_data["password_hash"] = password_hash

    await update.message.reply_text("🔐 پسورد خود را وارد کنید:")
    return LOGIN_PASSWORD


async def agent_login_password(update, context):
    password = update.message.text
    hashed = context.user_data["password_hash"]

    if not verify_password(password, hashed):
        await update.message.reply_text("❌ پسورد اشتباه است")
        return LOGIN_PASSWORD

    agent_id = context.user_data["login_agent_id"]
    telegram_id = update.effective_user.id

    bind_agent_telegram_id(agent_id, telegram_id)

    await update.message.reply_text(
        "✅ ورود موفق بود",
        reply_markup=agent_keyboard(),
    )

    return ConversationHandler.END
