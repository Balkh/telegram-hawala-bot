from telegram import ReplyKeyboardMarkup
import logging
from datetime import datetime as dt, timedelta

from bot.services.database import get_db
from bot.services.auth import require_admin
from bot.handlers.admin import get_lang
from bot.handlers.agent import _collect_future_obligations

logger = logging.getLogger(__name__)


# =======================
# 🚨 هشدارها و اطلاعیه‌ها
# =======================


@require_admin
async def alerts_and_notifications(update, context):
    """هشدارها و اطلاعیه‌های سیستم"""
    lang = get_lang(context)
    if lang == "fa":
        await update.message.reply_text("🚨 در حال بررسی هشدارهای سیستم...")
    else:
        await update.message.reply_text("⚠️ د سیستم خبرتیاوې او اعلانونه په کتنه کې...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # هشدار ۱: عامل‌های با موجودی کم
    cur.execute("""
        SELECT a.id, a.name, a.province, b.balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1 AND b.currency = 'AFN' AND b.balance < 1000
        ORDER BY b.balance ASC
        LIMIT 10
    """)
    low_balance_agents = cur.fetchall()
    
    # هشدار ۲: عامل‌های با موجودی صفر
    cur.execute("""
        SELECT a.id, a.name, a.province
        FROM agents a
        WHERE a.is_active = 1 AND a.id NOT IN (
            SELECT DISTINCT agent_id FROM balances WHERE balance > 0
        )
        ORDER BY a.name
    """)
    zero_balance_agents = cur.fetchall()
    
    # هشدار ۳: حواله‌های قدیمی در انتظار (بیش از ۷ روز)
    seven_days_ago = (dt.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT t.transaction_code, t.sender_name, t.receiver_name, 
               t.amount, t.currency, t.created_at, a.name as agent_name
        FROM transactions t
        JOIN agents a ON t.agent_id = a.id
        WHERE t.status = 'pending' AND DATE(t.created_at) < ?
        ORDER BY t.created_at ASC
        LIMIT 10
    """, (seven_days_ago,))
    old_pending_transactions = cur.fetchall()
    
    # هشدار ۴: عامل‌های غیرفعال با موجودی
    cur.execute("""
        SELECT a.id, a.name, a.province, b.balance, b.currency
        FROM agents a
        JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 0 AND b.balance > 0
        ORDER BY b.balance DESC
    """)
    inactive_with_balance = cur.fetchall()
    
    # هشدار ۵: عامل‌های بدون فعالیت اخیر (۳۰ روز اخیر)
    thirty_days_ago = (dt.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT a.id, a.name, a.province, MAX(t.created_at) as last_activity
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id
        WHERE a.is_active = 1
        GROUP BY a.id, a.name, a.province
        HAVING MAX(t.created_at) < ? OR MAX(t.created_at) IS NULL
        ORDER BY last_activity ASC
        LIMIT 10
    """, (thirty_days_ago,))
    inactive_agents = cur.fetchall()
    
    thirty_days_from_now = dt.now().date() + timedelta(days=30)
    cur.execute(
        """
        SELECT a.id,
               a.name,
               a.province,
               COALESCE(SUM(CASE WHEN b.currency = 'AFN' THEN b.balance END), 0) AS afn_balance
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        WHERE a.is_active = 1
        GROUP BY a.id, a.name, a.province
        """
    )
    all_agents = cur.fetchall()
    
    cur.execute(
        """
        SELECT agent_id, SUM(commission)
        FROM transactions
        WHERE status != 'cancelled'
          AND date(created_at) >= date('now', '-30 day')
          AND currency = 'AFN'
        GROUP BY agent_id
        """
    )
    commission_rows = cur.fetchall()
    commission_map = {row[0]: float(row[1] or 0) for row in commission_rows}
    
    risky_agents = []
    for agent_id, name, province, afn_balance in all_agents:
        obligations, obligations_end_date = _collect_future_obligations(agent_id, 30)
        obligations_afn = sum(amount for _, _, amount, _ in obligations.get("AFN", []))
        commissions_afn = commission_map.get(agent_id, 0.0)
        projected = afn_balance + commissions_afn - obligations_afn
        if obligations_afn > 0 and projected < 0:
            risky_agents.append(
                (agent_id, name, province, afn_balance, obligations_afn, commissions_afn, projected)
            )
    
    cur.execute("""
        SELECT t.transaction_code, t.sender_name, t.receiver_name, 
               t.amount, t.currency, t.created_at, a.name as agent_name
        FROM transactions t
        JOIN agents a ON t.agent_id = a.id
        WHERE t.status != 'cancelled' AND t.amount > 10000
        ORDER BY t.amount DESC
        LIMIT 5
    """)
    high_amount_transactions = cur.fetchall()
    
    conn.close()
    
    # ساخت گزارش هشدارها
    if lang == "fa":
        alerts = "🚨 *هشدارها و اطلاعیه‌های سیستم*\n"
    else:
        alerts = "⚠️ *د سیستم خبرتیاوې او اعلانونه*\n"
    alerts += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    # شمارش هشدارها
    alert_count = 0
    
    # هشدار موجودی کم
    if low_balance_agents:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: عامل‌های با موجودی کم (زیر ۱۰۰۰ افغانی)*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: هغه عاملان چې موجودی یې کمه ده (تر ۱۰۰۰ افغانی لاندې)*\n"
        for agent_id, name, province, balance, currency in low_balance_agents:
            balance_text = f"{balance:,.0f}" if balance is not None else "۰"
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {balance_text} {currency}\n"
        alerts += "\n"
    
    # هشدار موجودی صفر
    if zero_balance_agents:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: عامل‌های بدون موجودی*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: هغه عاملان چې هېڅ موجودی نه لري*\n"
        for agent_id, name, province in zero_balance_agents:
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province})\n"
        alerts += "\n"
    
    # هشدار حواله‌های قدیمی
    if old_pending_transactions:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: حواله‌های قدیمی در انتظار (بیش از ۷ روز)*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: زاړې په تمه حوالې (له ۷ ورځو ډېرې)*\n"
        for code, sender, receiver, amount, currency, created_at, agent_name in old_pending_transactions:
            days_old = (dt.now() - dt.strptime(created_at, '%Y-%m-%d %H:%M:%S')).days
            alerts += f"   🔴 `{code}` | {sender} → {receiver}\n"
            if lang == "fa":
                alerts += f"      💰 {amount:,.0f} {currency} | {days_old} روز پیش | عامل: {agent_name}\n"
            else:
                alerts += f"      💰 {amount:,.0f} {currency} | {days_old} ورځې وړاندې | عامل: {agent_name}\n"
        alerts += "\n"
    
    # هشدار عامل‌های غیرفعال با موجودی
    if inactive_with_balance:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: عامل‌های غیرفعال با موجودی*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: غیرفعال عاملان چې موجودی لري*\n"
        for agent_id, name, province, balance, currency in inactive_with_balance:
            balance_text = f"{balance:,.0f}" if balance is not None else "۰"
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {balance_text} {currency}\n"
        alerts += "\n"
    
    # هشدار عدم فعالیت
    if inactive_agents:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: عامل‌های بدون فعالیت (۳۰ روز اخیر)*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: هغه عاملان چې په ۳۰ ورځو کې فعال نه دي*\n"
        for agent_id, name, province, last_activity in inactive_agents:
            if last_activity:
                days_inactive = (dt.now() - dt.strptime(last_activity, '%Y-%m-%d %H:%M:%S')).days
                if lang == "fa":
                    alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {days_inactive} روز غیرفعال\n"
                else:
                    alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {days_inactive} ورځې غیر فعال\n"
            else:
                if lang == "fa":
                    alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): هیچ فعالیتی نداشته\n"
                else:
                    alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): هېڅ فعالیت نه لري\n"
        alerts += "\n"
    
    # هشدار عامل‌های پرریسک از نظر نقدینگی
    if risky_agents:
        alert_count += 1
        if lang == "fa":
            alerts += f"⚠️ *هشدار {alert_count}: عامل‌های در معرض کمبود نقدینگی در ۳۰ روز آینده*\n"
        else:
            alerts += f"⚠️ *خبرتیا {alert_count}: هغه عاملان چې په راتلونکو ۳۰ ورځو کې د نغدو کمښت خطر لري*\n"
        for agent_id, name, province, afn_balance, obligations_afn, commissions_afn, projected in risky_agents:
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province})\n"
            alerts += f"      💰 موجودی فعلی: {afn_balance:,.0f} AFN | 📉 تعهدات ۳۰ روز آینده: {obligations_afn:,.0f} AFN\n"
            alerts += f"      💸 کمیسیون ۳۰ روز گذشته: {commissions_afn:,.0f} AFN | 🔍 پیش‌بینی نقدینگی: {projected:,.0f} AFN\n"
        alerts += "\n"
    
    # اطلاعیه حواله‌های با مبلغ بالا
    if high_amount_transactions:
        if lang == "fa":
            alerts += "💎 *اطلاعیه: حواله‌های با مبلغ بالا (بیش از ۱۰۰۰۰ افغانی)*\n"
        else:
            alerts += "💎 *اطلاعیه: لوړې مبلغ لرونکي حوالې (له ۱۰۰۰۰ افغانی څخه ډېرې)*\n"
        for code, sender, receiver, amount, currency, created_at, agent_name in high_amount_transactions:
            alerts += f"   💎 `{code}` | {sender} → {receiver}\n"
            alerts += f"      💰 {amount:,.0f} {currency} | عامل: {agent_name}\n"
        alerts += "\n"
    
    # اگر هیچ هشداری نبود
    if alert_count == 0:
        if lang == "fa":
            alerts += "✅ *هیچ هشداری وجود ندارد! سیستم در وضعیت عالی است.*\n\n"
        else:
            alerts += "✅ *هیڅ خبرتیا نشته! سیستم په ډېر ښه حالت کې دی.*\n\n"
    else:
        if lang == "fa":
            alerts += f"📊 *مجموع هشدارها: {alert_count} مورد*\n\n"
        else:
            alerts += f"📊 *د خبرتیاوو ټول شمېر: {alert_count}*\n\n"
    
    alerts += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    if lang == "fa":
        alerts += f"📅 آخرین بررسی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
        keyboard = [
            ["🔄 بررسی مجدد هشدارها", "💰 مدیریت مالی مرکزی"],
            ["🔙 بازگشت به منوی ادمین"],
        ]
    else:
        alerts += f"📅 د وروستۍ کتنې وخت: {dt.now().strftime('%Y/%m/%d %H:%M')}"
        keyboard = [
            ["🔄 د خبرتیاوو بیا کتنه", "💰 د مرکزي مالی مدیریت"],
            ["🔙 د ادمین مینو ته شاته"],
        ]
    
    await update.message.reply_text(
        alerts,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def system_health_check(update, context):
    lang = get_lang(context)
    if lang == "fa":
        await update.message.reply_text("🏥 در حال بررسی سلامت سیستم...")
    else:
        await update.message.reply_text("🏥 د سیستم د سلامت په کتنه کې...")
    
    conn = get_db()
    cur = conn.cursor()
    
    health_status = []
    issues = []
    
    # بررسی ۱: تعداد کل عامل‌ها
    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]
    
    if active_agents == 0:
        if lang == "fa":
            issues.append("❌ هیچ عامل فعلی وجود ندارد")
        else:
            issues.append("❌ هېڅ فعال عامل شتون نه لري")
    elif active_agents < 3:
        if lang == "fa":
            issues.append(f"⚠️ تعداد عامل‌های فعال کم است: {active_agents}")
        else:
            issues.append(f"⚠️ د فعالو عاملانو شمېر کم دی: {active_agents}")
    else:
        if lang == "fa":
            health_status.append(f"✅ عامل‌های فعال: {active_agents}")
        else:
            health_status.append(f"✅ فعال عاملان: {active_agents}")
    
    # بررسی ۲: موجودی کل سیستم
    cur.execute("SELECT SUM(balance) FROM balances WHERE currency = 'AFN'")
    total_afn = cur.fetchone()[0] or 0
    
    if total_afn == 0:
        if lang == "fa":
            issues.append("❌ هیچ موجودی در سیستم ثبت نشده")
        else:
            issues.append("❌ په سیستم کې هېڅ موجودی ثبت نه ده")
    elif total_afn < 10000:
        if lang == "fa":
            issues.append(f"⚠️ موجودی کل سیستم کم است: {total_afn:,.0f} افغانی")
        else:
            issues.append(f"⚠️ د سیستم ټول موجودی کمه ده: {total_afn:,.0f} افغانی")
    else:
        if lang == "fa":
            health_status.append(f"✅ موجودی کل سیستم: {total_afn:,.0f} افغانی")
        else:
            health_status.append(f"✅ د سیستم ټول موجودی: {total_afn:,.0f} افغانی")
    
    # بررسی ۳: حواله‌های در انتظار
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
    pending_count = cur.fetchone()[0]
    
    if pending_count > 100:
        if lang == "fa":
            issues.append(f"⚠️ حواله‌های در انتظار زیاد است: {pending_count}")
        else:
            issues.append(f"⚠️ د تمه کې حوالې ډېرې دي: {pending_count}")
    else:
        if lang == "fa":
            health_status.append(f"✅ حواله‌های در انتظار: {pending_count}")
        else:
            health_status.append(f"✅ د تمه کې حوالې: {pending_count}")
    
    # بررسی ۴: حواله‌های قدیمی
    three_days_ago = (dt.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending' AND DATE(created_at) < ?", (three_days_ago,))
    old_pending = cur.fetchone()[0]
    
    if old_pending > 10:
        if lang == "fa":
            issues.append(f"⚠️ حواله‌های قدیمی در انتظار: {old_pending}")
        else:
            issues.append(f"⚠️ زړې د تمه کې حوالې: {old_pending}")
    else:
        if lang == "fa":
            health_status.append(f"✅ حواله‌های قدیمی: {old_pending}")
        else:
            health_status.append(f"✅ زړې د تمه کې حوالې: {old_pending}")
    
    # بررسی ۵: عامل‌های با موجودی صفر
    cur.execute("""
        SELECT COUNT(*) FROM agents a 
        WHERE a.is_active = 1 AND NOT EXISTS (
            SELECT 1 FROM balances b WHERE b.agent_id = a.id AND b.balance > 0
        )
    """)
    zero_balance_count = cur.fetchone()[0]
    
    if zero_balance_count > active_agents * 0.5:
        if lang == "fa":
            issues.append(f"⚠️ درصد بالایی از عامل‌ها موجودی صفر دارند: {zero_balance_count}/{active_agents}")
        else:
            issues.append(f"⚠️ د ډېرو عاملانو موجودی صفر دی: {zero_balance_count}/{active_agents}")
    else:
        if lang == "fa":
            health_status.append(f"✅ عامل‌های با موجودی صفر: {zero_balance_count}")
        else:
            health_status.append(f"✅ هغه عاملان چې موجودی یې صفر ده: {zero_balance_count}")
    
    conn.close()
    
    if lang == "fa":
        health_report = "🏥 *گزارش سلامت سیستم*\n"
        health_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    else:
        health_report = "🏥 *د سیستم د سلامت راپور*\n"
        health_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    if issues:
        if lang == "fa":
            health_report += "🚨 *مسائل شناسایی شده:*\n"
        else:
            health_report += "🚨 *موندل شوي ستونزې:*\n"
        for issue in issues:
            health_report += f"   {issue}\n"
        health_report += "\n"
    
    if health_status:
        if lang == "fa":
            health_report += "✅ *وضعیت عالی:*\n"
        else:
            health_report += "✅ *ښه وضعیت:* \n"
        for status in health_status:
            health_report += f"   {status}\n"
        health_report += "\n"
    
    total_checks = 5
    passed_checks = total_checks - len(issues)
    health_score = (passed_checks / total_checks) * 100
    
    if lang == "fa":
        health_report += "📊 *امتیاز سلامت:*\n"
        health_report += f"   🎯 {health_score:.0f}% ({passed_checks}/{total_checks})\n\n"
    else:
        health_report += "📊 *د سلامت نمره:*\n"
        health_report += f"   🎯 {health_score:.0f}% ({passed_checks}/{total_checks})\n\n"
    
    if health_score >= 80:
        if lang == "fa":
            health_report += "🟢 *وضعیت سیستم: عالی*\n"
        else:
            health_report += "🟢 *د سیستم وضعیت: ډېر ښه*\n"
    elif health_score >= 60:
        if lang == "fa":
            health_report += "🟡 *وضعیت سیستم: خوب*\n"
        else:
            health_report += "🟡 *د سیستم وضعیت: ښه*\n"
    else:
        if lang == "fa":
            health_report += "🔴 *وضعیت سیستم: نیاز به توجه*\n"
        else:
            health_report += "🔴 *د سیستم وضعیت: پاملرنې ته اړتیا لري*\n"
    
    if lang == "fa":
        health_report += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        health_report += f"📅 زمان بررسی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
        keyboard = [
            ["⚠️ هشدارها و اطلاعیه‌ها", "💰 مدیریت مالی مرکزی"],
            ["🔄 بررسی مجدد سلامت", "🔙 بازگشت به منوی ادمین"],
        ]
    else:
        health_report += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        health_report += f"📅 د کتنې وخت: {dt.now().strftime('%Y/%m/%d %H:%M')}"
        keyboard = [
            ["⚠️ خبرتیاوې او اعلانونه", "💰 د مرکزي مالی مدیریت"],
            ["🔄 د سلامت بیا کتنه", "🔙 د ادمین مینو ته شاته"],
        ]
    
    await update.message.reply_text(
        health_report,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
