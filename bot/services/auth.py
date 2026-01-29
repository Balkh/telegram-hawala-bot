from bot.services.database import (
    get_admin_by_telegram_id,
    get_agent_by_telegram_id,
)


def require_admin(func):
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user

        admin = get_admin_by_telegram_id(user.id)

        if not admin:
            await update.message.reply_text("⛔ دسترسی ادمین ندارید")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


def require_agent(func):
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        agent = get_agent_by_telegram_id(user.id)

        if not agent:
            await update.message.reply_text("🔐 ابتدا وارد حساب عامل شوید")
            return

        if not agent["is_active"]:
            await update.message.reply_text("⛔ حساب شما مسدود است")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
