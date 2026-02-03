from bot.services.database import get_admin_by_telegram_id

# آیدی تلگرام خودت رو بذار
admin = get_admin_by_telegram_id(6458047080)
print(f"Admin: {admin}")
