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

async def get_student_profile_text(student: dict, db=None, page_info: str = "") -> str:
    group = None
    if db:
        if student.get('group_id'):
            group = await db.get_group(student['group_id'])
        if not group and student.get('level'):
            async with db.pool.acquire() as connection:
                group = await connection.fetchrow("SELECT time, days FROM groups WHERE name = $1", student['level'])

    if group:
        days = group.get('days') or "Noma'lum"
        time = group.get('time') or "Noma'lum"
    else:
        days = student.get('days') or "Noma'lum"
        time = student.get('time') or "Noma'lum"
        
    import html
    
    bio = student.get('teacher_bio')
    bio_text = f"\n\n📝 <b>Ustoz fikri:</b> {html.escape(bio)}" if bio else ""
    
    level_val = student.get('level') or "Noma'lum"
    student_level_val = student.get('student_level') or 'Belgilanmagan'
    
    username = student.get('username')
    username_text = f"<b>Username:</b> @{html.escape(username)}\n" if username else "<b>Username:</b> Yo'q\n"
    
    first_name = html.escape(student.get('first_name') or '')
    last_name = html.escape(student.get('last_name') or '')
    
    age = student.get('age') or "Noma'lum"
    phone = str(student.get('phone_number') or '').lstrip('+')
    
    profile_link = f"<b>Profil:</b> <a href='tg://user?id={student['telegram_id']}'>{first_name}</a>\n"
    
    text = f"👤 <b>O'quvchi ma'lumotlari{page_info}:</b>\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"📛 <b>Ism-familiya:</b> {first_name} {last_name}\n" \
           f"🔗 {username_text}" \
           f"👤 {profile_link}" \
           f"🎂 <b>Yosh:</b> {html.escape(str(age))}\n" \
           f"📞 <b>Tel:</b> +{phone}\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"🏫 <b>Guruh/Daraja:</b> {html.escape(level_val)}\n" \
           f"🗓 <b>Kunlar:</b> {html.escape(shorten_days(days))}\n" \
           f"⏰ <b>Vaqti:</b> {html.escape(time)}\n" \
           f"━━━━━━━━━━━━━━━━━━━\n" \
           f"🆔 <b>ID:</b> {student['telegram_id']}\n" \
           f"🎓 <b>O'quvchi maqomi:</b> {html.escape(student_level_val)}" \
           f"{bio_text}"
    return text

def get_student_profile_keyboard(student_id: int, back_callback_data: str = "astud_list", extra_buttons=None):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="🎓 Ingliz tili darajasi", callback_data=f"astud_eng_lvl:{student_id}")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data=f"astud_score_info:{student_id}")],
        [InlineKeyboardButton(text="📅 Oylik davomat tarixi", callback_data=f"astud_att_hist:{student_id}")],
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
    text = await get_student_profile_text(student, db=db)
    kb = get_student_profile_keyboard(student_id, back_callback_data)
    return text, kb

