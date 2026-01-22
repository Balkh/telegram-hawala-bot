# bot.py
import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import db
import auth
from handlers.menu import show_menu


from handlers.admin import (
    list_agents,
    start_create_agent,
    get_agent_username,
    get_agent_password,
    get_agent_province,
    get_agent_balance,
    create_agent_currency,
    admin_financial_report,
    CREATE_USERNAME,
    CREATE_PASSWORD,
    CREATE_PROVINCE,
    CREATE_BALANCE,
    CREATE_CURRENCY,
)


from handlers.agent import (
    start_hawala,
    get_sender,
    get_receiver,
    get_amount,
    get_currency,
    get_province,
    start_track,
    track_hawala,
    start_confirm,
    get_confirm_code,
    confirm_hawala,
    list_my_hawalas,
    SENDER,
    RECEIVER,
    AMOUNT,
    CURRENCY,
    PROVINCE,
    TRACK_CODE,
    CONFIRM_CODE,
    CONFIRM_ID,
    start_manage_balance,
    handle_balance_action,
    handle_balance_currency,
    handle_balance_amount,
    BALANCE_ACTION,
    BALANCE_CURRENCY,
    BALANCE_AMOUNT,
    # edit hawala
    start_edit_hawala,
    get_edit_code,
    get_edit_amount,
    get_edit_currency,
    save_edit,
    EDIT_CODE,
    EDIT_AMOUNT,
    EDIT_CURRENCY,
    EDIT_PROVINCE,
    # delete hawala
    start_delete_hawala,
    get_delete_code,
    confirm_delete,
    DELETE_CODE,
    DELETE_CONFIRM,
)


load_dotenv()
logging.basicConfig(level=logging.INFO)


LOGIN_USERNAME, LOGIN_PASSWORD = range(2)


