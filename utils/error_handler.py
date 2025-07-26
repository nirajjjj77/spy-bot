from telegram import Update
from telegram.ext import CallbackContext
from utils.constants import ADMIN_IDS
from utils.logger import logger

def error_handler(update: Update, context: CallbackContext):
    """Log errors and notify admins"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ Error occurred:\n{context.error}\n\nIn update:\n{update}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")