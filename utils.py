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

def get_student_profile_text(student: dict, page_info: str = "") -> str:
    days = student.get('days') or "Noma'lum"
    time = student.get('time') or "Noma'lum"
    bio = student.get('teacher_bio')
    bio_text = f"\n\n📝 **Ustoz fikri:** {bio}" if bio else ""
    
    level_val = student.get('level', "Noma'lum")
    student_level_val = student.get('student_level', 'Belgilanmagan')
    
    username = student.get('username')
    username_text = f"**Username:** @{username}\n" if username else "**Username:** Yo'q\n"
    profile_link = f"**Profil:** [{student['first_name']}](tg://user?id={student['telegram_id']})\n"
    
    text = f"👤 **O'quvchi ma'lumotlari{page_info}:**\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"📛 **Ism-familiya:** {student['first_name']} {student['last_name']}\n" \
           f"🔗 {username_text}" \
           f"🎂 **Yosh:** {student['age']}\n" \
           f"📞 **Tel:** {student['phone_number']}\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"🏫 **Guruh/Daraja:** {level_val}\n" \
           f"🗓 **Kunlar:** {days}\n" \
           f"⏰ **Vaqti:** {time}\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"🆔 **ID:** {student['telegram_id']}\n" \
           f"👤 {profile_link}" \
           f"🎓 **O'quvchi maqomi:** {student_level_val}" \
           f"{bio_text}"
    return text

def get_student_profile_keyboard(student_id: int, back_callback_data: str = "astud_list", extra_buttons=None):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="🎓 Ingliz tili darajasi", callback_data=f"astud_eng_lvl:{student_id}")],
        [InlineKeyboardButton(text="📝 Dars o'zlashtirishi", callback_data=f"astud_score_info:{student_id}")],
        [InlineKeyboardButton(text="📝 Ustoz fikri (Bio) yozish", callback_data=f"astud_bio:{student_id}")],
        [InlineKeyboardButton(text="📩 Xabar yuborish", callback_data=f"astud_msg:{student_id}")]
    ]
    if extra_buttons:
        for b in extra_buttons:
            buttons.append(b)
            
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_student_profile_text_and_keyboard(db, student_id, back_callback_data="astud_list"):
    student = await db.get_user(student_id)
    if not student:
        return None, None
    text = get_student_profile_text(student)
    kb = get_student_profile_keyboard(student_id, back_callback_data)
    return text, kb