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
        
    groups = await db.get_all_groups()
    if not groups:
        await message.answer("Hozircha guruhlar yo'q.")
        return
        
    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=f"📁 {g['name']}", callback_data=f"v_stud_grp:{g['id']}")])
        
    await message.answer("👤 **Qaysi guruh o'quvchilarini ko'rmoqchisiz?**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data.startswith("v_stud_grp:"))
async def view_students_in_group(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split(":")[1])
    group = await db.get_group(group_id)
    group_name = group['name']
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", group_name)
        
    if not students:
        await callback.answer("Bu guruhda o'quvchilar yo'q.", show_alert=True)
        return
        
    kb = []
    for s in students:
        kb.append([InlineKeyboardButton(text=f"{s['first_name']} {s['last_name']}", callback_data=f"set_s_lvl:{s['telegram_id']}:{group_name}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_v_stud_grp")])
    await callback.message.edit_text(f"👥 **{group_name}** o'quvchilari:\nDarajasini belgilash uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data == "back_to_v_stud_grp")
async def back_to_v_stud_grp(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=f"📁 {g['name']}", callback_data=f"v_stud_grp:{g['id']}")])
    await callback.message.edit_text("👤 **Qaysi guruh o'quvchilarini ko'rmoqchisiz?**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
