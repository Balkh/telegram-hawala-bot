from telegram.ext import ConversationHandler
from bot.services.database import (
    get_admin_by_username,
    bind_admin_telegram_id,
)
from bot.services.security import verify_password

ADMIN_USERNAME, ADMIN_PASSWORD = range(2)


async def admin_login_start(update, context):
    await update.message.reply_text("👤 یوزرنیم ادمین را وارد کنید:")
    return ADMIN_USERNAME


async def admin_login_username(update, context):
    username = update.message.text.strip()
    admin = get_admin_by_username(username)

    if not admin:
        await update.message.reply_text("❌ ادمینی با این یوزرنیم وجود ندارد")
        return ConversationHandler.END

    if not admin["is_active"]:
        await update.message.reply_text("⛔ حساب ادمین غیرفعال است")
        return ConversationHandler.END

    context.user_data["admin"] = admin
    await update.message.reply_text("🔑 پسورد را وارد کنید:")
    return ADMIN_PASSWORD


async def admin_login_password(update, context):
    password = update.message.text
    admin = context.user_data["admin"]

    if not verify_password(password, admin["password_hash"]):
        await update.message.reply_text("❌ پسورد اشتباه است")
        return ConversationHandler.END

    bind_admin_telegram_id(
        admin_id=admin["id"],
        telegram_id=update.effective_user.id,
    )

    await update.message.reply_text("✅ ورود ادمین با موفقیت انجام شد 👑")
    return ConversationHandler.END
