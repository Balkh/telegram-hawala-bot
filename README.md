# Hawala Telegram Bot

ربات تلگرام برای مدیریت حواله، عامل‌ها و گزارش مالی

## Features
- مدیریت عامل‌ها (Admin)
- ثبت حواله
- محاسبه کارمزد
- گزارش مالی (در حال توسعه)

## Tech Stack
- Python
- python-telegram-bot
- SQLite / PostgreSQL

## Setup
```bash
git clone https://github.com/USERNAME/hawala-bot.git
cd hawala-bot
pip install -r requirements.txt
cp .env.example .env
python bot.py

## Database
The project uses a single `db.py` file to manage all database operations.
