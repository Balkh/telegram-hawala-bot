import datetime
import pandas as pd
import io
from datetime import datetime as dt

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
    ADMIN_SEARCH_TX,
) = range(11)

# =======================
# 👑 منوی ادمین
# =======================


@require_admin
async def admin_menu(update, context):
    """منوی ادمین برای Messageهای معمولی"""
    keyboard = [
        ["➕ ایجاد عامل", "📋 لیست عامل‌ها"],
        ["📥 درخواست‌های شارژ", "🔍 جستجوی عامل‌ها"],
        ["🔎 جستجوی حواله‌ها", "⛔ فعال / غیرفعال عامل"],
        ["📊 گزارش مالی", "📥 دانلود گزارش اکسل"],
        ["📈 داشبورد آماری", "💸 پنل سود ادمین"],
        ["💰 مدیریت مالی مرکزی"],
        ["🚪 خروج"],
    ]

    await update.message.reply_text(
        "👑 *منوی مدیریت ادمین*\n\nلطفاً یک گزینه انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


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


# تابع ایجاد عامل ساده و کارآمد
@require_admin
async def create_agent_start(update, context):
    """شروع فرآیند ایجاد عامل توسط ادمین"""
    try:
        # پاک کردن context
        context.user_data.clear()
        
        # شروع فرآیند ایجاد عامل
        await update.message.reply_text(
            "🧑‍💼 نام عامل را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
        )
        
        return NAME
        
    except Exception as e:
        logger.exception("Error in create_agent_start")
        await update.message.reply_text(f"❌ خطا در شروع ایجاد عامل: {str(e)}")
        return ConversationHandler.END





@require_admin
async def get_name(update, context):
    try:
        text = update.message.text.strip()
        if text == "❌ لغو":
            context.user_data.clear()
            await update.message.reply_text("❌ عملیات لغو شد")
            await admin_menu(update, context)
            return ConversationHandler.END

        context.user_data["name"] = text
        await update.message.reply_text(
            "🔐 پسورد عامل را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
        )
        return PASSWORD
    except Exception as e:
        logger.exception("Error in get_name")
        await update.message.reply_text(f"❌ خطا در دریافت نام: {str(e)}")
        return ConversationHandler.END


@require_admin
async def get_password(update, context):
    password_text = update.message.text.strip()
    
    if password_text == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

    if len(password_text) < 4:
        await update.message.reply_text("❌ پسورد باید حداقل ۴ کاراکتر باشد")
        return PASSWORD

    # موقتاً ذخیره plain
    context.user_data["temp_password"] = password_text

    await update.message.reply_text(
        "🔁 لطفاً پسورد را دوباره وارد کنید:",
        reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    )
    return CONFIRM_PASSWORD


@require_admin
async def confirm_password(update, context):
    confirm = update.message.text.strip()
    
    if confirm == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

    if confirm != context.user_data["temp_password"]:
        await update.message.reply_text(
            "❌ پسوردها یکسان نیست\n🔐 لطفاً دوباره پسورد را وارد کنید:"
        )
        return PASSWORD

    # حالا هش می‌کنیم
    context.user_data["password"] = hash_password(confirm)
    context.user_data.pop("temp_password", None)

    await update.message.reply_text(
        "📍 ولایت عامل را وارد کنید:",
        reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    )
    return PROVINCE


@require_admin
async def get_province(update, context):
    text = update.message.text.strip()
    if text == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

    context.user_data["province"] = text
    await update.message.reply_text(
        "📞 شماره تماس عامل را وارد کنید:",
        reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    )
    return PHONE


@require_admin
async def get_phone(update, context):
    phone = update.message.text.strip()
    
    if phone == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM agents WHERE phone = ?", (phone,))
    exists = cur.fetchone()
    conn.close()

    if exists:
        await update.message.reply_text("❌ این شماره قبلاً ثبت شده\n🏠 /start")
        return ConversationHandler.END

    context.user_data["phone"] = phone
    await update.message.reply_text(
        "🪪 شماره تذکره عامل را وارد کنید:",
        reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    )
    return TAZKIRA


@require_admin
async def get_tazkira(update, context):
    tazkira = update.message.text.strip()
    
    if tazkira == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

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

    await update.message.reply_text(
        "💰 بیلانس افتتاحیه را وارد کنید (عدد یا 0):",
        reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
    )
    return BALANCE


@require_admin
async def get_balance(update, context):
    try:
        balance_text = update.message.text.strip()
        
        if balance_text == "❌ لغو":
            context.user_data.clear()
            await update.message.reply_text("❌ عملیات لغو شد")
            await admin_menu(update, context)
            return ConversationHandler.END

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

    keyboard = [["🇦🇫 AFN", "🇺🇸 USD"], ["❌ لغو"]]

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
    
    if message_text == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text("❌ عملیات لغو شد")
        await admin_menu(update, context)
        return ConversationHandler.END

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
        # دیباگ: بررسی مقادیر context
        required_fields = ["name", "province", "phone", "tazkira", "password", "currency", "balance"]
        missing_fields = []
        
        for field in required_fields:
            if field not in context.user_data:
                missing_fields.append(field)
        
        if missing_fields:
            await update.message.reply_text(
                f"❌ خطا: اطلاعات ناقص\n"
                f"فیلدهای موجود: {list(context.user_data.keys())}\n"
                f"فیلدهای ناموجود: {missing_fields}"
            )
            return ConversationHandler.END
        
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
            f"❌ خطا در ثبت عامل: {str(e)}\n"
            f"لطفاً دوباره تلاش کنید یا با ادمین سیستم تماس بگیرید.",
            reply_markup=ReplyKeyboardRemove(),
        )
        
        # پاک کردن context در صورت خطا
        context.user_data.clear()
        
        from bot.handlers.start import start
        await start(update, context)
        return ConversationHandler.END


