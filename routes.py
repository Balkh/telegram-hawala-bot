# bot/routes.py
import logging

logger = logging.getLogger(__name__)

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
    # توابع ایجاد عامل
    create_agent_start,
    # توابع فعال/غیرفعال عامل
    toggle_agent_start,
    # توابع جستجوی عامل‌ها
    search_agents,
    search_by_name,
    search_by_province,
    search_by_phone,
    execute_search,
    filter_active_agents,
    filter_inactive_agents,
    handle_agents_callback,
    # توابع جستجوی حواله‌ها برای ادمین
    admin_search_tx_start,
    admin_search_tx_process,
    # حالت‌های Conversation
    TOGGLE_AGENT,
    ADMIN_SEARCH_TX,
    ADMIN_AGENT_EXPENSE,
    AGENT_PASSWORD_RESET,
    ADMIN_CHANGE_PASSWORD,
    ADMIN_CHANGE_USERNAME,
    admin_agent_expense_overview_start,
    admin_agent_expense_overview_show,
    reset_agent_password_start,
    reset_agent_password_process,
    admin_change_password_start,
    admin_change_password_process,
    admin_change_username_start,
    admin_change_username_process,
    admin_list_admins,
    admin_security_menu,
    admin_backup_db,
)

# admin dashboard handlers
from bot.handlers.admin_dashboard import (
    dashboard_stats,
    download_admin_excel_report,
)

# admin finance handlers
from bot.handlers.admin_finance import (
    central_finance_menu,
    detailed_balances,
    start_transfer_funds,
    get_transfer_amount,
    get_transfer_to_agent,
    confirm_transfer,
    transfer_report,
    FINANCE_MENU,
    TRANSFER_AMOUNT,
    TRANSFER_CONFIRM,
)

# admin alerts handlers
from bot.handlers.admin_alerts import (
    alerts_and_notifications,
    system_health_check,
)

# تابع جستجوی ادمین
from bot.handlers.admin import admin_search_handler

# agent handlers - جدید
from bot.handlers.agent import (
    agent_menu,
    agent_logout,
    send_hawala_start,
    send_receiver_agent,
    send_receiver_name,
    send_receiver_tazkira,
    send_amount,
    send_sender_name,
    send_currency,
    confirm_transaction,
    track_transaction_start,
    list_my_transactions,
    track_transaction_code,
    agent_login_start,
    agent_login_phone,
    agent_login_password,
    manage_pending_transactions_start,
    manage_pending_select_code,
    manage_pending_action,
    edit_pending_amount,
    delete_pending_confirm,
    pay_transaction_start,
    pay_transaction_confirm,
    list_payable_transactions,
    balance_and_report_menu,
    show_full_report,
    download_excel_report,
    balance_management_menu,
    increase_balance_start,
    increase_balance_currency,
    increase_balance_amount,
    decrease_balance_start,
    decrease_balance_currency,
    decrease_balance_amount,
    add_currency_start,
    add_currency_confirm,
    search_advanced_start,
    search_advanced_type,
    search_advanced_results,
    handle_receipt_callback,
    handle_pay_fast_callback,
    agent_expenses_menu,
    add_expense_start,
    add_expense_category,
    add_expense_currency,
    add_expense_amount,
    add_expense_description,
    show_expenses_report,
    staff_contract_start,
    staff_contract_name,
    staff_contract_currency,
    staff_contract_salary,
    staff_contract_start_date,
    staff_contract_pay_day,
    fixed_expense_start,
    fixed_expense_category,
    fixed_expense_currency,
    fixed_expense_amount,
    fixed_expense_start_date,
    fixed_expense_pay_day,
    show_future_obligations,
    send_daily_due_reminders,
    SEND_RECEIVER_AGENT,
    SEND_RECEIVER_NAME,
    SEND_RECEIVER_TAZKIRA,
    SEND_SENDER_NAME,
    SEND_AMOUNT,
    LOGIN_PHONE,
    LOGIN_PASSWORD,
    SEND_CURRENCY,
    CONFIRM_TRANSACTION,
    TRACK_CODE,
    EDIT_TRANSACTION_CHOICE,
    EDIT_AMOUNT,
    DELETE_CONFIRM,
    PAY_TRANSACTION_CODE,
    PAY_CONFIRM,
    BALANCE_MENU,
    INCREASE_BALANCE_AMOUNT,
    INCREASE_BALANCE_CURRENCY,
    DECREASE_BALANCE_AMOUNT,
    DECREASE_BALANCE_CURRENCY,
    ADD_CURRENCY_TYPE,
    SEARCH_TYPE,
    SEARCH_QUERY,
    SEARCH_DATE_RANGE,
    EXPENSE_CATEGORY,
    EXPENSE_CURRENCY,
    EXPENSE_AMOUNT,
    EXPENSE_DESCRIPTION,
    STAFF_NAME,
    STAFF_CURRENCY,
    STAFF_SALARY,
    STAFF_START_DATE,
    STAFF_PAY_DAY,
    FIXED_EXPENSE_CATEGORY,
    FIXED_EXPENSE_CURRENCY,
    FIXED_EXPENSE_AMOUNT,
    FIXED_EXPENSE_START_DATE,
    FIXED_EXPENSE_PAY_DAY,
    agent_change_password_start,
    agent_change_password_process,
    AGENT_CHANGE_PASSWORD,
)