def parse_lesson_days(days_input) -> list[int]:
    """
    Returns a sorted list of integer weekdays (0=Monday, 6=Sunday).
    Supports JSON arrays, full uzbek names, abbreviations (D.CH.J, S.P.SH), etc.
    """
    if not days_input or days_input == "[]":
        return []
    
    import json
    import re
    
    def _map_token(token: str):
        t = token.strip().lower()
        mapping = {
            "dushanba": 0, "dush": 0, "du": 0, "d": 0, "mon": 0, "monday": 0, "0": 0,
            "seshanba": 1, "sesh": 1, "se": 1, "s": 1, "tue": 1, "tuesday": 1, "1": 1,
            "chorshanba": 2, "chor": 2, "ch": 2, "wed": 2, "wednesday": 2, "2": 2,
            "payshanba": 3, "pay": 3, "pa": 3, "p": 3, "thu": 3, "thursday": 3, "3": 3,
            "juma": 4, "jum": 4, "ju": 4, "j": 4, "fri": 4, "friday": 4, "4": 4,
            "shanba": 5, "shan": 5, "sh": 5, "sat": 5, "saturday": 5, "5": 5,
            "yakshanba": 6, "yak": 6, "ya": 6, "y": 6, "sun": 6, "sunday": 6, "6": 6,
        }
        return mapping.get(t)

    if isinstance(days_input, list):
        result = []
        for item in days_input:
            if isinstance(item, int) and 0 <= item <= 6:
                result.append(item)
            elif isinstance(item, str):
                w = _map_token(item)
                if w is not None:
                    result.append(w)
        return sorted(list(set(result)))
        
    if isinstance(days_input, str):
        s = days_input.strip()
        if s.startswith('[') and s.endswith(']'):
            try:
                parsed = json.loads(s)
                return parse_lesson_days(parsed)
            except Exception:
                pass
        
        tokens = re.split(r'[,;\s/.\-–—()]+', s)
        result = []
        for t in tokens:
            w = _map_token(t)
            if w is not None:
                result.append(w)
        return sorted(list(set(result)))
        
    return []


def is_today_lesson_day(days_input, target_date=None) -> bool:
    """
    Checks if today (in Asia/Tashkent timezone) is among the user's lesson days.
    """
    lesson_weekdays = parse_lesson_days(days_input)
    if not lesson_weekdays:
        return False
        
    if target_date is not None:
        weekday = target_date.weekday()
    else:
        import pytz
        from datetime import datetime
        tz_uz = pytz.timezone('Asia/Tashkent')
        weekday = datetime.now(tz_uz).weekday()
        
    return weekday in lesson_weekdays


def get_days_schedule_info(days_input) -> tuple[str, str]:
    """
    Returns (lesson_days_text, non_lesson_days_text).
    Example: ("Dushanba, Chorshanba, Juma (D.CH.J)", "Seshanba, Payshanba, Shanba, Yakshanba (S.P.Sh.Y)")
    """
    weekdays = parse_lesson_days(days_input)
    
    UZ_DAY_NAMES = [
        "Dushanba", "Seshanba", "Chorshanba",
        "Payshanba", "Juma", "Shanba", "Yakshanba"
    ]
    UZ_SHORT = ["D", "S", "CH", "P", "J", "Sh", "Y"]
    
    if not weekdays:
        return "Noma'lum", "Noma'lum"
        
    lesson_names = [UZ_DAY_NAMES[w] for w in weekdays]
    lesson_short = ".".join([UZ_SHORT[w] for w in weekdays])
    lesson_text = f"{', '.join(lesson_names)} ({lesson_short})"
    
    non_lesson_weekdays = [w for w in range(7) if w not in weekdays]
    non_lesson_names = [UZ_DAY_NAMES[w] for w in non_lesson_weekdays]
    non_lesson_short = ".".join([UZ_SHORT[w] for w in non_lesson_weekdays])
    non_lesson_text = f"{', '.join(non_lesson_names)} ({non_lesson_short})"
    
    return lesson_text, non_lesson_text


def shorten_days(days_str) -> str:
    if not days_str or days_str == "[]": return ""
    weekdays = parse_lesson_days(days_str)
    if not weekdays:
        return str(days_str)
        
    UZ_SHORT = ["D", "S", "CH", "P", "J", "Sh", "Y"]
    abbreviations = ".".join([UZ_SHORT[w] for w in weekdays])
    return f"Haftada {len(weekdays)} kun ({abbreviations})"


def sort_groups(groups):
    GROUP_LEVELS_ORDER = {
        "Beginner": 1,
        "Elementary": 2,
        "Pre-Intermediate": 3,
        "Intermediate": 4,
        "Upper-Intermediate": 5,
        "Advanced": 6,
        "CEFR": 7,
        "IELTS": 8
    }
    def get_order(g):
        name = g['name']
        for level, order in GROUP_LEVELS_ORDER.items():
            if level.lower() in name.lower():
                return order
        return 99
    return sorted(groups, key=get_order)