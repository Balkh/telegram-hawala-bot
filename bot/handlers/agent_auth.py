from telegram.ext import ConversationHandler
from bot.services.database import get_agent_by_phone, bind_agent_telegram
from bot.services.security import verify_password

LOGIN_PHONE, LOGIN_PASS = range(2)


async def agent_login_start(update, context):
    await update.message.reply_text("📞 شماره تماس:")
    return LOGIN_PHONE


async def agent_login_phone(update, context):
    phone = update.message.text.strip()
    agent = get_agent_by_phone(phone)

    if not agent:
        await update.message.reply_text("❌ عامل یافت نشد")
        return ConversationHandler.END

    if not agent["is_active"]:
        await update.message.reply_text("⛔ حساب غیرفعال")
        return ConversationHandler.END

    context.user_data["agent"] = agent
    await update.message.reply_text("🔐 پسورد:")
    return LOGIN_PASS


async def agent_login_password(update, context):
    password = update.message.text
    agent = context.user_data["agent"]

    if not verify_password(password, agent["password_hash"]):
        await update.message.reply_text("❌ پسورد اشتباه")
        return LOGIN_PASS

    bind_agent_telegram(agent["id"], update.effective_user.id)

    await update.message.reply_text("✅ ورود موفق")
    return ConversationHandler.END
