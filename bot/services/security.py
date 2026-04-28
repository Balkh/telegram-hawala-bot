# bot/services/security.py
from bot.services.database import get_db
import bcrypt
import re


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_agent_password(password: str) -> bool:
    if len(password) < 6:
        return False
    if not re.search(r"[A-Za-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True


def validate_admin_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[A-Za-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True


# 🔐 چک فعال بودن عامل
def check_agent_active(agent_id: int) -> bool:
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT is_active FROM agents WHERE id = ?", (agent_id,))
    row = cur.fetchone()

    conn.close()
    return bool(row and row[0] == 1)
