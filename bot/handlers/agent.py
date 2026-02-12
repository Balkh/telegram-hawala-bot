from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
import pandas as pd
import io
from datetime import datetime as dt
import logging

from bot.services.database import (
    get_agent_by_phone,
    bind_agent_telegram_id,
    get_db,
    get_agent_balance,
    check_sufficient_balance,
)
from bot.services.security import verify_password
from bot.services.auth import require_agent, require_any_auth
from bot.services.receipt import generate_receipt_image

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
    PAY_TRANSACTION_CODE,
    PAY_CONFIRM,
    BALANCE_MENU,
    INCREASE_BALANCE_AMOUNT,
    INCREASE_BALANCE_CURRENCY,
    DECREASE_BALANCE_AMOUNT,
    DECREASE_BALANCE_CURRENCY,
    ADD_CURRENCY_TYPE,
    INCREASE_BALANCE_PHOTO,
    SEARCH_TYPE,
    SEARCH_QUERY,
    SEARCH_DATE_RANGE,
) = range(24)

# =======================
# 🎛 منوی عامل
# =======================


@require_agent
async def agent_menu(update, context):
    """
    منوی اصلی عامل
    """
    agent_id = context.user_data.get("agent_id")
    
    # 🔔 بررسی حواله‌های در انتظار برای این عامل (به عنوان گیرنده)
    pending_msg = ""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*), currency 
            FROM transactions 
            WHERE receiver_agent_id = ? AND status = 'pending'
            GROUP BY currency
            """,
            (agent_id,),
        )
        pending_counts = cur.fetchall()
        conn.close()

        if pending_counts:
            pending_msg = "🔔 *یادآوری حواله‌های در انتظار پرداخت:*\n"
            for count, currency in pending_counts:
                pending_msg += f"📦 تعداد {count} حواله ({currency})\n"
            pending_msg += "\nبرای پرداخت، به بخش 'حواله‌های من' مراجعه کنید.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    except Exception as e:
        logger.error(f"Error checking pending hawalas for menu: {e}")

    keyboard = [
        ["💸 ارسال حواله جدید"],
        ["📥 حواله‌های قابل پرداخت", "📋 حواله‌های من"],
        ["🔍 جستجوی پیشرفته", "🔍 پیگیری با کد حواله"],
        ["💰 موجودی و گزارش"],
        ["🚪 خروج از حساب عامل"],
    ]

    await update.message.reply_text(
        f"{pending_msg}🎛 *منوی عامل*\n\nلطفاً یک گزینه انتخاب کنید:",
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

    if telegram_id and not context.user_data.get("role"):
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

    # بررسی وضعیت فعال بودن عامل قبل از ورود
    from bot.services.database import get_agent_by_id
    agent = get_agent_by_id(agent_id)
    
    if not agent:
        await update.message.reply_text("❌ عامل پیدا نشد")
        return LOGIN_PASSWORD
    
    if not agent["is_active"]:
        await update.message.reply_text("⛔ حساب شما مسدود است. لطفاً با ادمین تماس بگیرید.")
        return ConversationHandler.END

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

        # در سیستم حواله، عامل مبدأ پول نقد می‌گیرد، پس نیازی به چک موجودی نیست
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

    # در سیستم حواله، عامل مبدأ پول نقد می‌گیرد، پس نیازی به چک موجودی نیست
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

        # 🔴 افزایش موجودی عامل مبدأ (چون پول نقد گرفته)
        # مطمئن شو رکورد موجودی وجود داره
        cur.execute(
            """
            SELECT id FROM balances 
            WHERE agent_id = ? AND currency = ?
        """,
            (agent_id, currency),
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO balances (agent_id, currency, balance)
                VALUES (?, ?, 0)
            """,
                (agent_id, currency),
            )

        cur.execute(
            """
            UPDATE balances 
            SET balance = balance + ?
            WHERE agent_id = ? AND currency = ?
        """,
            (amount, agent_id, currency),
        )

        conn.commit()

        # 🔔 اطلاع‌رسانی به عامل مقصد
        try:
            receiver_agent_id = context.user_data.get("receiver_agent_id")
            if not receiver_agent_id:
                logger.error("No receiver_agent_id found in context.user_data")
            else:
                db_conn = get_db()
                db_cur = db_conn.cursor()
                db_cur.execute("SELECT telegram_id, name FROM agents WHERE id = ?", (receiver_agent_id,))
                receiver_info = db_cur.fetchone()
                
                if receiver_info and receiver_info[0]:
                    receiver_telegram_id = receiver_info[0]
                    
                    db_cur.execute("SELECT name, province FROM agents WHERE id = ?", (agent_id,))
                    sender_agent_info = db_cur.fetchone()
                    sender_agent_name = sender_agent_info[0] if sender_agent_info else "نامشخص"
                    sender_agent_province = sender_agent_info[1] if sender_agent_info else "نامشخص"

                    notification_text = (
                        "🔔 *حواله جدید دریافت شد*\n"
                        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
                        f"📦 *کد حواله:* `{transaction_code}`\n"
                        f"👤 *فرستنده:* {context.user_data['sender_name']}\n"
                        f"👥 *گیرنده:* {context.user_data['receiver_name']}\n"
                        f"🆔 *تذکره گیرنده:* {context.user_data['receiver_tazkira']}\n"
                        f"💰 *مبلغ:* {amount:,.0f} {currency}\n"
                        f"📍 *عامل مبدأ:* {sender_agent_name} ({sender_agent_province})\n"
                        f"📅 *تاریخ ثبت:* {dt.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                        "✅ این حواله در بخش «حواله‌های قابل پرداخت» منوی شما ثبت شد."
                    )
                    
                    # 🔴 تغییر: استفاده از await مستقیم به جای create_task برای اطمینان از ارسال
                    await context.bot.send_message(
                        chat_id=receiver_telegram_id,
                        text=notification_text,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Notification sent successfully to TG: {receiver_telegram_id}")
                else:
                    logger.warning(f"Target agent {receiver_agent_id} has no telegram_id. No notification sent.")
                
                db_conn.close()
        except Exception as notify_err:
            logger.error(f"Failed to send notification: {notify_err}")

        conn.close()

        # دریافت موجودی جدید
        new_balance = get_agent_balance(agent_id, currency)

        # نمایش کد حواله با گزارش کامل
        keyboard = [["💸 ارسال حواله جدید"], ["🔙 بازگشت به منوی عامل"]]

        # تولید و ارسال رسید تصویری
        try:
            # دریافت نام عامل‌ها برای رسید
            db_conn = get_db()
            db_cur = db_conn.cursor()
            
            # نام عامل فرستنده
            db_cur.execute("SELECT name FROM agents WHERE id = ?", (agent_id,))
            sender_agent_name = db_cur.fetchone()[0]
            
            # نام عامل گیرنده
            db_cur.execute("SELECT name FROM agents WHERE id = ?", (context.user_data['receiver_agent_id'],))
            receiver_agent_name = db_cur.fetchone()[0]
            db_conn.close()

            receipt_data = {
                'transaction_code': transaction_code,
                'sender_name': context.user_data['sender_name'],
                'receiver_name': context.user_data['receiver_name'],
                'receiver_tazkira': context.user_data['receiver_tazkira'],
                'amount': amount,
                'currency': currency,
                'sender_agent': sender_agent_name,
                'receiver_agent': receiver_agent_name,
                'created_at': dt.now().strftime("%Y-%m-%d %H:%M"),
            }
            
            receipt_img = generate_receipt_image(receipt_data)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=receipt_img,
                caption=f"🧾 *رسید تصویری حواله {transaction_code}*",
                parse_mode="Markdown"
            )
        except Exception as receipt_err:
            logger.error(f"Failed to generate/send receipt image: {receipt_err}")

        debug_info = ""
        # اگر برای تست است، نمایش وضعیت نوتیفیکیشن
        try:
            receiver_agent_id = context.user_data.get("receiver_agent_id")
            db_conn = get_db()
            db_cur = db_conn.cursor()
            db_cur.execute("SELECT telegram_id FROM agents WHERE id = ?", (receiver_agent_id,))
            row = db_cur.fetchone()
            if row and row[0]:
                debug_info = f"\n\n📡 *وضعیت نوتیفیکیشن:* ارسال شد به `{row[0]}`"
            else:
                debug_info = f"\n\n⚠️ *وضعیت نوتیفیکیشن:* ارسال نشد (عامل مقصد با آیدی {receiver_agent_id} تلگرام متصل ندارد)"
            db_conn.close()
        except:
            pass

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
            f"کد حواله `{transaction_code}` را به گیرنده بدهد تا با نشان دادن تذکره، پول را دریافت کند."
            f"{debug_info}",
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


