from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, CallbackQuery
from datetime import date, datetime
from database.db import Database
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from states.register_states import Deletion, StudentAttendance, TeacherMessage
from config import ADMIN_IDS
import json

router = Router()

def get_user_keyboard(user_id: int, is_premium: bool = False):
    if user_id in ADMIN_IDS:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📢 Hammaga xabar yuborish"), KeyboardButton(text="👥 Guruhlar va O'quvchilar")],
                [KeyboardButton(text="👤 O'quvchilarni ko'rish"), KeyboardButton(text="🏫 Guruhlarni boshqarish")],
                [KeyboardButton(text="💰 Oylik to'lov"), KeyboardButton(text="🤖 Bot qoidalari va foydalanish")]
            ],
            resize_keyboard=True
        )
    else:
        top_button_text = "🏆 Top 10 O'quvchi" if is_premium else "🏆 Top 3 O'quvchi"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🙋‍♂️ Davomat"), KeyboardButton(text="📊 Mening Natijalarim")],
                [KeyboardButton(text=top_button_text)],
                [KeyboardButton(text="📈 Darslar o'zlashtirishim"), KeyboardButton(text="🎓 Sizning guruh darajangiz")],
                [KeyboardButton(text="🏆 O'zingizni darajangiz"), KeyboardButton(text="📩 Ustozga xabar yuborish")],
                [KeyboardButton(text="📢 Kanal va guruhlar"), KeyboardButton(text="🤖 Bot qoidalari va foydalanish")],
                [KeyboardButton(text="💰 Oylik to'lov"), KeyboardButton(text="💎 Premium")]
            ],
            resize_keyboard=True
        )
    return keyboard

async def get_async_user_keyboard(user_id: int, db: Database):
    is_premium = await db.is_premium(user_id)
    return get_user_keyboard(user_id, is_premium)

@router.message(F.text == "🙋‍♂️ Davomat", StateFilter(None))
async def mark_attendance(message: Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user['status'] != 'active':
        await message.answer("⚠️ Sizning hisobingiz faol emas yoki ro'yxatdan o'tmagansiz.")
        return

    # Check if today is a lesson day
    today_weekday = date.today().weekday()  # 0: Monday, 6: Sunday
    days_json = user.get('days')
    if days_json:
        try:
            lesson_days = json.loads(days_json)
            if today_weekday not in lesson_days:
                await message.answer("⚠️ Siz faqat dars kuningizda davomat belgilay olasiz!", reply_markup=await get_async_user_keyboard(message.from_user.id, db))
                return
        except:
            pass # fallback if not json

    today_date = date.today()
    
    # Check if attendance is already marked for today
    async with db.pool.acquire() as connection:
        record = await connection.fetchrow("SELECT is_present, reason FROM attendance WHERE user_id = $1 AND date = $2", user_id, today_date)
        
    if record is not None:
        status_str = "Keldi" if record['is_present'] else f"Kelmadi (Sabab: {record['reason']})"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Davomat tarixi", callback_data="attendance_history")]
        ])
        await message.answer(f"❌ Siz bugun davomatdan o'tgansiz!\nHolat: **{status_str}**", parse_mode="Markdown", reply_markup=kb)
        return

    # Show options
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Davomat tarixi", callback_data="attendance_history")],
            [
                InlineKeyboardButton(text="✅ Keldim", callback_data="attendance_present"),
                InlineKeyboardButton(text="❌ Kelmadim", callback_data="attendance_absent")
            ]
        ]
    )
    await message.answer("🏫 **Bugungi darsda ishtirok etdingizmi?**", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "attendance_present")
async def process_attendance_present(callback: CallbackQuery, db: Database):
    await callback.answer()
    user_id = callback.from_user.id
    today_date = date.today()
    
    async with db.pool.acquire() as connection:
        exists = await connection.fetchval("SELECT 1 FROM attendance WHERE user_id = $1 AND date = $2", user_id, today_date)
        
    if exists:
        await callback.message.delete()
        await callback.message.answer("⚠️ Siz bugun davomatdan o'tib bo'lgansiz!")
        return
        
    import pytz
    tz_uz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz_uz).strftime("%Y-%m-%d %H:%M")
    today_str = today_date.strftime("%Y-%m-%d")
    
    await callback.message.edit_text(f"⏳ So'rovingiz ustozga yuborildi.\n📅 Vaqt: {current_time}\nTasdiqlanishini kuting.")
    
    user = await db.get_user(user_id)
    if user:
        from utils import shorten_days
        short_d = shorten_days(user.get('days'))
        
        profile_url = f"tg://user?id={user_id}"
        admin_text = (
            f"🙋‍♂️ **Davomat so'rovi (Keldi)**\n\n"
            f"👤 **O'quvchi:** [{user['first_name']} {user['last_name']}]({profile_url})\n"
            f"📞 **Raqam:** +{str(user['phone_number']).lstrip('+')}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📚 **Guruh (Kurs):** {user['level'] or 'Belgilanmagan'}\n"
            f"🗓 **Kunlar:** {short_d}\n"
            f"📅 **Vaqt:** {current_time}\n"
            f"Siz ushbu o'quvchining kelganini tasdiqlaysizmi?"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"att_appr:{user_id}:{today_str}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"att_rej:{user_id}:{today_str}")
            ]
        ])
                     
        from utils import notify_admins_async
        await notify_admins_async(callback.bot, admin_text, ADMIN_IDS, reply_markup=kb)

