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
            FOREIGN KEY(agent_id) REFERENCES agents(id)
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
        "SELECT id, password_hash, is_active, telegram_id FROM admins WHERE username = ?",
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

    cur.execute(
        "UPDATE admins SET telegram_id = ? WHERE id = ?",
        (telegram_id, admin_id),
    )

    conn.commit()
    conn.close()


def get_agent_by_telegram_id(telegram_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, is_active FROM agents WHERE telegram_id = ?",
        (telegram_id,),
    )
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

    cur.execute(
        "UPDATE agents SET telegram_id = ? WHERE id = ?",
        (telegram_id, agent_id),
    )

    conn.commit()
    conn.close()


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
