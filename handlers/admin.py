from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from states.register_states import AdminDeletion, Deletion, AdminGroupCreation, AdminBroadcast, AdminGroupLevel, AdminStudentLevel
from datetime import date
from database.db import Database
from config import ADMIN_IDS
from handlers.student import get_user_keyboard
import asyncio

router = Router()

class AdminScore(StatesGroup):
    waiting_for_score = State()

class AdminStudentEdit(StatesGroup):
    waiting_for_bio = State()

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
            reply_markup=get_user_keyboard(message.from_user.id),
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
@router.message(F.text == "📢 Hammaga xabar yuborish", StateFilter(None))
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
        resize_keyboard=True
    )
    await message.answer("📢 Barcha faol o'quvchilarga yuboriladigan xabarni kiriting:", reply_markup=keyboard)
    await state.set_state(AdminBroadcast.waiting_for_message)

@router.message(AdminBroadcast.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    text_to_send = message.text
    if text_to_send == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("Bosh menyuga qaytdingiz.", reply_markup=get_user_keyboard(message.from_user.id))
        return

    await state.update_data(broadcast_msg=text_to_send)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data="confirm_broadcast:yes"),
             InlineKeyboardButton(text="❌ Yo'q", callback_data="confirm_broadcast:no")]
        ]
    )
    
    await message.answer(f"Shu xabarni jo'natishni tasdiqlaysizmi?\n\n**Xabar:**\n{text_to_send}", reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(AdminBroadcast.waiting_for_confirmation)

@router.callback_query(AdminBroadcast.waiting_for_confirmation, F.data.startswith("confirm_broadcast:"))
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, db: Database):
    choice = callback.data.split(":")[1]
    
    if choice == "no":
        await state.clear()
        from handlers.student import get_user_keyboard
        await callback.message.delete()
        await callback.message.answer("❌ Xabar yuborish bekor qilindi.", reply_markup=get_user_keyboard(callback.from_user.id))
        return
        
    data = await state.get_data()
    text_to_send = data.get("broadcast_msg")
    
    users = await db.get_active_users()
    admin_id = callback.from_user.id
    
    await callback.message.delete()
    from handlers.student import get_user_keyboard
    await callback.message.answer(f"⏳ Xabar {len(users)} ta o'quvchiga fonda yuborilishni boshladi. Botdan bemalol foydalanishingiz mumkin!", reply_markup=get_user_keyboard(admin_id))
    await state.clear()
    
    import asyncio
    async def run_broadcast():
        count = 0
        for u in users:
            try:
                await callback.bot.send_message(u['telegram_id'], f"📢 **Admindan xabar:**\n\n{text_to_send}", parse_mode="Markdown")
                count += 1
                await asyncio.sleep(0.05) # Prevent rate limits
            except Exception:
                pass
        
        try:
            await callback.bot.send_message(admin_id, f"✅ Ommaviy xabar {count} ta o'quvchiga muvaffaqiyatli yetkazildi.")
        except Exception:
            pass
            
    asyncio.create_task(run_broadcast())

