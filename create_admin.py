import getpass
import sqlite3
from bot.services.security import hash_password

DB_PATH = "hawala.db"


def create_admin():
    username = input("Admin username: ").strip()
    password = getpass.getpass("Admin password: ")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO admins (username, password_hash, is_active)
        VALUES (?, ?, 1)
        """,
        (username, hash_password(password)),
    )

    conn.commit()
    conn.close()

    print("✅ Admin created successfully")


if __name__ == "__main__":
    create_admin()
