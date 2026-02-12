from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler
import logging
from datetime import datetime as dt

from bot.services.database import get_db
from bot.services.auth import require_admin
from bot.handlers.admin import admin_menu

logger = logging.getLogger(__name__)

# حالت‌های مکالمه برای مدیریت مالی
FINANCE_MENU, TRANSFER_AMOUNT, TRANSFER_CONFIRM = range(3)


# =======================
# 💰 مدیریت مالی مرکزی
# =======================


@require_admin
async def central_finance_menu(update, context):
    """منوی مدیریت مالی مرکزی"""
    await update.message.reply_text("💰 در حال آماده‌سازی گزارش مالی مرکزی...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # کل موجودی سیستم بر اساس ارز
    cur.execute("""
        SELECT currency, SUM(balance) as total_balance
        FROM balances
        GROUP BY currency
        ORDER BY total_balance DESC
    """)
    system_balances = cur.fetchall()
    
    # آمار کل سیستم
    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT agent_id || currency) FROM balances")
    total_balance_records = cur.fetchone()[0]
    
    # عامل‌ها با موجودی کم (زیر ۱۰۰۰ افغانی)
    cur.execute("""
        SELECT a.name, a.province, SUM(b.balance) as total_balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1 AND b.currency = 'AFN'
        GROUP BY a.id, b.currency
        HAVING total_balance < 1000
        ORDER BY total_balance ASC
        LIMIT 5
    """)
    low_balance_agents = cur.fetchall()
    
    # عامل‌ها با موجودی بالا (بالای ۱۰۰۰۰ افغانی)
    cur.execute("""
        SELECT a.name, a.province, SUM(b.balance) as total_balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1 AND b.currency = 'AFN'
        GROUP BY a.id, b.currency
        HAVING total_balance > 10000
        ORDER BY total_balance DESC
        LIMIT 5
    """)
    high_balance_agents = cur.fetchall()
    
    conn.close()
    
    # ساخت گزارش مالی مرکزی
    report = "💰 *مدیریت مالی مرکزی*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    # کل موجودی سیستم
    report += "🏦 *کل موجودی سیستم:*\n"
    total_system_value = 0
    for currency, balance in system_balances:
        if balance:
            if currency == "AFN":
                total_system_value += balance
                report += f"   🇦🇫 {currency}: {balance:,.0f}\n"
            else:
                # فرض می‌کنیم USD به نرخ ۱۰۰ افغانی تبدیل می‌شود
                usd_value = balance * 100
                total_system_value += usd_value
                report += f"   🇺🇸 {currency}: {balance:,.0f} (~{usd_value:,.0f} افغانی)\n"
    
    report += f"   💎 ارزش کل سیستم: {total_system_value:,.0f} افغانی\n\n"
    
    # آمار کلی
    report += "📊 *آمار کلی:*\n"
    report += f"   👥 عامل‌های فعال: {active_agents}\n"
    report += f"   📋 رکوردهای موجودی: {total_balance_records}\n\n"
    
    # هشدار موجودی کم
    if low_balance_agents:
        report += "⚠️ *عامل‌های با موجودی کم (زیر ۱۰۰۰ افغانی):*\n"
        for name, province, balance, currency in low_balance_agents:
            report += f"   🔴 {name} ({province}): {balance:,.0f} {currency}\n"
        report += "\n"
    
    # عامل‌های با موجودی بالا
    if high_balance_agents:
        report += "💎 *عامل‌های با موجودی بالا (بالای ۱۰۰۰۰ افغانی):*\n"
        for name, province, balance, currency in high_balance_agents:
            report += f"   🟢 {name} ({province}): {balance:,.0f} {currency}\n"
        report += "\n"
    
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    keyboard = [
        ["💸 انتقال وجه بین عامل‌ها", "📊 جزئیات کامل موجودی‌ها"],
        ["⚠️ هشدارها و اطلاعیه‌ها", "🏥 بررسی سلامت سیستم"],
        ["🔙 بازگشت به منوی ادمین"]
    ]
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def detailed_balances(update, context):
    """جزئیات کامل موجودی‌ها"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.id, a.name, a.province, a.is_active,
               b.currency, b.balance
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        ORDER BY a.id, b.currency
    """)
    all_balances = cur.fetchall()
    conn.close()
    
    if not all_balances:
        await update.message.reply_text("❌ هیچ موجودی ثبت نشده است")
        return
    
    # گروه‌بندی بر اساس عامل
    agents_dict = {}
    for agent_id, name, province, is_active, currency, balance in all_balances:
        if agent_id not in agents_dict:
            agents_dict[agent_id] = {
                'name': name,
                'province': province,
                'is_active': is_active,
                'balances': {}
            }
        
        if currency and balance is not None:
            agents_dict[agent_id]['balances'][currency] = balance
    
    # ساخت گزارش
    report = "📊 *جزئیات کامل موجودی‌ها*\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    total_afn = 0
    total_usd = 0
    active_count = 0
    
    for agent_id, data in agents_dict.items():
        status = "🟢" if data['is_active'] else "🔴"
        if data['is_active']:
            active_count += 1
        
        report += f"{status} `#{agent_id:03d}` | **{data['name']}** ({data['province']})\n"
        
        balances_text = []
        for currency, balance in data['balances'].items():
            if currency == "AFN":
                total_afn += balance
                balances_text.append(f"💰 {balance:,.0f} {currency}")
            elif currency == "USD":
                total_usd += balance
                balances_text.append(f"💵 {balance:,.0f} {currency}")
        
        if balances_text:
            report += f"   {' | '.join(balances_text)}\n"
        else:
            report += f"   ❌ بدون موجودی\n"
        
        report += "\n"
    
    # خلاصه کل
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    report += f"📊 *خلاصه کل:*\n"
    report += f"   👥 عامل‌های فعال: {active_count}\n"
    report += f"   💰 مجموع AFN: {total_afn:,.0f}\n"
    report += f"   💵 مجموع USD: {total_usd:,.0f}\n"
    
    keyboard = [
        ["💰 مدیریت مالی مرکزی", "🔙 بازگشت به منوی ادمین"]
    ]
    
    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def start_transfer_funds(update, context):
    """شروع انتقال وجه بین عامل‌ها"""
    await update.message.reply_text(
        "💸 *انتقال وجه بین عامل‌ها*\n\n"
        "🆔 شناسه عامل مبدأ را وارد کنید:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    return TRANSFER_AMOUNT


@require_admin
async def get_transfer_amount(update, context):
    """دریافت شناسه عامل مبدأ"""
    conn = None
    try:
        from_agent_id = int(update.message.text.strip())
        
        conn = get_db()
        cur = conn.cursor()
        
        # بررسی وجود عامل مبدأ
        cur.execute("SELECT name, is_active FROM agents WHERE id = ?", (from_agent_id,))
        from_agent = cur.fetchone()
        
        if not from_agent:
            await update.message.reply_text("❌ عاملی با این شناسه پیدا نشد")
            return TRANSFER_AMOUNT
        
        from_name, is_active = from_agent
        if not is_active:
            await update.message.reply_text("❌ عامل مبدأ غیرفعال است")
            return TRANSFER_AMOUNT
        
        # دریافت موجودی‌های عامل مبدأ (تجمیع شده بر اساس ارز)
        cur.execute("""
            SELECT currency, SUM(balance) as total_balance FROM balances 
            WHERE agent_id = ? 
            GROUP BY currency
            HAVING total_balance > 0
            ORDER BY currency
        """, (from_agent_id,))
        from_balances = cur.fetchall()
        
        if not from_balances:
            await update.message.reply_text("❌ عامل مبدأ موجودی ندارد")
            return TRANSFER_AMOUNT
        
        # ذخیره اطلاعات تجمیع شده در context
        context.user_data["transfer_from_agent_id"] = from_agent_id
        context.user_data["transfer_from_name"] = from_name
        context.user_data["transfer_from_balances"] = from_balances
        
        # نمایش موجودی‌ها
        balance_text = f"💰 *موجودی عامل مبدأ: {from_name}*\n\n"
        
        # ایجاد کیبورد برای انتخاب ارز (دکمه‌ها کنار هم)
        currency_row = []
        for currency, balance in from_balances:
            balance_text += f"• {currency}: {balance:,.0f}\n"
            currency_row.append(f"💱 {currency}")
        
        balance_text += "\n💵 لطفاً ارز مورد نظر برای انتقال را انتخاب کنید یا مبلغ را وارد کنید:"
        
        keyboard = []
        if currency_row:
            keyboard.append(currency_row)
        keyboard.append(["🔙 بازگشت"])
        
        await update.message.reply_text(
            balance_text, 
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return TRANSFER_CONFIRM
        
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک شناسه عددی معتبر وارد کنید")
        return TRANSFER_AMOUNT
    except Exception as e:
        logger.exception("Error in get_transfer_amount")
        await update.message.reply_text(f"❌ خطا: {str(e)}")
        return TRANSFER_AMOUNT
    finally:
        if conn:
            conn.close()


@require_admin
async def get_transfer_to_agent(update, context):
    """دریافت مبلغ و ارز انتقال"""
    text = update.message.text.strip()
    
    # بررسی دکمه بازگشت - این باید در ابتدا باشد
    if text == "🔙 بازگشت":
        await central_finance_menu(update, context)
        return ConversationHandler.END
    
    # بررسی انتخاب ارز
    if text.startswith("💱 "):
        currency = text.replace("💱 ", "")
        context.user_data["selected_currency"] = currency
        
        await update.message.reply_text(
            f"💱 ارز {currency} انتخاب شد\n\n"
            f"💵 لطفاً مبلغ انتقال را به {currency} وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return TRANSFER_CONFIRM
    
    # اگر ارز قبلاً انتخاب شده، مبلغ را دریافت کن
    selected_currency = context.user_data.get("selected_currency")
    
    if selected_currency:
        try:
            amount = float(text)
            if amount <= 0:
                await update.message.reply_text("❌ مبلغ باید مثبت باشد")
                return TRANSFER_CONFIRM
            
            # بررسی موجودی کافی
            from_balances = context.user_data.get("transfer_from_balances", [])
            currency_balance = 0
            for currency, balance in from_balances:
                if currency == selected_currency:
                    currency_balance = balance
                    break
            
            if amount > currency_balance:
                await update.message.reply_text(
                    f"❌ موجودی ناکافی\n"
                    f"💰 موجودی {selected_currency}: {currency_balance:,.0f}\n"
                    f"💵 مبلغ درخواستی: {amount:,.0f}"
                )
                return TRANSFER_CONFIRM
            
            # ذخیره مبلغ و درخواست شناسه عامل مقصد
            context.user_data["transfer_amount"] = amount
            context.user_data["transfer_currency"] = selected_currency
            
            await update.message.reply_text(
                f"✅ مبلغ {amount:,.0f} {selected_currency} ثبت شد\n\n"
                f"🆔 شناسه عامل مقصد را وارد کنید:",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
            
            # پاک کردن انتخاب ارز برای استفاده‌های بعدی
            context.user_data.pop("selected_currency", None)
            
            # مهم: به مرحله بعدی نرویم، منتظر شناسه مقصد بمانیم
            return TRANSFER_CONFIRM
            
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید")
            return TRANSFER_CONFIRM
    
    # اگر عدد وارد شده و ارز انتخاب نشده، این شناسه عامل مقصد است
    try:
        to_agent_id = int(text)
        
        # بررسی اینکه آیا مبلغ و ارز قبلاً ثبت شده است
        if not context.user_data.get("transfer_amount"):
            # دریافت موجودی‌های عامل مبدأ برای نمایش مجدد دکمه‌ها
            from_balances = context.user_data.get("transfer_from_balances", [])
            currency_row = [f"💱 {currency}" for currency, balance in from_balances if balance > 0]
            
            keyboard = []
            if currency_row:
                keyboard.append(currency_row)
            keyboard.append(["🔙 بازگشت"])
            
            await update.message.reply_text(
                "❌ ابتدا ارز را انتخاب کرده و مبلغ را وارد کنید\n"
                "💱 لطفاً ارز را انتخاب کنید:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return TRANSFER_CONFIRM
        
        # اینجا شناسه عامل مقصد است، به تابع confirm_transfer برویم
        # چون در یک state هستیم، مستقیماً تابع confirm_transfer را فراخوانی می‌کنیم
        return await confirm_transfer(update, context)
        
    except ValueError:
        # اگر نه ارز انتخاب شده و نه عدد، پس ارز را انتخاب کن
        from_balances = context.user_data.get("transfer_from_balances", [])
        currency_row = []
        for currency, balance in from_balances:
            if balance > 0:
                currency_row.append(f"💱 {currency}")
        
        keyboard = []
        if currency_row:
            keyboard.append(currency_row)
        keyboard.append(["🔙 بازگشت"])
        
        await update.message.reply_text(
            "💱 لطفاً ابتدا ارز را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return TRANSFER_CONFIRM


@require_admin
async def confirm_transfer(update, context):
    """تأیید نهایی انتقال وجه"""
    from datetime import datetime
    
    # بررسی دکمه بازگشت به منوی ادمین
    if update.message.text.strip() == "🔙 بازگشت به منوی ادمین":
        await admin_menu(update, context)
        return ConversationHandler.END
    
    try:
        to_agent_id = int(update.message.text.strip())
        
        if to_agent_id == context.user_data["transfer_from_agent_id"]:
            await update.message.reply_text("❌ نمی‌توانید به همان عامل انتقال دهید")
            return TRANSFER_CONFIRM
        
        conn = get_db()
        cur = conn.cursor()
        
        # بررسی وجود عامل مقصد
        cur.execute("SELECT name, is_active FROM agents WHERE id = ?", (to_agent_id,))
        to_agent = cur.fetchone()
        
        if not to_agent:
            await update.message.reply_text("❌ عاملی با این شناسه پیدا نشد")
            return TRANSFER_CONFIRM
        
        to_name, is_active = to_agent
        if not is_active:
            await update.message.reply_text("❌ عامل مقصد غیرفعال است")
            return TRANSFER_CONFIRM
        
        # انجام انتقال
        from_agent_id = context.user_data["transfer_from_agent_id"]
        amount = context.user_data["transfer_amount"]
        currency = context.user_data["transfer_currency"]
        
        try:
            # کسر از عامل مبدأ
            cur.execute("""
                UPDATE balances 
                SET balance = balance - ?
                WHERE agent_id = ? AND currency = ?
            """, (amount, from_agent_id, currency))
            
            # افزودن به عامل مقصد
            cur.execute("""
                INSERT OR REPLACE INTO balances (agent_id, currency, balance)
                VALUES (?, ?, COALESCE(
                    (SELECT balance FROM balances WHERE agent_id = ? AND currency = ?), 0
                ) + ?)
            """, (to_agent_id, currency, to_agent_id, currency, amount))
            
            # ثبت تراکنش در جدول transactions (به عنوان حواله داخلی)
            transaction_code = f"TRF{dt.now().strftime('%Y%m%d%H%M%S')}"
            cur.execute("""
                INSERT INTO transactions (
                    transaction_code, sender_name, receiver_name, amount, 
                    currency, commission, status, agent_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?)
            """, (
                transaction_code,
                context.user_data["transfer_from_name"],
                to_name,
                amount,
                currency,
                0,  # انتقال داخلی کارمزد ندارد
                from_agent_id,
                dt.now()
            ))
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                f"✅ *انتقال وجه با موفقیت انجام شد*\n\n"
                f"📤 از: {context.user_data['transfer_from_name']} (#{from_agent_id:03d})\n"
                f"📥 به: {to_name} (#{to_agent_id:03d})\n"
                f"💰 مبلغ: {amount:,.0f} {currency}\n"
                f"🆔 کد تراکنش: `{transaction_code}`\n\n"
                f"لطفاً یک گزینه انتخاب کنید:",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 مدیریت مالی مرکزی"],
                    ["🔙 بازگشت به منوی ادمین"]
                ], resize_keyboard=True)
            )
            
            # پاک کردن context
            context.user_data.clear()
            return ConversationHandler.END
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.exception("Error in transfer funds")
            await update.message.reply_text("❌ خطا در انجام انتقال")
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("❌ شناسه باید عدد باشد")
        return TRANSFER_CONFIRM
    except Exception as e:
        logger.exception("Error in confirm_transfer")
        await update.message.reply_text(f"❌ خطا: {str(e)}")
        return TRANSFER_CONFIRM
