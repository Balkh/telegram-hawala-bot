import datetime

from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,  # اضافه شد
)
from telegram.ext import ConversationHandler
import logging

from bot.services.errors import global_error_handler
from bot.services.security import hash_password
from bot.services.database import get_db
from bot.services.auth import require_admin

logger = logging.getLogger(__name__)

# حالت‌های مکالمه
(
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
) = range(10)

# =======================
# 👑 منوی ادمین
# =======================


@require_admin
async def admin_menu(update, context):
    """منوی ادمین برای Messageهای معمولی"""
    keyboard = [
        ["➕ ایجاد عامل", "📋 لیست عامل‌ها"],
        ["⛔ فعال / غیرفعال عامل", "📊 گزارش مالی"],  # 🔴 دکمه گزارش مالی اضافه شد
        ["🚪 خروج"],
    ]

    await update.message.reply_text(
        "👑 منوی ادمین",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# @require_admin
# async def admin_menu_inline(update, context):
#     """منوی ادمین برای CallbackQuery (Inline)"""
#     keyboard = [
#         [
#             InlineKeyboardButton("➕ ایجاد عامل", callback_data="admin:create_agent"),
#             InlineKeyboardButton("📋 لیست عامل‌ها", callback_data="admin:list_agents"),
#         ],
#         [
#             InlineKeyboardButton("⛔ فعال/غیرفعال", callback_data="admin:toggle_agent"),
#             InlineKeyboardButton(
#                 "📊 گزارش مالی", callback_data="admin:financial_report"
#             ),
#         ],
#         [
#             InlineKeyboardButton("🚪 خروج", callback_data="admin:logout"),
#         ],
#     ]

#     text = "👑 *منوی ادمین*\n\nلطفاً یک گزینه را انتخاب کنید:"

#     # تشخیص نوع update
#     if update.callback_query:
#         message = update.callback_query.message
#         use_edit = True
#     else:
#         message = update.message
#         use_edit = False

#     if use_edit:
#         await message.edit_text(
#             text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
#         )
#     else:
#         await message.reply_text(
#             text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
#         )


@require_admin
async def admin_logout(update, context):
    """خروج ادمین"""
    user_id = update.effective_user.id

    # استفاده از تابع جدید
    from bot.services.database import unbind_admin_telegram_id

    unbind_admin_telegram_id(user_id)

    # پاک کردن context
    context.user_data.clear()

    await update.message.reply_text(
        "🚪 از حساب ادمین خارج شدید.", reply_markup=ReplyKeyboardRemove()
    )

    # برگشت به منوی اصلی
    from bot.handlers.start import start

    await start(update, context)


# =======================
# ➕ شروع ایجاد عامل
# =======================


@require_admin
async def create_agent_start(update, context):
    """شروع فرآیند ایجاد عامل توسط ادمین"""
    context.user_data.clear()
    await update.message.reply_text("🧑‍💼 نام عامل را وارد کنید:")
    return NAME


@require_admin
async def get_name(update, context):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🔐 پسورد عامل را وارد کنید:")
    return PASSWORD


@require_admin
async def get_password(update, context):
    password_text = update.message.text.strip()

    if len(password_text) < 4:
        await update.message.reply_text("❌ پسورد باید حداقل ۴ کاراکتر باشد")
        return PASSWORD

    # موقتاً ذخیره plain
    context.user_data["temp_password"] = password_text

    await update.message.reply_text("🔁 لطفاً پسورد را دوباره وارد کنید:")
    return CONFIRM_PASSWORD


@require_admin
async def confirm_password(update, context):
    confirm = update.message.text.strip()

    if confirm != context.user_data["temp_password"]:
        await update.message.reply_text(
            "❌ پسوردها یکسان نیست\n🔐 لطفاً دوباره پسورد را وارد کنید:"
        )
        return PASSWORD

    # حالا هش می‌کنیم
    context.user_data["password"] = hash_password(confirm)
    context.user_data.pop("temp_password", None)

    await update.message.reply_text("📍 ولایت عامل را وارد کنید:")
    return PROVINCE


@require_admin
async def get_province(update, context):
    context.user_data["province"] = update.message.text
    await update.message.reply_text("📞 شماره تماس عامل را وارد کنید:")
    return PHONE


@require_admin
async def get_phone(update, context):
    phone = update.message.text.strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM agents WHERE phone = ?", (phone,))
    exists = cur.fetchone()
    conn.close()

    if exists:
        await update.message.reply_text("❌ این شماره قبلاً ثبت شده\n🏠 /start")
        return ConversationHandler.END

    context.user_data["phone"] = phone
    await update.message.reply_text("🪪 شماره تذکره عامل را وارد کنید:")
    return TAZKIRA


@require_admin
async def get_tazkira(update, context):
    tazkira = update.message.text.strip()

    # 1️⃣ اعتبارسنجی اولیه (فقط عدد)
    if not tazkira.isdigit():
        await update.message.reply_text(
            "❌ شماره تذکره باید فقط عدد باشد\nلطفاً دوباره وارد کنید:"
        )
        return TAZKIRA

    # 2️⃣ چک تکراری بودن در دیتابیس
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM agents WHERE tazkira = ?", (tazkira,))
        exists = cur.fetchone()

        conn.close()

        if exists:
            await update.message.reply_text(
                "❌ این شماره تذکره قبلاً ثبت شده\n🏠 برای بازگشت /start"
            )
            return ConversationHandler.END

    except Exception:
        # خطای دیتابیس
        await update.message.reply_text("⚠️ خطا در بررسی تذکره، لطفاً دوباره تلاش کنید")
        return TAZKIRA

    # 3️⃣ ذخیره در context و رفتن به مرحله بعد
    context.user_data["tazkira"] = tazkira

    await update.message.reply_text("💰 بیلانس افتتاحیه را وارد کنید (عدد یا 0):")
    return BALANCE


@require_admin
async def get_balance(update, context):
    try:
        balance_text = update.message.text.strip()

        # بررسی اگر کاربر 0 وارد کرده
        if balance_text == "0":
            balance = 0.0
        else:
            balance = float(balance_text)

        if balance < 0:
            await update.message.reply_text("❌ مبلغ نمی‌تواند منفی باشد")
            return BALANCE

    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
        return BALANCE

    context.user_data["balance"] = balance

    keyboard = [["🇦🇫 AFN", "🇺🇸 USD"]]

    await update.message.reply_text(
        "💱 نوع ارز را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    return CURRENCY


@require_admin
async def get_currency(update, context):
    """دریافت ارز از کاربر"""
    message_text = update.message.text.strip().upper()

    if "AFN" in message_text:
        currency = "AFN"
    elif "USD" in message_text:
        currency = "USD"
    else:
        await update.message.reply_text("❌ فقط از دکمه‌ها استفاده کنید")
        return CURRENCY

    # ✅ ذخیره ارز در context
    context.user_data["currency"] = currency

    # نمایش خلاصه
    summary = (
        "🧾 خلاصه اطلاعات عامل:\n\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"📍 ولایت: {context.user_data['province']}\n"
        f"📞 تماس: {context.user_data['phone']}\n"
        f"🪪 تذکره: {context.user_data['tazkira']}\n"
        f"💰 بیلانس: {context.user_data['balance']} {currency}\n\n"
        "آیا تأیید می‌کنید؟"
    )

    keyboard = [["✅ تأیید", "❌ لغو"]]

    await update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return CONFIRM_AGENT


@require_admin
async def confirm_agent(update, context):
    text = update.message.text.strip()

    if text == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ عملیات لغو شد", reply_markup=ReplyKeyboardRemove()
        )
        # برگشت به منوی اصلی
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END

    if text != "✅ تأیید":
        await update.message.reply_text(
            "❗ عملیات لغو شد. لطفاً مجدداً اقدام کنید",
            reply_markup=ReplyKeyboardRemove(),
        )
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END

    # اگر تأیید کرد
    try:
        conn = get_db()
        cur = conn.cursor()

        # ثبت عامل در جدول agents
        cur.execute(
            """
            INSERT INTO agents (name, province, phone, tazkira, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                context.user_data["name"],
                context.user_data["province"],
                context.user_data["phone"],
                context.user_data["tazkira"],
                context.user_data["password"],
            ),
        )

        agent_id = cur.lastrowid

        # ثبت موجودی در جدول balances
        cur.execute(
            """
            INSERT INTO balances (agent_id, currency, balance)
            VALUES (?, ?, ?)
            """,
            (
                agent_id,
                context.user_data["currency"],
                context.user_data["balance"],
            ),
        )

        conn.commit()
        conn.close()

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ عامل با موفقیت ثبت شد\n🆔 کد عامل: {agent_id}",
            reply_markup=ReplyKeyboardRemove(),
        )
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Error in confirm_agent")
        await update.message.reply_text(
            "❌ خطا هنگام ثبت عامل", reply_markup=ReplyKeyboardRemove()
        )
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END


@require_admin
async def financial_report(update, context):
    """گزارش مالی ساده"""

    conn = get_db()
    cur = conn.cursor()

    # آمار عامل‌ها
    cur.execute("SELECT COUNT(*) FROM agents")
    total_agents = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]

    # موجودی‌ها
    cur.execute(
        """
        SELECT 
            currency,
            SUM(balance) as total_balance,
            COUNT(*) as account_count
        FROM balances 
        GROUP BY currency
    """
    )

    balances = cur.fetchall()

    conn.close()

    # ساخت گزارش
    report = "📊 *گزارش مالی سیستم*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    report += f"👥 *عامل‌ها:*\n"
    report += f"   کل عامل‌ها: {total_agents} نفر\n"
    report += f"   فعال: {active_agents} نفر\n"
    report += f"   غیرفعال: {total_agents - active_agents} نفر\n\n"

    report += f"💰 *موجودی‌ها:*\n"
    if balances:
        for currency, total, count in balances:
            report += f"   {currency}: {total:,.0f} ({count} حساب)\n"
    else:
        report += "   هیچ موجودی ثبت نشده\n\n"

    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    report += f"📅 تاریخ: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M')}"

    await update.message.reply_text(report, parse_mode="Markdown")


@require_admin
async def list_agents(update, context):
    """نمایش لیست عامل‌ها - پشتیبانی از Message و CallbackQuery"""

    # تشخیص نوع update
    if update.callback_query:
        message = update.callback_query.message
        is_callback = True
    else:
        message = update.message
        is_callback = False

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT a.id, a.name, a.province, a.phone, a.is_active,
               b.balance, b.currency
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        ORDER BY a.id
        """
    )

    agents = cur.fetchall()
    conn.close()

    if not agents:
        if is_callback:
            await message.edit_text("📭 هنوز هیچ عاملی ثبت نشده است")
        else:
            await message.reply_text("📭 هنوز هیچ عاملی ثبت نشده است")
        return

    # ساخت لیست
    lines = []
    active_count = 0

    for agent in agents:
        agent_id, name, province, phone, is_active, balance, currency = agent

        if is_active:
            active_count += 1

        status = "🟢" if is_active else "🔴"
        balance_display = f"{balance:,.0f}" if balance is not None else "۰"
        currency_display = currency if currency else "افغانی"

        line = (
            f"{status} `#{agent_id:03d}` | **{name}**\n"
            f"   📍 {province} | 📞 `{phone}`\n"
            f"   💰 {balance_display} {currency_display}"
        )
        lines.append(line)

    # سرتیتر
    header = "📋 *لیست عامل‌های حواله*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # محاسبات
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    inactive_count = len(agents) - active_count

    # پاورقی
    footer = (
        f"\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📊 *آمار:* {len(agents)} عامل | "
        f"🟢 {active_count} فعال | "
        f"🔴 {inactive_count} غیرفعال\n"
        f"🕒 آخرین بروزرسانی: {current_time}"
    )

    full_text = header + "\n\n".join(lines) + footer

    # دکمه‌ها
    keyboard = [
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh_agents"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_menu"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # ارسال/ویرایش
    if is_callback:
        await message.edit_text(
            full_text, parse_mode="Markdown", reply_markup=reply_markup
        )
    else:
        await message.reply_text(
            full_text, parse_mode="Markdown", reply_markup=reply_markup
        )


@require_admin
async def toggle_agent_start(update, context):
    await update.message.reply_text("🆔 شناسه عامل را وارد کنید:")
    return TOGGLE_AGENT


@require_admin
async def toggle_agent_by_id(update, context):
    try:
        agent_id = int(update.message.text.strip())

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT is_active FROM agents WHERE id = ?", (agent_id,))
        row = cur.fetchone()

        if not row:
            await update.message.reply_text("❌ عاملی با این شناسه پیدا نشد")
            conn.close()
            return ConversationHandler.END

        new_status = 0 if row[0] == 1 else 1

        cur.execute(
            "UPDATE agents SET is_active = ? WHERE id = ?",
            (new_status, agent_id),
        )

        conn.commit()
        conn.close()

        status_text = "✅ فعال شد" if new_status else "⛔ غیرفعال شد"
        await update.message.reply_text(
            f"🔄 وضعیت عامل با شناسه {agent_id} {status_text}"
        )

        # برگشت به منوی اصلی
        from bot.handlers.start import start

        await start(update, context)

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ شناسه باید عدد باشد")
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Error in toggle_agent_by_id")
        await global_error_handler(update, context, "❌ خطا در تغییر وضعیت عامل")
        from bot.handlers.start import start

        await start(update, context)
        return ConversationHandler.END


async def handle_agents_callback(update, context):
    """مدیریت کلیک روی دکمه‌های لیست عامل‌ها"""

    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "refresh_agents":
        await query.edit_message_text("🔄 در حال بروزرسانی لیست...", reply_markup=None)
        await list_agents(update, context)

    elif data == "back_to_menu":
        # 🔴 تغییر مهم: به admin_menu برمی‌گردیم (نه admin_menu_inline)
        await query.edit_message_text(
            "🏠 در حال بازگشت به منوی اصلی...", reply_markup=None
        )

        # ساخت update جعلی برای admin_menu
        from telegram import Update

        fake_update = Update(update_id=update.update_id, message=query.message)

        await admin_menu(fake_update, context)  # ✅ به منوی اصلی


# async def handle_admin_callback(update, context):
#     query = update.callback_query
#     await query.answer()

#     data = query.data

#     logger.info(f"Admin callback: {data}")

#     # حذف پیشوند "admin:"
#     action = data.replace("admin:", "")

#     if action == "list_agents":
#         await query.edit_message_text(
#             "📋 در حال بارگذاری لیست عامل‌ها...", reply_markup=None
#         )
#         await list_agents(update, context)

#     elif action == "create_agent":
#         # هدایت به ایجاد عامل
#         await query.edit_message_text(
#             "➕ *ایجاد عامل جدید*\n\n"
#             "برای ایجاد عامل، لطفاً از منوی اصلی ادمین استفاده کنید:\n"
#             "1. دستور /start را بزنید\n"
#             "2. منوی ادمین را انتخاب کنید\n"
#             "3. گزینه '➕ ایجاد عامل' را انتخاب کنید",
#             parse_mode="Markdown",
#             reply_markup=None,
#         )

#     elif action == "toggle_agent":
#         await query.edit_message_text("⛔ در حال انتقال...", reply_markup=None)

#         # ساخت update جعلی با message برای toggle_agent_start
#         fake_update = Update(update_id=update.update_id, message=query.message)

#         await toggle_agent_start(fake_update, context)

#     elif action == "financial_report":
#         # گزارش مالی ساده
#         conn = get_db()
#         cur = conn.cursor()

#         cur.execute("SELECT COUNT(*) FROM agents")
#         agent_count = cur.fetchone()[0]

#         cur.execute("SELECT SUM(balance) FROM balances")
#         total_balance = cur.fetchone()[0] or 0

#         cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
#         active_agents = cur.fetchone()[0]

#         conn.close()

#         await query.edit_message_text(
#             f"📊 *گزارش مالی*\n\n"
#             f"📈 آمار کلی سیستم:\n"
#             f"• تعداد عامل‌ها: {agent_count} نفر\n"
#             f"• عامل‌های فعال: {active_agents} نفر\n"
#             f"• مجموع موجودی: {total_balance:,.0f} افغانی\n\n"
#             f"🔄 گزارش‌های پیشرفته به زودی اضافه می‌شوند.",
#             parse_mode="Markdown",
#             reply_markup=InlineKeyboardMarkup(
#                 [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin:back")]]
#             ),
#         )

#     elif action == "logout":
#         await query.edit_message_text("🚪 در حال خروج...", reply_markup=None)

#         # ساخت update جعلی برای exit_menu
#         fake_update = Update(update_id=update.update_id, message=query.message)

#         from bot.handlers.common import exit_menu

#         await exit_menu(fake_update, context)

#     elif action == "back":
#         await admin_menu_inline(update, context)
