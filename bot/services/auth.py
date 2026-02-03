from bot.services.database import get_admin_by_telegram_id, get_agent_by_telegram_id


def require_admin(func):
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user

        # 1. اول context رو چک کن
        if "role" in context.user_data and context.user_data["role"] == "admin":
            return await func(update, context, *args, **kwargs)

        # 2. اگر context نداشت، دیتابیس رو چک کن
        admin = get_admin_by_telegram_id(user.id)

        if not admin:
            # 🔴 **ارسال پیام خطا با روش درست**
            if update.callback_query:
                await update.callback_query.message.reply_text("⛔ دسترسی ادمین ندارید")
            elif update.message:
                await update.message.reply_text("⛔ دسترسی ادمین ندارید")
            return

        # 3. ✅ **اینجا مهمه: context رو پر کن قبل از ادامه**
        context.user_data["role"] = "admin"
        context.user_data["admin_id"] = admin["id"]
        context.user_data["admin_username"] = admin["username"]

        # 4. حالا تابع اصلی رو اجرا کن
        return await func(update, context, *args, **kwargs)

    return wrapper


def require_agent(func):
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user

        # تابع کمکی برای ارسال پیام
        async def send_message(text):
            if update.callback_query:
                await update.callback_query.message.reply_text(text)
            elif update.message:
                await update.message.reply_text(text)

        # 1. اول context رو چک کن
        if "role" in context.user_data and context.user_data["role"] == "agent":
            return await func(update, context, *args, **kwargs)

        # 2. اگر context نداشت، دیتابیس رو چک کن
        agent = get_agent_by_telegram_id(user.id)

        if not agent:
            await send_message("🔐 ابتدا وارد حساب عامل شوید")
            return

        if not agent["is_active"]:
            await send_message("⛔ حساب شما مسدود است")
            return

        # 3. اگر در دیتابیس پیدا شد، context رو هم پر کن
        context.user_data["role"] = "agent"
        context.user_data["agent_id"] = agent["id"]

        return await func(update, context, *args, **kwargs)

    return wrapper