@router.callback_query(F.data == "attendance_absent")
async def process_attendance_absent(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    user_id = callback.from_user.id
    today_date = date.today()
    
    async with db.pool.acquire() as connection:
        exists = await connection.fetchval("SELECT 1 FROM attendance WHERE user_id = $1 AND date = $2", user_id, today_date)
        
    if exists:
        await callback.message.delete()
        await callback.message.answer("⚠️ Siz bugun davomatdan o'tib bo'lgansiz!")
        return
        
    await callback.message.delete()
    
    await callback.message.answer("Nega kelmadingiz? Sababini ayting.", reply_markup=ReplyKeyboardRemove())
    await state.set_state(StudentAttendance.waiting_for_absence_reason)

@router.message(StudentAttendance.waiting_for_absence_reason)
async def process_absence_reason(message: Message, state: FSMContext, db: Database):
    reason = message.text.strip()
    
    if reason.startswith('/'):
        await message.answer("⚠️ Iltimos, avval nega darsga kelmaganingiz sababini yozib yuboring (Buyruqlar hozir ishlamaydi):")
        return
        
    if not reason:
        await message.answer("⚠️ Iltimos, darsga kelmaganligingiz sababini yozib yuboring:")
        return
        
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await state.clear()
        return
        
    today_date = date.today()
    success, msg = await db.mark_attendance(user_id, today_date, is_present=False, reason=reason)
    
    if not success:
        await message.answer("⚠️ Siz bugun davomatdan o'tib bo'lgansiz.", reply_markup=await get_async_user_keyboard(message.from_user.id, db))
        await state.clear()
        return
        
    # Notify admins asynchronously
    import pytz
    tz_uz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz_uz).strftime("%Y-%m-%d %H:%M")
    profile_url = f"tg://user?id={user_id}"
    from utils import shorten_days
    short_d = shorten_days(user.get('days'))
    
    admin_text = f"🔴 **Kelmagan O'quvchi**\n" \
                 f"━━━━━━━━━━━━━━━━━━━\n" \
                 f"📛 **O'quvchi:** [{user['first_name']} {user['last_name']}]({profile_url})\n" \
                 f"📞 **Raqam:** +{str(user['phone_number']).lstrip('+')}\n" \
                 f"━━━━━━━━━━━━━━━━━━━\n" \
                 f"🏫 **Guruh:** {user['level'] or 'Belgilanmagan'}\n" \
                 f"🗓 **Kunlar:** {short_d}\n" \
                 f"📅 **Vaqt:** {current_time}\n" \
                 f"━━━━━━━━━━━━━━━━━━━\n" \
                 f"🆔 **ID:** `{user_id}`\n" \
                 f"❌ **Holat:** Kelmagan\n" \
                 f"📝 **Sababi:** {reason}"
                 
    from utils import notify_admins_async
    await notify_admins_async(message.bot, admin_text, ADMIN_IDS)
            
    await message.answer(f"✅ Sababi adminga yuborildi. Rahmat!\n📅 Vaqt: {current_time}\nHolat: Kelmagan", reply_markup=await get_async_user_keyboard(message.from_user.id, db))
    await state.clear()

