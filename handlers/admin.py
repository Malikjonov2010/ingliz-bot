from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from states.register_states import AdminDeletion, Deletion, AdminGroupCreation, AdminBroadcast, AdminGroupLevel, AdminStudentLevel
from datetime import date
from database.db import Database
from config import ADMIN_IDS
from handlers.student import get_student_keyboard
import asyncio

router = Router()

class AdminScore(StatesGroup):
    waiting_for_score = State()

@router.callback_query(F.data.startswith("approve_student:"))
async def approve_student(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return
        
    user_id = int(callback.data.split(":")[1])
    await db.update_user_status(user_id, 'active')
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ Tasdiqladi: {callback.from_user.first_name}")
    
    # Notify student
    try:
        await callback.bot.send_message(
            user_id,
            "🎉 **Tabriklaymiz!** Sizning hisobingiz admin tomonidan tasdiqlandi!\nEndi botdan to'liq foydalanishingiz mumkin.",
            reply_markup=get_student_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_student:"))
async def reject_student(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return
        
    user_id = int(callback.data.split(":")[1])
    await db.update_user_status(user_id, 'rejected')
    await callback.message.edit_text(f"{callback.message.text}\n\n❌ Rad etdi: {callback.from_user.first_name}")
    
    # Notify student
    try:
        await callback.bot.send_message(user_id, "❌ Sizning ro'yxatdan o'tish so'rovingiz rad etildi.")
    except Exception:
        pass

@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Siz admin emassiz.")
        return
        
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Guruhni baholash", callback_data="admin_eval_groups")],
            [InlineKeyboardButton(text="👤 O'quvchini baholash", callback_data="admin_eval_students")],
            [InlineKeyboardButton(text="📢 Hammaga xabar yuborish", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📈 Guruhlarni darajasini belgilash", callback_data="admin_set_levels")]
        ]
    )
    
    await message.answer("👨‍🏫 **O'qituvchi Paneli**\nQuyidagilardan birini tanlang:", parse_mode="Markdown", reply_markup=keyboard)

# ================= BROADCAST =================
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📢 Barcha faol o'quvchilarga yuboriladigan xabarni kiriting:")
    await state.set_state(AdminBroadcast.waiting_for_message)

@router.message(AdminBroadcast.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, db: Database):
    users = await db.get_active_users()
    admin_id = message.from_user.id
    text_to_send = message.text
    
    await message.answer(f"⏳ Xabar {len(users)} ta o'quvchiga fonda yuborilishni boshladi. Botdan bemalol foydalanishingiz mumkin!")
    await state.clear()
    
    import asyncio
    async def run_broadcast():
        count = 0
        for u in users:
            try:
                await message.bot.send_message(u['telegram_id'], f"📢 **Admindan xabar:**\n\n{text_to_send}", parse_mode="Markdown")
                count += 1
                await asyncio.sleep(0.05) # Prevent rate limits
            except Exception:
                pass
        
        try:
            await message.bot.send_message(admin_id, f"✅ Ommaviy xabar {count} ta o'quvchiga muvaffaqiyatli yetkazildi.")
        except Exception:
            pass
            
    asyncio.create_task(run_broadcast())

# ================= SET LEVELS =================
@router.callback_query(F.data == "admin_set_levels")
async def admin_set_levels(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    
    inline_kb = []
    if groups:
        inline_kb = [[InlineKeyboardButton(text=g['name'], callback_data=f"setlevel_grp_{g['id']}")] for g in groups]
        
    inline_kb.append([InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="add_group")])
    inline_kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("📈 **Guruhlarni darajasini belgilash**\nGuruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data.startswith("setlevel_grp_"))
async def setlevel_grp(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split("_")[2])
    group_name = await db.get_group_name(group_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏫 Guruhni darajasini qo'yish", callback_data=f"setgrplevel_{group_id}")],
        [InlineKeyboardButton(text="👥 O'quvchilarni ko'rish", callback_data=f"setstudlevel_{group_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_set_levels")]
    ])
    
    await callback.message.edit_text(f"📈 **Guruh:** {group_name}\nNima qilamiz?", parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("setgrplevel_"))
async def set_grp_level_opts(callback: CallbackQuery):
    group_id = int(callback.data.split("_")[1])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Starter", callback_data=f"savegrplvl_{group_id}_Starter")],
        [InlineKeyboardButton(text="2️⃣ Learner", callback_data=f"savegrplvl_{group_id}_Learner")],
        [InlineKeyboardButton(text="3️⃣ Best", callback_data=f"savegrplvl_{group_id}_Best")]
    ])
    
    await callback.message.edit_text("Guruh uchun darajani tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("savegrplvl_"))
async def save_grp_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split("_")
    group_id = int(parts[1])
    level = parts[2]
    
    await db.set_group_level(group_id, level)
    await callback.answer(f"Guruh darajasi {level} etib belgilandi!", show_alert=True)
    await admin_set_levels(callback, db)

@router.callback_query(F.data.startswith("setstudlevel_"))
async def view_students_for_level(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split("_")[1])
    students = await db.get_group_students(group_id)
    
    if not students:
        await callback.message.edit_text("Ushbu guruhda o'quvchilar yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"setlevel_grp_{group_id}")]]))
        return
        
    kb = []
    for s in students:
        kb.append([InlineKeyboardButton(text=f"{s['first_name']} {s['last_name']}", callback_data=f"studlvl_{s['telegram_id']}_{group_id}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"setlevel_grp_{group_id}")])
    await callback.message.edit_text("O'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("studlvl_"))
async def set_stud_level_opts(callback: CallbackQuery):
    parts = callback.data.split("_")
    stud_id = parts[1]
    group_id = parts[2]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Starter", callback_data=f"savestudlvl_{stud_id}_Starter_{group_id}")],
        [InlineKeyboardButton(text="2️⃣ Learner", callback_data=f"savestudlvl_{stud_id}_Learner_{group_id}")],
        [InlineKeyboardButton(text="3️⃣ Best", callback_data=f"savestudlvl_{stud_id}_Best_{group_id}")]
    ])
    
    await callback.message.edit_text("O'quvchi uchun darajani tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("savestudlvl_"))
async def save_stud_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split("_")
    stud_id = int(parts[1])
    level = parts[2]
    group_id = int(parts[3])
    
    await db.set_student_level(stud_id, level)
    await callback.answer(f"O'quvchi darajasi {level} etib belgilandi!", show_alert=True)
    
    # notify student
    try:
        await callback.bot.send_message(stud_id, f"🏆 **Sizning darajangiz yangilandi:** {level}")
    except:
        pass
        
    # simulate go back
    fake_cb = callback
    fake_cb.data = f"setstudlevel_{group_id}"
    await view_students_for_level(fake_cb, db)

# ================= EXISTING ADMIN FUNCTIONS (EVALUATE GROUPS) =================

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, db: Database):
    await admin_panel(callback.message, db)
    await callback.message.delete()

@router.callback_query(F.data == "admin_eval_groups")
async def admin_eval_groups(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    inline_kb = []
    if groups:
        inline_kb = [[InlineKeyboardButton(text=g['name'], callback_data=f"admin_group:{g['id']}")] for g in groups]
        
    inline_kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("👥 **Guruhni baholash**\nGuruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "admin_eval_students")
async def admin_eval_students(callback: CallbackQuery, db: Database):
    # For simplicity, we also show groups to select student to evaluate
    groups = await db.get_all_groups()
    inline_kb = []
    if groups:
        inline_kb = [[InlineKeyboardButton(text=g['name'], callback_data=f"admin_group:{g['id']}")] for g in groups]
        
    inline_kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("👤 **O'quvchini baholash**\nAvval guruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data == "add_group")
async def add_group_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Yangi guruh nomini kiriting:")
    await state.set_state(AdminGroupCreation.waiting_for_name)

@router.message(AdminGroupCreation.waiting_for_name)
async def process_add_group(message: Message, state: FSMContext, db: Database):
    group_name = message.text
    await db.create_group(group_name, message.from_user.id)
    await message.answer(f"✅ '{group_name}' guruhi muvaffaqiyatli yaratildi!\n\n/admin orqali guruhlarni ko'rishingiz mumkin.")
    await state.clear()

@router.callback_query(F.data.startswith("admin_group:"))
async def admin_group_view(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split(":")[1])
    group_name = await db.get_group_name(group_id)
    students = await db.get_group_students(group_id)
    
    if not students:
        await callback.message.edit_text(f"👥 **Guruh:** {group_name}\n\nBu guruhda faol o'quvchilar yo'q.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_eval_groups")]]))
        return
        
    text = f"👥 **Guruh:** {group_name}\n━━━━━━━━━━━━━━━━━━\n"
    
    today_date = date.today()
    keyboard_buttons = []
    
    async with db.pool.acquire() as connection:
        for student in students:
            is_present = await connection.fetchval("SELECT is_present FROM attendance WHERE user_id = $1 AND date = $2", student['telegram_id'], today_date)
            if is_present is None:
                status_emoji = "⏳"
            elif is_present:
                status_emoji = "✅"
            else:
                status_emoji = "❌"
            text += f"{status_emoji} {student['first_name']} {student['last_name']}\n"
            
            keyboard_buttons.append([InlineKeyboardButton(text=f"Baholash: {student['first_name']} {student['last_name']}", callback_data=f"score:{student['telegram_id']}:{group_id}")])
            
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_eval_groups")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data.startswith("score:"))
async def ask_for_score(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split(":")
    student_id = int(data[1])
    group_id = int(data[2])
    
    await state.update_data(score_student_id=student_id, score_group_id=group_id)
    await callback.message.answer(f"O'quvchi uchun ballni kiriting (0-25):")
    await state.set_state(AdminScore.waiting_for_score)

@router.message(AdminScore.waiting_for_score)
async def process_score(message: Message, state: FSMContext, db: Database):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting (0-25).")
        return
        
    score = int(message.text)
    if score < 0 or score > 25:
        await message.answer("Ball 0 dan 25 gacha bo'lishi kerak!")
        return
        
    data = await state.get_data()
    student_id = data['score_student_id']
    group_id = data['score_group_id']
    
    lesson_num, total_score = await db.add_score(student_id, score)
    await state.clear()
    
    await message.answer(f"✅ Ball muvaffaqiyatli saqlandi! (Dars {lesson_num}/6)")
    
    try:
        await message.bot.send_message(
            student_id,
            f"🔔 *Siz bugungi darsda {score}/25 ball to'pladingiz. Barakalla, izlanishdan to'xtamang!* 💪",
            parse_mode="Markdown"
        )
    except Exception:
        pass
        
    if lesson_num == 6:
        level, emoji = await db.complete_cycle(student_id, total_score)
        try:
            await message.bot.send_message(
                student_id,
                f"🎉 *Tabriklaymiz!*\nSiz ushbu siklda umumiy {total_score}/150 ball to'pladingiz.\n\n🏆 Darajangiz: **{level} {emoji}**.\n\nKeyingi siklda yanada yuqori natijaga harakat qiling!",
                parse_mode="Markdown"
            )
        except Exception:
            pass

@router.callback_query(F.data.startswith("del_req:"))
async def process_delete_request(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.update_data(delete_user_id=user_id)
    await callback.message.answer("O'quvchi uchun 4 xonali kod va izoh kiriting (masalan: 1234 bemalol o'chirishingiz mumkin):")
    await state.set_state(AdminDeletion.waiting_for_admin_code)

@router.message(AdminDeletion.waiting_for_admin_code)
async def process_admin_delete_code(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    user_id = data.get('delete_user_id')
    
    parts = message.text.split(maxsplit=1)
    code = parts[0]
    comment = parts[1] if len(parts) > 1 else ""
    
    if len(code) != 4 or not code.isdigit():
        await message.answer("Iltimos, avval 4 xonali kod kiriting, so'ngra bo'sh joy tashlab izoh yozing.")
        return
        
    await db.set_deletion_code(user_id, code)
    await message.answer("Kod o'quvchiga yuborildi.")
    
    try:
        await message.bot.send_message(
            user_id,
            f"Admindan ruxsat keldi.\nO'chirish kodi: {code}\nIzoh: {comment}\n\nIltimos, tasdiqlash uchun 4 xonali kodni kiriting:"
        )
    except Exception:
        pass
        
    await state.clear()
