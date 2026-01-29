# bot/services/security.py
from bot.services.database import get_db

import hashlib


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# 🔐 چک فعال بودن عامل
def check_agent_active(agent_id: int) -> bool:
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT is_active FROM agents WHERE id = ?", (agent_id,))
    row = cur.fetchone()

    conn.close()
    return bool(row and row[0] == 1)
