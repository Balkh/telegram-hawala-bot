from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging
import bcrypt
import db

# -------- STATES --------
CREATE_USERNAME, CREATE_PASSWORD, CREATE_PROVINCE, CREATE_BALANCE, CREATE_CURRENCY = (
    range(5)
)


# -------- START CREATE AGENT --------
async def start_create_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get("user")
    if not user or user.get("role") != "admin":
        await update.message.reply_text("❌ دسترسی غیرمجاز")
        return ConversationHandler.END

    # پاکسازی داده‌های قبلی و نگه داشتن شیء user برای ادامه
    context.user_data.clear()
    context.user_data["user"] = user

    await update.message.reply_text("👤 نام کاربری عامل را وارد کنید:")
    return CREATE_USERNAME


# -------- USERNAME --------
async def get_agent_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()

    if db.get_user_by_username(username):
        await update.message.reply_text("❌ این نام کاربری قبلاً وجود دارد")
        return CREATE_USERNAME

    context.user_data["new_agent_username"] = username
    await update.message.reply_text("🔑 رمز عبور عامل را وارد کنید:")
    return CREATE_PASSWORD


# -------- PASSWORD --------
async def get_agent_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()

    if len(password) < 4:
        await update.message.reply_text("❌ رمز عبور باید حداقل ۴ کاراکتر باشد")
        return CREATE_PASSWORD

    # موقتاً رمز خام را نگه می‌داریم تا هنگام ذخیره یک‌بار هش شود.
    context.user_data["new_agent_password_plain"] = password

    await update.message.reply_text("📍 نام استان عامل را وارد کنید (مثلاً kabul):")
    return CREATE_PROVINCE


# -------- PROVINCE --------
async def get_agent_province(update: Update, context: ContextTypes.DEFAULT_TYPE):
    province = update.message.text.strip().lower()
    context.user_data["new_agent_province"] = province

    await update.message.reply_text("💰 موجودی اولیه عامل را وارد کنید:")
    return CREATE_BALANCE


# -------- BALANCE --------
async def get_agent_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = int(update.message.text.strip())
        if balance < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ موجودی باید عدد صحیح و مثبت باشد")
        return CREATE_BALANCE

    context.user_data["new_agent_balance"] = balance

    await update.message.reply_text(
        "💱 ارز موجودی را وارد کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["AFN", "USD"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return CREATE_CURRENCY


# -------- CURRENCY & SAVE --------
async def create_agent_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = update.message.text.strip().upper()
    if currency not in ("AFN", "USD"):
        await update.message.reply_text("❌ فقط AFN یا USD مجاز است")
        return CREATE_CURRENCY

    data = context.user_data

    # اعتبارسنجی مقدماتی فیلدها
    username = data.get("new_agent_username")
    plain = data.get("new_agent_password_plain")
    province = data.get("new_agent_province")
    balance = data.get("new_agent_balance")

    if not username or not plain or not province or balance is None:
        await update.message.reply_text("❌ اطلاعات ناقص است. عملیات لغو شد.")
        logging.warning(
            "create_agent_currency: missing data in context.user_data: %s", data.keys()
        )
        data.pop("new_agent_password_plain", None)
        return ConversationHandler.END

    # هش کردن دقیقاً یک بار
    try:
        password_hash = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    except Exception:
        await update.message.reply_text(
            "❌ خطا در پردازش رمز عبور. لطفاً دوباره تلاش کنید."
        )
        logging.exception("Error hashing password for new agent %s", username)
        return ConversationHandler.END

    # حذف رمز خام از حافظهٔ context بلافاصله
    data.pop("new_agent_password_plain", None)

    # آخرین ولیدیشن نوعیِ balance
    try:
        balance_int = int(balance)
    except Exception:
        await update.message.reply_text("❌ موجودی نامعتبر است.")
        logging.warning("Invalid balance type for new agent %s: %r", username, balance)
        return ConversationHandler.END

    # فراخوانی DB با هندلینگ خطا و لاگ مناسب
    try:
        db.create_agent(
            username=username,
            password_hash=password_hash,
            province=province,
            balance=balance_int,
            currency=currency,
        )
    except Exception:
        logging.exception("Failed to create agent %s", username)
        await update.message.reply_text("❌ خطا هنگام ایجاد عامل. لطفاً بعداً تلاش کنید.")
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ عامل با موفقیت ایجاد شد",
        reply_markup=ReplyKeyboardMarkup([["📍 منوی اصلی"]], resize_keyboard=True),
    )
    return ConversationHandler.END


async def admin_financial_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get("user")
    if not user or user.get("role") != "admin":
        await update.message.reply_text("⛔ دسترسی ندارید")
        return

    agents = db.get_all_agents()

    report = "📊 گزارش مالی کلی عامل‌ها\n\n"

    for a in agents:
        # پشتیبانی از دو فرم خروجی db.get_all_agents: dict یا tuple
        if isinstance(a, dict):
            agent_id = a.get("id") or a.get("agent_id")
            username = a.get("username", "—")
            province = a.get("province", "—")
        else:
            try:
                agent_id, username, province = a[0], a[1], a[2]
            except Exception:
                continue

        sent = db.sum_sent_by_agent(agent_id) or 0
        paid = db.sum_paid_by_agent(agent_id) or 0
        net = sent - paid

        if net > 0:
            status = f"🟢 طلبکار: {net:,.0f}"
        elif net < 0:
            status = f"🔴 بدهکار: {abs(net):,.0f}"
        else:
            status = "⚪ تسویه"

        report += (
            f"👤 عامل: {username}\n"
            f"📍 استان: {province}\n"
            f"📤 ارسال: {sent:,.0f}\n"
            f"📥 پرداخت: {paid:,.0f}\n"
            f"{status}\n"
            "──────────────\n"
        )

    await update.message.reply_text(report)


async def list_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data.get("user")

    if not user or user.get("role") != "admin":
        await update.message.reply_text("⛔ دسترسی ندارید")
        return

    agents = db.get_all_agents()

    if not agents:
        await update.message.reply_text("📭 هیچ عاملی ثبت نشده است")
        return

    text = "👥 لیست عامل‌ها:\n\n"

    for a in agents:
        if isinstance(a, dict):
            username = a.get("username", "—")
            province = a.get("province", "—")
            balance = a.get("balance", 0)
            currency = a.get("currency", "—")
            is_active = a.get("is_active", False)
        else:
            try:
                username = a[1]
                province = a[2]
                balance = a[3]
                currency = a[4]
                is_active = a[5]
            except Exception:
                username = str(a)
                province = balance = currency = "—"
                is_active = False

        text += (
            f"👤 {username}\n"
            f"📍 استان: {province}\n"
            f"💰 موجودی: {balance} {currency}\n"
            f"📌 وضعیت: {'فعال' if is_active else 'غیرفعال'}\n"
            "──────────────\n"
        )

    await update.message.reply_text(text)
