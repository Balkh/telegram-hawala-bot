from functools import wraps
from config import ADMIN_IDS


def admin_required(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔ دسترسی غیرمجاز")
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