@router.message(F.text.in_(["🏆 Top 3 O'quvchi", "🏆 Top 10 O'quvchi"]), StateFilter(None))
async def show_top_students(message: Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or user['status'] != 'active':
        await message.answer("⚠️ Sizning hisobingiz faol emas yoki ro'yxatdan o'tmagansiz.")
        return
        
    is_premium = await db.is_premium(user_id)
    limit = 10 if is_premium else 3
    
    await message.answer("⏳ Hisoblanmoqda... (Barcha o'quvchilar natijalari solishtirilmoqda)")
    
    rankings = await db.get_rankings()
    top_list = rankings[:limit]
    
    if not top_list:
        await message.answer("Hozircha yetarli ma'lumot yo'q.")
        return
        
    text = f"🏆 **Bot bo'yicha TOP {limit} ta eng kuchli o'quvchilar:**\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for idx, r in enumerate(top_list):
        medal = medals[idx] if idx < 3 else "🏅"
        text += f"{medal} **{idx+1}-o'rin:** {r['name']}\n"
        text += f"   Darajasi: {r['level']}\n"
        text += f"   Joriy darslar balli: {r['current_score']}/150\n"
        text += f"   Botdagi faolligi: {r['activity_score']} ball\n\n"
        
    text += "*(Reyting o'zlashtirish ballari, davomat, maqom va botdagi faollikka qarab avtomatik hisoblanadi)*"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "📊 Mening Natijalarim", StateFilter(None))
