from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler
import logging

from bot.services.database import (
    get_agent_by_telegram_id,
    get_agent_by_phone,
    bind_agent_telegram_id,
    get_db,  # جدید
    get_agent_balance,  # 🔴 جدید
    check_sufficient_balance,
)
from bot.services.security import verify_password
from bot.services.auth import require_agent  # اگر نیاز داری

logger = logging.getLogger(__name__)

# حالت‌های مکالمه عامل
LOGIN_PHONE, LOGIN_PASSWORD = range(2)
(
    SEND_RECEIVER_AGENT,
    SEND_RECEIVER_NAME,
    SEND_RECEIVER_TAZKIRA,
    SEND_AMOUNT,
    SEND_SENDER_NAME,
    SEND_CURRENCY,
    CONFIRM_TRANSACTION,
    EDIT_TRANSACTION_CHOICE,
    EDIT_RECEIVER_INFO,
    EDIT_AMOUNT,
    TRACK_CODE,
    DELETE_CONFIRM,
) = range(12)

# =======================
# 🎛 منوی عامل
# =======================


@require_agent
async def agent_menu(update, context):
    """
    منوی اصلی عامل
    """
    keyboard = [
        ["💸 ارسال حواله جدید"],
        ["📋 حواله‌های من"],
        ["🔍 پیگیری با کد حواله"],
        ["💰 موجودی و گزارش"],
        ["🚪 خروج از حساب عامل"],  # 🔴 تغییر از "🚪 خروج" به این
    ]

    await update.message.reply_text(
        "🎛 *منوی عامل*\n\nلطفاً یک گزینه انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# =======================
# 🔐 ورود عامل
# =======================


async def agent_login_start(update, context):
    await update.message.reply_text("📞 شماره تماس خود را وارد کنید:")
    return LOGIN_PHONE


async def agent_login_phone(update, context):
    phone = update.message.text.strip()
    agent = get_agent_by_phone(phone)

    if not agent:
        await update.message.reply_text("❌ عامل با این شماره یافت نشد")
        return ConversationHandler.END

    agent_id, password_hash, telegram_id, is_active = agent

    if not is_active:
        await update.message.reply_text("⛔ حساب شما غیرفعال است")
        return ConversationHandler.END

    if telegram_id:
        await update.message.reply_text("❌ این عامل قبلاً لاگین شده")
        return ConversationHandler.END

    context.user_data["login_agent_id"] = agent_id
    context.user_data["password_hash"] = password_hash

    await update.message.reply_text("🔐 پسورد خود را وارد کنید:")
    return LOGIN_PASSWORD


async def agent_login_password(update, context):
    password = update.message.text
    hashed = context.user_data["password_hash"]

    if not verify_password(password, hashed):
        await update.message.reply_text("❌ پسورد اشتباه است")
        return LOGIN_PASSWORD

    agent_id = context.user_data["login_agent_id"]
    telegram_id = update.effective_user.id

    bind_agent_telegram_id(agent_id, telegram_id)

    # ذخیره اطلاعات عامل در context
    context.user_data["agent_id"] = agent_id
    context.user_data["role"] = "agent"

    await update.message.reply_text(
        "✅ ورود موفق بود", reply_markup=ReplyKeyboardRemove()
    )

    # نمایش منوی عامل
    await agent_menu(update, context)

    return ConversationHandler.END


# =======================
# 💸 ارسال حواله جدید
# =======================


@require_agent
async def send_hawala_start(update, context):
    """شروع فرآیند ارسال حواله"""

    # پاک کردن داده‌های قبلی
    for key in [
        "receiver_agent_id",
        "receiver_name",
        "receiver_tazkira",
        "amount",
        "sender_name",
        "currency",
        "commission",
    ]:
        context.user_data.pop(key, None)

    # دریافت لیست عامل‌های فعال (غیر از خودش)
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, province 
        FROM agents 
        WHERE is_active = 1 AND id != ?
        ORDER BY province
    """,
        (context.user_data["agent_id"],),
    )

    agents = cur.fetchall()
    conn.close()

    if not agents:
        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            "❌ *هیچ عامل فعال دیگری در سیستم وجود ندارد*\n\n"
            "📞 لطفاً به ادمین اطلاع دهید تا عامل جدیدی در شهرهای دیگر ایجاد کند.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return ConversationHandler.END

    # نمایش لیست عامل‌ها
    text = "📍 *عامل گیرنده را انتخاب کنید:*\n\n"

    # گروه‌بندی بر اساس ولایت
    provinces = {}
    for agent_id, name, province in agents:
        if province not in provinces:
            provinces[province] = []
        provinces[province].append((agent_id, name))

    for province, agent_list in provinces.items():
        text += f"🏙️ *{province}:*\n"
        for agent_id, name in agent_list:
            text += f"   👤 {name} - کد: `{agent_id}`\n"
        text += "\n"

    text += "لطفاً **کد عامل گیرنده** را وارد کنید:\n"
    text += "(برای لغو: /cancel)"

    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )

    return SEND_RECEIVER_AGENT


async def send_receiver_agent(update, context):
    """دریافت کد عامل گیرنده"""

    text = update.message.text.strip()

    # چک کردن اگر کاربر لغو کرده
    if text in ["/cancel", "❌ لغو"]:
        await update.message.reply_text(
            "❌ عملیات لغو شد", reply_markup=ReplyKeyboardRemove()
        )
        await agent_menu(update, context)
        return ConversationHandler.END

    try:
        receiver_agent_id = int(text)

        # بررسی وجود عامل گیرنده
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, name, province, is_active 
            FROM agents 
            WHERE id = ? AND is_active = 1 AND id != ?
        """,
            (receiver_agent_id, context.user_data["agent_id"]),
        )

        receiver = cur.fetchone()
        conn.close()

        if not receiver:
            await update.message.reply_text(
                "❌ عامل گیرنده یافت نشد یا غیرفعال است\n" "لطفاً کد صحیح را وارد کنید:"
            )
            return SEND_RECEIVER_AGENT

        # ذخیره در context
        context.user_data["receiver_agent_id"] = receiver_agent_id
        context.user_data["receiver_agent_name"] = receiver[1]
        context.user_data["receiver_province"] = receiver[2]

        await update.message.reply_text("👤 نام گیرنده را وارد کنید:")
        return SEND_RECEIVER_NAME

    except ValueError:
        await update.message.reply_text(
            "❌ لطفاً کد عامل را به عدد وارد کنید\n" "یا برای لغو: /cancel"
        )
        return SEND_RECEIVER_AGENT


