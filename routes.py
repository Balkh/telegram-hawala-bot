# bot/routes.py
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)

# admin handlers
from bot.handlers.admin import (
    # توابع ادمین
    admin_menu,
    admin_logout,
    list_agents,
    financial_report,
    handle_agents_callback,
    # توابع ایجاد عامل
    create_agent_start,
    get_name,
    get_password,
    confirm_password,
    get_province,
    get_phone,
    get_tazkira,
    get_balance,
    get_currency,
    confirm_agent,
    # توابع مدیریت عامل
    toggle_agent_start,
    toggle_agent_by_id,
    # حالت‌های Conversation ادمین
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

# agent handlers - جدید
from bot.handlers.agent import (
    # توابع منوی عامل
    agent_menu,
    agent_logout,
    # توابع حواله
    send_hawala_start,
    send_receiver_agent,
    send_receiver_name,
    send_receiver_tazkira,
    send_amount,
    send_sender_name,
    send_currency,
    confirm_transaction,
    list_my_transactions,
    track_transaction_start,
    list_my_transactions,
    track_transaction_code,
    manage_pending_transactions_start,
    # حالت‌های Conversation عامل
    SEND_RECEIVER_AGENT,
    SEND_RECEIVER_NAME,
    SEND_RECEIVER_TAZKIRA,
    SEND_SENDER_NAME,
    SEND_AMOUNT,
    SEND_CURRENCY,
    CONFIRM_TRANSACTION,
    TRACK_CODE,
)

# admin login
from bot.handlers.admin_login import (
    admin_login_start,
    admin_login_username,
    admin_login_password,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)

# agent login - جدید
from bot.handlers.agent import (
    agent_login_start,
    agent_login_phone,
    agent_login_password,
    LOGIN_PHONE,
    LOGIN_PASSWORD,
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

    # ========= ADMIN ACTIONS =========
    app.add_handler(MessageHandler(filters.Regex("^👑 منوی ادمین$"), admin_menu))
    app.add_handler(MessageHandler(filters.Regex("^📋 لیست عامل‌ها$"), list_agents))
    app.add_handler(MessageHandler(filters.Regex("^📊 گزارش مالی$"), financial_report))

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

    # ========= CALLBACK HANDLERS =========
    # هندلر لیست عامل‌ها
    app.add_handler(
        CallbackQueryHandler(
            handle_agents_callback, pattern="^(refresh_agents|back_to_menu)$"
        )
    )

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

    # ========= AGENT ACTIONS =========
    # لیست و مدیریت حواله‌ها
    app.add_handler(
        MessageHandler(filters.Regex("^📋 حواله‌های من$"), list_my_transactions)
    )
    app.add_handler(
        MessageHandler(filters.Regex("^🔄 بروزرسانی لیست$"), list_my_transactions)
    )
    app.add_handler(
        MessageHandler(filters.Regex("^📋 مشاهده همه حواله‌ها$"), list_my_transactions)
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^✏️ مدیریت حواله‌های در انتظار$"),
            manage_pending_transactions_start,
        )
    )
    app.add_handler(MessageHandler(filters.Regex("^❌ لغو عملیات$"), agent_menu))
    # ناوبری
    app.add_handler(
        MessageHandler(filters.Regex("^💰 موجودی و گزارش$"), agent_menu)
    )  # موقتاً
    app.add_handler(
        MessageHandler(filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu)
    )

    # خروج
    app.add_handler(
        MessageHandler(filters.Regex("^🚪 خروج از حساب عامل$"), agent_logout)
    )

    # بقیه دکمه‌ها توسط ConversationHandlerها مدیریت می‌شن
    # ارسال حواله جدید

    send_hawala_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 ارسال حواله جدید$"), send_hawala_start)
        ],
        states={
            SEND_RECEIVER_AGENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_receiver_agent)
            ],
            SEND_RECEIVER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_receiver_name)
            ],
            SEND_RECEIVER_TAZKIRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_receiver_tazkira)
            ],
            SEND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_amount)],
            SEND_SENDER_NAME: [  # 🔴 حالت جدید اضافه شد
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_sender_name)
            ],
            SEND_CURRENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_currency)
            ],
            CONFIRM_TRANSACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transaction)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", agent_menu),
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^❌ لغو$"), agent_menu),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu),
        ],
    )

    app.add_handler(send_hawala_conv)

    # پیگیری حواله
    track_hawala_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔍 پیگیری با کد حواله$"), track_transaction_start
            )
        ],
        states={
            TRACK_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, track_transaction_code)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(track_hawala_conv)

    # ========= COMMON =========
    app.add_handler(MessageHandler(filters.Regex("^🚪 خروج$"), exit_menu))

    # ========= ERRORS =========
    app.add_error_handler(global_error_handler)
