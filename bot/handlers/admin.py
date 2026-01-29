# bot/handlers/admin.py
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler
import logging

from bot.services.errors import global_error_handler
from bot.services.security import hash_password
from bot.services.database import get_db
from bot.services.auth import require_admin

logger = logging.getLogger(__name__)

# حالت‌های مکالمه - اصلاح شده: همه در یک رنج
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
    TOGGLE_AGENT,  # منتقل شده به اینجا
) = range(10)

# =======================
# 👑 منوی ادمین
# =======================


@require_admin
async def admin_menu(update, context):
    keyboard = [
        ["➕ ایجاد عامل", "📋 لیست عامل‌ها"],
        ["⛔ فعال / غیرفعال عامل"],
        ["🚪 خروج"],
    ]

    await update.message.reply_text(
        "👑 منوی ادمین",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


@require_admin
async def admin_logout(update, context):
    context.user_data.pop("admin_id", None)
    await update.message.reply_text("🚪 از حساب ادمین خارج شدید\n/start")


# =======================
# ➕ شروع ایجاد عامل
# =======================
@require_admin
async def create_agent_start(update, context):
    """
    شروع فرآیند ایجاد عامل توسط ادمین
    """
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
            "❌ پسوردها یکسان نیست\n" "🔐 لطفاً دوباره پسورد را وارد کنید:"
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
            "❌ شماره تذکره باید فقط عدد باشد\n" "لطفاً دوباره وارد کنید:"
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
                "❌ این شماره تذکره قبلاً ثبت شده\n" "🏠 برای بازگشت /start"
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
    """دریافت ارز از کاربر - این تابع جا افتاده بود!"""
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
        await update.message.reply_text("❌ عملیات لغو شد\n🏠 /start")
        return ConversationHandler.END

    if text != "✅ تأیید":
        await update.message.reply_text("❗ لطفاً یکی از دکمه‌ها را انتخاب کنید")
        return CONFIRM_AGENT

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
            f"✅ عامل با موفقیت ثبت شد\n" f"🆔 کد عامل: {agent_id}\n" f"🏠 /start"
        )
        return ConversationHandler.END

    except Exception as e:
        logger.exception("Error in confirm_agent")
        await update.message.reply_text("❌ خطا هنگام ثبت عامل\n🏠 /start")
        return ConversationHandler.END


@require_admin
async def list_agents(update, context):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name, province, is_active FROM agents")
    agents = cur.fetchall()
    conn.close()

    if not agents:
        await update.message.reply_text("📭 هیچ عاملی ثبت نشده")
        return

    text = "📋 لیست عامل‌ها:\n\n"
    for agent_id, name, province, is_active in agents:
        status = "✅ فعال" if is_active else "⛔ غیرفعال"
        text += f"🆔 {agent_id} | {name} | {province} | {status}\n"

    await update.message.reply_text(text)


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
            f"🔄 وضعیت عامل با شناسه {agent_id} {status_text}\n🏠 /start"
        )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ شناسه باید عدد باشد\n🏠 /start")
        return ConversationHandler.END
    except Exception as e:
        logger.exception("Error in toggle_agent_by_id")
        await global_error_handler(update, context, "❌ خطا در تغییر وضعیت عامل")
        return ConversationHandler.END