async def send_receiver_name(update, context):
    """دریافت نام گیرنده"""
    context.user_data["receiver_name"] = update.message.text.strip()

    await update.message.reply_text("🪪 شماره تذکره گیرنده را وارد کنید:")
    return SEND_RECEIVER_TAZKIRA


async def send_receiver_tazkira(update, context):
    """دریافت تذکره گیرنده"""
    tazkira = update.message.text.strip()

    if not tazkira.isdigit():
        await update.message.reply_text("❌ شماره تذکره باید عدد باشد")
        return SEND_RECEIVER_TAZKIRA

    context.user_data["receiver_tazkira"] = tazkira

    await update.message.reply_text("💰 مبلغ حواله را وارد کنید (عدد):")
    return SEND_AMOUNT


# قبل از ثبت در دیتابیس، از کاربر نام فرستنده رو بخواهیم:


async def send_amount(update, context):
    """دریافت مبلغ حواله"""
    try:
        amount = float(update.message.text.strip())

        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد")
            return SEND_AMOUNT

        # چک موجودی (اولیه)
        agent_id = context.user_data["agent_id"]
        from bot.services.database import get_agent_balance

        # فعلاً فرض می‌کنیم ارز AFN هست، بعداً کاربر انتخاب می‌کنه
        balance = get_agent_balance(agent_id, "AFN")

        if amount > balance:
            await update.message.reply_text(
                f"⚠️ *هشدار موجودی:*\n\n"
                f"💰 مبلغ درخواستی: {amount:,.0f} افغانی\n"
                f"💵 موجودی فعلی شما: {balance:,.0f} افغانی\n\n"
                f"اگر ادامه دهید، بعداً باید ارز را انتخاب کنید.\n"
                f"آیا ادامه می‌دهید؟",
                parse_mode="Markdown",
            )
            # می‌تونی اینجا از کاربر تأیید بگیری
            # برای سادگی، ادامه می‌دیم

        context.user_data["amount"] = amount

        # 🔴 دریافت نام فرستنده
        await update.message.reply_text("👤 نام فرستنده را وارد کنید:")
        return SEND_SENDER_NAME

    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
        return SEND_AMOUNT


