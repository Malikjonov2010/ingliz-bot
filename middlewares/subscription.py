from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any, Awaitable
from config import ADMIN_IDS

# The required channels
CHANNELS = [
    {"username": "@Muhammaddiyor_blog", "url": "https://t.me/Muhammaddiyor_blog"},
    {"username": "@Epic_brand", "url": "https://t.me/Epic_brand"}
]

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        # event is either Message or CallbackQuery
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if event.data == "check_subscription":
                return await handler(event, data)
        else:
            return await handler(event, data)
            
        # Adminlar uchun tekshiruv shart emas
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        bot = data.get("bot")
        if not bot:
            return await handler(event, data)
            
        unsubscribed_channels = []
        
        for channel in CHANNELS:
            try:
                member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
                # valid statuses: 'member', 'administrator', 'creator', 'restricted'
                if member.status not in ["member", "administrator", "creator", "restricted"]:
                    unsubscribed_channels.append(channel)
            except Exception:
                # Agar bot kanalga admin qilinmagan bo'lsa xato beradi yoki kanal topilmasa
                pass
                
        if unsubscribed_channels:
            keyboard = []
            for ch in unsubscribed_channels:
                keyboard.append([InlineKeyboardButton(text=f"Obuna bo'lish ({ch['username']})", url=ch['url'])])
            
            keyboard.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_subscription")])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            text = "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz shart!</b>\n\nIltimos, avval kanallarga obuna bo'ling va so'ng <b>Tasdiqlash</b> tugmasini bosing."
            
            if isinstance(event, Message):
                await event.answer(text, reply_markup=reply_markup, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
                await event.answer()
            return # Prevent further processing
            
        return await handler(event, data)
