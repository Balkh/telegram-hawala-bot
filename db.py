import sqlite3
import datetime
import bcrypt
import os
import logging

DB_NAME = "hawala.db"


# ================= CONNECTION =================


def get_conn():
    return sqlite3.connect(DB_NAME)


# ================= INIT DB =================


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # ---------- USERS ----------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        province TEXT,
        cash_afn REAL DEFAULT 0,
        cash_usd REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """
    )

    # ---------- HAWALAS ----------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS hawalas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        sender_name TEXT NOT NULL,
        receiver_name TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        from_province TEXT NOT NULL,
        to_province TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        paid_by INTEGER,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
    )

    # ---------- FINANCE LOG ----------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS finance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,        -- in / out
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    )
    """
    )

    conn.commit()
    conn.close()


# ================= ADMIN =================


def create_default_admin():
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")

    if not username or not password:
        return

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE role='admin'")
    if cur.fetchone():
        conn.close()
        return

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cur.execute(
        """
        INSERT INTO users (username, password, role)
        VALUES (?, ?, 'admin')
    """,
        (username, password_hash),
    )

    conn.commit()
    conn.close()


# ================= USERS =================


def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, username, password, role, province, cash_afn, cash_usd
        FROM users WHERE username=?
    """,
        (username,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "password": row[2],
        "role": row[3],
        "province": row[4],
        "cash_afn": row[5],
        "cash_usd": row[6],
    }


def create_agent(username, password_hash, province, balance=0, currency="AFN"):
    """
    Creates an agent and sets initial balance in the correct currency column.
    balance: numeric (int/float)
    currency: "AFN" or "USD"
    """
    conn = get_conn()
    cur = conn.cursor()

    # normalize
    try:
        bal = float(balance) if balance is not None else 0.0
    except Exception:
        bal = 0.0

    cash_afn = bal if currency == "AFN" else 0.0
    cash_usd = bal if currency == "USD" else 0.0

    try:
        cur.execute(
            """
            INSERT INTO users
            (username, password, role, province, cash_afn, cash_usd)
            VALUES (?, ?, 'agent', ?, ?, ?)
        """,
            (username, password_hash, province, cash_afn, cash_usd),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        logging.exception("IntegrityError when creating agent %s", username)
        conn.rollback()
        raise
    except Exception:
        logging.exception("Unexpected error when creating agent %s", username)
        conn.rollback()
        raise
    finally:
        conn.close()


# ================= BALANCE =================


def get_agent_balance(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT cash_afn, cash_usd
        FROM users WHERE id=?
    """,
        (user_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {"AFN": row[0], "USD": row[1]}


def update_agent_balance(user_id, currency, amount):
    field = "cash_afn" if currency == "AFN" else "cash_usd"

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        f"""
        UPDATE users
        SET {field} = {field} + ?
        WHERE id=?
    """,
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def log_finance(user_id, ftype, amount, currency, desc):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO finance_logs
        (user_id, type, amount, currency, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            user_id,
            ftype,
            amount,
            currency,
            desc,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )

    conn.commit()
    conn.close()


# ================= HAWALAS =================


def create_hawala(
    code, sender, receiver, amount, currency, from_province, to_province, user_id
):
    conn = get_conn()
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
            sender,
            receiver,
            amount,
            currency,
            from_province,
            to_province,
            user_id,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )

    conn.commit()
    conn.close()


def get_hawala_by_code(code):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT code, sender_name, receiver_name,
               amount, currency, from_province,
               to_province, status, created_by
        FROM hawalas WHERE code=?
    """,
        (code,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "code": row[0],
        "sender": row[1],
        "receiver": row[2],
        "amount": row[3],
        "currency": row[4],
        "from_province": row[5],
        "to_province": row[6],
        "status": row[7],
        "created_by": row[8],
    }


def mark_hawala_paid(code, agent_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hawalas
        SET status='paid', paid_by=?
        WHERE code=? AND status='pending'
    """,
        (agent_id, code),
    )

    conn.commit()
    conn.close()


def get_hawala_for_edit(code, user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM hawalas
        WHERE code=? AND created_by=? AND status='pending'
    """,
        (code, user_id),
    )

    row = cur.fetchone()
    conn.close()
    return row


def update_hawala(code, amount, currency, to_province):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hawalas
        SET amount=?, currency=?, to_province=?
        WHERE code=? AND status='pending'
    """,
        (amount, currency, to_province, code),
    )

    conn.commit()
    conn.close()


def delete_hawala(code):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM hawalas
        WHERE code=? AND status='pending'
    """,
        (code,),
    )

    conn.commit()
    conn.close()


# ================= REPORTS =================


def daily_report(date=None):
    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT to_province, currency, SUM(amount)
        FROM hawalas
        WHERE date(created_at)=?
        GROUP BY to_province, currency
    """,
        (date,),
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_agents():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, username, province, cash_afn, cash_usd, is_active
        FROM users
        WHERE role='agent'
        ORDER BY username
    """
    )

    rows = cur.fetchall()
    conn.close()

    agents = []
    for r in rows:
        cash_afn = r[3] or 0.0
        cash_usd = r[4] or 0.0
        # choose non-zero currency for convenience (if both zero, default AFN)
        if abs(cash_afn) > 0:
            balance = cash_afn
            currency = "AFN"
        elif abs(cash_usd) > 0:
            balance = cash_usd
            currency = "USD"
        else:
            balance = 0
            currency = "AFN"

        agents.append(
            {
                "id": r[0],
                "username": r[1],
                "province": r[2],
                "balance": balance,
                "currency": currency,
                "is_active": r[5],
            }
        )

    return agents
