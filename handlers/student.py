from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, CallbackQuery
from datetime import date
from database.db import Database
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from states.register_states import Deletion, StudentAttendance, TeacherMessage
from config import ADMIN_IDS
import json

router = Router()

def get_user_keyboard(user_id: int):
    if user_id in ADMIN_IDS:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📢 Hammaga xabar yuborish"), KeyboardButton(text="👥 Guruhlar va O'quvchilar")],
                [KeyboardButton(text="👤 O'quvchilarni ko'rish"), KeyboardButton(text="🏫 Guruhlarni boshqarish")]
            ],
            resize_keyboard=True
        )
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🙋‍♂️ Davomat"), KeyboardButton(text="📊 Mening Natijalarim")],
                [KeyboardButton(text="🎓 O'zini guruhini darajasi"), KeyboardButton(text="🏆 O'zini darajasini ko'rish")],
                [KeyboardButton(text="📩 Ustozga xabar yuborish"), KeyboardButton(text="📢 Kanal va guruhlar")]
            ],
            resize_keyboard=True
        )
    return keyboard

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
                await message.answer("⚠️ Siz faqat dars kuningizda davomat belgilay olasiz!", reply_markup=get_user_keyboard(message.from_user.id))
                return
        except:
            pass # fallback if not json

    today_date = date.today()
    
    # Check if attendance is already marked for today
    async with db.pool.acquire() as connection:
        record = await connection.fetchrow("SELECT is_present, reason FROM attendance WHERE user_id = $1 AND date = $2", user_id, today_date)
        
    if record is not None:
        status_str = "Keldi" if record['is_present'] else f"Kelmadi (Sabab: {record['reason']})"
        await message.answer(f"❌ Siz bugun davomatdan o'tgansiz!\nHolat: **{status_str}**", parse_mode="Markdown", reply_markup=get_user_keyboard(message.from_user.id))
        return

    # Show options
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Keldim", callback_data="attendance_present"),
                InlineKeyboardButton(text="❌ Kelmadim", callback_data="attendance_absent")
            ]
        ]
    )
    await message.answer("👋 Assalomu alaykum!\nBugungi darsda ishtirok etasizmi? Iltimos, tanlang:", reply_markup=keyboard)

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
        
    success, msg = await db.mark_attendance(user_id, today_date, is_present=True)
    await callback.message.edit_text("✅ Bugungi darsga kelganingiz tasdiqlandi. Rahmat!")

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
        await message.answer("⚠️ Siz bugun davomatdan o'tib bo'lgansiz.", reply_markup=get_user_keyboard(message.from_user.id))
        await state.clear()
        return
        
    # Notify admins asynchronously
    profile_url = f"tg://user?id={user_id}"
    admin_text = f"🔴 **Kelmagan O'quvchi**\n\n" \
                 f"👤 **O'quvchi:** [{user['first_name']} {user['last_name']}]({profile_url})\n" \
                 f"📞 **Raqam:** {user['phone_number']}\n" \
                 f"🆔 **ID:** `{user_id}`\n" \
                 f"📚 **Guruh (Kurs):** {user['level'] or 'Belgilanmagan'}\n" \
                 f"📝 **Kelmaslik sababi:** {reason}"
                 
    import asyncio
    from utils import notify_admins_async
    asyncio.create_task(notify_admins_async(message.bot, admin_text, ADMIN_IDS))
            
    await message.answer("✅ Sababi adminga yuborildi. Rahmat!", reply_markup=get_user_keyboard(message.from_user.id))
    await state.clear()

