from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from config import ADMIN_IDS
from datetime import datetime, timezone

class BlockMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        # Adminlar bloklanmaydi
        if user_id in ADMIN_IDS:
            return await handler(event, data)
            
        db = data.get("db")
        if not db:
            return await handler(event, data)
            
        # Check if user is blocked
        if await db.is_blocked(user_id):
            # DB.is_blocked() updates state if expired, so if it returns True, they are currently blocked.
            async with db.pool.acquire() as conn:
                block_info = await conn.fetchrow(
                    "SELECT blocked_until, block_reason FROM users WHERE telegram_id = $1",
                    user_id
                )
                
            if block_info and block_info['blocked_until']:
                now = datetime.now(timezone.utc)
                remaining = block_info['blocked_until'] - now
                if remaining.total_seconds() > 0:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    
                    is_allowed = False
                    if isinstance(event, Message):
                        text = event.text or ""
                        # Faqat /start va Davomat uchun ruxsat beramiz
                        if text == "🙋‍♂️ Davomat" or text.startswith("/start"):
                            is_allowed = True
                    elif isinstance(event, CallbackQuery):
                        # Davomat tarixi uchun ruxsat beramiz
                        if event.data in ["attendance_history", "attendance_present", "attendance_absent"]:
                            is_allowed = True
                    
                    if not is_allowed:
                        text = (
                            f"🚫 <b>Siz blokdasiz!</b>\n"
                            f"Blokdan ochilishga: <b>{days} kun, {hours} soat</b> qoldi.\n"
                            f"Faqat Davomat funksiyasidan foydalanishingiz mumkin."
                        )
                        if isinstance(event, Message):
                            await event.answer(text, parse_mode="HTML")
                        elif isinstance(event, CallbackQuery):
                            await event.answer(text, show_alert=True)
                        return # Stop processing event since user is blocked
                    
        return await handler(event, data)
