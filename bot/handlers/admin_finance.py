from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler
import logging
from datetime import datetime as dt, timedelta

from bot.services.database import get_db
from bot.services.auth import require_admin
from bot.services.localization import _
from bot.handlers.admin import admin_menu, get_lang
from bot.handlers.agent import _collect_future_obligations

logger = logging.getLogger(__name__)

FINANCE_MENU, TRANSFER_AMOUNT, TRANSFER_CONFIRM = range(3)


@require_admin
async def central_finance_menu(update, context):
    lang = get_lang(context)
    await update.message.reply_text(_("admin.financial_preparing", lang=lang))
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT currency, SUM(balance) as total_balance
        FROM balances
        GROUP BY currency
        ORDER BY total_balance DESC
    """)
    system_balances = cur.fetchall()
    
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
    
    cur.execute("SELECT COUNT(DISTINCT agent_id || currency) FROM balances")
    total_balance_records = cur.fetchone()[0]
    
    cur.execute("""
        SELECT a.id, a.name, a.province, SUM(b.balance) as total_balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1 AND b.currency = 'AFN'
        GROUP BY a.id, b.currency
        HAVING total_balance < 1000
        ORDER BY total_balance ASC
        LIMIT 5
    """)
    low_balance_agents = cur.fetchall()
    
    cur.execute("""
        SELECT a.id, a.name, a.province, SUM(b.balance) as total_balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1 AND b.currency = 'AFN'
        GROUP BY a.id, b.currency
        HAVING total_balance > 10000
        ORDER BY total_balance DESC
        LIMIT 5
    """)
    high_balance_agents = cur.fetchall()
    
    today = dt.utcnow().date()
    thirty_days_ago = today - timedelta(days=30)
    
    cur.execute(
        """
        SELECT agent_id, currency, SUM(commission) 
        FROM transactions
        WHERE status != 'cancelled'
          AND date(created_at) BETWEEN ? AND ?
        GROUP BY agent_id, currency
        """,
        (thirty_days_ago.isoformat(), today.isoformat()),
    )
    commissions_rows = cur.fetchall()
    commissions_map = {}
    for agent_id, currency, total_commission in commissions_rows:
        if agent_id not in commissions_map:
            commissions_map[agent_id] = {}
        commissions_map[agent_id][currency] = total_commission or 0
    
    cur.execute(
        """
        SELECT a.id, a.name, a.province, 
               COALESCE(SUM(CASE WHEN b.currency = 'AFN' THEN b.balance END), 0) AS afn_balance
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1
        GROUP BY a.id, a.name, a.province
        """
    )
    all_agents = cur.fetchall()
    
    risky_agents = []
    for agent_id, name, province, afn_balance in all_agents:
        obligations, obligations_end_date = _collect_future_obligations(agent_id, 30)
        obligations_afn = sum(amount for _, _, amount, _ in obligations.get("AFN", []))
        commissions_afn = commissions_map.get(agent_id, {}).get("AFN", 0)
        projected = afn_balance + commissions_afn - obligations_afn
        if obligations_afn > 0 and projected < 0:
            risky_agents.append(
                (
                    agent_id,
                    name,
                    province,
                    afn_balance,
                    obligations_afn,
                    commissions_afn,
                    projected,
                )
            )
    
    conn.close()
    
    report = _(
        "admin.financial_report",
        lang=lang,
        active_agents=active_agents,
        total_agents=total_agents,
        total_transactions=total_transactions,
        pending_transactions=pending_transactions,
        completed_transactions=completed_transactions,
        total_amount=f"{total_amount:,.0f}",
        total_commission=f"{total_commission:,.0f}",
    )
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    report += _("admin.financial_system_balance", lang=lang)
    total_system_value = 0
    for currency, balance in system_balances:
        if balance:
            if currency == "AFN":
                total_system_value += balance
                report += f"   🇦🇫 {currency}: {balance:,.0f}\n"
            else:
                usd_value = balance * 100
                total_system_value += usd_value
                report += f"   🇺🇸 {currency}: {balance:,.0f} (~{usd_value:,.0f} افغانی)\n"
    
    report += f"   💎 ارزش کل سیستم: {total_system_value:,.0f} افغانی\n\n"
    
    report += _("admin.financial_system_stats", lang=lang)
    report += f"   👥 عامل‌های فعال: {active_agents}\n"
    report += f"   📋 رکوردهای موجودی: {total_balance_records}\n\n"
    
    if low_balance_agents:
        report += _("admin.financial_low_balance_warning", lang=lang)
        for agent_id, name, province, balance, currency in low_balance_agents:
            report += f"   🔴 #{agent_id:03d} | {name} ({province}): {balance:,.0f} {currency}\n"
        report += "\n"
    
    if high_balance_agents:
        report += _("admin.financial_high_balance_info", lang=lang)
        for agent_id, name, province, balance, currency in high_balance_agents:
            report += f"   🟢 #{agent_id:03d} | {name} ({province}): {balance:,.0f} {currency}\n"
        report += "\n"
    
    if risky_agents:
        report += _("admin.financial_risky_agents_header", lang=lang)
        for (
            agent_id,
            name,
            province,
            afn_balance,
            obligations_afn,
            commissions_afn,
            projected,
        ) in risky_agents:
            line = _(
                "admin.financial_risky_agents_line",
                lang=lang,
                agent_id=f"{agent_id:03d}",
                name=name,
                province=province,
                balance_afn=f"{afn_balance:,.0f}",
                obligations_afn=f"{obligations_afn:,.0f}",
                commissions_afn=f"{commissions_afn:,.0f}",
                projected_afn=f"{projected:,.0f}",
            )
            report += f"{line}\n"
        report += "\n"
    
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    keyboard = [
        [
            _("buttons.admin_menu_transfer_funds", lang=lang),
            _("buttons.admin_menu_detailed_balances", lang=lang),
        ],
        [
            _("buttons.admin_menu_transfer_report", lang=lang),
            _("buttons.admin_menu_warnings", lang=lang),
        ],
        [
            _("buttons.admin_menu_system_health", lang=lang),
            _("buttons.admin_back_to_menu", lang=lang),
        ],
    ]
    
    await update.message.reply_text(
        report,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def detailed_balances(update, context):
    """جزئیات کامل موجودی‌ها"""
    lang = context.user_data.get("lang", "fa")
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
        if lang == "fa":
            msg = "❌ هیچ موجودی ثبت نشده است"
        else:
            msg = "❌ هېڅ موجودی ثبت نه ده شوې"
        await update.message.reply_text(msg)
        return
    
    # د عامل پر بنسټ ډله بندي
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
    
    # راپور جوړول
    if lang == "fa":
        report = "📊 *جزئیات کامل موجودی‌ها*\n"
    else:
        report = "📊 *د موجودیو بشپړ جزیات*\n"
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
            if lang == "fa":
                no_balance_text = "   ❌ بدون موجودی\n"
            else:
                no_balance_text = "   ❌ هېڅ موجودی نشته\n"
            report += no_balance_text
        
        report += "\n"
    
    # ټول خلاصه
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    if lang == "fa":
        report += "📊 *خلاصه کل:*\n"
        report += f"   👥 عامل‌های فعال: {active_count}\n"
        report += f"   💰 مجموع AFN: {total_afn:,.0f}\n"
        report += f"   💵 مجموع USD: {total_usd:,.0f}\n"
        keyboard = [
            ["💰 مدیریت مالی مرکزی", "🔙 بازگشت به منوی ادمین"]
        ]
    else:
        report += "📊 *عمومي لنډیز:*\n"
        report += f"   👥 فعال عاملان: {active_count}\n"
        report += f"   💰 د AFN ټولیزه اندازه: {total_afn:,.0f}\n"
        report += f"   💵 د USD ټولیزه اندازه: {total_usd:,.0f}\n"
        keyboard = [
            ["💰 د مرکزي مالی مدیریت", "🔙 د ادمین مینو ته شاته"]
        ]
    
    await update.message.reply_text(
        report,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def transfer_report(update, context):
    lang = context.user_data.get("lang", "fa")
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            t.transaction_code,
            t.amount,
            t.currency,
            t.created_at,
            a_from.id AS from_id,
            a_from.name AS from_name,
            a_from.province AS from_province,
            a_to.id AS to_id,
            a_to.name AS to_name,
            a_to.province AS to_province,
            t.receiver_name
        FROM transactions t
        JOIN agents a_from ON t.agent_id = a_from.id
        LEFT JOIN agents a_to ON t.receiver_agent_id = a_to.id
        WHERE t.transaction_code LIKE 'TRF%'
        ORDER BY t.created_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        if lang == "fa":
            msg = "❌ تاکنون هیچ انتقال داخلی بین عامل‌ها ثبت نشده است."
        else:
            msg = "❌ تر اوسه د عاملانو ترمنځ هېڅ داخلي لېږد نه دی ثبت شوی."
        await update.message.reply_text(msg)
        return
    
    if lang == "fa":
        text = "📤 *گزارش آخرین انتقال وجه بین عامل‌ها*\n"
    else:
        text = "📤 *د عاملانو ترمنځ د وروستیو لېږدونو راپور*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    for idx, row in enumerate(rows, start=1):
        (
            code,
            amount,
            currency,
            created_at,
            from_id,
            from_name,
            from_province,
            to_id,
            to_name,
            to_province,
            legacy_receiver_name,
        ) = row
        
        if to_name:
            to_display = f"{to_name} ({to_province})"
            if to_id:
                to_display += f" #{to_id:03d}"
        else:
            to_display = legacy_receiver_name or "-"
        
        if lang == "fa":
            text += (
                f"🧾 *انتقال {idx}:*\n"
                f"🆔 کد: `{code}`\n"
                f"📤 از: {from_name} ({from_province}) #{from_id:03d}\n"
                f"📥 به: {to_display}\n"
                f"💰 مبلغ: {amount:,.0f} {currency}\n"
                f"📅 تاریخ: {str(created_at)[:16]}\n\n"
            )
        else:
            text += (
                f"🧾 *لېږد {idx}:*\n"
                f"🆔 کوډ: `{code}`\n"
                f"📤 له: {from_name} ({from_province}) #{from_id:03d}\n"
                f"📥 ته: {to_display}\n"
                f"💰 مبلغ: {amount:,.0f} {currency}\n"
                f"📅 نېټه: {str(created_at)[:16]}\n\n"
            )
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    _("buttons.admin_menu_central_finance", lang=lang),
                    _("buttons.admin_back_to_menu", lang=lang),
                ]
            ],
            resize_keyboard=True,
        ),
    )


@require_admin
async def start_transfer_funds(update, context):
    """شروع انتقال وجه بین عامل‌ها"""
    lang = context.user_data.get("lang", "fa")
    if lang == "fa":
        text = (
            "💸 *انتقال وجه بین عامل‌ها*\n\n"
            "🆔 شناسه عامل مبدأ را وارد کنید:"
        )
        back_label = "🔙 بازگشت"
    else:
        text = (
            "💸 *د پيسوکو لېږدول د عاملانو ترمنځ*\n\n"
            "🆔 د لېږدونکي عامل پېژنیز لیکۍ:"
        )
        back_label = "🔙 شاته"
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[back_label]], resize_keyboard=True)
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
        
        # د لېږدونکي عامل شتون وګورو
        cur.execute("SELECT name, is_active FROM agents WHERE id = ?", (from_agent_id,))
        from_agent = cur.fetchone()
        
        if not from_agent:
            await update.message.reply_text("❌ عاملی با این شناسه پیدا نشد")
            return TRANSFER_AMOUNT
        
        from_name, is_active = from_agent
        if not is_active:
            await update.message.reply_text("❌ عامل مبدأ غیرفعال است")
            return TRANSFER_AMOUNT
        
        # د لېږدونکي عامل شته موجودی (د ارز پر بنسټ ټول شوی)
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
        
        # ټول شوی معلومات په context کې خوندي کول
        context.user_data["transfer_from_agent_id"] = from_agent_id
        context.user_data["transfer_from_name"] = from_name
        context.user_data["transfer_from_balances"] = from_balances
        
        # شته موجودی ښودل
        lang = context.user_data.get("lang", "fa")
        if lang == "fa":
            balance_text = f"💰 *موجودی عامل مبدأ: {from_name}*\n\n"
        else:
            balance_text = f"💰 *د مبدأ عامل موجودی: {from_name}*\n\n"
        
        # د ارز غوره کول لپاره کيبورډ جوړول (کليکې په يوه کرښه کې)
        currency_row = []
        for currency, balance in from_balances:
            balance_text += f"• {currency}: {balance:,.0f}\n"
            currency_row.append(f"💱 {currency}")
        
        if lang == "fa":
            balance_text += "\n💵 لطفاً ارز مورد نظر برای انتقال را انتخاب کنید یا مبلغ را وارد کنید:"
            back_label = "🔙 بازگشت"
        else:
            balance_text += "\n💵 مهرباني وکړئ د لېږد لپاره ارز غوره کړئ يا مبلغ وليکئ:"
            back_label = "🔙 شاته"
        
        keyboard = []
        if currency_row:
            keyboard.append(currency_row)
        keyboard.append([back_label])
        
        await update.message.reply_text(
            balance_text, 
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return TRANSFER_CONFIRM
        
    except ValueError:
        lang = context.user_data.get("lang", "fa")
        if lang == "fa":
            msg = "❌ لطفاً یک شناسه عددی معتبر وارد کنید"
        else:
            msg = "❌ مهرباني وکړئ يو سم پېژنیز لیکۍ وليکئ"
        await update.message.reply_text(msg)
        return TRANSFER_AMOUNT
    except Exception as e:
        logger.exception("Error in get_transfer_amount")
        await update.message.reply_text(f"❌ تېرونه: {str(e)}")
        return TRANSFER_AMOUNT
    finally:
        if conn:
            conn.close()


@require_admin
async def get_transfer_to_agent(update, context):
    """دریافت مبلغ و ارز انتقال"""
    text = update.message.text.strip()
    
    # بیرغته/بازگشت کليک وګورو - دا په لومړي کې بايد وي
    if text in ["🔙 شاته", "🔙 بازگشت"]:
        await central_finance_menu(update, context)
        return ConversationHandler.END
    
    # د ارز غوره کول وګورو
    if text.startswith("💱 "):
        currency = text.replace("💱 ", "")
        context.user_data["selected_currency"] = currency
        
        lang = context.user_data.get("lang", "fa")
        if lang == "fa":
            text_msg = (
                f"💱 ارز {currency} انتخاب شد\n\n"
                f"💵 لطفاً مبلغ انتقال را به {currency} وارد کنید:"
            )
            back_label = "🔙 بازگشت"
        else:
            text_msg = (
                f"💱 ارز {currency} غوره شو\n\n"
                f"💵 مهرباني وکړئ د لېږد مبلغ په {currency} وليکئ:"
            )
            back_label = "🔙 شاته"
        await update.message.reply_text(
            text_msg,
            reply_markup=ReplyKeyboardMarkup([[back_label]], resize_keyboard=True)
        )
        return TRANSFER_CONFIRM
    
    # که که ارز مخکې غوره شوی وي، مبلغ وليکئ
    selected_currency = context.user_data.get("selected_currency")
    
    if selected_currency:
        try:
            amount = float(text)
            if amount <= 0:
                lang = context.user_data.get("lang", "fa")
                msg = "❌ مبلغ باید مثبت باشد" if lang == "fa" else "❌ مبلغ بايد مثبت وي"
                await update.message.reply_text(msg)
                return TRANSFER_CONFIRM
            
            # کافي شته موجودی وګورو
            from_balances = context.user_data.get("transfer_from_balances", [])
            currency_balance = 0
            for currency, balance in from_balances:
                if currency == selected_currency:
                    currency_balance = balance
                    break
            
            if amount > currency_balance:
                lang = context.user_data.get("lang", "fa")
                if lang == "fa":
                    msg = (
                        "❌ موجودی ناکافی\n"
                        f"💰 موجودی {selected_currency}: {currency_balance:,.0f}\n"
                        f"💵 مبلغ درخواستی: {amount:,.0f}"
                    )
                else:
                    msg = (
                        "❌ کافي موجودی نشته\n"
                        f"💰 موجودی {selected_currency}: {currency_balance:,.0f}\n"
                        f"💵 غوښتل شوی مبلغ: {amount:,.0f}"
                    )
                await update.message.reply_text(msg)
                return TRANSFER_CONFIRM
            
            # مبلغ او ارز خوندي کول او د مقصد عامل پېژنیز لیکۍ غوښتنه
            context.user_data["transfer_amount"] = amount
            context.user_data["transfer_currency"] = selected_currency
            
            lang = context.user_data.get("lang", "fa")
            if lang == "fa":
                msg = (
                    f"✅ مبلغ {amount:,.0f} {selected_currency} ثبت شد\n\n"
                    "🆔 شناسه عامل مقصد را وارد کنید:"
                )
                back_label = "🔙 بازگشت"
            else:
                msg = (
                    f"✅ مبلغ {amount:,.0f} {selected_currency} ثبت شو\n\n"
                    "🆔 د مقصد عامل پېژنیز لیکۍ:"
                )
                back_label = "🔙 شاته"
            await update.message.reply_text(
                msg,
                reply_markup=ReplyKeyboardMarkup([[back_label]], resize_keyboard=True)
            )
            
            # د ارز غوره کول د راتلونکي کارونو لپاره پاکول
            context.user_data.pop("selected_currency", None)
            
            # مهم: بل مرحلې ته نه ځو، د مقصد پېژنیز لیکۍ انتظار کوو
            return TRANSFER_CONFIRM
            
        except ValueError:
            lang = context.user_data.get("lang", "fa")
            msg = "❌ لطفاً یک عدد معتبر وارد کنید" if lang == "fa" else "❌ مهرباني وکړئ يو سم عدد وليکئ"
            await update.message.reply_text(msg)
            return TRANSFER_CONFIRM
    
    # که که عدد لیکل شوی وي، يا د مقصد عامل پېژنیز لیکۍ دی يا کاربر مرحله را جا انداخته
    try:
        to_agent_id = int(text)
        
        # اگر هنوز مبلغ و ارز ثبت نشده، کاربر یک مرحله را جا انداخته است
        if not context.user_data.get("transfer_amount"):
            from_balances = context.user_data.get("transfer_from_balances", [])
            currency_row = [f"💱 {currency}" for currency, balance in from_balances if balance > 0]
            
            keyboard = []
            if currency_row:
                keyboard.append(currency_row)
            keyboard.append(["🔙 بازگشت" if context.user_data.get("lang", "fa") == "fa" else "🔙 شاته"])
            
            lang = context.user_data.get("lang", "fa")
            if lang == "fa":
                msg = (
                    "❌ ابتدا ارز را انتخاب کنید و مبلغ را وارد کنید\n"
                    "💱 لطفاً ارز را انتخاب کنید:"
                )
            else:
                msg = (
                    "❌ لومړی ارز غوره کړئ او مبلغ وليکئ\n"
                    "💱 مهرباني وکړئ ارز غوره کړئ:"
                )
            await update.message.reply_text(
                msg,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return TRANSFER_CONFIRM
        
        # در غیر این صورت، مبلغ و ارز قبلاً ثبت شده و این عدد، شناسه عامل مقصد است
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
        keyboard.append(["🔙 شاته" if context.user_data.get("lang", "fa") != "fa" else "🔙 بازگشت"])
        
        lang = context.user_data.get("lang", "fa")
        msg = "💱 ابتدا ارز را انتخاب کنید:" if lang == "fa" else "💱 لومړی ارز غوره کړئ:"
        await update.message.reply_text(
            msg,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return TRANSFER_CONFIRM


@require_admin
async def confirm_transfer(update, context):
    """تأیید نهایی انتقال وجه"""
    lang = context.user_data.get("lang", "fa")
    
    # بررسی دکمه بازگشت به منوی ادمین
    if update.message.text.strip() == _("buttons.admin_back_to_menu", lang=lang):
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
            cur.execute("""
                UPDATE balances 
                SET balance = balance - ?
                WHERE agent_id = ? AND currency = ?
            """, (amount, from_agent_id, currency))
            
            cur.execute("""
                INSERT OR REPLACE INTO balances (agent_id, currency, balance)
                VALUES (?, ?, COALESCE(
                    (SELECT balance FROM balances WHERE agent_id = ? AND currency = ?), 0
                ) + ?)
            """, (to_agent_id, currency, to_agent_id, currency, amount))
            
            transaction_code = f"TRF{dt.now().strftime('%Y%m%d%H%M%S')}"
            cur.execute("""
                INSERT INTO transactions (
                    transaction_code, agent_id, receiver_agent_id, sender_name, 
                    receiver_name, amount, currency, commission, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            """, (
                transaction_code,
                from_agent_id,
                to_agent_id,
                context.user_data["transfer_from_name"],
                to_name,
                amount,
                currency,
                0,
            ))
            
            conn.commit()
            conn.close()
            
            lang = context.user_data.get("lang", "fa")
            if lang == "fa":
                text = (
                    "✅ *انتقال وجه با موفقیت انجام شد*\n\n"
                    f"📤 از: {context.user_data['transfer_from_name']} (#{from_agent_id:03d})\n"
                    f"📥 به: {to_name} (#{to_agent_id:03d})\n"
                    f"💰 مبلغ: {amount:,.0f} {currency}\n"
                    f"🆔 کد تراکنش: `{transaction_code}`\n\n"
                    "لطفاً یکی از گزینه‌ها را انتخاب کنید:"
                )
            else:
                text = (
                    "✅ *د پيسوکو لېږدول په بریالۍ سرته شو*\n\n"
                    f"📤 له: {context.user_data['transfer_from_name']} (#{from_agent_id:03d})\n"
                    f"📥 ته: {to_name} (#{to_agent_id:03d})\n"
                    f"💰 مبلغ: {amount:,.0f} {currency}\n"
                    f"🆔 د تراکنش کوډ: `{transaction_code}`\n\n"
                    "مهرباني وکړئ يوه غوره کړئ:"
                )
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    [
                        [
                            _("buttons.admin_menu_central_finance", lang=lang),
                            _("buttons.admin_back_to_menu", lang=lang),
                        ]
                    ],
                    resize_keyboard=True,
                ),
            )
            
            preserved_lang = context.user_data.get("lang", "fa")
            context.user_data.clear()
            context.user_data["lang"] = preserved_lang
            return ConversationHandler.END
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.exception("Error in transfer funds")
            lang = context.user_data.get("lang", "fa")
            msg = "❌ خطا در انتقال وجه" if lang == "fa" else "❌ د پيسوکو لېږد کې تېرونه"
            await update.message.reply_text(msg)
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("❌ پېژنیز لیکۍ بايد عدد وي")
        return TRANSFER_CONFIRM
    except Exception as e:
        logger.exception("Error in confirm_transfer")
        await update.message.reply_text(f"❌ تېرونه: {str(e)}")
        return TRANSFER_CONFIRM