@router.message(F.text == "📊 Mening Natijalarim", StateFilter(None))
async def show_dashboard(message: Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user or user['status'] != 'active':
        await message.answer("⚠️ Sizning hisobingiz faol emas yoki ro'yxatdan o'tmagansiz.")
        return
        
    stats = await db.get_user_stats(user_id)
    last_score = stats['last_score']
    current_cycle_total = stats['current_cycle_total']
    
    history_text = "📂 **Oldingi natijalar tarixi (History):**\n"
    if stats['history']:
        for h in stats['history']:
            history_text += f"🔹 *{h['cycle_number']}-sikl:* {h['total_score']}/150 ({h['level']})\n"
    else:
        history_text += "Hali tarix mavjud emas.\n"

    dashboard = f"""👤 **Profilingiz**
━━━━━━━━━━━━━━━━━━
📛 **Ism:** {user['first_name']} {user['last_name']}
🎯 **Oxirgi darsdagi ball:** {last_score}/25
📊 **Joriy sikl (Jami):** {current_cycle_total}/150
━━━━━━━━━━━━━━━━━━
{history_text}"""
    
    await message.answer(dashboard, parse_mode="Markdown", reply_markup=get_user_keyboard(message.from_user.id))

@router.message(F.text == "🎓 O'zini guruhini darajasi", StateFilter(None))
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

@router.message(F.text == "🏆 O'zini darajasini ko'rish", StateFilter(None))
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
    if not await db.can_send_teacher_message(message.from_user.id):
        await message.answer("🚫 Kechirasiz, siz bugun ustozga 3 marta xabar yuborib bo'ldingiz.\nErtaga yana urinib ko'ring!")
        return

    bot = message.bot
    user_id = message.from_user.id
    
    channels = [
        ("🎓 Super Teaching", "https://t.me/superteaching", "@superteaching"),
        ("📝 Muhammaddiyor Blog", "https://t.me/Muhammaddiyor_blog", "@Muhammaddiyor_blog"),
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
        # All subbed
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
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz.")
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
    await message.answer("❌ Amaliyot bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))

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
    
    admin_text = f"🗑 **Akkauntni o'chirish so'rovi:**\nO'quvchi: {user['first_name']} {user['last_name']}\nSabab: {reason}\nID: {user['telegram_id']}"
    
    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash va Kod yuborish", callback_data=f"del_req:{user['telegram_id']}")] ]
    )
    
    import asyncio
    from utils import notify_admins_async
    asyncio.create_task(notify_admins_async(message.bot, admin_text, ADMIN_IDS, parse_mode=None, reply_markup=admin_keyboard))
            
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
            not_subscribed = True
            break
            
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
    text = message.text.strip() if message.text else ""
    
    if text == "⬅️ Orqaga":
        await state.clear()
        keyboard = get_user_keyboard(message.from_user.id)
        await message.answer("Bosh menyuga qaytdingiz.", reply_markup=keyboard)
        return

    if not text or text.startswith('/'):
        await message.answer("⚠️ Iltimos, faqat matnli xabar yuboring.")
        return
        
    user = await db.get_user(message.from_user.id)
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else message.from_user.full_name
    
    await db.log_teacher_message(message.from_user.id)
    
    from utils import notify_admins_async, get_student_profile_text, get_student_profile_keyboard
    
    profile_text = get_student_profile_text(user, page_info=" (Yangi xabar)")
    admin_text = f"{profile_text}\n\n💬 **O'quvchi xabari:**\n{text}"
    kb = get_student_profile_keyboard(user['telegram_id'], back_callback_data="astud_list")
                 
    import asyncio
    asyncio.create_task(notify_admins_async(message.bot, admin_text, ADMIN_IDS, parse_mode="Markdown", reply_markup=kb))
    
    await state.clear()
    keyboard = get_user_keyboard(message.from_user.id)
    await message.answer("✅ Xabaringiz ustozga yuborildi. Rahmat!", reply_markup=keyboard)


@router.message()
async def catch_all_messages(message: Message, state: FSMContext, db: Database):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("⚠️ Kechirasiz, men bu xabarni tushunmadim. Iltimos, menyudagi tugmalardan foydalaning.")
    else:
        await message.answer("⚠️ Noto'g'ri buyruq yoki format. Bekor qilish uchun /start ni bosing.")
