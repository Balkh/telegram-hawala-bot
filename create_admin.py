#!/usr/bin/env python3

import os
import sqlite3
import bcrypt
import secrets
import string


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()


def generate_strong_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_admin_once():
    # اطلاعات ادمین (ورودی از ENV یا پیش‌فرض امن)
    username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
    password = os.getenv("INITIAL_ADMIN_PASSWORD") or generate_strong_password()
    password_hash = hash_password(password)

    conn = sqlite3.connect("hawala.db")
    cursor = conn.cursor()

    # بررسی وجود ادمین
    cursor.execute("SELECT COUNT(*) FROM admins")
    admin_count = cursor.fetchone()[0]

    if admin_count > 0:
        print("ℹ️ ادمین قبلاً وجود دارد، کاری انجام نشد.")
        conn.close()
        return

    # ایجاد ادمین
    cursor.execute(
        """
        INSERT INTO admins (username, password_hash, is_active)
        VALUES (?, ?, 1)
        """,
        (username, password_hash),
    )

    conn.commit()
    conn.close()

    print("✅ ادمین با موفقیت ایجاد شد")
    print(f"👤 username: {username}")
    print(f"🔐 password: {password}")


if __name__ == "__main__":
    create_admin_once()