# ================= LEVEL & STUDENT MANAGEMENT =================
@router.message(F.text == "👥 Guruhlar va O'quvchilar", StateFilter(None))
async def admin_groups_and_students(message: Message, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        return
    groups = await db.get_all_groups()
    if not groups:
        await message.answer("Hozircha guruhlar yaratilmagan.")
        return
        
    inline_kb = []
    for i in range(0, len(groups), 2):
        row = [InlineKeyboardButton(text=groups[i]['name'], callback_data=f"admin_lvl:{groups[i]['name']}")]
        if i + 1 < len(groups):
            row.append(InlineKeyboardButton(text=groups[i+1]['name'], callback_data=f"admin_lvl:{groups[i+1]['name']}"))
        inline_kb.append(row)
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await message.answer("👥 **Guruhlar va O'quvchilar**\nKerakli guruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "admin_levels_menu")
async def back_to_levels_menu(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    inline_kb = []
    for i in range(0, len(groups), 2):
        row = [InlineKeyboardButton(text=groups[i]['name'], callback_data=f"admin_lvl:{groups[i]['name']}")]
        if i + 1 < len(groups):
            row.append(InlineKeyboardButton(text=groups[i+1]['name'], callback_data=f"admin_lvl:{groups[i+1]['name']}"))
        inline_kb.append(row)
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("👥 **Guruhlar va O'quvchilar**\nKerakli guruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_lvl:"))
async def admin_level_menu(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    async with db.pool.acquire() as connection:
        count = await connection.fetchval("SELECT COUNT(*) FROM users WHERE level = $1 AND status = 'active'", level)
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 O'quvchilarni ko'rish", callback_data=f"view_studs:{level}:0")],
        [InlineKeyboardButton(text="🎓 O'quvchini darajalash", callback_data=f"eval_studs:{level}")],
        [InlineKeyboardButton(text="🏫 Guruhni baholash", callback_data=f"eval_grp:{level}")],
        [InlineKeyboardButton(text="📝 Ball qo'yish", callback_data=f"score_list:{level}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_levels_menu")]
    ])
    
    await callback.message.edit_text(f"📚 **{level} guruhi**\n👥 O'quvchilar soni: {count}", parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("view_studs:"))
async def view_students_in_level(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    page = int(parts[2])
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)
        
    if not students:
        await callback.answer("Bu darajada o'quvchilar yo'q.", show_alert=True)
        return
        
    total = len(students)
    if page >= total:
        page = total - 1
    if page < 0:
        page = 0
        
    student = students[page]
    
    from utils import get_student_profile_text, get_student_profile_keyboard
    text = get_student_profile_text(student, page_info=f" {page + 1}/{total}")
           
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"view_studs:{level}:{page-1}"))
    if page < total - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"view_studs:{level}:{page+1}"))
        
    extra_buttons = [nav_row] if nav_row else []
    kb = get_student_profile_keyboard(student['telegram_id'], back_callback_data=f"admin_lvl:{level}", extra_buttons=extra_buttons)
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("eval_studs:"))
async def eval_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)
        
    if not students:
        await callback.answer("Bu darajada o'quvchilar yo'q.", show_alert=True)
        return
        
    kb = []
    for s in students:
        kb.append([InlineKeyboardButton(text=f"{s['first_name']} {s['last_name']}", callback_data=f"set_s_lvl:{s['telegram_id']}:{level}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_lvl:{level}")])
    await callback.message.edit_text("Baholash uchun o'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("set_s_lvl:"))
async def set_stud_level_opts(callback: CallbackQuery):
    parts = callback.data.split(":")
    stud_id = parts[1]
    level = parts[2]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="SUPPORT", callback_data=f"save_s_lvl:{stud_id}:SUPPORT:{level}")],
        [InlineKeyboardButton(text="CAPTAIN", callback_data=f"save_s_lvl:{stud_id}:CAPTAIN:{level}")],
        [InlineKeyboardButton(text="MAIN", callback_data=f"save_s_lvl:{stud_id}:MAIN:{level}")],
        [InlineKeyboardButton(text="LEARNER", callback_data=f"save_s_lvl:{stud_id}:LEARNER:{level}")],
        [InlineKeyboardButton(text="INTRODUCTORY", callback_data=f"save_s_lvl:{stud_id}:INTRODUCTORY:{level}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"eval_studs:{level}")]
    ])
    
    await callback.message.edit_text("O'quvchi uchun darajani tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("save_s_lvl:"))
async def save_stud_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    stud_id = int(parts[1])
    stud_level = parts[2]
    level = parts[3]
    
    await db.set_student_level(stud_id, stud_level)
    await callback.answer(f"O'quvchi darajasi {stud_level} etib belgilandi!", show_alert=True)
    
    try:
        await callback.bot.send_message(stud_id, f"🏆 **Sizning darajangiz yangilandi:** {stud_level}")
    except:
        pass
        
    fake_cb = callback
    fake_cb.data = f"eval_studs:{level}"
    await eval_students_list(fake_cb, db)

@router.callback_query(F.data.startswith("eval_grp:"))
async def eval_grp_opts(callback: CallbackQuery):
    level = callback.data.split(":")[1]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="SMART GROUP", callback_data=f"save_g_lvl:{level}:SMART GROUP")],
        [InlineKeyboardButton(text="MIDDLE CLASS", callback_data=f"save_g_lvl:{level}:MIDDLE CLASS")],
        [InlineKeyboardButton(text="LAZY TEAM", callback_data=f"save_g_lvl:{level}:LAZY TEAM")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_lvl:{level}")]
    ])
    
    await callback.message.edit_text(f"🏫 **{level}** guruhi(darajasi) uchun nom/daraja tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("save_g_lvl:"))
async def save_grp_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    grp_level = parts[2]
    
    async with db.pool.acquire() as connection:
        await connection.execute("""
            UPDATE groups SET group_level = $2 WHERE name = $1
        """, level, grp_level)
        
    await callback.answer(f"Guruh darajasi {grp_level} etib belgilandi!", show_alert=True)
    
    fake_cb = callback
    fake_cb.data = f"admin_lvl:{level}"
    await admin_level_menu(fake_cb, db)

@router.callback_query(F.data.startswith("score_list:"))
async def score_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active'", level)
        
    if not students:
        await callback.answer("Bu darajada o'quvchilar yo'q.", show_alert=True)
        return
        
    kb = []
    for s in students:
        kb.append([InlineKeyboardButton(text=f"{s['first_name']} {s['last_name']}", callback_data=f"score:{s['telegram_id']}:{level}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_lvl:{level}")])
    await callback.message.edit_text("Ball qo'yish uchun o'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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

@router.message(F.text == "🤖 Bot qoidalari va foydalanish", lambda message: message.from_user.id in ADMIN_IDS, StateFilter(None))
async def show_admin_rules(message: Message):
    from rules.adminrule import ADMIN_RULES_TEXT
    await message.answer(ADMIN_RULES_TEXT, parse_mode="Markdown")

@router.callback_query(F.data.startswith("astud_set_lvl:"))
async def process_astud_set_lvl(callback: CallbackQuery):
    student_id = int(callback.data.split(":")[1])
    
    levels = [
        "Excellent 🥇", "Very Good 🟢", "Good 🟡", 
        "Needs Improvement 🟠", "Weak 🔴"
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lvl, callback_data=f"astud_save_lvl:{student_id}:{lvl}")] for lvl in levels
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_astud_edit")])
    
    await callback.message.answer("🎓 O'quvchining joriy darajasini (o'zlashtirishini) belgilang:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("astud_save_lvl:"))
async def process_astud_save_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    student_id = int(parts[1])
    new_lvl = parts[2]
    
    await db.set_performance_grade(student_id, new_lvl)
    await callback.answer(f"Daraja {new_lvl} ga o'zgartirildi!", show_alert=True)
    await callback.message.delete()

@router.callback_query(F.data.startswith("astud_eng_lvl:"))
async def process_astud_eng_lvl(callback: CallbackQuery):
    student_id = int(callback.data.split(":")[1])
    
    levels = [
        "SUPPORT", "CAPTAIN", "MAIN", "LEARNER", "INTRODUCTORY"
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lvl, callback_data=f"astud_save_eng_lvl:{student_id}:{lvl}")] for lvl in levels
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_astud_edit")])
    
    await callback.message.answer("🎓 O'quvchining Ingliz tili darajasini belgilang:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("astud_save_eng_lvl:"))
async def process_astud_save_eng_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    student_id = int(parts[1])
    new_lvl = parts[2]
    
    await db.set_student_level(student_id, new_lvl)
    await callback.answer(f"Ingliz tili darajasi {new_lvl} ga o'zgartirildi!", show_alert=True)
    await callback.message.delete()

@router.callback_query(F.data.startswith("astud_bio:"))
async def process_astud_bio(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split(":")[1])
    await state.update_data(bio_student_id=student_id)
    await state.set_state(AdminStudentEdit.waiting_for_bio)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_astud_edit")]
    ])
    await callback.message.answer("✍️ O'quvchi uchun tafsif (bio/fikr) yozing.\nBu xabar uning o'zlashtirish panelida doimiy turadi:", reply_markup=kb)
    await callback.answer()

@router.message(AdminStudentEdit.waiting_for_bio)
async def save_astud_bio(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    student_id = data.get('bio_student_id')
    bio = message.text
    
    await db.update_teacher_bio(student_id, bio)
    await message.answer("✅ Ustoz tafsifi muvaffaqiyatli saqlandi!")
    await state.clear()

@router.callback_query(F.data == "cancel_astud_edit")
async def cancel_astud_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