# --- Helpers: auth decorators and cancel handler --------------------------------
def require_auth(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = context.user_data.get("user")
        if not user:
            await update.message.reply_text(
                "⚠️ لطفاً ابتدا وارد شوید (دستور /start یا دکمهٔ شروع)."
            )
            return
        return await handler(update, context)

    return wrapper


def require_admin(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = context.user_data.get("user")
        if not user:
            await update.message.reply_text("⚠️ لطفاً ابتدا وارد شوید.")
            return

        if user.get("role") != "admin":
            await update.message.reply_text("🚫 شما دسترسی لازم را ندارید.")
            return

        return await handler(update, context)

    return wrapper


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get("user")
    context.user_data.clear()
    if user:
        context.user_data["user"] = user

    await update.message.reply_text("❎ عملیات لغو شد.")
    await show_menu(update, context)
    return ConversationHandler.END


# ---------------- START / LOGIN ----------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 خوش آمدید به سیستم حواله\n\n" "برای ورود روی دکمه زیر کلیک کنید",
        reply_markup=ReplyKeyboardMarkup(
            [["🚀 شروع سیستم"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )


async def start_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👤 نام کاربری را وارد کنید:")
    return LOGIN_USERNAME


async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login_username"] = update.message.text.strip()
    await update.message.reply_text("🔑 رمز عبور را وارد کنید:")
    return LOGIN_PASSWORD


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data.get("login_username")
    password = update.message.text.strip()

    # اگر authenticate پردازش‌بر است (DB/IO)، آن را در executor اجرا کنید تا event loop بلوک نشود
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(None, auth.authenticate, username, password)

    if not user:
        await update.message.reply_text("❌ نام کاربری یا رمز عبور اشتباه است")
        return ConversationHandler.END

    context.user_data["user"] = user
    await update.message.reply_text("✅ با موفقیت وارد شدید")
    # پردازش منو فرض می‌شود async باشد
    await show_menu(update, context)
    return ConversationHandler.END


# ---------------- MENU ----------------


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context)


# ---------------- LOGOUT ----------------


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ از سیستم خارج شدید",
        reply_markup=ReplyKeyboardMarkup(
            [["🚀 شروع سیستم"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )


# ---------------- MAIN ----------------


def main():
    db.init_db()
    db.create_default_admin()

    token = os.getenv("BOT_TOKEN")
    if not token:
        logging.error(
            "BOT_TOKEN is not set. Set BOT_TOKEN in environment or .env file."
        )
        return

    app = Application.builder().token(token).build()

    # Login
    login_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^🚀\s*شروع سیستم$"), start_system),
        ],
        states={
            LOGIN_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)
            ],
            LOGIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Wrap admin handlers to require admin auth
    wrapped_start_create_agent = require_admin(start_create_agent)
    wrapped_get_agent_username = require_admin(get_agent_username)
    wrapped_get_agent_password = require_admin(get_agent_password)
    wrapped_get_agent_province = require_admin(get_agent_province)
    wrapped_get_agent_balance = require_admin(get_agent_balance)
    wrapped_create_agent_currency = require_admin(create_agent_currency)
    wrapped_list_agents = require_admin(list_agents)
    wrapped_admin_financial_report = require_admin(admin_financial_report)

    # Admin
    admin_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^➕\s*ایجاد عامل$"), wrapped_start_create_agent
            )
        ],
        states={
            CREATE_USERNAME: [MessageHandler(filters.TEXT, wrapped_get_agent_username)],
            CREATE_PASSWORD: [MessageHandler(filters.TEXT, wrapped_get_agent_password)],
            CREATE_PROVINCE: [MessageHandler(filters.TEXT, wrapped_get_agent_province)],
            CREATE_BALANCE: [MessageHandler(filters.TEXT, wrapped_get_agent_balance)],
            CREATE_CURRENCY: [
                MessageHandler(filters.TEXT, wrapped_create_agent_currency)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=False,
    )

    # Hawala create (require auth)
    wrapped_start_hawala = require_auth(start_hawala)
    wrapped_get_sender = require_auth(get_sender)
    wrapped_get_receiver = require_auth(get_receiver)
    wrapped_get_amount = require_auth(get_amount)
    wrapped_get_currency = require_auth(get_currency)
    wrapped_get_province = require_auth(get_province)

    hawala_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^📌\s*ثبت حواله$"), wrapped_start_hawala)
        ],
        states={
            SENDER: [MessageHandler(filters.TEXT, wrapped_get_sender)],
            RECEIVER: [MessageHandler(filters.TEXT, wrapped_get_receiver)],
            AMOUNT: [MessageHandler(filters.TEXT, wrapped_get_amount)],
            CURRENCY: [MessageHandler(filters.TEXT, wrapped_get_currency)],
            PROVINCE: [MessageHandler(filters.TEXT, wrapped_get_province)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Track
    wrapped_start_track = require_auth(start_track)
    wrapped_track_hawala = require_auth(track_hawala)
    track_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🔎\s*پیگیری حواله$"), wrapped_start_track)
        ],
        states={TRACK_CODE: [MessageHandler(filters.TEXT, wrapped_track_hawala)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Confirm
    wrapped_start_confirm = require_auth(start_confirm)
    wrapped_get_confirm_code = require_auth(get_confirm_code)
    wrapped_confirm_hawala = require_auth(confirm_hawala)
    confirm_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^✅\s*تأیید حواله$"), wrapped_start_confirm)
        ],
        states={
            CONFIRM_CODE: [MessageHandler(filters.TEXT, wrapped_get_confirm_code)],
            CONFIRM_ID: [MessageHandler(filters.TEXT, wrapped_confirm_hawala)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    balance_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^⚙️ مدیریت موجودی$"), require_auth(start_manage_balance)
            )
        ],
        states={
            BALANCE_ACTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, require_auth(handle_balance_action)
                )
            ],
            BALANCE_CURRENCY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    require_auth(handle_balance_currency),
                )
            ],
            BALANCE_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, require_auth(handle_balance_amount)
                )
            ],
        },
        fallbacks=[],
    )
    edit_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^✏️ ویرایش حواله$"), require_auth(start_edit_hawala)
            )
        ],
        states={
            EDIT_CODE: [MessageHandler(filters.TEXT, require_auth(get_edit_code))],
            EDIT_AMOUNT: [MessageHandler(filters.TEXT, require_auth(get_edit_amount))],
            EDIT_CURRENCY: [
                MessageHandler(filters.TEXT, require_auth(get_edit_currency))
            ],
            EDIT_PROVINCE: [MessageHandler(filters.TEXT, require_auth(save_edit))],
        },
        fallbacks=[],
    )

    delete_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🗑 حذف حواله$"), require_auth(start_delete_hawala)
            )
        ],
        states={
            DELETE_CODE: [MessageHandler(filters.TEXT, require_auth(get_delete_code))],
            DELETE_CONFIRM: [
                MessageHandler(filters.TEXT, require_auth(confirm_delete))
            ],
        },
        fallbacks=[],
    )

    app.add_handler(login_conv)
    app.add_handler(admin_conv)
    app.add_handler(hawala_conv)
    app.add_handler(track_conv)
    app.add_handler(confirm_conv)
    app.add_handler(balance_conv)
    app.add_handler(edit_conv)
    app.add_handler(delete_conv)

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📋\s*لیست حواله‌ها$"), require_auth(list_my_hawalas)
        )
    )
    app.add_handler(MessageHandler(filters.Regex(r"^🚪\s*خروج$"), logout))
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(🏠\s*صفحه اصلی|📍\s*منوی اصلی)$"), back_to_main_menu
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📊\s*گزارش مالی$"), wrapped_admin_financial_report
        )
    )
    app.add_handler(
        MessageHandler(filters.Regex(r"^👥\s*لیست عامل‌ها$"), wrapped_list_agents)
    )

    # Global error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logging.exception("Unhandled exception while handling an update")
        try:
            if isinstance(update, Update) and update.message:
                await update.message.reply_text(
                    "⚠️ خطای داخلی رخ داد. لطفاً بعداً تلاش کنید."
                )
        except Exception:
            pass

    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
