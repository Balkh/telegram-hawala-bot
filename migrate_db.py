import sqlite3

conn = sqlite3.connect("hawala.db")
cur = conn.cursor()

# افزودن موجودی
try:
    cur.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

# افزودن ارز موجودی
try:
    cur.execute("ALTER TABLE users ADD COLUMN currency TEXT DEFAULT 'AFN'")
except sqlite3.OperationalError:
    pass

# وضعیت فعال / غیرفعال
try:
    cur.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("✅ دیتابیس با موفقیت آپدیت شد")
