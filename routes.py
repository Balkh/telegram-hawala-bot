# bot/routes.py
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters

# admin handlers
from bot.handlers.admin import (
    create_agent_start,
    get_name,
    get_password,
    confirm_password,
    get_province,
    get_phone,
    get_tazkira,
    get_balance,
    confirm_agent,
    list_agents,
    get_currency,
    toggle_agent_start,
    toggle_agent_by_id,
    NAME,
    PASSWORD,
    CONFIRM_PASSWORD,
    PROVINCE,
    PHONE,
    TAZKIRA,
    BALANCE,
    CURRENCY,
    CONFIRM_AGENT,
    TOGGLE_AGENT,
)


# agent handlers
from bot.handlers.agent import (
    agent_login_start,
    agent_login_password,
    agent_login_phone,
    LOGIN_PASSWORD,
    LOGIN_PHONE,
)
from bot.handlers.admin_login import (
    admin_login_start,
    admin_login_username,
    admin_login_password,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)

# common
from bot.handlers.common import exit_menu
from bot.handlers.start import start

# errors
from bot.services.errors import global_error_handler


def register_routes(app):

    # ========= START =========
    app.add_handler(CommandHandler("start", start))

    # ========= ADMIN LOGIN =========
    admin_login_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^👑 ورود ادمین$"), admin_login_start)
        ],
        states={
            ADMIN_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_login_username)
            ],
            ADMIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_login_password)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(admin_login_conv)

    # ========= ADMIN ACTIONS (protected by decorator) =========
    app.add_handler(MessageHandler(filters.Regex("^📋 لیست عامل‌ها$"), list_agents))

    toggle_agent_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^⛔ فعال / غیرفعال عامل$"), toggle_agent_start
            )
        ],
        states={
            TOGGLE_AGENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, toggle_agent_by_id)
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(toggle_agent_conv)

    create_agent_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ ایجاد عامل$"), create_agent_start)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            CONFIRM_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_password)
            ],
            PROVINCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_province)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            TAZKIRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tazkira)],
            BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_balance)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_currency)],
            CONFIRM_AGENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_agent)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(create_agent_conv)

    # ========= AGENT LOGIN =========
    agent_login_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔐 ورود عامل$"), agent_login_start)
        ],
        states={
            LOGIN_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_phone)
            ],
            LOGIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_login_password)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(agent_login_conv)

    # ========= COMMON =========
    app.add_handler(MessageHandler(filters.Regex("^🚪 خروج$"), exit_menu))

    # ========= ERRORS =========
    app.add_error_handler(global_error_handler)