async def show_dashboard(message: Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user['status'] != 'active':
        await message.answer("⚠️ Sizning hisobingiz faol emas yoki ro'yxatdan o'tmagansiz.")
        return
        
    await message.answer("⏳ Ma'lumotlaringiz yuklanmoqda...")
    
    stats = await db.get_user_stats(user_id)
    current_cycle_scores = stats.get('current_cycle_scores', [])
    current_cycle_total = stats.get('current_cycle_total', 0)
    
    # Calculate global and group rank
    rankings = await db.get_rankings()
    global_rank = 0
    group_rank = 0
    group_rank_counter = 1
    
    my_group_id = user.get('group_id')
    
    for idx, r in enumerate(rankings, 1):
        if r['user_id'] == user_id:
            global_rank = idx
            group_rank = group_rank_counter
            break
        if r['group_id'] == my_group_id:
            group_rank_counter += 1
            
    scores_text = "📊 **Joriy 6 ta darslik bo'yicha natijalaringiz:**\n"
    if current_cycle_scores:
        for s in current_cycle_scores:
            scores_text += f"🔹 {s['lesson_number']}-dars: {s['score']} ball\n"
    else:
        scores_text += "Hozircha joriy siklda ballar yo'q.\n"
        
    scores_text += f"\n**Joriy sikldagi umumiy ball:** {current_cycle_total}/150\n"
    
    rank_text = (
        f"🏆 **Sizning Reytingdagi O'rningiz:**\n\n"
        f"👥 O'z guruhingizda: **{group_rank}-o'rindasiz!**\n"
        f"🌐 Barcha o'quvchilar orasida: **{global_rank}-o'rindasiz!**\n\n"
        f"💡 _Izoh: Sizning o'rningiz darslardagi o'zlashtirishingiz (ballaringiz), vazifalarni vaqtida bajarishingiz, davomatingiz va botdagi faolligingizga qarab avtomatik ravishda reyting qilinadi._"
    )
    
    is_premium = await db.is_premium(user_id)
    history_text = ""
    if is_premium:
        history_text = "\n\n📂 **Oldingi natijalar tarixi (Premium History):**\n"
        if stats.get('history'):
            for h in stats['history']:
                history_text += f"🔹 *{h['cycle_number']}-sikl:* {h['total_score']}/150 ({h['level']})\n"
        else:
            history_text += "Hali tarix mavjud emas.\n"
    
    dashboard = f"👤 **{user['first_name']} {user['last_name']}**\n\n{scores_text}\n{rank_text}{history_text}"
    
    await message.answer(dashboard, parse_mode="Markdown", reply_markup=await get_async_user_keyboard(message.from_user.id, db))

@router.message(F.text == "📈 Darslar o'zlashtirishim", StateFilter(None))
async def show_detailed_dashboard(message: Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user['status'] != 'active':
        await message.answer("⚠️ Sizning hisobingiz faol emas yoki ro'yxatdan o'tmagansiz.")
        return
        
    stats = await db.get_user_stats(user_id)
    current_cycle_scores = stats.get('current_cycle_scores', [])
    attendance_count = stats.get('attendance_count', 0)
    current_cycle_total = stats['current_cycle_total']
    student_level = stats.get('student_level') or "Belgilanmagan"
    performance_grade = stats.get('performance_grade')
    teacher_bio = stats.get('teacher_bio')
    
    if 140 <= current_cycle_total <= 150:
        grade = "Excellent 🥇"
    elif 120 <= current_cycle_total <= 139:
        grade = "Very Good 🟢"
    elif 100 <= current_cycle_total <= 119:
        grade = "Good 🟡"
    elif 80 <= current_cycle_total <= 99:
        grade = "Needs Improvement 🟠"
    else:
        grade = "Weak 🔴"

    scores_text = ""
    if current_cycle_scores:
        for row in current_cycle_scores:
            scores_text += f"🔹 {row['lesson_number']}-dars: {row['score']}\n"
    else:
        scores_text = "Hali ballar yo'q.\n"
        
    bio_text = f"\n💬 **Ustoz sizga aytadigan gapi:**\n_{teacher_bio}_\n" if teacher_bio else ""

    text = f"""📈 **Darslar o'zlashtirishim**
━━━━━━━━━━━━━━━━━━
🎓 **Ingliz tili darajangiz:** {student_level}
🚶‍♂️ Jami kelgan darslaringiz: {attendance_count} marta

📊 **Joriy oy (sikl) ballari:**
{scores_text}
📌 **Jami:** {current_cycle_total}/150
🏅 **O'zlashtirish:** {grade}
{bio_text}"""
    
    await message.answer(text, parse_mode="Markdown", reply_markup=await get_async_user_keyboard(message.from_user.id, db))

@router.message(F.text == "🎓 Sizning guruh darajangiz", StateFilter(None))
async def show_group_level(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'active':
        return
        
    level = user.get('level')
    if not level:
        await message.answer("Siz hali daraja tanlamagansiz. ⏳")
        return
        
    async with db.pool.acquire() as connection:
        try:
            # First try fetching from groups table since we are migrating to dynamic groups
            group_row = await connection.fetchrow("SELECT group_level FROM groups WHERE name = $1", level)
            status = group_row['group_level'] if group_row else None
            
            # Fetch updated_at from old level_status table to preserve existing timestamps
            status_row = await connection.fetchrow("SELECT updated_at FROM level_status WHERE level_name = $1", level)
            updated_at = status_row['updated_at'] if status_row else None
        except Exception:
            status = None
            updated_at = None
            
    g_level = status or "Hali belgilanmagan"
    
    if updated_at:
        from pytz import timezone
        uz_tz = timezone('Asia/Tashkent')
        time_str = updated_at.astimezone(uz_tz).strftime('%d.%m.%Y %H:%M')
        time_msg = f"\n\n🕒 <b>O'zgargan vaqti:</b> {time_str}"
    else:
        time_msg = ""
        
    g_emojis = {
        "SMART GROUP": "💡",
        "MIDDLE CLASS": "⚖️",
        "LAZY TEAM": "🐌"
    }
    g_emoji = g_emojis.get(g_level, "")
    
    if g_emoji:
        g_level_display = f"{g_emoji} <b>{g_level}</b> {g_emoji}"
    else:
        g_level_display = f"<b>{g_level}</b>"
    
    text = (
        f"🏫 <b>Guruh nomi:</b> {level}\n"
        f"📈 <b>Guruh darajasi:</b> {g_level_display}"
        f"{time_msg}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🏆 O'zingizni darajangiz", StateFilter(None))
async def show_student_level(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'active':
        return
        
    s_level = user.get('student_level') or "Hali belgilanmagan"
    updated_at = user.get('student_level_updated_at')
    
    if updated_at:
        from pytz import timezone
        uz_tz = timezone('Asia/Tashkent')
        time_str = updated_at.astimezone(uz_tz).strftime('%d.%m.%Y %H:%M')
        time_msg = f"\n\n🕒 <b>O'zgargan vaqti:</b> {time_str}"
    else:
        time_msg = ""
        
    level_emojis = {
        "SUPPORT": "💎",
        "CAPTAIN": "👑",
        "MAIN": "🎯",
        "LEARNER": "📖",
        "INTRODUCTORY": "🌱"
    }
    emoji = level_emojis.get(s_level, "🏅")
    
    if s_level == "Hali belgilanmagan":
        level_display = f"<b>{s_level}</b>"
    else:
        level_display = f"{emoji} <b>{s_level}</b> {emoji}"
        
    text = (
        f"🏅 <b>Sizning shaxsiy darajangiz:</b>\n\n"
        f"{level_display}\n\n"
        f"<i>O'qituvchi tomonidan belgilangan baholash.</i>"
        f"{time_msg}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📩 Ustozga xabar yuborish", StateFilter(None))
async def msg_teacher(message: Message, db: Database, state: FSMContext):
    user_id = message.from_user.id
    is_premium = await db.is_premium(user_id)

    # Limit va Dars kuni tekshiruvi
    if is_premium:
        if not await db.can_send_teacher_message_premium(user_id):
            await message.answer(
                "🚫 Siz bugun ustozga 10 marta xabar yuborib bo'ldingiz.\n"
                "💎 Premium limit: kuniga 10 ta xabar.\nErtaga yana urinib ko'ring!"
            )
            return
    else:
        # Odatiy o'quvchi uchun dars kuni yozish mumkin emas
        from datetime import date
        import json
        today_weekday = date.today().weekday()
        days_json = user.get('days')
        if days_json:
            try:
                lesson_days = json.loads(days_json)
                if today_weekday in lesson_days:
                    await message.answer("⚠️ Siz dars kuni ustozga yoza olmaysiz, ustozning o'ziga ayting!")
                    return
            except:
                pass
                
        if not await db.can_send_teacher_message(user_id):
            await message.answer(
                "🚫 Kechirasiz, siz bugun ustozga xabar yuborish limitini (1 ta) tugatdingiz.\n"
                "Ertaga yana urinib ko'ring!\n\n"
                "💡 <b>Premium</b> obuna bilan kuniga 10 ta ixtiyoriy xabar (ovozli, rasm, fayl) va kanalga obunasiz yuborish mumkin!",
                parse_mode="HTML"
            )
            return

    bot = message.bot

    # Premium foydalanuvchi — kanal tekshiruvisiz to'g'ridan xabar yozadi
    if is_premium:
        await state.set_state(TeacherMessage.waiting_for_message)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
            resize_keyboard=True
        )
        await message.answer(
            "📝 Ustozga nima demoqchisiz, yozing:\n"
            "<i>💎 Premium: kanal obunasisiz yuborish mumkin</i>",
            parse_mode="HTML", reply_markup=keyboard
        )
        return

    channels = [
        ("🎓 Super Teaching", "https://t.me/superteaching", "@superteaching"),
        ("📝 Muhammaddiyor Blog", "https://t.me/Muhammaddiyor_blog", "@Muhammaddiyor_blog"),
        ("🤖 Bomb Kinolar Bot", "https://t.me/tarjimabombakinolar_bot", "@tarjimabombakinolar_bot"),
        ("🤖 Epic Kinolar Bot", "https://t.me/tarjimaepickinolarbot", "@tarjimaepickinolarbot"),
        ("🎬 Bomb Kinolar", "https://t.me/Tarjimabombakinolar", "@Tarjimabombakinolar"),
        ("🔥 Epic Brand", "https://t.me/Epic_brand", "@Epic_brand")
    ]

    unsubbed_buttons = []
    for name, url, username in channels:
        try:
            member = await bot.get_chat_member(chat_id=username, user_id=user_id)
            if member.status in ['left', 'kicked']:
                unsubbed_buttons.append(InlineKeyboardButton(text=name, url=url))
        except Exception:
            unsubbed_buttons.append(InlineKeyboardButton(text=name, url=url))

    if unsubbed_buttons:
        kb_rows = [unsubbed_buttons[i:i+2] for i in range(0, len(unsubbed_buttons), 2)]
        kb_rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_teacher_sub")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        if len(unsubbed_buttons) == len(channels):
            text = "Ustozga xabar yuborish uchun **barcha** kanal va guruhlarga obuna bo'lishingiz shart!\n\nObuna bo'lgach, **✅ Tasdiqlash** tugmasini bosing."
        else:
            text = "Ustozga xabar yuborish uchun quyidagi **qolib ketgan** kanallarga obuna bo'ling:\n\nObuna bo'lgach, **✅ Tasdiqlash** tugmasini bosing."
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await state.set_state(TeacherMessage.waiting_for_message)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
            resize_keyboard=True
        )
        await message.answer("📝 Ustozga nima demoqchisiz, yozing:", reply_markup=keyboard)

@router.message(F.text == "📢 Kanal va guruhlar", StateFilter(None))
async def channels_info(message: Message):
    text = "📢 **Bizning rasmiy kanal, guruh va botlarimiz:**\n\n" \
           "🔗 [Super Teaching](https://t.me/superteaching)\n" \
           "🔗 [Muhammaddiyor Blog](https://t.me/Muhammaddiyor_blog)\n" \
           "🔗 [Tarjima Bomb Kinolar Bot](https://t.me/tarjimabombakinolar_bot)\n" \
           "🔗 [Tarjima Epic Kinolar Bot](https://t.me/tarjimaepickinolarbot)\n" \
           "🔗 [Tarjima Bomb Kinolar](https://t.me/Tarjimabombakinolar)\n" \
           "🔗 [Epic Brand](https://t.me/Epic_brand)\n\n" \
           "Kerakli manzilga o'tish uchun yuqoridagi havolalarni yoki pastdagi tugmalarni bosing: 👇"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎓 Super Teaching", url="https://t.me/superteaching"),
                InlineKeyboardButton(text="📝 Muhammaddiyor Blog", url="https://t.me/Muhammaddiyor_blog")
            ],
            [
                InlineKeyboardButton(text="🤖 Bomb Kinolar Bot", url="https://t.me/tarjimabombakinolar_bot"),
                InlineKeyboardButton(text="🤖 Epic Kinolar Bot", url="https://t.me/tarjimaepickinolarbot")
            ],
            [
                InlineKeyboardButton(text="🎬 Bomb Kinolar", url="https://t.me/Tarjimabombakinolar"),
                InlineKeyboardButton(text="🔥 Epic Brand", url="https://t.me/Epic_brand")
            ]
        ]
    )
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard, disable_web_page_preview=True)

