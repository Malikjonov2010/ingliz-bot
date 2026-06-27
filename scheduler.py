import asyncio
from datetime import datetime
import pytz
import logging
from config import ADMIN_IDS

# Weekday mapping from Python's weekday() to Uzbek standard names
WEEKDAYS_UZ = {
    0: "Dushanba",
    1: "Seshanba",
    2: "Chorshanba",
    3: "Payshanba",
    4: "Juma",
    5: "Shanba",
    6: "Yakshanba"
}

async def check_schedules(bot, db):
    tz = pytz.timezone('Asia/Tashkent')
    
    while True:
        try:
            now = datetime.now(tz)
            current_day_str = WEEKDAYS_UZ[now.weekday()].lower()
            current_time_str = now.strftime("%H:%M")
            
            groups = await db.get_all_groups()
            for group in groups:
                days = group.get('days', '').lower()
                g_time = group.get('time', '').strip()
                
                # Check if today is in the group's days and the current time matches
                if current_day_str in days and current_time_str == g_time:
                    teacher_id = group.get('teacher_id')
                    group_name = group.get('name')
                    
                    msg = (f"🔔 **Dars vaqti bo'ldi!**\n\n"
                           f"Sizning **{group_name}** guruhingiz uchun dars boshlandi.\n"
                           f"Darsni o'tib bo'lgach, iltimos o'quvchilarning davomatini va dars o'zlashtirish ballarini belgilashni unutmang!")
                    
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    
                    # Create inline button for easy grading
                    # Note: Telegram callback_data limit is 64 bytes, ensure group_name is not too long
                    safe_group_name = group_name[:40] if group_name else ""
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 O'quvchilarga ball qo'yish", callback_data=f"score_list:{safe_group_name}")]
                    ])
                    
                    # Send to teacher if exists, else send to all admins
                    if teacher_id:
                        try:
                            await bot.send_message(teacher_id, msg, parse_mode="Markdown", reply_markup=kb)
                        except Exception as e:
                            logging.error(f"Failed to send schedule to teacher {teacher_id}: {e}")
                    else:
                        for admin_id in ADMIN_IDS:
                            try:
                                await bot.send_message(admin_id, msg, parse_mode="Markdown", reply_markup=kb)
                            except Exception as e:
                                pass
                                
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
            
        # Wait until the start of the next minute
        now = datetime.now(tz)
        sleep_seconds = 60 - now.second
        if sleep_seconds <= 0:
            sleep_seconds = 60
        await asyncio.sleep(sleep_seconds)

def start_scheduler(bot, db):
    asyncio.create_task(check_schedules(bot, db))
