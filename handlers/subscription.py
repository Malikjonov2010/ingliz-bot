from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from middlewares.subscription import CHANNELS

router = Router()

@router.callback_query(F.data == "check_subscription")
async def process_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    unsubscribed_channels = []
    
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator", "restricted"]:
                unsubscribed_channels.append(channel)
        except Exception:
            pass
            
    if unsubscribed_channels:
        await callback.answer("❌ Siz hamma kanallarga obuna bo'lmagansiz! Iltimos, barcha kanallarga obuna bo'ling.", show_alert=True)
    else:
        await callback.answer("✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.", show_alert=True)
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer("🎉 Rahmat! Botdan foydalanish uchun /start buyrug'ini yuboring yoki o'z ishingizni davom ettiring.")