async def send_sender_name(update, context):
    """دریافت نام فرستنده"""
    sender_name = update.message.text.strip()

    if not sender_name or len(sender_name) < 2:
        await update.message.reply_text("❌ نام فرستنده باید حداقل ۲ حرف باشد")
        return SEND_SENDER_NAME

    context.user_data["sender_name"] = sender_name

    # محاسبه کارمزد (۱٪ ثابت)
    amount = context.user_data["amount"]
    commission = amount * 0.01
    context.user_data["commission"] = commission

    keyboard = [["🇦🇫 AFN", "🇺🇸 USD"]]

    await update.message.reply_text(
        "💱 نوع ارز را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return SEND_CURRENCY


async def send_currency(update, context):
    """دریافت نوع ارز"""
    currency_text = update.message.text.strip()

    # 🔴 اصلاح: دکمه‌ها "🇦🇫 AFN" و "🇺🇸 USD" هستن
    if "AFN" in currency_text:
        currency = "AFN"
    elif "USD" in currency_text:
        currency = "USD"
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return SEND_CURRENCY

    # چک نهایی موجودی با ارز انتخاب‌شده
    agent_id = context.user_data["agent_id"]
    amount = context.user_data["amount"]

    from bot.services.database import get_agent_balance, check_sufficient_balance

    if not check_sufficient_balance(agent_id, amount, currency):
        balance = get_agent_balance(agent_id, currency)

        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            f"❌ *موجودی کافی نیست!*\n\n"
            f"💰 مبلغ درخواستی: {amount:,.0f} {currency}\n"
            f"💵 موجودی شما: {balance:,.0f} {currency}\n\n"
            f"📞 لطفاً موجودی حساب خود را افزایش دهید.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return ConversationHandler.END

    context.user_data["currency"] = currency

    # نمایش خلاصه
    summary = (
        "🧾 *خلاصه حواله:*\n\n"
        f"📍 *عامل گیرنده:* {context.user_data['receiver_agent_name']} ({context.user_data['receiver_province']})\n"
        f"👤 *فرستنده:* {context.user_data['sender_name']}\n"
        f"👤 *گیرنده:* {context.user_data['receiver_name']}\n"
        f"🪪 *تذکره گیرنده:* {context.user_data['receiver_tazkira']}\n"
        f"💰 *مبلغ:* {context.user_data['amount']:,.0f} {currency}\n"
        f"💸 *کارمزد:* {context.user_data['commission']:,.0f} {currency}\n"
        f"💵 *قابل پرداخت به فرستنده:* {context.user_data['amount'] - context.user_data['commission']:,.0f} {currency}\n\n"
        "آیا تأیید می‌کنید؟"
    )

    keyboard = [["✅ تأیید و ثبت", "❌ لغو"]]

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return CONFIRM_TRANSACTION


@require_agent
async def confirm_transaction(update, context):
    """تأیید نهایی حواله"""
    choice = update.message.text.strip()

    if choice == "❌ لغو":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ عملیات لغو شد", reply_markup=ReplyKeyboardRemove()
        )
        await agent_menu(update, context)
        return ConversationHandler.END

    if choice != "✅ تأیید و ثبت":
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return CONFIRM_TRANSACTION

    try:
        # تولید کد حواله
        import random

        transaction_code = f"HWL{random.randint(100000, 999999)}"

        agent_id = context.user_data["agent_id"]
        amount = context.user_data["amount"]
        currency = context.user_data["currency"]

        # 🔴 چک نهایی موجودی (یک بار دیگه برای اطمینان)
        from bot.services.database import check_sufficient_balance, get_agent_balance

        if not check_sufficient_balance(agent_id, amount, currency):
            balance = get_agent_balance(agent_id, currency)

            await update.message.reply_text(
                f"❌ *موجودی تغییر کرده است!*\n\n"
                f"💰 مبلغ درخواستی: {amount:,.0f} {currency}\n"
                f"💵 موجودی فعلی: {balance:,.0f} {currency}\n\n"
                f"لطفاً مجدداً تلاش کنید.",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    [["🔙 بازگشت به منوی عامل"]], resize_keyboard=True
                ),
            )
            return ConversationHandler.END

        # ثبت در دیتابیس
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO transactions 
            (transaction_code, agent_id, receiver_agent_id, sender_name, 
             receiver_name, receiver_tazkira, amount, currency, commission, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                transaction_code,
                agent_id,
                context.user_data["receiver_agent_id"],
                context.user_data["sender_name"],
                context.user_data["receiver_name"],
                context.user_data["receiver_tazkira"],
                amount,
                currency,
                context.user_data["commission"],
                "pending",
            ),
        )

        # 🔴 کسر از موجودی عامل
        cur.execute(
            """
            UPDATE balances 
            SET balance = balance - ?
            WHERE agent_id = ? AND currency = ?
        """,
            (amount, agent_id, currency),
        )

        conn.commit()
        conn.close()

        # دریافت موجودی جدید
        new_balance = get_agent_balance(agent_id, currency)

        # نمایش کد حواله با گزارش کامل
        keyboard = [["💸 ارسال حواله جدید"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ *حواله با موفقیت ثبت شد!*\n\n"
            f"📦 *کد حواله:* `{transaction_code}`\n"
            f"👤 *فرستنده:* {context.user_data['sender_name']}\n"
            f"👤 *گیرنده:* {context.user_data['receiver_name']}\n"
            f"🪪 *تذکره گیرنده:* {context.user_data['receiver_tazkira']}\n"
            f"📍 *مقصد:* {context.user_data['receiver_province']}\n"
            f"💰 *مبلغ حواله:* {amount:,.0f} {currency}\n"
            f"💸 *کارمزد:* {context.user_data['commission']:,.0f} {currency}\n"
            f"💵 *قابل پرداخت به فرستنده:* {amount - context.user_data['commission']:,.0f} {currency}\n"
            f"🏦 *موجودی جدید شما:* {new_balance:,.0f} {currency}\n\n"
            f"📝 *به مشتری بگویید:*\n"
            f"کد حواله `{transaction_code}` را به گیرنده بدهد تا با نشان دادن تذکره، پول را دریافت کند.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Error in confirm_transaction")
        await update.message.reply_text(
            "❌ خطا در ثبت حواله",
            reply_markup=ReplyKeyboardMarkup(
                [["🔙 بازگشت به منوی عامل"]], resize_keyboard=True
            ),
        )
        return ConversationHandler.END


# =======================
# 📋 حواله‌های من
# =======================


@require_agent
async def list_my_transactions(update, context):
    """نمایش حواله‌های ثبت‌شده توسط این عامل"""

    conn = get_db()
    cur = conn.cursor()

    # آمار کلی
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count,
            SUM(amount) as total_amount
        FROM transactions 
        WHERE agent_id = ?
    """,
        (context.user_data["agent_id"],),
    )

    stats = cur.fetchone()
    total, pending_count, completed_count, cancelled_count, total_amount = stats

    # لیست تراکنش‌ها
    cur.execute(
        """
        SELECT 
            t.transaction_code,
            t.receiver_name,
            t.amount,
            t.currency,
            t.status,
            t.created_at,
            a.name as receiver_agent_name,
            a.province as receiver_province
        FROM transactions t
        LEFT JOIN agents a ON t.receiver_agent_id = a.id
        WHERE t.agent_id = ?
        ORDER BY t.created_at DESC
        LIMIT 20
    """,
        (context.user_data["agent_id"],),
    )

    transactions = cur.fetchall()
    conn.close()

    if not transactions:
        await update.message.reply_text(
            "📭 *هنوز هیچ حواله‌ای ثبت نکرده‌اید*\n\n"
            "برای ثبت حواله جدید، گزینه '💸 ارسال حواله جدید' را انتخاب کنید.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [["💸 ارسال حواله جدید"], ["🔙 بازگشت به منوی عامل"]],
                resize_keyboard=True,
            ),
        )
        return

    # ساخت گزارش
    text = "📋 *حواله‌های ثبت‌شده توسط شما*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # آمار سریع
    text += f"📊 *آمار سریع:*\n"
    text += f"   کل حواله‌ها: {total or 0} مورد\n"
    text += f"   در انتظار: {pending_count or 0} مورد\n"
    text += f"   تکمیل شده: {completed_count or 0} مورد\n"
    text += f"   لغو شده: {cancelled_count or 0} مورد\n"
    if total_amount:
        text += f"   مجموع مبلغ: {total_amount:,.0f} افغانی\n"
    text += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for i, (
        code,
        name,
        amount,
        currency,
        status,
        created_at,
        agent_name,
        province,
    ) in enumerate(transactions, 1):
        # اموجی وضعیت
        if status == "pending":
            status_emoji = "🟡"
            status_text = "در انتظار"
            action_note = "(قابل ویرایش/حذف)"
        elif status == "completed":
            status_emoji = "🟢"
            status_text = "تکمیل شده"
            action_note = ""
        elif status == "cancelled":
            status_emoji = "🔴"
            status_text = "لغو شده"
            action_note = ""
        else:
            status_emoji = "⚪"
            status_text = status
            action_note = ""

        text += f"{status_emoji} **{code}** {action_note}\n"
        text += f"   👤 گیرنده: {name}\n"
        text += f"   📍 مقصد: {province} ({agent_name})\n"
        text += f"   💰 مبلغ: {amount:,.0f} {currency}\n"
        text += f"   📊 وضعیت: {status_text}\n"
        text += f"   📅 تاریخ: {created_at[:16]}\n"

        if i < len(transactions):
            text += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # دکمه‌های عملیاتی
    keyboard = []

    # اگر حواله در انتظار داره، دکمه مدیریت اضافه کن
    if pending_count and pending_count > 0:
        keyboard.append(["✏️ مدیریت حواله‌های در انتظار"])

    keyboard.append(["🔄 بروزرسانی لیست"])
    keyboard.append(["🔙 بازگشت به منوی عامل"])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# =======================
# 🔍 پیگیری با کد حواله
# =======================


async def track_transaction_start(update, context):
    """شروع پیگیری حواله"""
    await update.message.reply_text(
        "🔍 کد حواله را وارد کنید (مثال: HWL123456):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TRACK_CODE


@require_agent
async def track_transaction_code(update, context):
    """پیگیری با کد حواله"""
    code = update.message.text.strip().upper()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            t.transaction_code,
            t.receiver_name,
            t.amount,
            t.currency,
            t.status,
            t.created_at,
            a1.name as sender_agent_name,
            a2.name as receiver_agent_name,
            a2.province as receiver_province
        FROM transactions t
        LEFT JOIN agents a1 ON t.agent_id = a1.id
        LEFT JOIN agents a2 ON t.receiver_agent_id = a2.id
        WHERE t.transaction_code = ?
    """,
        (code,),
    )

    transaction = cur.fetchone()
    conn.close()

    if not transaction:
        await update.message.reply_text("❌ حواله‌ای با این کد یافت نشد")
        await agent_menu(update, context)
        return ConversationHandler.END

    # نمایش اطلاعات
    (
        code,
        name,
        amount,
        currency,
        status,
        created_at,
        sender_agent,
        receiver_agent,
        province,
    ) = transaction

    if status == "pending":
        status_emoji = "🟡"
        status_text = "در انتظار پرداخت"
        action_text = "\n📍 گیرنده می‌تواند با این کد و تذکره به عامل مقصد مراجعه کند."
    elif status == "completed":
        status_emoji = "🟢"
        status_text = "تکمیل شده"
        action_text = "\n✅ این حواله پرداخت شده است."
    else:
        status_emoji = "🔴"
        status_text = "لغو شده"
        action_text = "\n❌ این حواله لغو شده است."

    text = (
        f"{status_emoji} *پیگیری حواله*\n\n"
        f"📦 کد: `{code}`\n"
        f"👤 گیرنده: {name}\n"
        f"📍 مقصد: {province} ({receiver_agent})\n"
        f"💰 مبلغ: {amount:,.0f} {currency}\n"
        f"📊 وضعیت: {status_text}\n"
        f"📅 تاریخ ثبت: {created_at[:10]}\n"
        f"{action_text}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 بازگشت به منوی عامل"]], resize_keyboard=True
        ),  # اضافه شد
    )

    return ConversationHandler.END


