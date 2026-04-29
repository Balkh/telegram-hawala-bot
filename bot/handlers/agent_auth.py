from telegram.ext import ConversationHandler
from bot.services.database import (
    get_agent_by_phone,
    bind_agent_telegram_id,
    increase_failed_attempts,
    reset_failed_attempts,
    lock_agent,
)
from bot.services.security import verify_password
from bot.services.localization import _


LOGIN_PHONE, LOGIN_PASS = range(2)


def get_lang(context):
    return context.user_data.get("lang", "fa")


async def agent_login_start(update, context):
    lang = get_lang(context)
    await update.message.reply_text(_("agent.login_phone", lang=lang))
    return LOGIN_PHONE


async def agent_login_phone(update, context):
    lang = get_lang(context)
    phone = update.message.text.strip()
    agent = get_agent_by_phone(phone)

    if not agent:
        await update.message.reply_text(_("agent.login_not_found", lang=lang))
        return ConversationHandler.END

    if not agent["is_active"]:
        await update.message.reply_text(_("agent.login_inactive", lang=lang))
        return ConversationHandler.END

    context.user_data["agent"] = agent
    await update.message.reply_text(_("agent.login_password", lang=lang))
    return LOGIN_PASS


async def agent_login_password(update, context):
    lang = get_lang(context)
    password = update.message.text
    agent = context.user_data["agent"]
    agent_id = agent["id"]

    if not verify_password(password, agent["password_hash"]):
        # 🛡️ سیستم ضد بروت‌فورس برای عامل
        increase_failed_attempts(agent_id)
        
        # چک کردن تعداد تلاش‌ها
        current_agent = get_agent_by_phone(agent["phone"])
        attempts = current_agent["failed_attempts"] if current_agent and "failed_attempts" in current_agent.keys() else 0
        
        if attempts >= 5:
            lock_agent(agent_id)
            context.user_data.pop("agent", None)
            await update.message.reply_text(_("agent.login_too_many_attempts", lang=lang))
            return ConversationHandler.END

        await update.message.reply_text(_("agent.login_wrong_password", lang=lang))
        return LOGIN_PASS

    # ✅ لاگین موفق
    bind_agent_telegram_id(agent_id, update.effective_user.id)
    reset_failed_attempts(agent_id)
    context.user_data.pop("agent", None)

    await update.message.reply_text(_("agent.login_success", lang=lang))
    return ConversationHandler.END