@router.message(Command("delete_account"), StateFilter(None))
async def cmd_delete_account(message: Message, state: FSMContext, db: Database):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("⚠️ Ushbu buyruq faqat o'quvchilar uchun ishlaydi.")
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz.")
        return
        
    if user.get('is_blocked'):
        await message.answer("⚠️ Bloklangan foydalanuvchilar o'z akkauntlarini o'chira olmaydilar.")
        return
        
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True
    )
    await message.answer("Nima uchun akkauntingizni o'chirmoqchisiz? Iltimos, sababini yozib yuboring:", reply_markup=keyboard)
    await state.set_state(Deletion.waiting_for_reason)

@router.message(F.text == "⬅️ Orqaga", StateFilter(Deletion.waiting_for_reason, Deletion.waiting_for_code))
async def cancel_deletion(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amaliyot bekor qilindi.", reply_markup=await get_async_user_keyboard(message.from_user.id, db))

@router.message(Deletion.waiting_for_reason)
async def process_deletion_reason(message: Message, state: FSMContext, db: Database):
    reason = message.text.strip()
    
    if reason.startswith('/'):
        await message.answer("⚠️ Iltimos, avval akkauntni o'chirish sababini yozib yuboring (Buyruqlar hozir ishlamaydi):")
        return
        
    user = await db.get_user(message.from_user.id)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True
    )
    await message.answer("Sizning so'rovingiz adminga yuborildi. Kuting...", reply_markup=keyboard)
    
    username = user.get('username')
    username_text = f"@{username}" if username else "Yo'q"
    profile_link = f"[{user['first_name']}](tg://user?id={user['telegram_id']})"
    
    admin_text = (
        f"🗑 **Akkauntni o'chirish so'rovi:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **O'quvchi:** {profile_link}\n"
        f"🔗 **Username:** {username_text}\n"
        f"📝 **Sabab:** {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 **ID:** `{user['telegram_id']}`"
    )
    
    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash va Kod yuborish", callback_data=f"del_req:{user['telegram_id']}")] ]
    )
    
    import asyncio
    from utils import notify_admins_async
    asyncio.create_task(notify_admins_async(message.bot, admin_text, ADMIN_IDS, parse_mode="Markdown", reply_markup=admin_keyboard))

            
    await state.set_state(Deletion.waiting_for_code)

