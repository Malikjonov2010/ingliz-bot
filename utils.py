import asyncio
import logging

async def notify_admins_async(bot, text: str, admin_ids: list, parse_mode: str = "Markdown", reply_markup=None):
    """
    Asynchronously sends a notification to all admins without blocking the main workflow.
    """
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            await asyncio.sleep(0.05)  # Telegram API limits: max 30 messages/second
        except Exception as e:
            logging.error(f"Failed to send to admin {admin_id}: {e}")

async def broadcast_message_async(bot, users: list, text: str, parse_mode: str = "Markdown"):
    """
    Asynchronously broadcasts a message to multiple users.
    """
    count = 0
    for u in users:
        try:
            await bot.send_message(
                chat_id=u['telegram_id'],
                text=f"📢 **Admindan xabar:**\n\n{text}",
                parse_mode=parse_mode
            )
            count += 1
            await asyncio.sleep(0.05)  # Telegram API limits
        except Exception as e:
            logging.error(f"Failed to send to user {u['telegram_id']}: {e}")
    
    return count