@require_agent
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
            t.receiver_tazkira,
            t.amount,
            t.currency,
            t.status,
            t.created_at,
            t.receiver_agent_id,
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
        receiver_tazkira,
        amount,
        currency,
        status,
        created_at,
        receiver_agent_id,
        sender_agent,
        receiver_agent,
        province,
    ) = transaction

    current_agent_id = context.user_data.get("agent_id")
    is_receiver_agent = current_agent_id == receiver_agent_id

    if status == "pending":
        status_emoji = "🟡"
        status_text = "در انتظار پرداخت"
        keyboard.append([InlineKeyboardButton("🧾 دریافت رسید تصویری", callback_data=f"get_receipt_{code}")])
        if is_receiver_agent:
            action_text = "\n💵 شما عامل مقصد هستید. می‌توانید با تأیید تذکره گیرنده، پرداخت را انجام دهید."
            keyboard.append([InlineKeyboardButton("💵 پرداخت سریع این حواله", callback_data=f"pay_fast_{code}")])
        else:
            action_text = "\n📍 گیرنده می‌تواند با این کد و تذکره به عامل مقصد مراجعه کند."
    elif status == "completed":
        status_emoji = "🟢"
        status_text = "تکمیل شده"
        keyboard.append([InlineKeyboardButton("🧾 دریافت رسید تصویری", callback_data=f"get_receipt_{code}")])
        action_text = "\n✅ این حواله قبلاً پرداخت شده است."
    else:
        status_emoji = "🔴"
        status_text = "لغو شده"
        action_text = ""

    text = (
        f"{status_emoji} *وضعیت حواله:* {status_text}\n\n"
        f"📦 *کد حواله:* `{code}`\n"
        f"👤 *گیرنده:* {name}\n"
        f"💰 *مبلغ:* {amount:,.0f} {currency}\n"
        f"📍 *مقصد:* {province} ({receiver_agent})\n"
        f"📅 *تاریخ ثبت:* {created_at}\n"
        f"{action_text}"
    )

    # دکمه‌های عملیاتی
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = []
    
    # دکمه دانلود رسید
    keyboard.append([InlineKeyboardButton("🧾 دانلود رسید تصویری", callback_data=f"get_receipt_{code}")])
    
    # اگر عامل مقصد است و حواله pending، دکمه پرداخت سریع بده
    if is_receiver_agent and status == "pending":
        keyboard.append([InlineKeyboardButton("💵 پرداخت این حواله", callback_data=f"pay_fast_{code}")])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # برای دکمه‌های ریپلای معمولی
    await agent_menu(update, context)
    return ConversationHandler.END


