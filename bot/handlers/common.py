from telegram import ReplyKeyboardRemove

from bot.services.database import unbind_telegram_id


async def exit_menu(update, context):
    user_id = update.effective_user.id

    unbind_telegram_id(user_id)

    await update.message.reply_text(
        "🚪 با موفقیت خارج شدید",
        reply_markup=ReplyKeyboardRemove(),
    )
