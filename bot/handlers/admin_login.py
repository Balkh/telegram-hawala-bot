from telegram.ext import ConversationHandler
from bot.services.database import (
    get_admin_by_username,
    bind_admin_telegram_id,
    increase_admin_failed_attempts,
    reset_admin_failed_attempts,
    lock_admin,
)
from bot.services.localization import _
from bot.handlers.admin import get_lang
from bot.services.security import verify_password

ADMIN_USERNAME, ADMIN_PASSWORD = range(2)


async def admin_login_start(update, context):
    lang = get_lang(context)
    await update.message.reply_text(_("admin.login_username", lang=lang))
    return ADMIN_USERNAME


async def admin_login_username(update, context):
    lang = get_lang(context)
    username = update.message.text.strip()
    admin = get_admin_by_username(username)

    if not admin:
        await update.message.reply_text(_("admin.login_username_not_found", lang=lang))
        return ConversationHandler.END

    if not admin["is_active"]:
        await update.message.reply_text(_("admin.login_admin_inactive", lang=lang))
        return ConversationHandler.END

    if admin["telegram_id"] and not context.user_data.get("role"):
        await update.message.reply_text(_("admin.login_already_logged_in", lang=lang))
        return ConversationHandler.END

    context.user_data["admin"] = admin
    await update.message.reply_text(_("admin.login_password_prompt", lang=lang))
    return ADMIN_PASSWORD


async def admin_login_password(update, context):
    lang = get_lang(context)
    password = update.message.text
    admin = context.user_data["admin"]

    if not verify_password(password, admin["password_hash"]):
        admin_id = admin["id"]
        username = admin["username"]

        increase_admin_failed_attempts(admin_id)
        refreshed = get_admin_by_username(username)
        attempts = (
            refreshed["failed_attempts"]
            if refreshed and "failed_attempts" in refreshed.keys()
            else 0
        )

        if attempts >= 5:
            lock_admin(admin_id)
            context.user_data.pop("admin", None)
            await update.message.reply_text(_("admin.login_too_many_attempts", lang=lang))
            return ConversationHandler.END

        await update.message.reply_text(_("admin.login_password_incorrect", lang=lang))
        return ConversationHandler.END

    # 1) ذخیره telegram_id در دیتابیس
    bind_admin_telegram_id(
        admin_id=admin["id"],
        telegram_id=update.effective_user.id,
    )

    # 2) ذخیره اطلاعات ادمین در context
    context.user_data["admin_id"] = admin["id"]
    context.user_data["role"] = "admin"
    context.user_data["admin_data"] = admin

    # 3) پاک کردن داده‌های موقت لاگین
    reset_admin_failed_attempts(admin["id"])
    context.user_data.pop("admin", None)

    # 4) ارسال پیام موفقیت و نمایش منوی ادمین
    await update.message.reply_text(_("admin.login_success", lang=lang))

    from bot.handlers.admin import admin_menu

    await admin_menu(update, context)

    return ConversationHandler.END