# admin login
from bot.handlers.admin_login import (
    admin_login_start,
    admin_login_username,
    admin_login_password,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)


# common
from bot.handlers.common import exit_menu
from bot.handlers.start import start, select_language

# errors
from bot.services.errors import global_error_handler


def register_routes(app):

    # ========= COMMON DISPATCHERS =========
    async def smart_excel_report_dispatcher(update, context):
        """توزیع‌کننده هوشمند گزارش اکسل بر اساس نقش کاربر"""
        role = context.user_data.get("role")
        
        # اگر نقش در سشن نیست، از دیتابیس چک کن
        if not role:
            from bot.services.database import get_admin_by_telegram_id, get_agent_by_telegram_id
            user_id = update.effective_user.id
            if get_admin_by_telegram_id(user_id):
                role = "admin"
                context.user_data["role"] = "admin"
            elif get_agent_by_telegram_id(user_id):
                role = "agent"
                context.user_data["role"] = "agent"

        if role == "admin":
            return await download_admin_excel_report(update, context)
        elif role == "agent":
            return await download_excel_report(update, context)
        else:
            await update.message.reply_text("🔐 لطفاً ابتدا وارد حساب کاربری خود شوید.")

    # ========= START =========
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(دری|پشتو|پښتو)$"), select_language))
    
    # هندلر مشترک برای دانلود گزارش اکسل (باید قبل از بقیه باشد)
    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^📥 (دانلود گزارش اکسل|د اکسل راپور ښکته کول)$"
            ),
            smart_excel_report_dispatcher,
        )
    )

    # ========= ADMIN ACTIONS =========
    # این بخش باید قبل از AGENT ACTIONS باشد تا تداخل دکمه‌ها (مثل "📥 دانلود گزارش اکسل") پیش نیاید
    
    app.add_handler(
        MessageHandler(
            filters.Regex("^👑 (منوی ادمین|د ادمین د مدیریت مینو)$"),
            admin_menu,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📋 (لیست عامل‌ها|د عاملانو لست)$"),
            list_agents,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📊 (گزارش مالی|مالی راپور|مالیه راپور)$"),
            financial_report,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^🗄 (بک‌آپ دیتابیس|د ډیټابېس بیکاپ)$"),
            admin_backup_db,
        )
    )

    # گزارش حواله‌ها (ادمین)
    admin_search_tx_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔎 (گزارش حواله‌ها|د حوالو راپور)$"),
                admin_search_tx_start,
            ),
        ],
        states={
            ADMIN_SEARCH_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_tx_process)
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"),
                admin_menu,
            ),
        ],
    )
    app.add_handler(admin_search_tx_conv)

    # خلاصه مصارف عامل (ادمین)
    admin_agent_expense_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^📊 (خلاصه مصارف عامل|د عامل د مصارف لنډیز)$"),
                admin_agent_expense_overview_start,
            ),
        ],
        states={
            ADMIN_AGENT_EXPENSE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_agent_expense_overview_show,
                )
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(
                    "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                ),
                admin_menu,
            ),
        ],
    )
    app.add_handler(admin_agent_expense_conv)

    # ریست پسورد عامل توسط ادمین
    admin_reset_agent_password_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔐 (ریست پسورد عامل|د عامل پاسورد بیا ټاکل)$"),
                reset_agent_password_start,
            )
        ],
        states={
            AGENT_PASSWORD_RESET: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    reset_agent_password_process,
                )
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(
                    "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                ),
                admin_menu,
            ),
        ],
    )
    app.add_handler(admin_reset_agent_password_conv)
    
    # ورود ادمین (انتقال به ابتدای هندلرها برای اولویت بالاتر)
    admin_login_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^👑 (ورود ادمین|د ادمین ننوتل)$"),
                admin_login_start,
            )
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

    # تغییر پسورد توسط خود ادمین
    admin_change_password_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔐 (تغییر پسورد ادمین|د ادمین پاسورد بدلول)$"),
                admin_change_password_start,
            )
        ],
        states={
            ADMIN_CHANGE_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_change_password_process,
                )
            ]
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(
                    "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                ),
                admin_menu,
            )
        ],
    )
    app.add_handler(admin_change_password_conv)

    app.add_handler(
        MessageHandler(
            filters.Regex("^📋 (لیست ادمین‌ها|د ادمینانو لست)$"),
            admin_list_admins,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^⚙️ (مدیریت حساب و امنیت|د حساب او امنیت مدیریت)$"),
            admin_security_menu,
        )
    )

    # تغییر نام کاربری توسط خود ادمین
    admin_change_username_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^📝 (تغییر نام کاربری ادمین|د ادمین یوزرنیم بدلول)$"),
                admin_change_username_start,
            )
        ],
        states={
            ADMIN_CHANGE_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_change_username_process,
                )
            ]
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(
                    "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                ),
                admin_menu,
            )
        ],
    )
    app.add_handler(admin_change_username_conv)

    # ورود عامل (انتقال به ابتدای هندلرها برای اولویت بالاتر)
    agent_login_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔐 (ورود عامل|د عامل ننوتل)$"),
                agent_login_start,
            )
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

    # تغییر پسورد توسط خود عامل
    agent_change_password_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔐 (تغییر پسورد|پاسورد بدلول)$"),
                agent_change_password_start,
            )
        ],
        states={
            AGENT_CHANGE_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    agent_change_password_process,
                )
            ]
        },
        fallbacks=[
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی عامل|د عامل منو ته ستنیدل)$"),
                agent_menu,
            )
        ],
    )
    app.add_handler(agent_change_password_conv)
    
    # لیست عامل‌ها
    app.add_handler(
        MessageHandler(
            filters.Regex("^📋 (لیست عامل‌ها|د عاملانو لست)$"),
            list_agents,
        )
    )
    
    # ایجاد عامل جدید
    from bot.handlers.admin import (
        NAME, PASSWORD, CONFIRM_PASSWORD, PROVINCE, PHONE, TAZKIRA, BALANCE, CURRENCY, CONFIRM_AGENT,
        get_name, get_password, confirm_password, get_province, get_phone, get_tazkira, get_balance, get_currency, confirm_agent
    )
    
    create_agent_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^➕ (ایجاد عامل|نوی عامل جوړول)$"),
                create_agent_start,
            )
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            CONFIRM_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_password)],
            PROVINCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_province)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            TAZKIRA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tazkira)],
            BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_balance)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_currency)],
            CONFIRM_AGENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_agent)],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"),
                admin_menu,
            ),
            MessageHandler(
                filters.Regex("^❌ (لغو|لغوه)$"),
                admin_menu,
            ),
        ],
    )
    app.add_handler(create_agent_conv)
    
    # فعال/غیرفعال عامل
    from bot.handlers.admin import TOGGLE_AGENT, toggle_agent_by_id
    
    toggle_agent_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^⛔ (فعال / غیرفعال عامل|عامل فعال/غیرفعال کول)$"),
                toggle_agent_start,
            )
        ],
        states={
            TOGGLE_AGENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, toggle_agent_by_id)],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"),
                admin_menu,
            ),
            MessageHandler(
                filters.Regex("^❌ (لغو|لغوه)$"),
                admin_menu,
            ),
        ],
    )
    app.add_handler(toggle_agent_conv)
    
    # خروج ادمین
    app.add_handler(
        MessageHandler(
            filters.Regex("^🚪 (خروج|د ادمین وتل)$"),
            admin_logout,
        )
    )
    
    # داشبورد و گزارش اکسل
    app.add_handler(
        MessageHandler(
            filters.Regex("^📈 (داشبورد آماری|احصایوي ډشبورډ)$"),
            dashboard_stats,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔄 (بروزرسانی داشبورد|د ډشبورډ نو کول)$"),
            dashboard_stats,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔄 (بروزرسانی گزارش|د راپور نو کول)$"),
            financial_report,
        )
    )
    
    # مدیریت مالی مرکزی - تست ساده
    async def test_central_finance(update, context):
        """تست ساده مدیریت مالی مرکزی"""
        try:
            await update.message.reply_text("🧪 تست: مدیریت مالی مرکزی فراخوانی شد")
            await central_finance_menu(update, context)
        except Exception as e:
            logger.exception("Error in test_central_finance")
            await update.message.reply_text(f"❌ خطا: {str(e)}")
    
    app.add_handler(
        MessageHandler(
            filters.Regex("^💰 (مدیریت مالی مرکزی|د مرکزي مالی مدیریت)$"),
            test_central_finance,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📊 (جزئیات کامل موجودی‌ها|د موجودیو بشپړ جزیات)$"),
            detailed_balances,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📤 (گزارش انتقال بین عامل‌ها|د عاملانو ترمنځ د لېږد راپور)$"),
            transfer_report,
        )
    )
    
    # بررسی سلامت سیستم
    app.add_handler(
        MessageHandler(
            filters.Regex("^🏥 (بررسی سلامت سیستم|د سیستم د سلامت کتنه)$"),
            system_health_check,
        )
    )
    
    # هشدارها و اطلاعیه‌ها
    app.add_handler(
        MessageHandler(
            filters.Regex("^⚠️ (هشدارها و اطلاعیه‌ها|خبرتیاوې او اعلانونه)$"),
            alerts_and_notifications,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔄 (بررسی مجدد هشدارها|د خبرتیاوو بیا کتنه)$"),
            alerts_and_notifications,
        )
    )
    
    # انتقال وجه بین عامل‌ها - فقط ConversationHandler
    # مسیریابی مستقیم حذف شد، فقط ConversationHandler استفاده می‌شود
    
    # ConversationHandler انتقال وجه بین عامل‌ها
    transfer_funds_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^💸 (انتقال وجه بین عامل‌ها|د عاملانو ترمنځ د پیسو لېږد)$"),
                start_transfer_funds,
            )
        ],
        states={
            TRANSFER_AMOUNT: [
                # بازگشت مستقیم به منوی ادمین در هر مرحله
                MessageHandler(
                    filters.Regex(
                        "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                    ),
                    admin_menu,
                ),
                # بازگشت به مدیریت مالی مرکزی
                MessageHandler(
                    filters.Regex("^🔙 (بازگشت|بېرته)$"),
                    central_finance_menu,
                ),
                # سایر ورودی‌ها در این مرحله به عنوان شناسه عامل مبدأ پردازش می‌شوند
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_transfer_amount,
                ),
            ],
            TRANSFER_CONFIRM: [
                # بازگشت مستقیم به منوی ادمین در هر مرحله
                MessageHandler(
                    filters.Regex(
                        "^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"
                    ),
                    admin_menu,
                ),
                # بازگشت به مدیریت مالی مرکزی
                MessageHandler(
                    filters.Regex("^🔙 (بازگشت|بېرته)$"),
                    central_finance_menu,
                ),
                # سایر ورودی‌ها در این مرحله به عنوان شناسه عامل مقصد پردازش می‌شوند
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    get_transfer_to_agent,
                ),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت|بېرته)$"),
                central_finance_menu,
            ),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته|د ادمین مینو ته شاته)$"),
                admin_menu,
            ),
        ],
    )
    app.add_handler(transfer_funds_conv)
    
    # هندلر جداگانه برای دکمه‌های خاص پس از انتقال وجه
    async def handle_post_transfer_buttons(update, context):
        """مدیریت دکمه‌های خاص پس از انتقال وجه"""
        text = update.message.text.strip()
        
        if text in ["💰 مدیریت مالی مرکزی", "💰 د مرکزي مالی مدیریت"]:
            await central_finance_menu(update, context)
            return
        elif text in ["🔙 بازگشت به منوی ادمین", "🔙 بېرته د ادمین منو ته"]:
            await admin_menu(update, context)
            return

    # هندلر پیام‌های متنی برای دکمه‌های خاص
    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^(💰 (مدیریت مالی مرکزی|د مرکزي مالی مدیریت)|🔙 (بازگشت به منوی ادمین|بېرته د ادمین منو ته))$"
            ),
            handle_post_transfer_buttons,
        )
    )
    
    # جستجوی عامل‌ها
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔍 (جستجوی عامل‌ها|د عاملانو لټون)$"),
            search_agents,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^👤 (جستجو بر اساس نام|د نوم له مخې لټون)$"),
            search_by_name,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📍 (جستجو بر اساس ولایت|د ولایت له مخې لټون)$"),
            search_by_province,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📞 (جستجو بر اساس تلفن|د تلیفون له مخې لټون)$"),
            search_by_phone,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🟢 (فقط عامل‌های فعال|یوازې فعال عاملان)$"),
            filter_active_agents,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔴 (فقط عامل‌های غیرفعال|یوازې غیرفعال عاملان)$"),
            filter_inactive_agents,
        )
    )
    
    # جستجوی مجدد
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔍 (جستجوی جدید|نوې لټون)$"),
            search_agents,
        )
    )
    
    # ========= AGENT ACTIONS =========
    # ارسال حواله جدید / نوی حواله
    send_hawala_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^💸 (ارسال حواله جدید|نوی حواله)$"),
                send_hawala_start,
            )
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
            SEND_SENDER_NAME: [
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

    # پیگیری حواله و پرداخت توسط عامل مقصد
    track_hawala_conv = ConversationHandler(
        entry_points=[
                MessageHandler(
                    filters.Regex("^🔍 (پیگیری با کد حواله|د حوالې د کوډ په وسیله تعقیب)$"),
                    track_transaction_start,
                )
        ],
        states={
            TRACK_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, track_transaction_code)
            ],
            PAY_TRANSACTION_CODE: [
                MessageHandler(
                    filters.Regex(
                        "^(💵 پرداخت به گیرنده|💵 د گیرنده تادیه|🔙 بازگشت به منوی عامل|🔙 د عامل منو ته ستنیدل)$"
                    ),
                    pay_transaction_start,
                )
            ],
            PAY_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pay_transaction_confirm)
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", agent_menu),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu),
        ],
    )
    app.add_handler(track_hawala_conv)

    # لیست و مدیریت حواله‌ها
    app.add_handler(
        MessageHandler(
            filters.Regex("^📥 (حواله‌های قابل پرداخت|د تادیې وړ حوالې)$"),
            list_payable_transactions,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📋 (حواله‌های من|زما حوالې)$"),
            list_my_transactions,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔄 (بروزرسانی لیست|لست نو کول)$"),
            list_my_transactions,
        )
    )
    app.add_handler(
        MessageHandler(filters.Regex("^📋 مشاهده همه حواله‌ها$"), list_my_transactions)
    )
    
    manage_pending_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^✏️ (مدیریت حواله‌های در انتظار|د تمه کې حوالو مدیریت)$"
                ),
                manage_pending_transactions_start,
            )
        ],
        states={
            EDIT_TRANSACTION_CHOICE: [
                MessageHandler(
                    filters.Regex(
                        "^(✏️ ویرایش مبلغ|🗑 لغو حواله|🔙 بازگشت به منوی عامل|📋 مشاهده همه حواله‌ها)$"
                    ),
                    manage_pending_action,
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    manage_pending_select_code,
                ),
            ],
            EDIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pending_amount)
            ],
            DELETE_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_pending_confirm)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", agent_menu),
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^❌ لغو$"), agent_menu),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu),
        ],
    )
    app.add_handler(manage_pending_conv)
    
    # ناوبری و گزارشات عامل
    app.add_handler(
        MessageHandler(
            filters.Regex("^💰 (موجودی و گزارش|بیلانس او راپور)$"),
            balance_and_report_menu,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex("^📊 (نمایش گزارش کامل|بشپړ راپور)$"),
            show_full_report,
        )
    )
    app.add_handler(MessageHandler(filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu))
    app.add_handler(MessageHandler(filters.Regex("^🎛 منوی عامل$"), agent_menu))

    # مدیریت موجودی
    app.add_handler(
        MessageHandler(
            filters.Regex("^💵 (مدیریت موجودی|د بیلانس مدیریت)$"),
            balance_management_menu,
        )
    )
    app.add_handler(MessageHandler(filters.Regex("^🔙 بازگشت$"), balance_management_menu))

    # افزایش/کاهش موجودی و ارز جدید
    increase_balance_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^➕ (افزایش موجودی|د بیلانس زیاتوالی)$"
                ),
                increase_balance_start,
            )
        ],
        states={
            INCREASE_BALANCE_CURRENCY: [
                MessageHandler(
                    filters.Regex("^(🇦🇫 AFN|🇺🇸 USD|🔙 بازگشت)$"),
                    increase_balance_currency,
                )
            ],
            INCREASE_BALANCE_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, increase_balance_amount
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🔙 بازگشت"), balance_management_menu),
        ],
    )
    app.add_handler(increase_balance_conv)

    decrease_balance_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^➖ (کاهش موجودی|د بیلانس کمول)$"
                ),
                decrease_balance_start,
            )
        ],
        states={
            DECREASE_BALANCE_CURRENCY: [
                MessageHandler(
                    filters.Regex("^(🇦🇫 AFN|🇺🇸 USD|🔙 بازگشت)$"),
                    decrease_balance_currency,
                )
            ],
            DECREASE_BALANCE_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, decrease_balance_amount
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🔙 بازگشت"), balance_management_menu),
        ],
    )
    app.add_handler(decrease_balance_conv)

    add_currency_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^💱 (اضافه کردن ارز جدید|نوی ارز اضافه کول)$"
                ),
                add_currency_start,
            )
        ],
        states={
            ADD_CURRENCY_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_currency_confirm)
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🔙 بازگشت"), balance_management_menu),
        ],
    )
    app.add_handler(add_currency_conv)

    app.add_handler(
        MessageHandler(
            filters.Regex("^📒 (مدیریت مصارف|د مصارف مدیریت)$"),
            agent_expenses_menu,
        )
    )

    staff_contract_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^👥 (ثبت کارمند و معاش ماهانه|د کارمند معاش ثبتول)$"
                ),
                staff_contract_start,
            )
        ],
        states={
            STAFF_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    staff_contract_name,
                )
            ],
            STAFF_CURRENCY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    staff_contract_currency,
                )
            ],
            STAFF_SALARY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    staff_contract_salary,
                )
            ],
            STAFF_START_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    staff_contract_start_date,
                )
            ],
            STAFF_PAY_DAY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    staff_contract_pay_day,
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی عامل|بېرته د عامل منو ته)$"),
                agent_menu,
            ),
        ],
    )
    app.add_handler(staff_contract_conv)

    fixed_expense_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    "^📌 (ثبت مصارف ثابت \\(غذا، برق، انترنت، قرطاسیه\\)|ثابت مصارف \\(غذا، برق، انټرنټ، قرطاسیه\\) ثبتول)$"
                ),
                fixed_expense_start,
            )
        ],
        states={
            FIXED_EXPENSE_CATEGORY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    fixed_expense_category,
                )
            ],
            FIXED_EXPENSE_CURRENCY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    fixed_expense_currency,
                )
            ],
            FIXED_EXPENSE_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    fixed_expense_amount,
                )
            ],
            FIXED_EXPENSE_START_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    fixed_expense_start_date,
                )
            ],
            FIXED_EXPENSE_PAY_DAY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    fixed_expense_pay_day,
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 (بازگشت به منوی عامل|بېرته د عامل منو ته)$"),
                agent_menu,
            ),
        ],
    )
    app.add_handler(fixed_expense_conv)

    if app.job_queue is not None:
        app.job_queue.run_repeating(
            send_daily_due_reminders,
            interval=24 * 60 * 60,
            first=60,
            name="daily_due_reminders",
        )

    app.add_handler(
        MessageHandler(
            filters.Regex("^📊 (گزارش مصارف|د مصارف راپور)$"),
            show_expenses_report,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^⏱"),
            show_expenses_report,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^📅 (گزارش تعهدات ۳۰ روز آینده|د راتلونکو ۳۰ ورځو تعهداتو راپور)$"),
            show_future_obligations,
        )
    )

    # خروج عامل
    app.add_handler(
        MessageHandler(
            filters.Regex("^🚪 (خروج از حساب عامل|د عامل له حساب څخه وتل)$"),
            agent_logout,
        )
    )

    # جستجوی پیشرفته عامل
    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🔍 (جستجوی پیشرفته|پرمختللې لټون)$"),
                search_advanced_start,
            )
        ],
        states={
            SEARCH_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, search_advanced_type
                )
            ],
            SEARCH_QUERY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, search_advanced_results
                )
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(
                filters.Regex("^🔙 بازگشت به منوی عامل$"), agent_menu
            ),
        ],
    )
    app.add_handler(search_conv)

    # ========= CALLBACK HANDLERS =========
    # هندلر دکمه‌های رسید و پرداخت سریع
    app.add_handler(CallbackQueryHandler(handle_receipt_callback, pattern="^get_receipt_"))
    app.add_handler(CallbackQueryHandler(handle_pay_fast_callback, pattern="^pay_fast_"))

    # هندلر لیست عامل‌ها
    app.add_handler(
        CallbackQueryHandler(
            handle_agents_callback, pattern="^(refresh_agents|back_to_menu)$"
        )
    )

    # هندلر دکمه بازگشت عمومی (برای تمام حالت‌ها)
    async def universal_back_handler(update, context):
        text = update.message.text.strip()
        
        if text in [
            "🔙 بازگشت",
            "🔙 بازگشت به منوی ادمین",
            "🔙 بازگشت به منوی عامل",
            "🔙 د عامل منو ته ستنیدل",
            "🔙 د ادمین مینو ته شاته",
        ]:
            # پاکسازی داده‌های موقت
            for key in ["current_step", "transfer_from_agent_id", "search_type", "login_agent_id"]:
                context.user_data.pop(key, None)
            
            role = context.user_data.get("role")
            if role == "admin":
                await admin_menu(update, context)
            elif role == "agent":
                await agent_menu(update, context)
            else:
                from bot.handlers.start import start
                await start(update, context)
            return
    
    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^(🔙 بازگشت|🔙 بازگشت به منوی ادمین|🔙 بازگشت به منوی عامل|🔙 د عامل منو ته ستنیدل|🔙 د ادمین مینو ته شاته)$"
            ),
            universal_back_handler,
        )
    )

    # ========= ADMIN SEARCH HANDLER - مخصوص جستجو =========
    # این هندلر فقط زمانی فعال می‌شود که در مرحله جستجو هستیم
    async def smart_search_handler(update, context):
        if context.user_data.get("search_type"):
            await admin_search_handler(update, context)
    
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            smart_search_handler
        )
    )

    # ========= COMMON =========
    app.add_handler(MessageHandler(filters.Regex("^🚪 خروج$"), exit_menu))

    # ========= ERRORS =========
    app.add_error_handler(global_error_handler)
