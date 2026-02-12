from telegram import ReplyKeyboardMarkup
import logging
from datetime import datetime as dt, timedelta

from bot.services.database import get_db
from bot.services.auth import require_admin

logger = logging.getLogger(__name__)


# =======================
# 🚨 هشدارها و اطلاعیه‌ها
# =======================


@require_admin
async def alerts_and_notifications(update, context):
    """هشدارها و اطلاعیه‌های سیستم"""
    await update.message.reply_text("🚨 در حال بررسی هشدارهای سیستم...")
    
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
    
    # هشدار ۶: حواله‌های با مبلغ بالا (بیش از ۱۰۰۰۰ افغانی)
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
    alerts = "🚨 *هشدارها و اطلاعیه‌های سیستم*\n"
    alerts += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    # شمارش هشدارها
    alert_count = 0
    
    # هشدار موجودی کم
    if low_balance_agents:
        alert_count += 1
        alerts += f"⚠️ *هشدار {alert_count}: عامل‌های با موجودی کم (زیر ۱۰۰۰ افغانی)*\n"
        for agent_id, name, province, balance, currency in low_balance_agents:
            balance_text = f"{balance:,.0f}" if balance is not None else "۰"
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {balance_text} {currency}\n"
        alerts += "\n"
    
    # هشدار موجودی صفر
    if zero_balance_agents:
        alert_count += 1
        alerts += f"⚠️ *هشدار {alert_count}: عامل‌های بدون موجودی*\n"
        for agent_id, name, province in zero_balance_agents:
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province})\n"
        alerts += "\n"
    
    # هشدار حواله‌های قدیمی
    if old_pending_transactions:
        alert_count += 1
        alerts += f"⚠️ *هشدار {alert_count}: حواله‌های قدیمی در انتظار (بیش از ۷ روز)*\n"
        for code, sender, receiver, amount, currency, created_at, agent_name in old_pending_transactions:
            days_old = (dt.now() - dt.strptime(created_at, '%Y-%m-%d %H:%M:%S')).days
            alerts += f"   🔴 `{code}` | {sender} → {receiver}\n"
            alerts += f"      💰 {amount:,.0f} {currency} | {days_old} روز پیش | عامل: {agent_name}\n"
        alerts += "\n"
    
    # هشدار عامل‌های غیرفعال با موجودی
    if inactive_with_balance:
        alert_count += 1
        alerts += f"⚠️ *هشدار {alert_count}: عامل‌های غیرفعال با موجودی*\n"
        for agent_id, name, province, balance, currency in inactive_with_balance:
            balance_text = f"{balance:,.0f}" if balance is not None else "۰"
            alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {balance_text} {currency}\n"
        alerts += "\n"
    
    # هشدار عدم فعالیت
    if inactive_agents:
        alert_count += 1
        alerts += f"⚠️ *هشدار {alert_count}: عامل‌های بدون فعالیت (۳۰ روز اخیر)*\n"
        for agent_id, name, province, last_activity in inactive_agents:
            if last_activity:
                days_inactive = (dt.now() - dt.strptime(last_activity, '%Y-%m-%d %H:%M:%S')).days
                alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): {days_inactive} روز غیرفعال\n"
            else:
                alerts += f"   🔴 #{agent_id:03d} | {name} ({province}): هیچ فعالیتی نداشته\n"
        alerts += "\n"
    
    # اطلاعیه حواله‌های با مبلغ بالا
    if high_amount_transactions:
        alerts += "💎 *اطلاعیه: حواله‌های با مبلغ بالا (بیش از ۱۰۰۰۰ افغانی)*\n"
        for code, sender, receiver, amount, currency, created_at, agent_name in high_amount_transactions:
            alerts += f"   💎 `{code}` | {sender} → {receiver}\n"
            alerts += f"      💰 {amount:,.0f} {currency} | عامل: {agent_name}\n"
        alerts += "\n"
    
    # اگر هیچ هشداری نبود
    if alert_count == 0:
        alerts += "✅ *هیچ هشداری وجود ندارد! سیستم در وضعیت عالی است.*\n\n"
    else:
        alerts += f"📊 *مجموع هشدارها: {alert_count} مورد*\n\n"
    
    alerts += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    alerts += f"📅 آخرین بررسی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
    
    keyboard = [
        ["🔄 بررسی مجدد هشدارها", "💰 مدیریت مالی مرکزی"],
        ["📊 گزارش مالی", "🔙 بازگشت به منوی ادمین"]
    ]
    
    await update.message.reply_text(
        alerts,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


@require_admin
async def system_health_check(update, context):
    """بررسی سلامت کلی سیستم"""
    await update.message.reply_text("🏥 در حال بررسی سلامت سیستم...")
    
    conn = get_db()
    cur = conn.cursor()
    
    health_status = []
    issues = []
    
    # بررسی ۱: تعداد کل عامل‌ها
    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]
    
    if active_agents == 0:
        issues.append("❌ هیچ عامل فعلی وجود ندارد")
    elif active_agents < 3:
        issues.append(f"⚠️ تعداد عامل‌های فعال کم است: {active_agents}")
    else:
        health_status.append(f"✅ عامل‌های فعال: {active_agents}")
    
    # بررسی ۲: موجودی کل سیستم
    cur.execute("SELECT SUM(balance) FROM balances WHERE currency = 'AFN'")
    total_afn = cur.fetchone()[0] or 0
    
    if total_afn == 0:
        issues.append("❌ هیچ موجودی در سیستم ثبت نشده")
    elif total_afn < 10000:
        issues.append(f"⚠️ موجودی کل سیستم کم است: {total_afn:,.0f} افغانی")
    else:
        health_status.append(f"✅ موجودی کل سیستم: {total_afn:,.0f} افغانی")
    
    # بررسی ۳: حواله‌های در انتظار
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending'")
    pending_count = cur.fetchone()[0]
    
    if pending_count > 100:
        issues.append(f"⚠️ حواله‌های در انتظار زیاد است: {pending_count}")
    else:
        health_status.append(f"✅ حواله‌های در انتظار: {pending_count}")
    
    # بررسی ۴: حواله‌های قدیمی
    three_days_ago = (dt.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM transactions WHERE status = 'pending' AND DATE(created_at) < ?", (three_days_ago,))
    old_pending = cur.fetchone()[0]
    
    if old_pending > 10:
        issues.append(f"⚠️ حواله‌های قدیمی در انتظار: {old_pending}")
    else:
        health_status.append(f"✅ حواله‌های قدیمی: {old_pending}")
    
    # بررسی ۵: عامل‌های با موجودی صفر
    cur.execute("""
        SELECT COUNT(*) FROM agents a 
        WHERE a.is_active = 1 AND NOT EXISTS (
            SELECT 1 FROM balances b WHERE b.agent_id = a.id AND b.balance > 0
        )
    """)
    zero_balance_count = cur.fetchone()[0]
    
    if zero_balance_count > active_agents * 0.5:  # بیش از نصف عامل‌ها موجودی صفر دارند
        issues.append(f"⚠️ درصد بالایی از عامل‌ها موجودی صفر دارند: {zero_balance_count}/{active_agents}")
    else:
        health_status.append(f"✅ عامل‌های با موجودی صفر: {zero_balance_count}")
    
    conn.close()
    
    # ساخت گزارش سلامت
    health_report = "🏥 *گزارش سلامت سیستم*\n"
    health_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    if issues:
        health_report += "🚨 *مسائل شناسایی شده:*\n"
        for issue in issues:
            health_report += f"   {issue}\n"
        health_report += "\n"
    
    if health_status:
        health_report += "✅ *وضعیت عالی:*\n"
        for status in health_status:
            health_report += f"   {status}\n"
        health_report += "\n"
    
    # امتیاز سلامت
    total_checks = 5
    passed_checks = total_checks - len(issues)
    health_score = (passed_checks / total_checks) * 100
    
    health_report += "📊 *امتیاز سلامت:*\n"
    health_report += f"   🎯 {health_score:.0f}% ({passed_checks}/{total_checks})\n\n"
    
    if health_score >= 80:
        health_report += "🟢 *وضعیت سیستم: عالی*\n"
    elif health_score >= 60:
        health_report += "🟡 *وضعیت سیستم: خوب*\n"
    else:
        health_report += "🔴 *وضعیت سیستم: نیاز به توجه*\n"
    
    health_report += "\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    health_report += f"📅 زمان بررسی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
    
    keyboard = [
        ["🚨 هشدارها و اطلاعیه‌ها", "💰 مدیریت مالی مرکزی"],
        ["🔄 بررسی مجدد سلامت", "🔙 بازگشت به منوی ادمین"]
    ]
    
    await update.message.reply_text(
        health_report,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