@require_admin
async def financial_report(update, context):
    """گزارش مالی پیشرفته برای ادمین"""
    await update.message.reply_text("📊 در حال آماده‌سازی گزارش مالی...")

    conn = get_db()
    cur = conn.cursor()

    # آمار کل سیستم
    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM agents")
    total_agents = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM transactions 
        WHERE status = 'pending'
    """
    )
    pending_transactions = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM transactions 
        WHERE status = 'completed'
    """
    )
    completed_transactions = cur.fetchone()[0]

    cur.execute(
        """
        SELECT SUM(amount) FROM transactions 
        WHERE status != 'cancelled'
    """
    )
    total_amount = cur.fetchone()[0] or 0

    cur.execute(
        """
        SELECT SUM(commission) FROM transactions 
        WHERE status != 'cancelled'
    """
    )
    total_commission = cur.fetchone()[0] or 0

    # آمار بر اساس ولایت
    cur.execute(
        """
        SELECT a.province, COUNT(*) as agent_count, 
               SUM(b.balance) as total_balance
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1
        GROUP BY a.province
        ORDER BY agent_count DESC
    """
    )
    province_stats = cur.fetchall()

    # برترین عامل‌ها
    cur.execute(
        """
        SELECT a.name, a.province, COUNT(t.id) as transaction_count,
               SUM(t.commission) as total_commission
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        WHERE a.is_active = 1
        GROUP BY a.id, a.name, a.province
        ORDER BY transaction_count DESC
        LIMIT 5
    """
    )
    top_agents = cur.fetchall()

    conn.close()

    # ساخت گزارش
    report = "📊 *گزارش مالی پیشرفته سیستم*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # آمار کلی
    report += "📈 *آمار کلی سیستم:*\n"
    report += f"   👥 عامل‌ها: {active_agents} فعال از {total_agents} کل\n"
    report += f"   📦 حواله‌ها: {total_transactions} کل\n"
    report += f"   ⏳ در انتظار: {pending_transactions}\n"
    report += f"   ✅ تکمیل شده: {completed_transactions}\n"
    report += f"   💰 مجموع مبلغ: {total_amount:,.0f} افغانی\n"
    report += f"   💸 مجموع کارمزد: {total_commission:,.0f} افغانی\n\n"

    # آمار ولایت‌ها
    if province_stats:
        report += "🗺️ *آمار بر اساس ولایت:*\n"
        for province, count, balance in province_stats[:5]:
            balance_text = f"{balance:,.0f}" if balance else "۰"
            report += f"   📍 {province}: {count} عامل، موجودی {balance_text} افغانی\n"
        report += "\n"

    # برترین عامل‌ها
    if top_agents:
        report += "🏆 *برترین عامل‌ها (بر اساس تعداد حواله):*\n"
        for i, (name, province, count, commission) in enumerate(top_agents, 1):
            commission_text = f"{commission:,.0f}" if commission else "۰"
            report += f"   {i}. {name} ({province}) - {count} حواله، {commission_text} افغانی کارمزد\n"
        report += "\n"

    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    report += f"📅 تاریخ: {dt.now().strftime('%Y/%m/%d %H:%M')}"

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

    # دریافت اطلاعات پایه عامل‌ها
    cur.execute(
        """
        SELECT id, name, province, phone, is_active
        FROM agents
        ORDER BY id
        """
    )
    agents_rows = cur.fetchall()
    
    # دریافت تمام موجودی‌ها
    cur.execute(
        """
        SELECT agent_id, balance, currency
        FROM balances
        """
    )
    balances_rows = cur.fetchall()
    conn.close()

    if not agents_rows:
        if is_callback:
            await message.edit_text("📭 هنوز هیچ عاملی ثبت نشده است")
        else:
            await message.reply_text("📭 هنوز هیچ عاملی ثبت نشده است")
        return

    # سازماندهی موجودی‌ها بر اساس ID عامل
    agent_balances = {}
    for b_agent_id, balance, currency in balances_rows:
        if b_agent_id not in agent_balances:
            agent_balances[b_agent_id] = []
        agent_balances[b_agent_id].append(f"{balance:,.0f} {currency}")

    # ساخت لیست
    lines = []
    active_count = 0

    for agent in agents_rows:
        agent_id, name, province, phone, is_active = agent

        if is_active:
            active_count += 1

        status = "🟢" if is_active else "🔴"
        
        # نمایش موجودی‌ها به صورت تجمیع شده
        balances_list = agent_balances.get(agent_id, ["۰ افغانی"])
        balances_display = " | ".join(balances_list)

        line = (
            f"{status} `#{agent_id:03d}` | **{name}**\n"
            f"   📍 {province} | 📞 `{phone}`\n"
            f"   💰 {balances_display}"
        )
        lines.append(line)

    # سرتیتر
    header = "📋 *لیست عامل‌های حواله*\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # محاسبات
    current_time = dt.now().strftime("%H:%M:%S")
    inactive_count = len(agents_rows) - active_count

    # پاورقی
    footer = (
        f"\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📊 *آمار:* {len(agents_rows)} عامل | "
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
    """شروع فرآیند فعال/غیرفعال عامل"""
    try:
        # پاک کردن context برای شروع جدید
        context.user_data.clear()
        
        await update.message.reply_text(
            "🆔 شناسه عامل را برای فعال/غیرفعال کردن وارد کنید:\n"
            "(برای انصراف ❌ لغو را بزنید)",
            reply_markup=ReplyKeyboardMarkup([["❌ لغو"]], resize_keyboard=True)
        )
        
        return TOGGLE_AGENT
        
    except Exception as e:
        logger.exception("Error in toggle_agent_start")
        await update.message.reply_text(f"❌ خطا در شروع فعال/غیرفعال: {str(e)}")
        return ConversationHandler.END


@require_admin
async def toggle_agent_by_id(update, context):
    try:
        text = update.message.text.strip()
        
        if text == "❌ لغو":
            context.user_data.clear()
            await update.message.reply_text("❌ عملیات لغو شد")
            await admin_menu(update, context)
            return ConversationHandler.END
            
        agent_id = int(text)

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


@require_admin
async def list_balance_requests(update, context):
    """نمایش لیست درخواست‌های شارژ در انتظار"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute(
        """
        SELECT 
            br.id, br.agent_id, br.amount, br.currency, br.receipt_photo_id, br.created_at,
            a.name as agent_name
        FROM balance_requests br
        JOIN agents a ON br.agent_id = a.id
        WHERE br.status = 'pending'
        ORDER BY br.created_at ASC
        """
    )
    requests = cur.fetchall()
    conn.close()
    
    if not requests:
        await update.message.reply_text("📥 هیچ درخواست شارژ در انتظاری وجود ندارد.")
        return

    await update.message.reply_text(f"📥 تعداد {len(requests)} درخواست در انتظار بررسی است:")

    for req in requests:
        req_id, agent_id, amount, currency, photo_id, created_at, agent_name = req
        
        caption = (
            f"💰 *درخواست شارژ حساب*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👤 *عامل:* {agent_name} (ID: {agent_id})\n"
            f"💰 *مبلغ:* {amount:,.0f} {currency}\n"
            f"📅 *تاریخ:* {created_at[:16]}\n"
            f"🆔 *شناسه درخواست:* `{req_id}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "لطفاً با استفاده از دکمه‌های زیر تعیین تکلیف کنید:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"approve_br_{req_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_br_{req_id}")
            ]
        ]
        
        try:
            await update.message.reply_photo(
                photo=photo_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error sending request {req_id}: {e}")
            await update.message.reply_text(
                f"⚠️ خطا در نمایش عکس درخواست `{req_id}`. اطلاعات متنی:\n{caption}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


@require_admin
async def process_balance_request_callback(update, context):
    """پردازش کلیک روی تأیید یا رد درخواست شارژ"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not (data.startswith("approve_br_") or data.startswith("reject_br_")):
        return

    action = "approved" if data.startswith("approve_br_") else "rejected"
    req_id = int(data.split("_")[-1])
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # دریافت اطلاعات درخواست
        cur.execute(
            "SELECT agent_id, amount, currency, status FROM balance_requests WHERE id = ?",
            (req_id,)
        )
        request = cur.fetchone()
        
        if not request:
            await query.edit_message_caption("❌ درخواست یافت نشد.")
            conn.close()
            return
            
        agent_id, amount, currency, status = request
        
        if status != "pending":
            await query.edit_message_caption(f"⚠️ این درخواست قبلاً `{status}` شده است.")
            conn.close()
            return

        if action == "approved":
            # ۱. افزایش موجودی عامل
            # چک موجود بودن رکورد
            cur.execute(
                "SELECT balance FROM balances WHERE agent_id = ? AND currency = ?",
                (agent_id, currency)
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE balances SET balance = balance + ? WHERE agent_id = ? AND currency = ?",
                    (amount, agent_id, currency)
                )
            else:
                cur.execute(
                    "INSERT INTO balances (agent_id, currency, balance) VALUES (?, ?, ?)",
                    (agent_id, currency, amount)
                )
            
            # ۲. آپدیت وضعیت درخواست
            cur.execute(
                "UPDATE balance_requests SET status = 'approved', processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (req_id,)
            )
            
            status_msg = "✅ تأیید شد"
            notif_to_agent = (
                "💰 *اطلاعیه افزایش موجودی*\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                "✅ درخواست شارژ حساب شما تأیید شد.\n\n"
                f"💵 مبلغ: *{amount:,.0f} {currency}*\n"
                "📈 موجودی شما با موفقیت بروزرسانی شد.\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                "🙏 از شکیبایی شما سپاسگزاریم."
            )
        else:
            # فقط آپدیت وضعیت
            cur.execute(
                "UPDATE balance_requests SET status = 'rejected', processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (req_id,)
            )
            status_msg = "❌ رد شد"
            notif_to_agent = (
                "⚠️ *اطلاعیه درخواست شارژ*\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                "❌ درخواست شارژ حساب شما رد شد.\n\n"
                f"💵 مبلغ: {amount:,.0f} {currency}\n\n"
                "💡 دلایل احتمالی:\n"
                "۱. تصویر فیش ناخوانا است.\n"
                "۲. مبلغ وارد شده با فیش مطابقت ندارد.\n\n"
                "📞 برای اطلاعات بیشتر با مدیریت تماس بگیرید.\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
            )

        conn.commit()
        
        # اطلاع‌رسانی به عامل
        cur.execute("SELECT telegram_id FROM agents WHERE id = ?", (agent_id,))
        agent_tg = cur.fetchone()[0]
        if agent_tg:
            try:
                await context.bot.send_message(
                    chat_id=agent_tg,
                    text=notif_to_agent,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify agent {agent_id}: {e}")

        await query.edit_message_caption(f"{query.message.caption}\n\n🏁 *نتیجه:* {status_msg}", parse_mode="Markdown")

    except Exception as e:
        logger.exception("Error processing balance request")
        await query.edit_message_caption(f"{query.message.caption}\n\n❌ خطا در پردازش: {str(e)}")
    finally:
        conn.close()

@require_admin
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

        fake_update = Update(update_id=update.update_id, message=query.message)

        await admin_menu(fake_update, context)  # ✅ به منوی اصلی


# =======================
# 🔍 جستجوی پیشرفته عامل‌ها
# =======================


@require_admin
async def search_agents(update, context):
    """جستجوی پیشرفته عامل‌ها"""
    await update.message.reply_text(
        "🔍 *جستجوی عامل‌ها*\n\n"
        "لطفاً نوع جستجو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["👤 جستجو بر اساس نام"],
            ["📍 جستجو بر اساس ولایت"],
            ["📞 جستجو بر اساس تلفن"],
            ["🟢 فقط عامل‌های فعال"],
            ["🔴 فقط عامل‌های غیرفعال"],
            ["🔙 بازگشت به منوی ادمین"]
        ], resize_keyboard=True)
    )


