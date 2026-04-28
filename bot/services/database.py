import sqlite3
from datetime import datetime


def get_db():
    conn = sqlite3.connect("hawala.db")
    conn.row_factory = sqlite3.Row  # ⭐⭐⭐ مهم
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # جدول ادمین
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        telegram_id INTEGER UNIQUE,
        is_active INTEGER DEFAULT 1
    );

        """
    )

    # اطمینان از وجود ستون‌های امنیتی برای ادمین
    cur.execute("PRAGMA table_info(admins)")
    admin_columns = [row["name"] for row in cur.fetchall()]
    if "failed_attempts" not in admin_columns:
        cur.execute("ALTER TABLE admins ADD COLUMN failed_attempts INTEGER DEFAULT 0")
    if "locked_at" not in admin_columns:
        cur.execute("ALTER TABLE admins ADD COLUMN locked_at TEXT")

    # جدول عامل‌ها
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            province TEXT,
            phone TEXT UNIQUE,
            tazkira TEXT UNIQUE,
            telegram_id INTEGER UNIQUE,
            password_hash TEXT,
            is_active INTEGER DEFAULT 1,
            -- 🔐 امنیت لاگین
            failed_attempts INTEGER DEFAULT 0,
            locked_at TEXT
        )
        """
    )

    # جدول بیلانس‌ها
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            currency TEXT,
            balance REAL DEFAULT 0,
            FOREIGN KEY(agent_id) REFERENCES agents(id),
            UNIQUE(agent_id, currency)
        )
        """
    )

    # جدول حواله‌ها
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_code VARCHAR(10) UNIQUE,
            agent_id INTEGER,
            receiver_agent_id INTEGER,
            sender_name TEXT,
            receiver_name TEXT,
            receiver_tazkira TEXT,
            amount REAL,
            currency TEXT,
            commission REAL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            FOREIGN KEY (receiver_agent_id) REFERENCES agents(id)
        )
    """
    )

    # جدول درخواست‌های افزایش موجودی (شارژ حساب)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            amount REAL,
            currency TEXT,
            receipt_photo_id TEXT,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            admin_note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            category TEXT,
            amount REAL,
            currency TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            employee_name TEXT,
            monthly_salary REAL,
            currency TEXT,
            start_date TEXT,
            pay_day_of_month INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS fixed_expense_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER,
            name TEXT,
            category TEXT,
            amount REAL,
            currency TEXT,
            frequency TEXT,
            start_date TEXT,
            pay_day_of_month INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """
    )

    # پاکسازی ارزهای تکراری (در صورت وجود)
    cur.execute(
        """
        DELETE FROM balances 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM balances 
            GROUP BY agent_id, currency
        )
        """
    )

    conn.commit()
    conn.close()


# services/database.py
def get_admin_by_username(username):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            id,
            username,
            password_hash,
            is_active,
            telegram_id,
            failed_attempts,
            locked_at
        FROM admins 
        WHERE username = ?
        """,
        (username,),
    )
    row = cur.fetchone()
    conn.close()

    return row


def get_admin_by_telegram_id(telegram_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, username, is_active
        FROM admins
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "is_active": row[2],
    }


def bind_admin_telegram_id(admin_id: int, telegram_id: int):
    conn = get_db()
    cur = conn.cursor()

    # برای تست با یک اکانت تکی، آنبایند کردن را غیرفعال می‌کنیم
    # cur.execute(
    #     "UPDATE admins SET telegram_id = NULL WHERE telegram_id = ?",
    #     (telegram_id,),
    # )

    # متصل کردن به ادمین جدید
    cur.execute(
        "UPDATE admins SET telegram_id = ? WHERE id = ?",
        (telegram_id, admin_id),
    )

    conn.commit()
    conn.close()


def get_all_admins():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            id,
            username,
            is_active,
            telegram_id,
            failed_attempts,
            locked_at
        FROM admins
        ORDER BY id ASC
        """
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def increase_admin_failed_attempts(admin_id: int):
    """
    افزایش شمارنده تلاش ناموفق برای ادمین
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE admins
        SET failed_attempts = failed_attempts + 1
        WHERE id = ?
        """,
        (admin_id,),
    )

    conn.commit()
    conn.close()


def reset_admin_failed_attempts(admin_id: int):
    """
    ریست شمارنده تلاش ناموفق و پاک کردن زمان قفل برای ادمین
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE admins
        SET failed_attempts = 0,
            locked_at = NULL
        WHERE id = ?
        """,
        (admin_id,),
    )

    conn.commit()
    conn.close()


def lock_admin(admin_id: int):
    """
    قفل کامل حساب ادمین بعد از تلاش‌های ناموفق زیاد
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE admins
        SET is_active = 0,
            locked_at = ?
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(), admin_id),
    )

    conn.commit()
    conn.close()