@require_agent
async def manage_pending_transactions_start(update, context):
    """شروع مدیریت حواله‌های در انتظار"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT transaction_code, receiver_name, amount, currency, created_at
        FROM transactions 
        WHERE agent_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 10
    """,
        (context.user_data["agent_id"],),
    )

    pending = cur.fetchall()
    conn.close()

    if not pending:
        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            "📭 هیچ حواله در حال انتظاری ندارید.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    # ساخت لیست
    text = "✏️ *حواله‌های در انتظار شما*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    for i, (code, name, amount, currency, created_at) in enumerate(pending, 1):
        text += f"📦 `{code}`\n"
        text += f"   👤 گیرنده: {name}\n"
        text += f"   💰 مبلغ: {amount:,.0f} {currency}\n"
        text += f"   📅 ثبت: {created_at[:16]}\n"

        if i < len(pending):
            text += "   ⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    text += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    text += "📝 برای ویرایش/حذف، کد حواله را وارد کنید.\n"
    text += "یا از دکمه‌های زیر استفاده کنید:"

    # اضافه کردن دکمه بازگشت
    keyboard = [["🔙 بازگشت به منوی عامل"], ["📋 مشاهده همه حواله‌ها"]]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    # باید حالت Conversation برای ویرایش تعریف کنی
    # return EDIT_TRANSACTION_CHOICE


# =======================
# 🚪 خروج عامل
# =======================


@require_agent
async def agent_logout(update, context):
    """خروج عامل از سیستم"""
    user_id = update.effective_user.id

    # استفاده از تابع unbind
    from bot.services.database import unbind_agent_telegram_id

    unbind_agent_telegram_id(user_id)

    # پاک کردن context
    context.user_data.clear()

    await update.message.reply_text(
        "🚪 از حساب عامل خارج شدید.", reply_markup=ReplyKeyboardRemove()
    )

    # برگشت به منوی اصلی
    from bot.handlers.start import start

    await start(update, context)
