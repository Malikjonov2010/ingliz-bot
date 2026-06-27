from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from states.register_states import AdminGroupCreation
from database.db import Database
from config import ADMIN_IDS

router = Router()

@router.message(F.text == "🏫 Guruhlarni boshqarish", StateFilter(None))
async def manage_groups_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Guruhlarni ko'rish", callback_data="admin_view_groups")],
        [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="admin_add_group")]
    ])
    await message.answer("🏫 **Guruhlarni boshqarish:**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "admin_view_groups")
async def admin_view_groups(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    if not groups:
        await callback.message.edit_text("Hozircha guruhlar yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="admin_add_group")]]))
        return
        
    text = f"📊 **Jami guruhlar soni:** {len(groups)}\n\n"
    for g in groups:
        lvl = g['group_level'] or "Belgilanmagan"
        text += f"🏫 <b>{g['name']}</b>\n🗓 Kunlari: {g['days']} | ⏰ Vaqti: {g['time']}\n📈 Darajasi: {lvl}\n\n"
        
    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=f"📈 {g['name']} darajasini o'zgartirish", callback_data=f"eval_grp:{g['name']}")])
    kb.append([InlineKeyboardButton(text="✏️ Guruhni tahrirlash", callback_data="edit_group_menu")])
        
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "edit_group_menu")
async def edit_group_menu(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=f"✏️ {g['name']}", callback_data=f"edit_grp:{g['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_view_groups")])
    await callback.message.edit_text("Tahrirlash uchun guruhni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("edit_grp:"))
async def edit_grp_start(callback: CallbackQuery, state: FSMContext, db: Database):
    group_id = int(callback.data.split(":")[1])
    group = await db.get_group(group_id)
    await state.update_data(edit_group_id=group_id)
    await callback.message.edit_text(f"Guruhning yangi nomini kiriting (Eskisi: {group['name']}):")
    await state.set_state(AdminGroupCreation.waiting_for_name)

@router.callback_query(F.data == "admin_add_group")
async def start_add_group(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_group_id=None)
    await callback.message.edit_text("Yangi guruh nomini kiriting:")
    await state.set_state(AdminGroupCreation.waiting_for_name)

@router.message(AdminGroupCreation.waiting_for_name)
async def add_group_name(message: Message, state: FSMContext):
    await state.update_data(group_name=message.text)
    await message.answer("Guruh qaysi kunlari bo'ladi? (masalan: Dushanba, Chorshanba, Juma):")
    await state.set_state(AdminGroupCreation.waiting_for_days)

@router.message(AdminGroupCreation.waiting_for_days)
async def add_group_days(message: Message, state: FSMContext):
    await state.update_data(group_days=message.text)
    await message.answer("Guruh soat nechida bo'ladi? (masalan: 14:00):")
    await state.set_state(AdminGroupCreation.waiting_for_time)

@router.message(AdminGroupCreation.waiting_for_time)
async def add_group_time(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    name = data['group_name']
    days = data['group_days']
    time = message.text
    edit_id = data.get('edit_group_id')
    
    try:
        if edit_id:
            group = await db.get_group(edit_id)
            old_name = group['name']
            async with db.pool.acquire() as connection:
                await connection.execute("UPDATE users SET level = $1 WHERE level = $2", name, old_name)
                
            await db.update_group(edit_id, name, days, time)
            await message.answer(f"✅ Guruh muvaffaqiyatli yangilandi!\nNomi: {name}\nKunlari: {days}\nVaqti: {time}")
        else:
            await db.create_group(name, days, time, message.from_user.id)
            await message.answer(f"✅ Yangi guruh qo'shildi!\nNomi: {name}\nKunlari: {days}\nVaqti: {time}")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}\nIltimos, qaytadan urinib ko'ring yoki adminga murojaat qiling.")
        
    await state.clear()

@router.message(F.text == "👤 O'quvchilarni ko'rish", StateFilter(None))
async def view_students_menu(message: Message, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    students = await db.get_active_users()
    if not students:
        await message.answer("Hozircha ro'yxatdan o'tgan o'quvchilar yo'q.")
        return
        
    kb = []
    # Telegram inline keyboard limit is 100 buttons.
    for s in students[:90]:
        kb.append([InlineKeyboardButton(text=f"👤 {s['first_name']} {s['last_name']}", callback_data=f"astud:{s['telegram_id']}")])
        
    await message.answer("👤 **Barcha o'quvchilar ro'yxati:**\nBatafsil ma'lumot va boshqarish uchun o'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data == "astud_list")
async def back_to_astud_list(callback: CallbackQuery, db: Database):
    students = await db.get_active_users()
    kb = []
    for s in students[:90]:
        kb.append([InlineKeyboardButton(text=f"👤 {s['first_name']} {s['last_name']}", callback_data=f"astud:{s['telegram_id']}")])
    await callback.message.edit_text("👤 **Barcha o'quvchilar ro'yxati:**\nBatafsil ma'lumot va boshqarish uchun o'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data.startswith("astud:"))
async def view_astud_details(callback: CallbackQuery, db: Database):
    stud_id = int(callback.data.split(":")[1])
    student = await db.get_user(stud_id)
    
    if not student:
        await callback.answer("O'quvchi topilmadi.", show_alert=True)
        return
        
    days = student.get('days') or "Noma'lum"
    bio = student.get('teacher_bio')
    bio_text = f"\n**📝 Ustoz fikri:** {bio}" if bio else ""
    
    level_val = student.get('level', "Noma'lum")
    student_level_val = student.get('student_level', 'Belgilanmagan')
    
    text = f"👤 **O'quvchi ma'lumotlari:**\n\n" \
           f"**Ism-familiya:** {student['first_name']} {student['last_name']}\n" \
           f"**Yosh:** {student['age']}\n" \
           f"**Tel:** {student['phone_number']}\n" \
           f"**Guruh/Daraja:** {level_val}\n" \
           f"**Kunlar:** {days}\n" \
           f"**ID:** {student['telegram_id']}\n" \
           f"**O'quvchi maqomi:** {student_level_val}" \
           f"{bio_text}"
           
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Darajani belgilash", callback_data=f"astud_set_lvl:{stud_id}")],
        [InlineKeyboardButton(text="📝 Ustoz fikri (Bio) yozish", callback_data=f"astud_bio:{stud_id}")],
        [InlineKeyboardButton(text="📩 Xabar yuborish", callback_data=f"astud_msg:{stud_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="astud_list")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("astud_set_lvl:"))
async def astud_set_lvl(callback: CallbackQuery):
    stud_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="SUPPORT", callback_data=f"astud_save_lvl:{stud_id}:SUPPORT")],
        [InlineKeyboardButton(text="CAPTAIN", callback_data=f"astud_save_lvl:{stud_id}:CAPTAIN")],
        [InlineKeyboardButton(text="MAIN", callback_data=f"astud_save_lvl:{stud_id}:MAIN")],
        [InlineKeyboardButton(text="LEARNER", callback_data=f"astud_save_lvl:{stud_id}:LEARNER")],
        [InlineKeyboardButton(text="INTRODUCTORY", callback_data=f"astud_save_lvl:{stud_id}:INTRODUCTORY")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"astud:{stud_id}")]
    ])
    await callback.message.edit_text("O'quvchi uchun darajani (maqomini) tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("astud_save_lvl:"))
async def astud_save_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    stud_id = int(parts[1])
    stud_level = parts[2]
    
    await db.set_student_level(stud_id, stud_level)
    await callback.answer(f"O'quvchi darajasi {stud_level} etib belgilandi!", show_alert=True)
    
    student = await db.get_user(stud_id)
    days = student.get('days') or "Noma'lum"
    bio = student.get('teacher_bio')
    bio_text = f"\n**📝 Ustoz fikri:** {bio}" if bio else ""
    
    level_val = student.get('level', "Noma'lum")
    student_level_val = student.get('student_level', 'Belgilanmagan')
    
    text = f"👤 **O'quvchi ma'lumotlari:**\n\n" \
           f"**Ism-familiya:** {student['first_name']} {student['last_name']}\n" \
           f"**Yosh:** {student['age']}\n" \
           f"**Tel:** {student['phone_number']}\n" \
           f"**Guruh/Daraja:** {level_val}\n" \
           f"**Kunlar:** {days}\n" \
           f"**ID:** {student['telegram_id']}\n" \
           f"**O'quvchi maqomi:** {student_level_val}" \
           f"{bio_text}"
           
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Darajani belgilash", callback_data=f"astud_set_lvl:{stud_id}")],
        [InlineKeyboardButton(text="📝 Ustoz fikri (Bio) yozish", callback_data=f"astud_bio:{stud_id}")],
        [InlineKeyboardButton(text="📩 Xabar yuborish", callback_data=f"astud_msg:{stud_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="astud_list")]
    ])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

from states.register_states import AdminPersonalMessage

@router.callback_query(F.data.startswith("astud_msg:"))
async def astud_msg(callback: CallbackQuery, state: FSMContext):
    stud_id = int(callback.data.split(":")[1])
    await state.update_data(student_id=stud_id)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True
    )
    
    await callback.message.delete()
    await callback.message.answer("📩 **O'quvchiga yuboriladigan xabarni kiriting:**\n(Bekor qilish uchun '⬅️ Orqaga' ni bosing)", parse_mode="Markdown", reply_markup=keyboard)
    await state.set_state(AdminPersonalMessage.waiting_for_message)

@router.message(AdminPersonalMessage.waiting_for_message)
async def process_admin_personal_message(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
        
    data = await state.get_data()
    stud_id = data.get('student_id')
    
    try:
        await message.bot.send_message(
            chat_id=stud_id,
            text=f"👨‍🏫 **Ustozdan shaxsiy xabar:**\n\n{message.text}",
            parse_mode="Markdown"
        )
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("✅ Xabar o'quvchiga muvaffaqiyatli yuborildi!", reply_markup=get_user_keyboard(message.from_user.id))
    except Exception as e:
        await message.answer(f"❌ Xabar yuborishda xatolik yuz berdi. Balki o'quvchi botni bloklagan bo'lishi mumkin.\nSabab: {e}")

from states.register_states import AdminSetBio

@router.callback_query(F.data.startswith("astud_bio:"))
async def astud_bio(callback: CallbackQuery, state: FSMContext):
    stud_id = int(callback.data.split(":")[1])
    await state.update_data(student_id=stud_id)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True
    )
    
    await callback.message.delete()
    await callback.message.answer(
        "📝 **O'quvchi uchun qisqacha ustoz fikrini (bio) kiriting (max 100-150 harf):**\n\n"
        "*(Ushbu fikr o'quvchi botga har safar kirganida ko'rinib turadi. Bekor qilish uchun '⬅️ Orqaga' ni bosing)*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await state.set_state(AdminSetBio.waiting_for_bio)

@router.message(AdminSetBio.waiting_for_bio)
async def process_admin_set_bio(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
        
    bio_text = message.text[:250] # Enforce safety length limit
    data = await state.get_data()
    stud_id = data.get('student_id')
    
    await db.set_teacher_bio(stud_id, bio_text)
    
    try:
        await message.bot.send_message(
            chat_id=stud_id,
            text=f"💡 **Ustozingiz profilingizni yangiladi va sizga maslahat qoldirdi!**\n\n"
                 f"\"{bio_text}\"\n\n"
                 f"_(Buni har doim botga kirganda ko'rasiz)_",
            parse_mode="Markdown"
        )
    except Exception as e:
        pass # Ignore if student blocked bot
        
    await state.clear()
    from handlers.student import get_user_keyboard
    await message.answer("✅ Ustoz fikri saqlandi va o'quvchiga yuborildi!", reply_markup=get_user_keyboard(message.from_user.id))
