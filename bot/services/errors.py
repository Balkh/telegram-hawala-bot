import logging
from config import ADMIN_IDS

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


async def global_error_handler(update, context):
    """
    Error Handler سراسری
    """

    # 🔥 لاگ کامل خطا با traceback
    logging.error(
        "Unhandled error occurred",
        exc_info=context.error,
    )

    # 📩 پیام ساده به کاربر
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ خطای سیستمی رخ داد\n🏠 برای بازگشت /start را بزنید",
        )

    # 🚨 ارسال جزئیات خطا به ادمین
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"🚨 ERROR:\n{context.error}",
        )