@router.message(Deletion.waiting_for_code)
async def process_deletion_code(message: Message, state: FSMContext, db: Database):
    user = await db.get_user(message.from_user.id)
    text = message.text.strip()
    
    if text.startswith('/'):
        await message.answer("⚠️ Iltimos, avval tasdiqlash kodini kiriting (Buyruqlar hozir ishlamaydi):")
        return
        
    if user['deletion_code'] and text == user['deletion_code']:
        await db.delete_user(message.from_user.id)
        await message.answer("Akkauntingiz muvaffaqiyatli o'chirildi. /start orqali qayta ro'yxatdan o'tishingiz mumkin.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
    else:
        await message.answer("Noto'g'ri kod. Iltimos, qayta urunib ko'ring yoki /start ni bosing.")

@router.callback_query(F.data == "check_teacher_sub")
async def process_teacher_sub(callback: CallbackQuery, state: FSMContext, db: Database):
    user_id = callback.from_user.id
    bot = callback.bot
    channels_to_check = [
        "@superteaching",
        "@Muhammaddiyor_blog",
        "@tarjimabombakinolar_bot",
        "@tarjimaepickinolarbot",
        "@Tarjimabombakinolar",
        "@Epic_brand"
    ]
    
    not_subscribed = False
    for channel in channels_to_check:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed = True
                break
        except Exception:
            pass
            
    if not_subscribed:
        await callback.answer("❌ Kechirasiz, siz hali barcha kerakli kanal va guruhlarga obuna bo'lmagansiz. Iltimos, barchasiga obuna bo'ling!", show_alert=True)
    else:
        await callback.message.delete()
        await state.set_state(TeacherMessage.waiting_for_message)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
            resize_keyboard=True
        )
        await callback.message.answer("📝 Ustozga nima demoqchisiz, yozing:", reply_markup=keyboard)