@require_agent
async def list_payable_transactions(update, context):
    """نمایش لیست حواله‌هایی که این عامل باید پرداخت کند"""
    agent_id = context.user_data.get("agent_id")
    
    conn = get_db()
    cur = conn.cursor()
    
    # دریافت حواله‌های در انتظار برای این عامل
    cur.execute(
        """
        SELECT 
            t.transaction_code, 
            t.receiver_name, 
            t.amount, 
            t.currency, 
            t.sender_name,
            t.created_at,
            a.name as sender_agent_name
        FROM transactions t
        JOIN agents a ON t.agent_id = a.id
        WHERE t.receiver_agent_id = ? AND t.status = 'pending'
        ORDER BY t.created_at DESC
    """,
        (agent_id,),
    )
    
    payable_list = cur.fetchall()
    conn.close()
    
    if not payable_list:
        await update.message.reply_text(
            "📭 هیچ حواله قابل پرداختی در سیستم برای شما وجود ندارد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت به منوی عامل"]], resize_keyboard=True)
        )
        return
    
    text = "📥 *حواله‌های قابل پرداخت برای شما*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    for code, receiver, amount, currency, sender, date, sender_agent in payable_list:
        text += f"📦 *کد:* `{code}`\n"
        text += f"👥 *گیرنده:* {receiver}\n"
        text += f"💰 *مبلغ:* {amount:,.0f} {currency}\n"
        text += f"👤 *فرستنده:* {sender}\n"
        text += f"📍 *عامل مبدأ:* {sender_agent}\n"
        text += f"📅 *تاریخ:* {date[:16]}\n"
        text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
    text += "📝 برای پرداخت هر یک از حواله‌های بالا، از بخش «🔍 پیگیری با کد حواله» استفاده کنید."
    
    keyboard = [["🔍 پیگیری با کد حواله"], ["🔙 بازگشت به منوی عامل"]]
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_agent
async def pay_transaction_start(update, context):
    """شروع فرآیند پرداخت حواله توسط عامل مقصد"""
    choice = update.message.text.strip()

    if choice == "🔙 بازگشت به منوی عامل":
        await agent_menu(update, context)
        return ConversationHandler.END

    if choice != "💵 پرداخت به گیرنده":
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return PAY_TRANSACTION_CODE

    code = context.user_data.get("pay_transaction_code")
    if not code:
        await update.message.reply_text("❌ خطا: کد حواله پیدا نشد")
        await agent_menu(update, context)
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            t.transaction_code,
            t.receiver_name,
            t.receiver_tazkira,
            t.amount,
            t.currency,
            t.status,
            t.receiver_agent_id
        FROM transactions t
        WHERE t.transaction_code = ? AND t.status = 'pending'
    """,
        (code,),
    )

    transaction = cur.fetchone()
    conn.close()

    if not transaction:
        await update.message.reply_text("❌ حواله‌ای با این کد یافت نشد یا قبلاً پرداخت شده است")
        await agent_menu(update, context)
        return ConversationHandler.END

    (
        code,
        receiver_name,
        receiver_tazkira,
        amount,
        currency,
        status,
        receiver_agent_id,
    ) = transaction

    current_agent_id = context.user_data.get("agent_id")
    if current_agent_id != receiver_agent_id:
        await update.message.reply_text("❌ شما عامل مقصد این حواله نیستید")
        await agent_menu(update, context)
        return ConversationHandler.END

    # چک موجودی عامل مقصد (باید پول داشته باشد تا بدهد)
    balance = get_agent_balance(current_agent_id, currency)
    if balance < amount:
        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            f"❌ *موجودی شما برای پرداخت کافی نیست!*\n\n"
            f"💰 مبلغ حواله: {amount:,.0f} {currency}\n"
            f"💵 موجودی شما: {balance:,.0f} {currency}\n\n"
            f"📞 لطفاً موجودی حساب خود را افزایش دهید.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return ConversationHandler.END

    # ذخیره اطلاعات در context
    context.user_data["pay_transaction_code"] = code
    context.user_data["pay_amount"] = amount
    context.user_data["pay_currency"] = currency
    context.user_data["pay_receiver_name"] = receiver_name
    context.user_data["pay_receiver_tazkira"] = receiver_tazkira

    text = (
        "💵 *تأیید پرداخت حواله*\n\n"
        f"📦 کد حواله: `{code}`\n"
        f"👤 گیرنده: {receiver_name}\n"
        f"🪪 تذکره گیرنده: {receiver_tazkira}\n"
        f"💰 مبلغ: {amount:,.0f} {currency}\n"
        f"💵 موجودی شما: {balance:,.0f} {currency}\n\n"
        "⚠️ لطفاً تذکره گیرنده را بررسی کنید.\n"
        "آیا پرداخت را تأیید می‌کنید؟"
    )

    keyboard = [["✅ تأیید پرداخت", "❌ انصراف"]]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return PAY_CONFIRM


@require_agent
async def pay_transaction_confirm(update, context):
    """تأیید نهایی پرداخت حواله توسط عامل مقصد"""
    choice = update.message.text.strip()

    if choice == "❌ انصراف":
        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            "❌ عملیات پرداخت لغو شد.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        context.user_data.pop("pay_transaction_code", None)
        context.user_data.pop("pay_amount", None)
        context.user_data.pop("pay_currency", None)
        context.user_data.pop("pay_receiver_name", None)
        context.user_data.pop("pay_receiver_tazkira", None)
        return ConversationHandler.END

    if choice != "✅ تأیید پرداخت":
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return PAY_CONFIRM

    code = context.user_data.get("pay_transaction_code")
    amount = context.user_data.get("pay_amount")
    currency = context.user_data.get("pay_currency")
    receiver_agent_id = context.user_data.get("agent_id")

    if not code or not amount:
        await update.message.reply_text("❌ خطا: اطلاعات حواله پیدا نشد")
        await agent_menu(update, context)
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()

    try:
        # چک مجدد که حواله هنوز pending است و این عامل مقصد است
        cur.execute(
            """
            SELECT receiver_agent_id, status
            FROM transactions
            WHERE transaction_code = ? AND status = 'pending'
        """,
            (code,),
        )

        row = cur.fetchone()
        if not row or row[0] != receiver_agent_id:
            await update.message.reply_text(
                "❌ این حواله قبلاً پرداخت شده یا شما عامل مقصد نیستید"
            )
            conn.close()
            await agent_menu(update, context)
            return ConversationHandler.END

        # چک موجودی نهایی
        balance = get_agent_balance(receiver_agent_id, currency)
        if balance < amount:
            await update.message.reply_text(
                f"❌ موجودی شما برای پرداخت کافی نیست.\n"
                f"💵 موجودی فعلی: {balance:,.0f} {currency}"
            )
            conn.close()
            await agent_menu(update, context)
            return ConversationHandler.END

        # کسر از موجودی عامل مقصد (چون پول را به گیرنده می‌دهد)
        cur.execute(
            """
            UPDATE balances
            SET balance = balance - ?
            WHERE agent_id = ? AND currency = ?
        """,
            (amount, receiver_agent_id, currency),
        )

        # تغییر وضعیت حواله به completed
        cur.execute(
            """
            UPDATE transactions
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE transaction_code = ? AND status = 'pending'
        """,
            (code,),
        )

        conn.commit()
        conn.close()

        new_balance = get_agent_balance(receiver_agent_id, currency)

        keyboard = [["💸 ارسال حواله جدید"], ["🔙 بازگشت به منوی عامل"]]

        # تولید و ارسال رسید تصویری پرداخت
        try:
            # دریافت اطلاعات کامل حواله برای رسید
            db_conn = get_db()
            db_cur = db_conn.cursor()
            db_cur.execute("""
                SELECT t.sender_name, t.receiver_tazkira, a_sender.name as sender_agent_name, a_receiver.name as receiver_agent_name
                FROM transactions t
                JOIN agents a_sender ON t.agent_id = a_sender.id
                JOIN agents a_receiver ON t.receiver_agent_id = a_receiver.id
                WHERE t.transaction_code = ?
            """, (code,))
            row = db_cur.fetchone()
            db_conn.close()

            if row:
                sender_name, receiver_tazkira, sender_agent_name, receiver_agent_name = row
                receipt_data = {
                    'transaction_code': code,
                    'sender_name': sender_name,
                    'receiver_name': context.user_data.get('pay_receiver_name'),
                    'receiver_tazkira': receiver_tazkira,
                    'amount': amount,
                    'currency': currency,
                    'sender_agent': sender_agent_name,
                    'receiver_agent': receiver_agent_name,
                    'created_at': dt.now().strftime("%Y-%m-%d %H:%M"),
                }
                
                receipt_img = generate_receipt_image(receipt_data)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=receipt_img,
                    caption=f"🧾 *رسید تصویری پرداخت حواله {code}*",
                    parse_mode="Markdown"
                )
        except Exception as receipt_err:
            logger.error(f"Failed to generate/send payment receipt image: {receipt_err}")

        await update.message.reply_text(
            f"✅ *پرداخت با موفقیت انجام شد!*\n\n"
            f"📦 کد حواله: `{code}`\n"
            f"👤 گیرنده: {context.user_data.get('pay_receiver_name')}\n"
            f"💰 مبلغ پرداخت شده: {amount:,.0f} {currency}\n"
            f"🏦 موجودی جدید شما: {new_balance:,.0f} {currency}\n\n"
            f"📝 حواله تکمیل شد و از حساب شما کسر شد.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        # تمیز کردن context
        context.user_data.pop("pay_transaction_code", None)
        context.user_data.pop("pay_amount", None)
        context.user_data.pop("pay_currency", None)
        context.user_data.pop("pay_receiver_name", None)
        context.user_data.pop("pay_receiver_tazkira", None)

        return ConversationHandler.END

    except Exception:
        conn.close()
        logger.exception("Error completing payment")
        await update.message.reply_text(
            "❌ خطا در پرداخت حواله. لطفاً بعداً دوباره تلاش کنید."
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
        return ConversationHandler.END

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

    # اضافه کردن دکمه‌ها
    keyboard = [["🔙 بازگشت به منوی عامل"], ["📋 مشاهده همه حواله‌ها"]]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    # شروع Conversation برای انتخاب حواله
    return EDIT_TRANSACTION_CHOICE


@require_agent
async def manage_pending_select_code(update, context):
    """دریافت و بررسی کد حواله در انتظار برای ویرایش/حذف"""
    text = update.message.text.strip().upper()

    # برخورد با دکمه‌های عمومی
    if text == "🔙 بازگشت به منوی عامل":
        await agent_menu(update, context)
        return ConversationHandler.END

    if text == "📋 مشاهده همه حواله‌ها":
        await list_my_transactions(update, context)
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT transaction_code, receiver_name, amount, currency, created_at
        FROM transactions
        WHERE agent_id = ? AND transaction_code = ? AND status = 'pending'
        """,
        (context.user_data["agent_id"], text),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text(
            "❌ هیچ حواله در انتظاری با این کد برای شما پیدا نشد.\n"
            "لطفاً کد صحیح را وارد کنید یا با دکمه‌ها بازگردید."
        )
        return EDIT_TRANSACTION_CHOICE

    code, receiver_name, amount, currency, created_at = row

    # ذخیره اطلاعات در context برای مراحل بعدی
    context.user_data["edit_transaction_code"] = code
    context.user_data["edit_transaction_amount"] = amount
    context.user_data["edit_transaction_currency"] = currency

    text = (
        "✏️ *مدیریت حواله انتخاب‌شده*\n\n"
        f"📦 کد: `{code}`\n"
        f"👤 گیرنده: {receiver_name}\n"
        f"💰 مبلغ فعلی: {amount:,.0f} {currency}\n"
        f"📅 ثبت: {created_at[:16]}\n\n"
        "چه کاری می‌خواهید انجام دهید؟"
    )

    keyboard = [
        ["✏️ ویرایش مبلغ", "🗑 لغو حواله"],
        ["🔙 بازگشت به منوی عامل"],
    ]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return EDIT_TRANSACTION_CHOICE