# =======================
# 🔍 جستجوی حواله‌ها (ادمین)
# =======================

@require_admin
async def admin_search_tx_start(update, context):
    """شروع جستجوی حواله‌ها توسط ادمین"""
    await update.message.reply_text(
        "🔍 *جستجوی حواله‌ها (ادمین)*\n\n"
        "لطفاً بخشی از *نام گیرنده* یا *کد حواله* را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت به منوی ادمین"]], resize_keyboard=True)
    )
    return ADMIN_SEARCH_TX


@require_admin
async def admin_search_tx_process(update, context):
    """پردازش جستجوی حواله‌ها و نمایش نتایج"""
    query = update.message.text.strip()
    
    if query == "🔙 بازگشت به منوی ادمین":
        await admin_menu(update, context)
        return ConversationHandler.END
        
    conn = get_db()
    cur = conn.cursor()
    
    # جستجو در کل سیستم (بدون محدودیت عامل)
    cur.execute("""
        SELECT t.transaction_code, t.receiver_name, t.amount, t.currency, t.status, t.created_at,
               a_sender.name as sender_agent, a_receiver.name as receiver_agent
        FROM transactions t
        JOIN agents a_sender ON t.agent_id = a_sender.id
        JOIN agents a_receiver ON t.receiver_agent_id = a_receiver.id
        WHERE t.transaction_code LIKE ? OR t.receiver_name LIKE ? OR t.sender_name LIKE ?
        ORDER BY t.created_at DESC
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    
    results = cur.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text(
            f"❌ هیچ حواله‌ای برای عبارت '{query}' یافت نشد.",
            reply_markup=ReplyKeyboardMarkup([["🔍 جستجوی جدید"], ["🔙 بازگشت به منوی ادمین"]], resize_keyboard=True)
        )
        return ADMIN_SEARCH_TX

    text = f"🔎 *نتایج جستجو برای: {query}*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    keyboard = []
    for code, name, amount, currency, status, created_at, s_agent, r_agent in results:
        status_emoji = "🟢" if status == 'completed' else "🟡" if status == 'pending' else "🔴"
        text += f"{status_emoji} کد: `{code}`\n"
        text += f"👤 گیرنده: {name}\n"
        text += f"💰 {amount:,.0f} {currency}\n"
        text += f"🏢 از: {s_agent} ➔ به: {r_agent}\n"
        text += f"📅 {created_at[:16]}\n"
        text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        # دکمه دریافت رسید برای ادمین
        keyboard.append([InlineKeyboardButton(f"🧾 رسید تصویری {code}", callback_data=f"get_receipt_{code}")])
    
    await update.message.reply_text(
        text, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # نمایش منوی جستجوی جدید
    await update.message.reply_text(
        "میتوانید جستجوی دیگری انجام دهید یا به منو برگردید:",
        reply_markup=ReplyKeyboardMarkup([["🔍 جستجوی جدید"], ["🔙 بازگشت به منوی ادمین"]], resize_keyboard=True)
    )
    return ADMIN_SEARCH_TX


@require_admin
async def search_by_name(update, context):
    """جستجو بر اساس نام عامل"""
    await update.message.reply_text(
        "👤 *جستجو بر اساس نام*\n\n"
        "نام یا بخشی از نام عامل را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    context.user_data["search_type"] = "name"


@require_admin
async def search_by_province(update, context):
    """جستجو بر اساس ولایت"""
    await update.message.reply_text(
        "📍 *جستجو بر اساس ولایت*\n\n"
        "نام ولایت را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    context.user_data["search_type"] = "province"


@require_admin
async def search_by_phone(update, context):
    """جستجو بر اساس شماره تلفن"""
    await update.message.reply_text(
        "📞 *جستجو بر اساس تلفن*\n\n"
        "شماره تلفن یا بخشی از آن را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    context.user_data["search_type"] = "phone"


@require_admin
async def execute_search(update, context):
    """اجرای جستجوی عامل‌ها"""
    search_term = update.message.text.strip()
    search_type = context.user_data.get("search_type")
    
    if search_term == "🔙 بازگشت":
        await search_agents(update, context)
        return
    
    if not search_type:
        await search_agents(update, context)
        return
    
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT a.id, a.name, a.province, a.phone, a.is_active,
               b.balance, b.currency,
               COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        LEFT JOIN transactions t ON a.id = t.agent_id
    """
    params = []
    
    if search_type == "name":
        query += " WHERE a.name LIKE ?"
        params.append(f"%{search_term}%")
    elif search_type == "province":
        query += " WHERE a.province LIKE ?"
        params.append(f"%{search_term}%")
    elif search_type == "phone":
        query += " WHERE a.phone LIKE ?"
        params.append(f"%{search_term}%")
    
    query += " GROUP BY a.id ORDER BY a.name"
    
    cur.execute(query, params)
    results = cur.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text(
            f"❌ هیچ عاملی با این مشخصات پیدا نشد:\n"
            f"🔍 جستجو: {search_term}",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return
    
    # نمایش نتایج
    report = f"🔍 *نتایج جستجو ({len(results)} عامل پیدا شد)*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    for agent_id, name, province, phone, is_active, balance, currency, transaction_count in results:
        status = "🟢" if is_active else "🔴"
        balance_display = f"{balance:,.0f}" if balance else "۰"
        currency_display = currency if currency else "افغانی"
        
        report += f"{status} `#{agent_id:03d}` | **{name}**\n"
        report += f"   📍 {province} | 📞 `{phone}`\n"
        report += f"   💰 {balance_display} {currency_display} | 📦 {transaction_count} حواله\n\n"
    
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["🔍 جستجوی جدید", "🔙 بازگشت به منوی ادمین"]
        ], resize_keyboard=True)
    )
    
    context.user_data.pop("search_type", None)


