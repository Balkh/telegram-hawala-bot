import datetime
import pandas as pd
import io
from datetime import datetime as dt

from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler
import logging

from bot.services.database import get_db
from bot.services.auth import require_admin

logger = logging.getLogger(__name__)


# =======================
# 📈 داشبورد آماری پیشرفته
# =======================


@require_admin
async def dashboard_stats(update, context):
    """داشبورد آماری پیشرفته"""
    await update.message.reply_text("📈 در حال آماده‌سازی داشبورد آماری...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # آمار کلی
    cur.execute("SELECT COUNT(*) FROM agents WHERE is_active = 1")
    active_agents = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(amount) FROM transactions WHERE status != 'cancelled'")
    total_amount = cur.fetchone()[0] or 0
    
    cur.execute("SELECT SUM(commission) FROM transactions WHERE status != 'cancelled'")
    total_commission = cur.fetchone()[0] or 0
    
    # آمار ۷ روز گذشته
    seven_days_ago = (dt.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT COUNT(*) FROM transactions 
        WHERE DATE(created_at) >= ?
    """, (seven_days_ago,))
    last_7_days_transactions = cur.fetchone()[0]
    
    cur.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE DATE(created_at) >= ? AND status != 'cancelled'
    """, (seven_days_ago,))
    last_7_days_amount = cur.fetchone()[0] or 0
    
    # آمار ۳۰ روز گذشته
    thirty_days_ago = (dt.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT COUNT(*) FROM transactions 
        WHERE DATE(created_at) >= ?
    """, (thirty_days_ago,))
    last_30_days_transactions = cur.fetchone()[0]
    
    cur.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE DATE(created_at) >= ? AND status != 'cancelled'
    """, (thirty_days_ago,))
    last_30_days_amount = cur.fetchone()[0] or 0
    
    # پرکارترین عامل‌ها
    cur.execute("""
        SELECT a.name, COUNT(t.id) as transaction_count,
               SUM(t.commission) as total_commission
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        WHERE a.is_active = 1
        GROUP BY a.id, a.name
        ORDER BY transaction_count DESC
        LIMIT 3
    """)
    top_agents = cur.fetchall()
    
    # کم‌کارترین عامل‌ها (فعال)
    cur.execute("""
        SELECT a.name, COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        WHERE a.is_active = 1
        GROUP BY a.id, a.name
        ORDER BY transaction_count ASC
        LIMIT 3
    """)
    least_active_agents = cur.fetchall()
    
    # بیشترین درآمدزا
    cur.execute("""
        SELECT a.name, SUM(t.commission) as total_commission,
               COUNT(t.id) as transaction_count
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        WHERE a.is_active = 1
        GROUP BY a.id, a.name
        HAVING total_commission > 0
        ORDER BY total_commission DESC
        LIMIT 3
    """)
    top_earners = cur.fetchall()
    
    conn.close()
    
    # ساخت داشبورد
    dashboard = "📈 *داشبورد آماری پیشرفته*\n"
    dashboard += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    # آمار کلی
    dashboard += "📊 *آمار کلی سیستم:*\n"
    dashboard += f"   👥 عامل‌های فعال: {active_agents}\n"
    dashboard += f"   📦 کل حواله‌ها: {total_transactions:,}\n"
    dashboard += f"   💰 مجموع مبالغ: {total_amount:,.0f} افغانی\n"
    dashboard += f"   💸 مجموع کارمزدها: {total_commission:,.0f} افغانی\n\n"
    
    # مقایسه دوره‌های زمانی
    dashboard += "📅 *مقایسه دوره‌های زمانی:*\n"
    dashboard += f"   🗓️ ۷ روز گذشته: {last_7_days_transactions:,} حواله ({last_7_days_amount:,.0f} افغانی)\n"
    dashboard += f"   🗓️ ۳۰ روز گذشته: {last_30_days_transactions:,} حواله ({last_30_days_amount:,.0f} افغانی)\n"
    
    if last_7_days_transactions > 0:
        avg_per_day = last_7_days_transactions / 7
        dashboard += f"   📊 میانگین روزانه (۷ روز): {avg_per_day:.1f} حواله\n"
    dashboard += "\n"
    
    # پرکارترین‌ها
    if top_agents:
        dashboard += "🏆 *پرکارترین عامل‌ها:*\n"
        for i, (name, count, commission) in enumerate(top_agents, 1):
            commission_text = f"{commission:,.0f}" if commission else "۰"
            dashboard += f"   {i}. {name} - {count} حواله ({commission_text} افغانی)\n"
        dashboard += "\n"
    
    # کم‌کارترین‌ها
    if least_active_agents:
        dashboard += "📉 *کم‌کارترین عامل‌ها (فعال):*\n"
        for i, (name, count) in enumerate(least_active_agents, 1):
            dashboard += f"   {i}. {name} - {count} حواله\n"
        dashboard += "\n"
    
    # بیشترین درآمدزا
    if top_earners:
        dashboard += "💰 *بیشترین درآمدزاها:*\n"
        for i, (name, commission, count) in enumerate(top_earners, 1):
            dashboard += f"   {i}. {name} - {commission:,.0f} افغانی ({count} حواله)\n"
        dashboard += "\n"
    
    dashboard += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    dashboard += f"📅 به‌روزرسانی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
    
    keyboard = [
        ["🔄 بروزرسانی داشبورد", "📊 گزارش مالی"],
        ["📥 دانلود گزارش اکسل", "🔙 بازگشت به منوی ادمین"]
    ]
    
    await update.message.reply_text(
        dashboard,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# =======================
# 📥 گزارش اکسل ادمین
# =======================


@require_admin
async def download_admin_excel_report(update, context):
    """دانلود گزارش کامل اکسل برای ادمین"""
    await update.message.reply_text("📥 در حال آماده‌سازی گزارش اکسل ادمین...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # دریافت تمام اطلاعات عامل‌ها
    cur.execute("""
        SELECT a.id, a.name, a.province, a.phone, a.is_active,
               b.balance, b.currency,
               COUNT(t.id) as transaction_count,
               SUM(t.amount) as total_amount,
               SUM(t.commission) as total_commission
        FROM agents a
        LEFT JOIN balances b ON a.id = b.agent_id
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        GROUP BY a.id, b.currency
        ORDER BY a.id
    """)
    agents_data = cur.fetchall()
    
    # دریافت آمار حواله‌ها بر اساس روز
    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count,
               SUM(amount) as total_amount, SUM(commission) as total_commission
        FROM transactions
        WHERE status != 'cancelled'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 30
    """)
    daily_stats = cur.fetchall()
    
    # دریافت آمار بر اساس ولایت
    cur.execute("""
        SELECT a.province, COUNT(t.id) as transaction_count,
               SUM(t.amount) as total_amount, SUM(t.commission) as total_commission
        FROM agents a
        LEFT JOIN transactions t ON a.id = t.agent_id AND t.status != 'cancelled'
        WHERE a.is_active = 1
        GROUP BY a.province
        ORDER BY total_amount DESC
    """)
    province_stats = cur.fetchall()
    
    conn.close()
    
    # ایجاد فایل اکسل
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # شیت خلاصه سیستم
            summary_data = {
                'بخش': ['کل عامل‌ها', 'عامل‌های فعال', 'کل حواله‌ها', 'مجموع مبلغ', 'مجموع کارمزد'],
                'مقدار': [
                    len(agents_data),
                    len([a for a in agents_data if a[4] == 1]),
                    sum([a[7] if a[7] is not None and isinstance(a[7], (int, float)) else 0 for a in agents_data]),
                    f"{sum([a[8] if a[8] is not None and isinstance(a[8], (int, float)) else 0 for a in agents_data]):,.0f} افغانی",
                    f"{sum([a[9] if a[9] is not None and isinstance(a[9], (int, float)) else 0 for a in agents_data]):,.0f} افغانی"
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='خلاصه سیستم', index=False)
            
            # شیت اطلاعات عامل‌ها
            agents_df = pd.DataFrame(agents_data, columns=[
                'کد عامل', 'نام', 'ولایت', 'تلفن', 'وضعیت', 'موجودی', 'ارز',
                'تعداد حواله', 'مجموع مبلغ', 'مجموع کارمزد'
            ])
            agents_df['وضعیت'] = agents_df['وضعیت'].apply(lambda x: 'فعال' if x == 1 else 'غیرفعال')
            agents_df.to_excel(writer, sheet_name='عامل‌ها', index=False)
            
            # شیت آمار روزانه
            daily_df = pd.DataFrame(daily_stats, columns=[
                'تاریخ', 'تعداد حواله', 'مبلغ کل', 'کارمزد کل'
            ])
            daily_df.to_excel(writer, sheet_name='آمار روزانه', index=False)
            
            # شیت آمار ولایت‌ها
            province_df = pd.DataFrame(province_stats, columns=[
                'ولایت', 'تعداد حواله', 'مبلغ کل', 'کارمزد کل'
            ])
            province_df.to_excel(writer, sheet_name='آمار ولایت‌ها', index=False)
        
        output.seek(0)
        
        filename = f"گزارش_ادمین_کامل_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        await update.message.reply_document(
            document=output,
            filename=filename,
            caption=f"📊 *گزارش کامل ادمین*\n\n"
                    f"📅 تاریخ: {dt.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"📦 شامل: اطلاعات عامل‌ها، آمار روزانه، آمار ولایت‌ها\n"
                    f"📊 تحلیل کامل عملکرد سیستم",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Error creating admin excel report")
        await update.message.reply_text(f"❌ خطا در ایجاد گزارش اکسل: {str(e)}")


# =======================
# 💸 پنل سود ادمین
# =======================

@require_admin
async def admin_profit_panel(update, context):
    """نمایش پنل سود ادمین بر اساس کمیسیون‌ها"""
    await update.message.reply_text("💸 در حال محاسبه سود سیستم...")
    
    conn = get_db()
    cur = conn.cursor()
    
    # سود کل بر اساس ارز
    cur.execute("""
        SELECT currency, SUM(commission) as total_profit, COUNT(*) as tx_count
        FROM transactions
        WHERE status != 'cancelled'
        GROUP BY currency
        ORDER BY total_profit DESC
    """)
    total_profits = cur.fetchall()
    
    # سود ۳۰ روز گذشته
    thirty_days_ago = (dt.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT currency, SUM(commission) as monthly_profit
        FROM transactions
        WHERE status != 'cancelled' AND DATE(created_at) >= ?
        GROUP BY currency
    """, (thirty_days_ago,))
    monthly_profits = {row[0]: row[1] for row in cur.fetchall()}
    
    # سود ۷ روز گذشته
    seven_days_ago = (dt.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT currency, SUM(commission) as weekly_profit
        FROM transactions
        WHERE status != 'cancelled' AND DATE(created_at) >= ?
        GROUP BY currency
    """, (seven_days_ago,))
    weekly_profits = {row[0]: row[1] for row in cur.fetchall()}
    
    # سود امروز
    today = dt.now().strftime('%Y-%m-%d')
    cur.execute("""
        SELECT currency, SUM(commission) as daily_profit
        FROM transactions
        WHERE status != 'cancelled' AND DATE(created_at) >= ?
        GROUP BY currency
    """, (today,))
    daily_profits = {row[0]: row[1] for row in cur.fetchall()}

    conn.close()
    
    # ساخت متن پنل
    text = "💸 *پنل سود و درآمد سیستم*\n"
    text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    if not total_profits:
        text += "📭 هنوز هیچ تراکنشی ثبت نشده است."
    else:
        for currency, total, count in total_profits:
            text += f"💰 *ارز: {currency}*\n"
            text += f"   📊 کل سود: {total:,.0f} {currency} ({count} حواله)\n"
            
            daily = daily_profits.get(currency, 0)
            text += f"   📅 سود امروز: {daily:,.0f} {currency}\n"
            
            weekly = weekly_profits.get(currency, 0)
            text += f"   🗓️ ۷ روز گذشته: {weekly:,.0f} {currency}\n"
            
            monthly = monthly_profits.get(currency, 0)
            text += f"   🗓️ ۳۰ روز گذشته: {monthly:,.0f} {currency}\n"
            text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
    text += f"\n📅 آخرین بروزرسانی: {dt.now().strftime('%Y/%m/%d %H:%M')}"
    
    keyboard = [
        ["🔄 بروزرسانی سود", "📊 گزارش مالی"],
        ["🔙 بازگشت به منوی ادمین"]
    ]
    
    # اضافه کردن دکمه بروزرسانی به context برای تشخیص در هندلرها اگر نیاز بود
    # در اینجا از MessageHandler با Regex استفاده می‌کنیم
    
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