def get_agent_by_telegram_id(telegram_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM agents WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()

    return row


def get_agent_by_id(agent_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
    row = cur.fetchone()
    conn.close()

    return row


def get_agent_by_phone(phone):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, password_hash, telegram_id, is_active FROM agents WHERE phone = ?",
        (phone,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def bind_agent_telegram_id(agent_id: int, telegram_id: int):
    conn = get_db()
    cur = conn.cursor()

    # برای تست با یک اکانت تکی، آنبایند کردن را غیرفعال می‌کنیم
    # cur.execute(
    #     "UPDATE agents SET telegram_id = NULL WHERE telegram_id = ?",
    #     (telegram_id,),
    # )

    # متصل کردن به عامل جدید
    cur.execute(
        "UPDATE agents SET telegram_id = ? WHERE id = ?",
        (telegram_id, agent_id),
    )

    conn.commit()
    conn.close()


def get_active_agents_with_telegram():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, telegram_id
        FROM agents
        WHERE is_active = 1 AND telegram_id IS NOT NULL
        """,
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def increase_failed_attempts(agent_id):
    """
    افزایش شمارنده تلاش ناموفق
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE agents
        SET failed_attempts = failed_attempts + 1
        WHERE id = ?
        """,
        (agent_id,),
    )

    conn.commit()
    conn.close()


def reset_failed_attempts(agent_id):
    """
    ریست شمارنده بعد از لاگین موفق
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE agents
        SET failed_attempts = 0,
            locked_at = NULL
        WHERE id = ?
        """,
        (agent_id,),
    )

    conn.commit()
    conn.close()


def lock_agent(agent_id):
    """
    قفل کامل حساب عامل
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE agents
        SET is_active = 0,
            locked_at = ?
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(), agent_id),
    )

    conn.commit()
    conn.close()


def unbind_telegram_id(telegram_id: int):
    """
    قطع اتصال telegram_id از ادمین یا عامل (برای logout)
    """
    conn = get_db()
    cur = conn.cursor()

    # حذف از ادمین
    cur.execute(
        "UPDATE admins SET telegram_id = NULL WHERE telegram_id = ?",
        (telegram_id,),
    )

    # حذف از عامل
    cur.execute(
        "UPDATE agents SET telegram_id = NULL WHERE telegram_id = ?",
        (telegram_id,),
    )

    conn.commit()
    conn.close()


def unbind_admin_telegram_id(telegram_id: int):
    """
    قطع اتصال telegram_id فقط از ادمین
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE admins SET telegram_id = NULL WHERE telegram_id = ?",
        (telegram_id,),
    )

    conn.commit()
    conn.close()
    print(f"✅ Admin telegram_id {telegram_id} unbound")  # برای دیباگ


def unbind_agent_telegram_id(telegram_id: int):
    """
    قطع اتصال telegram_id فقط از عامل
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE agents SET telegram_id = NULL WHERE telegram_id = ?",
        (telegram_id,),
    )

    conn.commit()
    conn.close()
    print(f"✅ Agent telegram_id {telegram_id} unbound")  # برای دیباگ


# توابع مربوط به transactions
def get_agent_balance(agent_id, currency="AFN"):
    """دریافت موجودی عامل"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT balance 
        FROM balances 
        WHERE agent_id = ? AND currency = ?
    """,
        (agent_id, currency),
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else 0.0


def check_sufficient_balance(agent_id, amount, currency="AFN"):
    """چک کردن کافی بودن موجودی"""
    balance = get_agent_balance(agent_id, currency)
    return balance >= amount


def update_agent_balance(agent_id, amount, currency="AFN"):
    """
    بروزرسانی موجودی عامل
    amount: مقدار مثبت برای افزایش، منفی برای کاهش
    """
    conn = get_db()
    cur = conn.cursor()

    # اول مطمئن شو رکورد وجود داره
    cur.execute(
        """
        SELECT id FROM balances 
        WHERE agent_id = ? AND currency = ?
    """,
        (agent_id, currency),
    )

    if not cur.fetchone():
        # اگر رکورد وجود نداشت، ایجاد کن
        cur.execute(
            """
            INSERT INTO balances (agent_id, currency, balance)
            VALUES (?, ?, ?)
        """,
            (agent_id, currency, 0.0),
        )

    # حالا موجودی رو بروز کن
    cur.execute(
        """
        UPDATE balances 
        SET balance = balance + ?
        WHERE agent_id = ? AND currency = ?
    """,
        (amount, agent_id, currency),
    )

    conn.commit()
    conn.close()