# تابع جستجوی ساده برای ادمین
async def admin_search_handler(update, context):
    """جستجوی عامل‌ها برای ادمین"""
    search_term = update.message.text.strip()
    search_type = context.user_data.get("search_type")
    
    # اگر در حالت جستجو نیستیم، برگرد
    if not search_type:
        return
    
    if search_term == "🔙 بازگشت":
        await search_agents(update, context)
        return
    
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT a.id, a.name, a.province, a.phone, a.is_active,
               b.balance, b.currency,
               COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        LEFT JOIN transactions t ON a.id = t.agent_id
    """
    params = []
    
    if search_type == "name":
        query += " WHERE a.name LIKE ?"
        params.append(f"%{search_term}%")
    elif search_type == "province":
        query += " WHERE a.province LIKE ?"
        params.append(f"%{search_term}%")
    elif search_type == "phone":
        query += " WHERE a.phone LIKE ?"
        params.append(f"%{search_term}%")
    
    query += " GROUP BY a.id ORDER BY a.name"
    
    try:
        cur.execute(query, params)
        results = cur.fetchall()
        conn.close()
        
        if not results:
            await update.message.reply_text(
                f"❌ هیچ عاملی با این مشخصات پیدا نشد:\n"
                f"🔍 جستجو: {search_term}\n"
                f"📝 نوع جستجو: {search_type}",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
            return
        
        # نمایش نتایج
        report = f"🔍 *نتایج جستجو ({len(results)} عامل پیدا شد)*\n"
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        for agent_id, name, province, phone, is_active, balance, currency, transaction_count in results:
            status = "🟢" if is_active else "🔴"
            balance_display = f"{balance:,.0f}" if balance else "۰"
            currency_display = currency if currency else "افغانی"
            
            report += f"{status} `#{agent_id:03d}` | **{name}**\n"
            report += f"   📍 {province} | 📞 `{phone}`\n"
            report += f"   💰 {balance_display} {currency_display} | 📦 {transaction_count} حواله\n\n"
        
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        
        await update.message.reply_text(
            report,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([
                ["🔍 جستجوی جدید", "🔙 بازگشت به منوی ادمین"]
            ], resize_keyboard=True)
        )
        
        context.user_data.pop("search_type", None)
        
    except Exception as e:
        logger.exception("Error in admin search")
        await update.message.reply_text("❌ خطا در جستجو. لطفاً دوباره تلاش کنید.")
        context.user_data.pop("search_type", None)


@require_admin
async def filter_active_agents(update, context):
    """فیلتر عامل‌های فعال"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.id, a.name, a.province, a.phone,
               b.balance, b.currency,
               COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        LEFT JOIN transactions t ON a.id = t.agent_id
        WHERE a.is_active = 1
        GROUP BY a.id
        ORDER BY a.name
    """)
    results = cur.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("❌ هیچ عامل فعالی وجود ندارد")
        return
    
    report = f"🟢 *عامل‌های فعال ({len(results)} عامل)*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    for agent_id, name, province, phone, balance, currency, transaction_count in results:
        balance_display = f"{balance:,.0f}" if balance else "۰"
        currency_display = currency if currency else "افغانی"
        
        report += f"🟢 `#{agent_id:03d}` | **{name}**\n"
        report += f"   📍 {province} | 📞 `{phone}`\n"
        report += f"   💰 {balance_display} {currency_display} | 📦 {transaction_count} حواله\n\n"
    
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["🔍 جستجوی جدید", "🔙 بازگشت به منوی ادمین"]
        ], resize_keyboard=True)
    )


@require_admin
async def filter_inactive_agents(update, context):
    """فیلتر عامل‌های غیرفعال"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.id, a.name, a.province, a.phone,
               b.balance, b.currency,
               COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        LEFT JOIN transactions t ON a.id = t.agent_id
        WHERE a.is_active = 0
        GROUP BY a.id
        ORDER BY a.name
    """)
    results = cur.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("❌ هیچ عامل غیرفعالی وجود ندارد")
        return
    
    report = f"🔴 *عامل‌های غیرفعال ({len(results)} عامل)*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    for agent_id, name, province, phone, balance, currency, transaction_count in results:
        balance_display = f"{balance:,.0f}" if balance else "۰"
        currency_display = currency if currency else "افغانی"
        
        report += f"🔴 `#{agent_id:03d}` | **{name}**\n"
        report += f"   📍 {province} | 📞 `{phone}`\n"
        report += f"   💰 {balance_display} {currency_display} | 📦 {transaction_count} حواله\n\n"
    
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            ["🔍 جستجوی جدید", "🔙 بازگشت به منوی ادمین"]
        ], resize_keyboard=True)
    )