@router.message(TeacherMessage.waiting_for_message)
async def process_teacher_message(message: Message, state: FSMContext, db: Database):
    text = message.text.strip() if message.text else message.caption.strip() if message.caption else ""
    user_id = message.from_user.id
    is_premium = await db.is_premium(user_id)
    
    if text == "⬅️ Orqaga":
        await state.clear()
        keyboard = await get_async_user_keyboard(user_id, db)
        await message.answer("Bosh menyuga qaytdingiz.", reply_markup=keyboard)
        return

    # Check for media limitation
    has_media = message.photo or message.video or message.audio or message.document or message.voice
    if not is_premium and has_media:
        await message.answer(
            "⚠️ Odatiy o'quvchilar ustozga faqatgina **matnli xabar (text)** yuborishi mumkin!\n\n"
            "Agar ovozli xabar, fayl yoki rasm yubormoqchi bo'lsangiz hamda kuniga 10 marta yozishni xohlasangiz **Premium** obuna oling! 💎",
            parse_mode="Markdown"
        )
        return

    if not is_premium and (not text or text.startswith('/')):
        await message.answer("⚠️ Iltimos, ustozga o'z matnli xabaringizni yozing.")
        return
        
    user = await db.get_user(user_id)
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else message.from_user.full_name
    
    await db.log_teacher_message(user_id)
    
    from utils import notify_admins_async, get_student_profile_text, get_student_profile_keyboard
    
    profile_text = await get_student_profile_text(user, db=db, page_info=" (Yangi xabar)")
    import pytz
    tz_uz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz_uz).strftime('%Y-%m-%d %H:%M')
    
    admin_text = f"{profile_text}\n\n💬 <b>O'quvchi xabari:</b>\n{text}\n\n⏳ <b>Yuborilgan vaqt:</b> {current_time}"
    kb = get_student_profile_keyboard(user['telegram_id'], back_callback_data="astud_list")
    
    # Send message or forward media to admins
    for a_id in ADMIN_IDS:
        try:
            if has_media:
                await message.copy_to(chat_id=a_id, caption=admin_text, parse_mode="HTML", reply_markup=kb)
            else:
                await message.bot.send_message(chat_id=a_id, text=admin_text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            print(f"Failed to send to admin {a_id}: {e}")
    
    await state.clear()
    keyboard = await get_async_user_keyboard(message.from_user.id, db)
    await message.answer("✅ Xabaringiz ustozga yuborildi. Rahmat!", reply_markup=keyboard)


@router.message(F.text == "🤖 Bot qoidalari va foydalanish", StateFilter(None))
async def show_student_rules(message: Message):
    from rules.studentrule import STUDENT_RULES_TEXT
    await message.answer(STUDENT_RULES_TEXT, parse_mode="Markdown")

@router.message()
async def catch_all_messages(message: Message, state: FSMContext, db: Database):
    user = await db.get_user(message.from_user.id)

    # Bloklangan foydalanuvchi tekshiruvi endi BlockMiddleware orqali amalga oshiriladi
    if user and user.get('deletion_code') and message.text:
        text = message.text.strip()
        if text == user['deletion_code']:
            await db.delete_user(message.from_user.id)
            from aiogram.types import ReplyKeyboardRemove
            await message.answer("Akkauntingiz muvaffaqiyatli o'chirildi. /start orqali qayta ro'yxatdan o'tishingiz mumkin.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
        elif text.isdigit():
            await message.answer("❌ Noto'g'ri tasdiqlash kodi kiritildi. Iltimos, qayta urinib ko'ring.")
            return

    current_state = await state.get_state()
    if current_state is None:
        await message.answer("⚠️ Kechirasiz, men bu xabarni tushunmadim. Iltimos, menyudagi tugmalardan foydalaning.")
    else:
        await message.answer("⚠️ Noto'g'ri buyruq yoki format. Bekor qilish uchun /start ni bosing.")

@router.callback_query(F.data == "attendance_history")
async def show_attendance_history(callback: CallbackQuery, db: Database):
    await callback.answer()
    user_id = callback.from_user.id
    
    async with db.pool.acquire() as connection:
        records = await connection.fetch("""
            SELECT date, created_at, is_present, reason 
            FROM attendance 
            WHERE user_id = $1 AND date >= current_date - interval '30 days'
            ORDER BY date DESC
        """, user_id)
        
    if not records:
        await callback.message.answer("📅 Oxirgi 30 kun ichida davomat tarixingiz topilmadi.")
        return
        
    total_days = len(records)
    present_count = sum(1 for r in records if r['is_present'])
    absent_count = total_days - present_count
    
    import pytz
    tz_uz = pytz.timezone('Asia/Tashkent')
    
    history_lines = []
    for r in records:
        created_dt = r['created_at'].astimezone(tz_uz) if r['created_at'] else r['date']
        date_str = created_dt.strftime("%Y-%m-%d %H:%M")
        if r['is_present']:
            history_lines.append(f"✅ {date_str} - Keldi")
        else:
            reason_str = r['reason'] or ""
            if "rad etildi" in reason_str.lower():
                history_lines.append(f"❌ {date_str} - Kelmadi (Tasdiqlanmadi)")
            else:
                history_lines.append(f"❌ {date_str} - Kelmadi ({reason_str})")
                
    text = (
        f"📅 **Oxirgi 30 kunlik davomat tarixi:**\n\n"
        f"📊 Umumiy darslar: {total_days}\n"
        f"✅ Kelgan / ❌ Kelmagan: {present_count}/{absent_count}\n\n"
        f"**Tarix (Sana va vaqt):**\n" + "\n".join(history_lines)
    )
    
    await callback.message.answer(text, parse_mode="Markdown")

async def ask_for_free_premium(bot, student_id):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    text = (
        "🎉 <b>Tabriklaymiz!</b>\n\n"
        "Siz qatorasiga 3 oy (3 ta tsikl) davomida to'xtovsiz Excellent natija va Support maqomini o'zingizda saqlab qoldingiz!\n"
        "Shu sababli sizga 1 oylik <b>Tekin Premium</b> taqdim etilmoqda.\n\n"
        "Premium olishga rozimisiz?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Roziman (Olish)", callback_data=f"claim_free_premium:yes:{student_id}")],
        [InlineKeyboardButton(text="ℹ️ Premium haqida ma'lumot", callback_data="premium_info_btn")]
    ])
    
    try:
        await bot.send_message(student_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass

@router.callback_query(F.data.startswith("claim_free_premium:"))
async def process_claim_free_premium(callback: CallbackQuery, db: Database):
    data = callback.data.split(":")
    action = data[1]
    student_id = int(data[2])
    
    if action == "yes":
        await callback.message.edit_text("✅ So'rovingiz adminga yuborildi. Kuting...")
        
        # Adminlarga yuborish
        student = await db.get_user(student_id)
        first_name = student.get('first_name', '')
        last_name = student.get('last_name', '')
        username = f"@{student.get('username')}" if student.get('username') else "Yo'q"
        
        # 3 oylik natijalarni olish
        async with db.pool.acquire() as connection:
            recent_cycles = await connection.fetch("SELECT cycle_number, total_score, level FROM cycles WHERE user_id = $1 ORDER BY cycle_number DESC LIMIT 3", student_id)
            
        history_str = ""
        for idx, c in enumerate(recent_cycles, 1):
            history_str += f"{idx}-qism: {c['total_score']}/150 ball - {c['level']}\n"
            
        admin_msg = (
            f"🎁 <b>Premium So'rov (Avtomatik):</b>\n\n"
            f"O'quvchi {first_name} {last_name} ({username}) qatorasiga 3 marta Excellent oldi va 1 oylik tekin Premium olishga rozi bo'ldi.\n\n"
            f"Natijalar tarixi:\n{history_str}\n"
            f"Ushbu o'quvchiga 1 oylik tekin Premium ochib beramizmi?"
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from config import ADMIN_IDS
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ruxsat berish", callback_data=f"approve_free_premium:{student_id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_free_premium:{student_id}")]
        ])
        
        from utils import notify_admins_async
        import asyncio
        asyncio.create_task(notify_admins_async(callback.bot, admin_msg, ADMIN_IDS, parse_mode="HTML", reply_markup=admin_kb))
        
@router.callback_query(F.data == "premium_info_btn")
async def process_premium_info_btn(callback: CallbackQuery):
    info_text = (
        "💎 <b>Premium nima beradi?</b>\n\n"
        "- Bot fonini va dizaynini o'zgartirish (qora fon, maxsus dizayn)\n"
        "- Darsliklardan va barcha materiallardan cheklovlarsiz foydalanish\n"
        "- Qo'shimcha funksiyalar va qulayliklar.\n\n"
        "Davom etish uchun yuqoridagi 'Roziman' tugmasini bosing!"
    )
    await callback.answer(info_text, show_alert=True)
