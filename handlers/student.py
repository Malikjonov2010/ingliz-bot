from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, CallbackQuery
from datetime import date
from database.db import Database
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from states.register_states import Deletion, StudentAttendance
from config import ADMIN_IDS
import json

router = Router()

def get_student_keyboard():
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
                await message.answer("⚠️ Siz faqat dars kuningizda davomat belgilay olasiz!", reply_markup=get_student_keyboard())
                return
        except:
            pass # fallback if not json

    today_date = date.today()
    
    # Check if attendance is already marked for today
    async with db.pool.acquire() as connection:
        record = await connection.fetchrow("SELECT is_present, reason FROM attendance WHERE user_id = $1 AND date = $2", user_id, today_date)
        
    if record is not None:
        status_str = "Keldi" if record['is_present'] else f"Kelmadi (Sabab: {record['reason']})"
        await message.answer(f"❌ Siz bugun davomatdan o'tgansiz!\nHolat: **{status_str}**", parse_mode="Markdown", reply_markup=get_student_keyboard())
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
        await message.answer("⚠️ Siz bugun davomatdan o'tib bo'lgansiz.", reply_markup=get_student_keyboard())
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
            
    await message.answer("✅ Sababi adminga yuborildi. Rahmat!", reply_markup=get_student_keyboard())
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
    
    await message.answer(dashboard, parse_mode="Markdown", reply_markup=get_student_keyboard())

@router.message(F.text == "🎓 O'zini guruhini darajasi", StateFilter(None))
async def show_group_level(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'active':
        return
        
    group_id = user.get('group_id')
    if not group_id:
        await message.answer("Siz hali guruhga biriktirilmagansiz. ⏳")
        return
        
    # Get group level directly or via a new db method.
    async with db.pool.acquire() as connection:
        group = await connection.fetchrow("SELECT name, group_level FROM groups WHERE id = $1", group_id)
        
    if not group:
        await message.answer("Guruhingiz topilmadi.")
        return
        
    g_name = group['name']
    g_level = group['group_level'] or "Hali belgilanmagan"
    
    await message.answer(f"🏫 **Guruh:** {g_name}\n📈 **Guruh darajasi:** {g_level}")

@router.message(F.text == "🏆 O'zini darajasini ko'rish", StateFilter(None))
async def show_student_level(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)
    if not user or user['status'] != 'active':
        return
        
    s_level = user.get('student_level') or "Hali belgilanmagan"
    await message.answer(f"🏅 **Sizning shaxsiy darajangiz:** {s_level}\n\nO'qituvchi tomonidan belgilangan baholash.")

@router.message(F.text == "📩 Ustozga xabar yuborish", StateFilter(None))
async def msg_teacher(message: Message):
    await message.answer("Ustozingizga xabar yubormoqchi bo'lsangiz, ushbu manzilga yozing:\n👉 @Muhammaddiyor_courses_admin")

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
        
    await message.answer("Nima uchun akkauntingizni o'chirmoqchisiz? Iltimos, sababini yozib yuboring:")
    await state.set_state(Deletion.waiting_for_reason)

@router.message(Deletion.waiting_for_reason)
async def process_deletion_reason(message: Message, state: FSMContext, db: Database):
    reason = message.text.strip()
    
    if reason.startswith('/'):
        await message.answer("⚠️ Iltimos, avval akkauntni o'chirish sababini yozib yuboring (Buyruqlar hozir ishlamaydi):")
        return
        
    user = await db.get_user(message.from_user.id)
    
    await message.answer("Sizning so'rovingiz adminga yuborildi. Kuting...")
    
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