def create_transaction(transaction_data):
    """
    ایجاد حواله جدید
    transaction_data: دیکشنری با کلیدهای مورد نیاز
    """
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO transactions 
            (transaction_code, agent_id, receiver_agent_id, sender_name, 
             receiver_name, receiver_tazkira, amount, currency, commission, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                transaction_data["transaction_code"],
                transaction_data["agent_id"],
                transaction_data["receiver_agent_id"],
                transaction_data.get("sender_name", "مشتری حضوری"),
                transaction_data["receiver_name"],
                transaction_data["receiver_tazkira"],
                transaction_data["amount"],
                transaction_data["currency"],
                transaction_data["commission"],
                transaction_data.get("status", "pending"),
            ),
        )

        transaction_id = cur.lastrowid
        conn.commit()

        return transaction_id

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_agent_transactions(agent_id, limit=20):
    """
    دریافت حواله‌های یک عامل
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            t.id,
            t.transaction_code,
            t.receiver_name,
            t.amount,
            t.currency,
            t.commission,
            t.status,
            t.created_at,
            a.name as receiver_agent_name,
            a.province as receiver_province
        FROM transactions t
        LEFT JOIN agents a ON t.receiver_agent_id = a.id
        WHERE t.agent_id = ?
        ORDER BY t.created_at DESC
        LIMIT ?
    """,
        (agent_id, limit),
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def get_transaction_by_code(transaction_code):
    """
    دریافت حواله با کد
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            t.*,
            a1.name as sender_agent_name,
            a2.name as receiver_agent_name,
            a2.province as receiver_province
        FROM transactions t
        LEFT JOIN agents a1 ON t.agent_id = a1.id
        LEFT JOIN agents a2 ON t.receiver_agent_id = a2.id
        WHERE t.transaction_code = ?
    """,
        (transaction_code,),
    )

    row = cur.fetchone()
    conn.close()

    return row


def update_transaction_status(transaction_id, status):
    """
    بروزرسانی وضعیت حواله
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE transactions 
        SET status = ?, 
            completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END
        WHERE id = ?
    """,
        (status, status, transaction_id),
    )

    conn.commit()
    conn.close()


def create_agent_expense(agent_id, category, amount, currency, description=""):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO agent_expenses (agent_id, category, amount, currency, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (agent_id, category, amount, currency, description),
    )

    conn.commit()
    conn.close()


def create_staff_contract(
    agent_id,
    employee_name,
    monthly_salary,
    currency,
    start_date,
    pay_day_of_month,
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO staff_contracts (
            agent_id,
            employee_name,
            monthly_salary,
            currency,
            start_date,
            pay_day_of_month
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            employee_name,
            monthly_salary,
            currency,
            start_date,
            pay_day_of_month,
        ),
    )

    conn.commit()
    conn.close()


def get_staff_contracts_for_agent(agent_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            employee_name,
            monthly_salary,
            currency,
            start_date,
            pay_day_of_month,
            is_active
        FROM staff_contracts
        WHERE agent_id = ?
        ORDER BY employee_name
        """,
        (agent_id,),
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def create_fixed_expense_contract(
    agent_id,
    name,
    category,
    amount,
    currency,
    frequency,
    start_date,
    pay_day_of_month,
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO fixed_expense_contracts (
            agent_id,
            name,
            category,
            amount,
            currency,
            frequency,
            start_date,
            pay_day_of_month
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent_id,
            name,
            category,
            amount,
            currency,
            frequency,
            start_date,
            pay_day_of_month,
        ),
    )

    conn.commit()
    conn.close()


def get_fixed_expense_contracts_for_agent(agent_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            name,
            category,
            amount,
            currency,
            frequency,
            start_date,
            pay_day_of_month,
            is_active
        FROM fixed_expense_contracts
        WHERE agent_id = ?
        ORDER BY name
        """,
        (agent_id,),
    )

    rows = cur.fetchall()
    conn.close()

    return rows