@require_agent
async def manage_pending_action(update, context):
    """انتخاب نوع عملیات روی حواله: ویرایش مبلغ یا لغو"""
    choice = update.message.text.strip()

    if choice == "🔙 بازگشت به منوی عامل":
        await agent_menu(update, context)
        return ConversationHandler.END

    if choice == "📋 مشاهده همه حواله‌ها":
        await list_my_transactions(update, context)
        return ConversationHandler.END

    if "edit_transaction_code" not in context.user_data:
        await update.message.reply_text("❗ ابتدا کد حواله را از لیست انتخاب کنید.")
        return EDIT_TRANSACTION_CHOICE

    if choice == "✏️ ویرایش مبلغ":
        await update.message.reply_text(
            "💰 مبلغ جدید حواله را وارد کنید:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return EDIT_AMOUNT

    if choice == "🗑 لغو حواله":
        amount = context.user_data["edit_transaction_amount"]
        currency = context.user_data["edit_transaction_currency"]
        code = context.user_data["edit_transaction_code"]

        text = (
            "⚠️ *تأیید لغو حواله*\n\n"
            f"📦 کد: `{code}`\n"
            f"💰 مبلغ: {amount:,.0f} {currency}\n\n"
            "آیا از لغو این حواله مطمئن هستید؟"
        )

        keyboard = [["✅ تأیید لغو", "❌ انصراف"]]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        return DELETE_CONFIRM

    await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
    return EDIT_TRANSACTION_CHOICE


@require_agent
async def edit_pending_amount(update, context):
    """ویرایش مبلغ حواله در انتظار"""
    text = update.message.text.strip()

    try:
        new_amount = float(text)
        if new_amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد")
            return EDIT_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
        return EDIT_AMOUNT

    if "edit_transaction_code" not in context.user_data:
        await update.message.reply_text("❗ حواله‌ای برای ویرایش انتخاب نشده است.")
        await agent_menu(update, context)
        return ConversationHandler.END

    old_amount = context.user_data["edit_transaction_amount"]
    currency = context.user_data["edit_transaction_currency"]
    code = context.user_data["edit_transaction_code"]
    agent_id = context.user_data["agent_id"]

    diff = new_amount - old_amount

    conn = get_db()
    cur = conn.cursor()

    try:
        if diff > 0:
            # اگر مبلغ افزایش یافت، موجودی عامل مبدأ هم باید افزایش یابد (پول بیشتر گرفته)
            cur.execute(
                """
                UPDATE balances
                SET balance = balance + ?
                WHERE agent_id = ? AND currency = ?
                """,
                (diff, agent_id, currency),
            )

        elif diff < 0:
            # اگر مبلغ کاهش یافت، موجودی عامل مبدأ هم باید کاهش یابد (باید پول برگرداند)
            cur.execute(
                """
                UPDATE balances
                SET balance = balance + ?
                WHERE agent_id = ? AND currency = ?
                """,
                (diff, agent_id, currency),
            )

        # محاسبه کارمزد جدید (۱٪)
        new_commission = new_amount * 0.01

        # بروزرسانی رکورد حواله
        cur.execute(
            """
            UPDATE transactions
            SET amount = ?, commission = ?
            WHERE transaction_code = ? AND agent_id = ? AND status = 'pending'
            """,
            (new_amount, new_commission, code, agent_id),
        )

        conn.commit()
        conn.close()

        new_balance = get_agent_balance(agent_id, currency)

        keyboard = [["✏️ مدیریت حواله‌های در انتظار"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ مبلغ حواله با موفقیت بروزرسانی شد.\n\n"
            f"📦 کد: `{code}`\n"
            f"💰 مبلغ جدید: {new_amount:,.0f} {currency}\n"
            f"💸 کارمزد جدید (۱٪): {new_commission:,.0f} {currency}\n"
            f"🏦 موجودی فعلی شما: {new_balance:,.0f} {currency}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        # تمیز کردن context مربوط به این عملیات
        context.user_data.pop("edit_transaction_code", None)
        context.user_data.pop("edit_transaction_amount", None)
        context.user_data.pop("edit_transaction_currency", None)

        return ConversationHandler.END
    except Exception:
        conn.close()
        logger.exception("Error updating pending transaction amount")
        await update.message.reply_text(
            "❌ خطا در بروزرسانی مبلغ حواله. لطفاً بعداً دوباره تلاش کنید."
        )
        return ConversationHandler.END


@require_agent
async def delete_pending_confirm(update, context):
    """تأیید نهایی لغو حواله در انتظار"""
    choice = update.message.text.strip()

    if choice == "❌ انصراف":
        keyboard = [["✏️ مدیریت حواله‌های در انتظار"], ["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            "❌ عملیات لغو شد.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        context.user_data.pop("edit_transaction_code", None)
        context.user_data.pop("edit_transaction_amount", None)
        context.user_data.pop("edit_transaction_currency", None)
        return ConversationHandler.END

    if choice != "✅ تأیید لغو":
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return DELETE_CONFIRM

    if "edit_transaction_code" not in context.user_data:
        await update.message.reply_text("❗ حواله‌ای برای لغو انتخاب نشده است.")
        await agent_menu(update, context)
        return ConversationHandler.END

    code = context.user_data["edit_transaction_code"]
    amount = context.user_data["edit_transaction_amount"]
    currency = context.user_data["edit_transaction_currency"]
    agent_id = context.user_data["agent_id"]

    conn = get_db()
    cur = conn.cursor()

    try:
        # کسر مبلغ از موجودی عامل مبدأ (چون حواله لغو شد و باید پول برگرداند)
        cur.execute(
            """
            UPDATE balances
            SET balance = balance - ?
            WHERE agent_id = ? AND currency = ?
            """,
            (amount, agent_id, currency),
        )

        # علامت‌گذاری حواله به‌عنوان لغو شده (فقط اگر هنوز pending است)
        cur.execute(
            """
            UPDATE transactions
            SET status = 'cancelled'
            WHERE transaction_code = ? AND agent_id = ? AND status = 'pending'
            """,
            (code, agent_id),
        )

        conn.commit()
        conn.close()

        new_balance = get_agent_balance(agent_id, currency)

        keyboard = [["💸 ارسال حواله جدید"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ حواله با موفقیت لغو شد.\n\n"
            f"📦 کد: `{code}`\n"
            f"💰 مبلغ برگشتی: {amount:,.0f} {currency}\n"
            f"🏦 موجودی فعلی شما: {new_balance:,.0f} {currency}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        context.user_data.pop("edit_transaction_code", None)
        context.user_data.pop("edit_transaction_amount", None)
        context.user_data.pop("edit_transaction_currency", None)

        return ConversationHandler.END
    except Exception:
        conn.close()
        logger.exception("Error cancelling pending transaction")
        await update.message.reply_text(
            "❌ خطا در لغو حواله. لطفاً بعداً دوباره تلاش کنید."
        )
        return ConversationHandler.END


# =======================
# 💰 موجودی و گزارش
# =======================


@require_agent
async def balance_and_report_menu(update, context):
    """منوی موجودی و گزارش"""
    keyboard = [
        ["📊 نمایش گزارش کامل"],
        ["📥 دانلود گزارش اکسل"],
        ["💵 مدیریت موجودی"],
        ["🔙 بازگشت به منوی عامل"],
    ]

    await update.message.reply_text(
        "💰 *موجودی و گزارش*\n\nلطفاً یک گزینه انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


@require_agent
async def show_full_report(update, context):
    """نمایش گزارش کامل: موجودی، آمار حواله‌ها، بدهی/طلب، کمیسیون"""
    agent_id = context.user_data["agent_id"]

    conn = get_db()
    cur = conn.cursor()

    # ۱. موجودی‌ها (تجمیع شده)
    cur.execute(
        """
        SELECT currency, SUM(balance)
        FROM balances
        WHERE agent_id = ?
        GROUP BY currency
        ORDER BY currency
    """,
        (agent_id,),
    )
    balances = cur.fetchall()

    # ۲. درآمد از کمیسیون (فقط حواله‌های غیر لغو شده)
    cur.execute(
        """
        SELECT currency, SUM(commission)
        FROM transactions
        WHERE agent_id = ? AND status != 'cancelled'
        GROUP BY currency
    """,
        (agent_id,),
    )
    commissions = {row[0]: row[1] for row in cur.fetchall()}

    # ۳. بدهی‌های دقیق به عامل‌های دیگر (حواله‌های ارسالی که هنوز پرداخت نشده‌اند)
    cur.execute(
        """
        SELECT 
            a.name as receiver_name,
            t.currency,
            SUM(t.amount) as debt_amount
        FROM transactions t
        JOIN agents a ON t.receiver_agent_id = a.id
        WHERE t.agent_id = ? AND t.status = 'pending'
        GROUP BY t.receiver_agent_id, t.currency
    """,
        (agent_id,),
    )
    debts = cur.fetchall()

    # ۴. طلب‌های دقیق از عامل‌های دیگر (حواله‌های دریافتی که هنوز پرداخت نشده‌اند)
    cur.execute(
        """
        SELECT 
            a.name as sender_name,
            t.currency,
            SUM(t.amount) as credit_amount
        FROM transactions t
        JOIN agents a ON t.agent_id = a.id
        WHERE t.receiver_agent_id = ? AND t.status = 'pending'
        GROUP BY t.agent_id, t.currency
    """,
        (agent_id,),
    )
    credits = cur.fetchall()

    conn.close()

    # ساخت گزارش
    report = "📊 *گزارش مالی و عملکرد حرفه‌ای*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

    # ۱. درآمد خالص (کمیسیون شما)
    report += "💰 *۱. درآمد خالص (کمیسیون شما):*\n"
    report += "_(سود حاصل از ثبت حواله‌ها)_\n"
    if not commissions:
        report += "▫️ هنوز درآمدی ثبت نشده است.\n"
    for curr, comm in commissions.items():
        report += f"✅ {comm:,.0f} {curr}\n"
    report += "\n"

    # ۲. وضعیت بدهی‌ها
    report += "🔴 *۲. بدهی به سایر همکاران:*\n"
    report += "_(حواله‌های ارسالی شما که هنوز پرداخت نشده‌اند)_\n"
    if not debts:
        report += "✅ هیچ بدهی فعالی ندارید.\n"
    else:
        total_debts = {}
        for name, curr, amount in debts:
            report += f"▪️ {name}: {amount:,.0f} {curr}\n"
            total_debts[curr] = total_debts.get(curr, 0) + amount
        
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        for curr, total in total_debts.items():
            report += f"🚩 مجموع بدهی: {total:,.0f} {curr}\n"
    report += "\n"

    # ۳. وضعیت طلب‌ها
    report += "🔵 *۳. طلب از سایر همکاران:*\n"
    report += "_(حواله‌های دریافتی که باید توسط شما پرداخت شوند)_\n"
    if not credits:
        report += "▫️ طلب فعالی ندارید.\n"
    else:
        total_credits = {}
        for name, curr, amount in credits:
            report += f"▪️ {name}: {amount:,.0f} {curr}\n"
            total_credits[curr] = total_credits.get(curr, 0) + amount
        
        report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        for curr, total in total_credits.items():
            report += f"🔹 مجموع طلب: {total:,.0f} {curr}\n"
    report += "\n"

    # ۴. تراز نهایی
    report += "⚖️ *۴. تراز نهایی (Net Position):*\n"
    report += "_(تفاضل طلب و بدهی)_\n"
    
    all_currencies = set(list(commissions.keys()))
    if debts:
        all_currencies.update([d[1] for d in debts])
    if credits:
        all_currencies.update([c[1] for c in credits])
        
    for curr in sorted(all_currencies):
        debt_sum = sum(d[2] for d in debts if d[1] == curr)
        credit_sum = sum(c[2] for c in credits if c[1] == curr)
        net = credit_sum - debt_sum
        emoji = "📈" if net >= 0 else "📉"
        report += f"{emoji} {curr}: {net:,.0f}\n"
    report += "\n"

    # ۵. موجودی فعلی در صندوق
    report += "🏦 *۵. موجودی نقدی فعلی:*\n"
    report += "_(مبلغ فیزیکی موجود در حساب شما)_\n"
    if not balances:
        report += "▫️ موجودی ثبت نشده است.\n"
    for curr, bal in balances:
        report += f"💵 {bal:,.0f} {curr}\n"
    
    report += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    report += "📈 *خلاصه عملکرد:* گزارش فوق بر اساس آخرین تراکنش‌های ثبت شده در سیستم می‌باشد."

    keyboard = [["📊 نمایش گزارش کامل"], ["📥 دانلود گزارش اکسل"], ["💵 مدیریت موجودی"], ["🔙 بازگشت به منوی عامل"]]

    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )



@require_agent
async def download_excel_report(update, context):
    """تولید و ارسال گزارش اکسل کامل"""
    agent_id = context.user_data["agent_id"]
    
    await update.message.reply_text("📥 در حال آماده‌سازی گزارش اکسل...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # دریافت اطلاعات عامل
    cur.execute("SELECT name, province FROM agents WHERE id = ?", (agent_id,))
    agent_info = cur.fetchone()
    agent_name, agent_province = agent_info if agent_info else ("نامشخص", "نامشخص")
    
    # دریافت تمام حواله‌های عامل
    cur.execute(
        """
        SELECT 
            t.transaction_code,
            t.sender_name,
            t.receiver_name,
            t.receiver_tazkira,
            t.amount,
            t.currency,
            t.commission,
            t.status,
            t.created_at,
            t.completed_at,
            a.name as receiver_agent_name,
            a.province as receiver_province
        FROM transactions t
        LEFT JOIN agents a ON t.receiver_agent_id = a.id
        WHERE t.agent_id = ?
        ORDER BY t.created_at DESC
    """,
        (agent_id,),
    )
    transactions = cur.fetchall()
    
    # دریافت موجودی‌ها
    cur.execute(
        "SELECT currency, SUM(balance) FROM balances WHERE agent_id = ? GROUP BY currency ORDER BY currency",
        (agent_id,),
    )
    balances = cur.fetchall()
    
    conn.close()
    
    # ایجاد DataFrame برای حواله‌ها
    df_transactions = pd.DataFrame(transactions, columns=[
        'کد حواله', 'نام فرستنده', 'نام گیرنده', 'تذکره گیرنده',
        'مبلغ', 'ارز', 'کارمزد', 'وضعیت', 'تاریخ ثبت', 'تاریخ تکمیل',
        'عامل مقصد', 'ولایت مقصد'
    ])
    
    # ایجاد DataFrame برای موجودی‌ها
    df_balances = pd.DataFrame(balances, columns=['ارز', 'موجودی'])
    
    # ایجاد فایل اکسل با چند شیت
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # شیت اطلاعات عامل
            agent_data = {
                'نام عامل': [agent_name],
                'ولایت': [agent_province],
                'تاریخ گزارش': [dt.now().strftime('%Y-%m-%d %H:%M:%S')],
                'تعداد کل حواله‌ها': [len(transactions)]
            }
            pd.DataFrame(agent_data).to_excel(writer, sheet_name='اطلاعات عامل', index=False)
            
            # شیت حواله‌ها
            if not df_transactions.empty:
                df_transactions.to_excel(writer, sheet_name='حواله‌ها', index=False)
            
            # شیت موجودی‌ها
            if not df_balances.empty:
                df_balances.to_excel(writer, sheet_name='موجودی‌ها', index=False)
            
            # شیت خلاصه آمار
            if not df_transactions.empty:
                summary_data = {
                    'نوع آمار': [
                        'تعداد کل حواله‌ها',
                        'حواله‌های در انتظار',
                        'حواله‌های تکمیل شده',
                        'حواله‌های لغو شده',
                        'مجموع مبلغ حواله‌ها',
                        'مجموع کارمزد دریافتی'
                    ],
                    'مقدار': [
                        len(df_transactions),
                        len(df_transactions[df_transactions['وضعیت'] == 'pending']),
                        len(df_transactions[df_transactions['وضعیت'] == 'completed']),
                        len(df_transactions[df_transactions['وضعیت'] == 'cancelled']),
                        f"{df_transactions['مبلغ'].sum():,.0f}",
                        f"{df_transactions['کارمزد'].sum():,.0f}"
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='خلاصه آمار', index=False)
        
        output.seek(0)
        
        # ارسال فایل
        filename = f"گزارش_حواله‌ها_{agent_name}_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        await update.message.reply_document(
            document=output,
            filename=filename,
            caption=f"📊 *گزارش کامل حواله‌های شما*\n\n"
                    f"👤 عامل: {agent_name}\n"
                    f"📍 ولایت: {agent_province}\n"
                    f"📦 تعداد حواله‌ها: {len(transactions)}\n"
                    f"📅 تاریخ: {dt.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"فایل شامل چند شیت با اطلاعات کامل است.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Error creating agent excel report")
        await update.message.reply_text(f"❌ خطا در ایجاد گزارش اکسل: {str(e)}")


@require_agent
async def balance_management_menu(update, context):
    """منوی مدیریت موجودی"""
    text = update.message.text.strip() if update.message else ""

    # اگر دکمه بازگشت زده شد
    if text == "🔙 بازگشت به منوی عامل":
        await agent_menu(update, context)
        return

    keyboard = [
        ["➕ افزایش موجودی"],
        ["➖ کاهش موجودی"],
        ["💱 اضافه کردن ارز جدید"],
        ["🔙 بازگشت به منوی عامل"],
    ]

    await update.message.reply_text(
        "💵 *مدیریت موجودی*\n\nلطفاً یک گزینه انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


@require_agent
async def increase_balance_start(update, context):
    """شروع افزایش موجودی"""
    keyboard = [["🇦🇫 AFN", "🇺🇸 USD"], ["🔙 بازگشت"]]

    await update.message.reply_text(
        "💱 *افزایش موجودی*\n\nنوع ارز را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return INCREASE_BALANCE_CURRENCY


@require_agent
async def increase_balance_currency(update, context):
    """انتخاب ارز برای افزایش موجودی"""
    text = update.message.text.strip()

    if text == "🔙 بازگشت":
        await balance_management_menu(update, context)
        return ConversationHandler.END

    if "AFN" in text:
        currency = "AFN"
    elif "USD" in text:
        currency = "USD"
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return INCREASE_BALANCE_CURRENCY

    context.user_data["balance_currency"] = currency
    context.user_data["balance_operation"] = "increase"

    await update.message.reply_text(
        f"💰 مبلغ را وارد کنید ({currency}):",
        reply_markup=ReplyKeyboardRemove(),
    )

    return INCREASE_BALANCE_AMOUNT


@require_agent
async def increase_balance_amount(update, context):
    """دریافت مبلغ و درخواست عکس فیش"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد")
            return INCREASE_BALANCE_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
        return INCREASE_BALANCE_AMOUNT

    context.user_data["balance_amount"] = amount

    await update.message.reply_text(
        "📸 *ارسال عکس فیش*\n\nلطفاً عکس فیش واریزی یا سند پرداخت خود را ارسال کنید:",
        parse_mode="Markdown",
    )

    return INCREASE_BALANCE_PHOTO


@require_agent
async def increase_balance_photo(update, context):
    """دریافت عکس فیش و ثبت درخواست برای ادمین"""
    if not update.message.photo:
        await update.message.reply_text("❌ لطفاً یک عکس معتبر ارسال کنید.")
        return INCREASE_BALANCE_PHOTO

    photo_id = update.message.photo[-1].file_id
    agent_id = context.user_data["agent_id"]
    currency = context.user_data["balance_currency"]
    amount = context.user_data["balance_amount"]

    conn = get_db()
    cur = conn.cursor()

    try:
        # ثبت درخواست در جدول balance_requests
        cur.execute(
            """
            INSERT INTO balance_requests (agent_id, amount, currency, receipt_photo_id, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (agent_id, amount, currency, photo_id),
        )
        request_id = cur.lastrowid
        conn.commit()

        # اطلاع‌رسانی به ادمین (در صورت وجود)
        cur.execute("SELECT telegram_id FROM admins WHERE is_active = 1")
        admins = cur.fetchall()
        
        cur.execute("SELECT name FROM agents WHERE id = ?", (agent_id,))
        agent_name = cur.fetchone()[0]
        
        admin_notif = (
            "🔔 *درخواست شارژ حساب جدید*\n\n"
            f"👤 *عامل:* {agent_name}\n"
            f"💰 *مبلغ:* {amount:,.0f} {currency}\n"
            f"🆔 *شناسه درخواست:* `{request_id}`\n\n"
            "لطفاً برای بررسی به پنل مدیریت مراجعه کنید."
        )

        for admin_row in admins:
            if admin_row[0]:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_row[0],
                        photo=photo_id,
                        caption=admin_notif,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_row[0]}: {e}")

        conn.close()

        keyboard = [["🔙 بازگشت به منوی عامل"]]
        await update.message.reply_text(
            "✅ *درخواست شما با موفقیت ثبت شد.*\n\n"
            "پس از بررسی و تأیید توسط مدیریت، موجودی حساب شما شارژ خواهد شد.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        return ConversationHandler.END

    except Exception as e:
        if conn:
            conn.close()
        logger.exception("Error registering balance request")
        await update.message.reply_text("❌ خطا در ثبت درخواست. لطفاً بعداً تلاش کنید.")
        return ConversationHandler.END

        keyboard = [["➕ افزایش موجودی"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ موجودی با موفقیت افزایش یافت.\n\n"
            f"💰 مبلغ اضافه شده: {amount:,.0f} {currency}\n"
            f"🏦 موجودی جدید: {new_balance:,.0f} {currency}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        context.user_data.pop("balance_currency", None)
        context.user_data.pop("balance_operation", None)

        return ConversationHandler.END

    except Exception:
        conn.close()
        logger.exception("Error increasing balance")
        await update.message.reply_text("❌ خطا در افزایش موجودی")
        return ConversationHandler.END


@require_agent
async def decrease_balance_start(update, context):
    """شروع کاهش موجودی"""
    keyboard = [["🇦🇫 AFN", "🇺🇸 USD"], ["🔙 بازگشت"]]

    await update.message.reply_text(
        "💱 *کاهش موجودی*\n\nنوع ارز را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return DECREASE_BALANCE_CURRENCY


@require_agent
async def decrease_balance_currency(update, context):
    """دریافت نوع ارز برای کاهش موجودی"""
    text = update.message.text.strip()

    if text == "🔙 بازگشت":
        await balance_management_menu(update, context)
        return ConversationHandler.END

    if "AFN" in text:
        currency = "AFN"
    elif "USD" in text:
        currency = "USD"
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return DECREASE_BALANCE_CURRENCY

    agent_id = context.user_data["agent_id"]
    balance = get_agent_balance(agent_id, currency)

    if balance <= 0:
        keyboard = [["🔙 بازگشت"]]
        await update.message.reply_text(
            f"❌ موجودی شما در {currency} صفر است یا موجودی ندارید.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return DECREASE_BALANCE_CURRENCY

    context.user_data["balance_currency"] = currency
    context.user_data["balance_operation"] = "decrease"

    await update.message.reply_text(
        f"💰 مبلغ را وارد کنید ({currency}):\n"
        f"💵 موجودی فعلی: {balance:,.0f} {currency}",
        reply_markup=ReplyKeyboardRemove(),
    )

    return DECREASE_BALANCE_AMOUNT


@require_agent
async def decrease_balance_amount(update, context):
    """دریافت مبلغ و کاهش موجودی"""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید بیشتر از صفر باشد")
            return DECREASE_BALANCE_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
        return DECREASE_BALANCE_AMOUNT

    agent_id = context.user_data["agent_id"]
    currency = context.user_data["balance_currency"]

    # چک موجودی
    balance = get_agent_balance(agent_id, currency)
    if balance < amount:
        await update.message.reply_text(
            f"❌ موجودی شما کافی نیست.\n"
            f"💵 موجودی فعلی: {balance:,.0f} {currency}\n"
            f"💰 مبلغ درخواستی: {amount:,.0f} {currency}"
        )
        return DECREASE_BALANCE_AMOUNT

    conn = get_db()
    cur = conn.cursor()

    try:
        # کاهش موجودی
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

        new_balance = get_agent_balance(agent_id, currency)

        keyboard = [["➖ کاهش موجودی"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ موجودی با موفقیت کاهش یافت.\n\n"
            f"💰 مبلغ کسر شده: {amount:,.0f} {currency}\n"
            f"🏦 موجودی جدید: {new_balance:,.0f} {currency}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        context.user_data.pop("balance_currency", None)
        context.user_data.pop("balance_operation", None)

        return ConversationHandler.END

    except Exception:
        conn.close()
        logger.exception("Error decreasing balance")
        await update.message.reply_text("❌ خطا در کاهش موجودی")
        return ConversationHandler.END


@require_agent
async def add_currency_start(update, context):
    """شروع اضافه کردن ارز جدید"""
    agent_id = context.user_data["agent_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT currency
        FROM balances
        WHERE agent_id = ?
    """,
        (agent_id,),
    )
    existing_currencies = [row[0] for row in cur.fetchall()]
    conn.close()

    keyboard = []
    if "AFN" not in existing_currencies:
        keyboard.append(["🇦🇫 AFN"])
    if "USD" not in existing_currencies:
        keyboard.append(["🇺🇸 USD"])

    if not keyboard:
        await update.message.reply_text(
            "✅ شما همه ارزهای موجود را دارید.\n"
            "ارزهای شما: " + ", ".join(existing_currencies)
        )
        await balance_management_menu(update, context)
        return

    keyboard.append(["🔙 بازگشت"])

    await update.message.reply_text(
        "💱 *اضافه کردن ارز جدید*\n\nارز مورد نظر را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

    return ADD_CURRENCY_TYPE


@require_agent
async def add_currency_confirm(update, context):
    """تأیید و اضافه کردن ارز جدید"""
    text = update.message.text.strip()

    if text == "🔙 بازگشت":
        await balance_management_menu(update, context)
        return ConversationHandler.END

    if "AFN" in text:
        currency = "AFN"
    elif "USD" in text:
        currency = "USD"
    else:
        await update.message.reply_text("❌ لطفاً از دکمه‌ها استفاده کنید")
        return ADD_CURRENCY_TYPE

    agent_id = context.user_data["agent_id"]

    conn = get_db()
    cur = conn.cursor()

    try:
        # چک کن که قبلاً اضافه نشده باشد
        cur.execute(
            """
            SELECT id FROM balances
            WHERE agent_id = ? AND currency = ?
        """,
            (agent_id, currency),
        )
        if cur.fetchone():
            await update.message.reply_text(
                f"❌ ارز {currency} قبلاً اضافه شده است."
            )
            conn.close()
            await balance_management_menu(update, context)
            return

        # اضافه کردن ارز با موجودی صفر
        cur.execute(
            """
            INSERT INTO balances (agent_id, currency, balance)
            VALUES (?, ?, 0)
        """,
            (agent_id, currency),
        )

        conn.commit()
        conn.close()

        keyboard = [["➕ افزایش موجودی"], ["🔙 بازگشت به منوی عامل"]]

        await update.message.reply_text(
            f"✅ ارز {currency} با موفقیت اضافه شد.\n\n"
            f"💰 موجودی فعلی: 0 {currency}\n"
            f"💡 می‌توانید موجودی را افزایش دهید.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

        return ConversationHandler.END

    except Exception:
        conn.close()
        logger.exception("Error adding currency")
        await update.message.reply_text("❌ خطا در اضافه کردن ارز")
        return ConversationHandler.END


@require_agent
async def search_advanced_start(update, context):
    """شروع جستجوی پیشرفته"""
    keyboard = [
        ["👤 جستجو بر اساس نام گیرنده"],
        ["📦 جستجو بر اساس کد حواله"],
        ["📅 جستجو بر اساس تاریخ (امروز)"],
        ["🔙 بازگشت به منوی عامل"]
    ]
    await update.message.reply_text(
        "🔍 *جستجوی پیشرفته*\n\nلطفاً پارامتر جستجو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SEARCH_TYPE

@require_agent
async def search_advanced_type(update, context):
    """انتخاب نوع جستجو"""
    choice = update.message.text.strip()
    
    if choice == "🔙 بازگشت به منوی عامل":
        await agent_menu(update, context)
        return ConversationHandler.END
        
    context.user_data["search_type"] = choice
    
    if "نام گیرنده" in choice:
        await update.message.reply_text("👤 نام گیرنده را وارد کنید (قسمتی از نام هم قابل قبول است):", reply_markup=ReplyKeyboardRemove())
        return SEARCH_QUERY
    elif "کد حواله" in choice:
        await update.message.reply_text("📦 کد حواله را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return SEARCH_QUERY
    elif "تاریخ (امروز)" in choice:
        # جستجوی مستقیم برای امروز
        return await search_advanced_results(update, context, query=dt.now().strftime('%Y-%m-%d'))
    else:
        await update.message.reply_text("❌ گزینه نامعتبر")
        return SEARCH_TYPE

@require_agent
async def search_advanced_results(update, context, query=None):
    """نمایش نتایج جستجو"""
    if not query:
        query = update.message.text.strip()
    
    search_type = context.user_data.get("search_type", "")
    agent_id = context.user_data.get("agent_id")
    
    conn = get_db()
    cur = conn.cursor()
    
    sql = """
        SELECT t.transaction_code, t.receiver_name, t.amount, t.currency, t.status, t.created_at
        FROM transactions t
        WHERE (t.agent_id = ? OR t.receiver_agent_id = ?)
    """
    params = [agent_id, agent_id]
    
    if "نام گیرنده" in search_type:
        sql += " AND t.receiver_name LIKE ?"
        params.append(f"%{query}%")
    elif "کد حواله" in search_type:
        sql += " AND t.transaction_code = ?"
        params.append(query.upper())
    elif "تاریخ" in search_type:
        sql += " AND t.created_at LIKE ?"
        params.append(f"{query}%")
        
    sql += " ORDER BY t.created_at DESC LIMIT 10"
    
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("🔍 متأسفانه نتیجه‌ای یافت نشد.")
        await agent_menu(update, context)
        return ConversationHandler.END
        
    text = f"🔎 *نتایج جستجو برای: {query}*\n\n"
    keyboard = []
    for code, name, amount, currency, status, created_at in results:
        status_emoji = "🟢" if status == 'completed' else "🟡" if status == 'pending' else "🔴"
        text += f"{status_emoji} `{code}` | {name}\n"
        text += f"💰 {amount:,.0f} {currency} | 📅 {created_at[:16]}\n"
        text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        keyboard.append([InlineKeyboardButton(f"🧾 رسید {code}", callback_data=f"get_receipt_{code}")])
        
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    await agent_menu(update, context)
    return ConversationHandler.END

@require_any_auth
async def handle_receipt_callback(update, context):
    """هندلر دکمه شیشه‌ای دانلود رسید"""
    query = update.callback_query
    await query.answer()
    
    code = query.data.replace("get_receipt_", "")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.transaction_code, t.sender_name, t.receiver_name, t.receiver_tazkira, 
               t.amount, t.currency, t.created_at,
               a_sender.name as sender_agent_name, a_receiver.name as receiver_agent_name
        FROM transactions t
        JOIN agents a_sender ON t.agent_id = a_sender.id
        JOIN agents a_receiver ON t.receiver_agent_id = a_receiver.id
        WHERE t.transaction_code = ?
    """, (code,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await query.message.reply_text("❌ اطلاعات حواله یافت نشد.")
        return

    receipt_data = {
        'transaction_code': row[0],
        'sender_name': row[1],
        'receiver_name': row[2],
        'receiver_tazkira': row[3],
        'amount': row[4],
        'currency': row[5],
        'sender_agent': row[7],
        'receiver_agent': row[8],
        'created_at': row[6],
    }
    
    try:
        receipt_img = generate_receipt_image(receipt_data)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=receipt_img,
            caption=f"🧾 *رسید مجدد حواله {code}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error sending receipt: {e}")
        await query.message.reply_text("❌ خطا در تولید رسید.")


@require_agent
async def handle_pay_fast_callback(update, context):
    """هندلر دکمه شیشه‌ای پرداخت سریع"""
    query = update.callback_query
    await query.answer()
    
    code = query.data.replace("pay_fast_", "")
    
    # انتقال به جریان پرداخت
    context.user_data["pay_transaction_code"] = code
    
    # فراخوانی هندلر موجود برای شروع پرداخت
    # توجه: چون در همین فایل هستیم، مستقیم فراخوانی می‌کنیم
    return await pay_transaction_start(update, context)

# =======================
# 🚪 خروج عامل
# =======================


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
