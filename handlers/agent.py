from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import db
import random
import datetime

# -------- STATES --------
BALANCE_ACTION, BALANCE_CURRENCY, BALANCE_AMOUNT = range(3)
SENDER, RECEIVER, AMOUNT, CURRENCY, PROVINCE = range(5)
TRACK_CODE = 10
CONFIRM_CODE, CONFIRM_ID = range(20, 22)
EDIT_CODE, EDIT_AMOUNT, EDIT_CURRENCY, EDIT_PROVINCE = range(30, 34)
DELETE_CODE, DELETE_CONFIRM = range(40, 42)


# -------- HELPERS --------
def is_agent(context):
    return context.user_data.get("user", {}).get("role") == "agent"


def generate_code():
    return f"H{random.randint(100000, 999999)}"


# ================== REGISTER HAWALA ==================


async def start_hawala(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_agent(context):
        await update.message.reply_text("⛔ فقط عامل مجاز است")
        return ConversationHandler.END

    await update.message.reply_text("👤 نام فرستنده:")
    return SENDER


async def get_sender(update, context):
    context.user_data["sender"] = update.message.text.strip()
    await update.message.reply_text("👤 نام گیرنده:")
    return RECEIVER


async def get_receiver(update, context):
    context.user_data["receiver"] = update.message.text.strip()
    await update.message.reply_text("💵 مبلغ:")
    return AMOUNT


async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبر است")
        return AMOUNT

    context.user_data["amount"] = amount

    await update.message.reply_text(
        "💱 ارز حواله را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["AFN", "USD"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return CURRENCY


async def get_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()
    if currency not in ("AFN", "USD"):
        await update.message.reply_text("❌ ارز نامعتبر است")
        return CURRENCY

    user = context.user_data["user"]
    amount = context.user_data["amount"]

    balances = db.get_agent_balance(user["id"])
    available = balances.get(currency, 0)

    if amount > available:
        await update.message.reply_text(
            f"❌ موجودی کافی نیست\n💰 موجودی شما: {available} {currency}"
        )
        return CURRENCY

    context.user_data["currency"] = currency
    await update.message.reply_text("📍 استان مقصد را وارد کنید:")
    return PROVINCE


async def get_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data["user"]
    code = generate_code()

    amount = context.user_data["amount"]
    currency = context.user_data["currency"]
    to_province = update.message.text.strip()

    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO hawalas
        (code, sender_name, receiver_name, amount, currency,
         from_province, to_province, created_by, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """,
        (
            code,
            context.user_data["sender"],
            context.user_data["receiver"],
            amount,
            currency,
            user["province"],
            to_province,
            user["id"],
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )

    field = "cash_afn" if currency == "AFN" else "cash_usd"
    cur.execute(
        f"""
        UPDATE users
        SET {field} = {field} - ?
        WHERE id = ?
    """,
        (amount, user["id"]),
    )

    conn.commit()
    conn.close()

    db.log_finance(
        username=user["username"],
        ftype="out",
        amount=amount,
        currency=currency,
        desc=f"ثبت حواله {code}",
    )

    await update.message.reply_text(
        f"✅ حواله ثبت شد\n\n"
        f"🔑 {code}\n"
        f"👤 {context.user_data['sender']} ➜ {context.user_data['receiver']}\n"
        f"💵 {amount} {currency}\n"
        f"📍 مقصد: {to_province}"
    )

    from handlers.menu import show_menu

    await show_menu(update, context)

    return ConversationHandler.END


# ================== TRACK HAWALA ==================


async def start_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_agent(context):
        await update.message.reply_text("⛔ دسترسی ندارید")
        return ConversationHandler.END

    await update.message.reply_text("🔎 کد حواله را وارد کنید:")
    return TRACK_CODE


async def track_hawala(update, context):
    code = update.message.text.strip()

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sender_name, receiver_name, amount, currency, to_province, status
        FROM hawalas
        WHERE code=?
    """,
        (code,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ حواله پیدا نشد")
        return ConversationHandler.END

    await update.message.reply_text(
        f"📄 اطلاعات حواله:\n\n"
        f"🔑 کد: {code}\n"
        f"👤 {row[0]} ➜ {row[1]}\n"
        f"💵 {row[2]} {row[3]}\n"
        f"📍 مقصد: {row[4]}\n"
        f"📌 وضعیت: {row[5]}"
    )

    return ConversationHandler.END


# ================== CONFIRM HAWALA ==================


async def start_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_agent(context):
        await update.message.reply_text("⛔ دسترسی ندارید")
        return ConversationHandler.END

    await update.message.reply_text("🔑 کد حواله:")
    return CONFIRM_CODE


async def get_confirm_code(update, context):
    context.user_data["confirm_code"] = update.message.text.strip()
    await update.message.reply_text("🆔 شماره تذکره گیرنده:")
    return CONFIRM_ID


async def confirm_hawala(update, context):
    code = context.user_data["confirm_code"]
    agent = context.user_data["user"]

    conn = db.get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, to_province, status, amount, currency
        FROM hawalas
        WHERE code=?
    """,
        (code,),
    )
    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ حواله پیدا نشد")
        conn.close()
        return ConversationHandler.END

    hawala_id, to_province, status, amount, currency = row

    if to_province != agent["province"]:
        await update.message.reply_text("❌ این حواله مربوط به استان شما نیست")
        conn.close()
        return ConversationHandler.END

    if status == "paid":
        await update.message.reply_text("ℹ️ این حواله قبلاً تسویه شده")
        conn.close()
        return ConversationHandler.END

    cur.execute(
        """
        UPDATE hawalas
        SET status='paid', paid_by=?
        WHERE id=?
    """,
        (agent["id"], hawala_id),
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ حواله تسویه شد\n" f"💵 {amount} {currency}")

    return ConversationHandler.END


# ================== LIST MY HAWALAS ==================


async def list_my_hawalas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_agent(context):
        await update.message.reply_text("⛔ دسترسی ندارید")
        return

    user = context.user_data["user"]

    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT code, sender_name, receiver_name, amount, currency, status
        FROM hawalas
        WHERE created_by=?
        ORDER BY id DESC
        LIMIT 20
    """,
        (user["id"],),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 حواله‌ای ثبت نکرده‌اید")
        return

    text = "📋 حواله‌های شما:\n\n"
    for r in rows:
        text += (
            f"🔑 {r[0]}\n"
            f"👤 {r[1]} ➜ {r[2]}\n"
            f"💵 {r[3]} {r[4]}\n"
            f"📌 {r[5]}\n"
            "────────────\n"
        )

    await update.message.reply_text(text)


# ================== MANAGE BALANCE ==================


async def start_manage_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_agent(context):
        await update.message.reply_text("⛔ دسترسی ندارید")
        return ConversationHandler.END

    await update.message.reply_text(
        "⚙️ مدیریت موجودی:\n\n" "چه کاری می‌خواهید انجام دهید؟",
        reply_markup=ReplyKeyboardMarkup(
            [["➕ افزایش موجودی"], ["➖ کاهش موجودی"], ["🏠 صفحه اصلی"]],
            resize_keyboard=True,
        ),
    )
    return BALANCE_ACTION


async def handle_balance_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "🏠 صفحه اصلی":
        from handlers.menu import show_menu

        await show_menu(update, context)
        return ConversationHandler.END

    if text not in ("➕ افزایش موجودی", "➖ کاهش موجودی"):
        await update.message.reply_text("❌ گزینه نامعتبر است")
        return BALANCE_ACTION

    context.user_data["balance_action"] = "add" if "افزایش" in text else "sub"

    await update.message.reply_text(
        "💱 ارز را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["AFN", "USD"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return BALANCE_CURRENCY


async def handle_balance_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()

    if currency not in ("AFN", "USD"):
        await update.message.reply_text("❌ ارز نامعتبر")
        return BALANCE_CURRENCY

    context.user_data["balance_currency"] = currency
    await update.message.reply_text("💵 مبلغ را وارد کنید:")
    return BALANCE_AMOUNT


async def handle_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبر است")
        return BALANCE_AMOUNT

    user = context.user_data["user"]
    action = context.user_data["balance_action"]
    currency = context.user_data["balance_currency"]

    balances = db.get_agent_balance(user["id"])
    current = balances[currency]

    if action == "sub" and amount > current:
        await update.message.reply_text(
            f"❌ موجودی کافی نیست\n" f"💰 موجودی فعلی: {current} {currency}"
        )
        return BALANCE_AMOUNT

    final_amount = amount if action == "add" else -amount
    db.update_agent_balance(user["id"], currency, final_amount)

    await update.message.reply_text(
        "✅ موجودی با موفقیت بروزرسانی شد\n\n"
        f"💱 ارز: {currency}\n"
        f"💵 تغییر: {'+' if action == 'add' else '-'}{amount}\n"
        f"💰 موجودی جدید: {db.get_agent_balance(user['id'])[currency]} {currency}",
        reply_markup=ReplyKeyboardMarkup([["🏠 صفحه اصلی"]], resize_keyboard=True),
    )

    return ConversationHandler.END


async def start_edit_hawala(update, context):
    user = context.user_data.get("user")
    if user["role"] != "agent":
        await update.message.reply_text("⛔ دسترسی ندارید")
        return ConversationHandler.END

    await update.message.reply_text("🔑 کد حواله برای ویرایش:")
    return EDIT_CODE


async def get_edit_code(update, context):
    code = update.message.text.strip()
    user = context.user_data["user"]

    hawala = db.get_hawala_for_edit(code, user["id"])
    if not hawala:
        await update.message.reply_text("❌ حواله قابل ویرایش نیست")
        return ConversationHandler.END

    context.user_data["edit_code"] = code
    await update.message.reply_text("💵 مبلغ جدید:")
    return EDIT_AMOUNT


async def get_edit_amount(update, context):
    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ مبلغ نامعتبر")
        return EDIT_AMOUNT

    context.user_data["edit_amount"] = amt
    await update.message.reply_text(
        "💱 ارز:",
        reply_markup=ReplyKeyboardMarkup(
            [["AFN", "USD"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return EDIT_CURRENCY


async def get_edit_currency(update, context):
    cur = update.message.text.strip().upper()
    if cur not in ("AFN", "USD"):
        await update.message.reply_text("❌ ارز نامعتبر")
        return EDIT_CURRENCY

    context.user_data["edit_currency"] = cur
    await update.message.reply_text("📍 استان مقصد:")
    return EDIT_PROVINCE


async def save_edit(update, context):
    db.update_hawala(
        code=context.user_data["edit_code"],
        amount=context.user_data["edit_amount"],
        currency=context.user_data["edit_currency"],
        province=update.message.text.strip(),
    )
    await update.message.reply_text("✅ حواله ویرایش شد")
    from handlers.menu import show_menu

    await show_menu(update, context)
    return ConversationHandler.END


async def start_delete_hawala(update, context):
    user = context.user_data["user"]
    if user["role"] != "agent":
        await update.message.reply_text("⛔ دسترسی ندارید")
        return ConversationHandler.END

    await update.message.reply_text("🔑 کد حواله برای حذف:")
    return DELETE_CODE


async def get_delete_code(update, context):
    code = update.message.text.strip()
    user = context.user_data["user"]

    hawala = db.get_hawala_for_edit(code, user["id"])
    if not hawala:
        await update.message.reply_text("❌ حواله قابل حذف نیست")
        return ConversationHandler.END

    context.user_data["delete_code"] = code
    await update.message.reply_text(
        "⚠️ مطمئن هستید؟",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ بله", "❌ خیر"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return DELETE_CONFIRM


async def confirm_delete(update, context):
    if update.message.text != "✅ بله":
        await update.message.reply_text("❎ لغو شد")
        return ConversationHandler.END

    db.delete_hawala(context.user_data["delete_code"])
    await update.message.reply_text("🗑 حواله حذف شد")
    from handlers.menu import show_menu

    await show_menu(update, context)
    return ConversationHandler.END
