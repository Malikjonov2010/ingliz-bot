from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from states.register_states import AdminDeletion, Deletion, AdminGroupCreation, AdminBroadcast, AdminGroupLevel, AdminStudentLevel
from datetime import date
from database.db import Database
from config import ADMIN_IDS, TEACHER_IDS, is_teacher, is_pure_admin
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
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        await message.answer("⚠️ Siz admin emassiz.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Guruhni baholash",                callback_data="admin_eval_groups")],
        [InlineKeyboardButton(text="👤 O'quvchini baholash",             callback_data="admin_eval_students")],
        [InlineKeyboardButton(text="📊 Guruhlar darajasini belgilash",   callback_data="admin_set_levels")],
        [InlineKeyboardButton(text="📢 Hammaga xabar yuborish",          callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💰 Oylik to'lov boshqaruvi",         callback_data="admin_monthly_fee")],
    ])
    
    await message.answer(
        "👨‍🏫 <b>Ustoz (Admin) Paneli</b>\n"
        "Quyidagilardan birini tanlang:",
        parse_mode="HTML", reply_markup=keyboard
    )


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
        row = [InlineKeyboardButton(text=groups[i]['name'], callback_data=f"admin_lvl:{groups[i]['id']}")]
        if i + 1 < len(groups):
            row.append(InlineKeyboardButton(text=groups[i+1]['name'], callback_data=f"admin_lvl:{groups[i+1]['id']}"))
        inline_kb.append(row)
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await message.answer("👥 **Guruhlar va O'quvchilar**\nKerakli guruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "admin_levels_menu")
async def back_to_levels_menu(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    inline_kb = []
    for i in range(0, len(groups), 2):
        row = [InlineKeyboardButton(text=groups[i]['name'], callback_data=f"admin_lvl:{groups[i]['id']}")]
        if i + 1 < len(groups):
            row.append(InlineKeyboardButton(text=groups[i+1]['name'], callback_data=f"admin_lvl:{groups[i+1]['id']}"))
        inline_kb.append(row)
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text("👥 **Guruhlar va O'quvchilar**\nKerakli guruhni tanlang:", parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_lvl:"))
async def admin_level_menu(callback: CallbackQuery, db: Database):
    group_id_str = callback.data.split(":")[1]
    
    if group_id_str.isdigit():
        group_id = int(group_id_str)
        group = await db.get_group(group_id)
        if not group:
            await callback.answer("Guruh topilmadi", show_alert=True)
            return
        level_name = group['name']
        async with db.pool.acquire() as connection:
            count = await connection.fetchval("SELECT COUNT(*) FROM users WHERE group_id = $1 AND status = 'active'", group_id)
    else:
        group_id = group_id_str
        level_name = group_id_str
        async with db.pool.acquire() as connection:
            count = await connection.fetchval("SELECT COUNT(*) FROM users WHERE level = $1 AND status = 'active'", level_name)
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 O'quvchilarni ko'rish", callback_data=f"view_studs:{group_id}:0")],
        [InlineKeyboardButton(text="🎓 O'quvchini darajalash", callback_data=f"eval_studs:{group_id}")],
        [InlineKeyboardButton(text="🏫 Guruhni baholash", callback_data=f"eval_grp:{group_id}")],
        [InlineKeyboardButton(text="📝 Ball qo'yish", callback_data=f"score_list:{group_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_levels_menu")]
    ])
    
    await callback.message.edit_text(f"📚 **{level_name} guruhi**\n👥 O'quvchilar soni: {count}", parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("view_studs:"))
async def view_students_in_level(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    page = int(parts[2])
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE group_id = $1 AND status = 'active' ORDER BY created_at ASC", group_id)
    else:
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)
    students = [s for s in students if s['telegram_id'] not in ADMIN_IDS and s['telegram_id'] not in TEACHER_IDS]
        
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
    text = await get_student_profile_text(student, db=db, page_info=f" {page + 1}/{total}")
           
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"view_studs:{level}:{page-1}"))
    if page < total - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"view_studs:{level}:{page+1}"))
        
    extra_buttons = [nav_row] if nav_row else []
    kb = get_student_profile_keyboard(student['telegram_id'], back_callback_data=f"admin_lvl:{level}", extra_buttons=extra_buttons)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("eval_studs:"))
async def eval_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE group_id = $1 AND status = 'active' ORDER BY created_at ASC", group_id)
    else:
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)
    students = [s for s in students if s['telegram_id'] not in ADMIN_IDS and s['telegram_id'] not in TEACHER_IDS]
        
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

@router.callback_query(F.data.startswith("approve_free_premium:"))
async def process_approve_free_premium(callback: CallbackQuery, db: Database):
    student_id = int(callback.data.split(":")[1])
    
    # 1 oylik premium qo'shish
    from datetime import datetime, timedelta
    import pytz
    tz_uz = pytz.timezone('Asia/Tashkent')
    
    # Activate premium
    async with db.pool.acquire() as connection:
        now = datetime.now(tz_uz)
        expires = now + timedelta(days=30)
        
        await connection.execute("""
            INSERT INTO premium_users (user_id, activated_at, expires_at, activated_by) 
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) 
            DO UPDATE SET expires_at = GREATEST(premium_users.expires_at, EXCLUDED.activated_at) + INTERVAL '30 days', activated_at = EXCLUDED.activated_at
        """, student_id, now, expires, callback.from_user.id)
        
    await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Ruxsat berildi va Premium yoqildi!</b>", parse_mode="HTML")
    
    try:
        await callback.bot.send_message(student_id, "🎉 <b>Tabriklaymiz!</b> Admin tomonidan sizga 1 oylik Tekin Premium yoqildi!\n\nIlova menyusidan 👑 Premium bo'limiga kirib imtiyozlardan foydalanishingiz mumkin.", parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("reject_free_premium:"))
async def process_reject_free_premium(callback: CallbackQuery):
    student_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Rad etildi!</b>", parse_mode="HTML")
    
    try:
        await callback.bot.send_message(student_id, "❌ Afsuski, sizning tekin Premium so'rovingiz admin tomonidan rad etildi.")
    except Exception:
        pass

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
async def eval_grp_opts(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    if level.isdigit():
        group_id = int(level)
        group = await db.get_group(group_id)
        group_name = group['name'] if group else str(group_id)
    else:
        group_id = level
        group_name = level
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 SMART GROUP",  callback_data=f"save_g_lvl:{group_id}:SMART GROUP")],
        [InlineKeyboardButton(text="📚 MIDDLE CLASS", callback_data=f"save_g_lvl:{group_id}:MIDDLE CLASS")],
        [InlineKeyboardButton(text="😴 LAZY TEAM",   callback_data=f"save_g_lvl:{group_id}:LAZY TEAM")],
        [InlineKeyboardButton(text="🔙 Orqaga",       callback_data=f"admin_lvl:{group_id}")]
    ])
    
    await callback.message.edit_text(
        f"🏫 <b>{group_name}</b> guruhi uchun nom/daraja tanlang:",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("save_g_lvl:"))
async def save_grp_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    grp_level = parts[2]
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            await connection.execute("""
                UPDATE groups SET group_level = $2 WHERE id = $1
            """, group_id, grp_level)
    else:
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
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE group_id = $1 AND status = 'active'", group_id)
    else:
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active'", level)
    students = [s for s in students if s['telegram_id'] not in ADMIN_IDS and s['telegram_id'] not in TEACHER_IDS]
        
    if not students:
        await callback.answer("Bu darajada o'quvchilar yo'q.", show_alert=True)
        return
        
    kb = []
    for s in students:
        kb.append([InlineKeyboardButton(text=f"{s['first_name']} {s['last_name']}", callback_data=f"score:{s['telegram_id']}:{level}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_lvl:{level}")])
    await callback.message.edit_text("Ball qo'yish uchun o'quvchini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("astud_prof:"))
async def process_astud_prof(callback: CallbackQuery, db: Database):
    student_id = int(callback.data.split(":")[1])
    student = await db.get_user(student_id)
    if not student:
        await callback.answer("O'quvchi topilmadi.", show_alert=True)
        return
        
    from utils import get_student_profile_text, get_student_profile_keyboard
    text = await get_student_profile_text(student, db=db)
    level = student.get('group_id') or student.get('level')
    back_cb = f"admin_lvl:{level}" if level else "admin_levels_menu"
    kb = get_student_profile_keyboard(student_id, back_callback_data=back_cb)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("astud_score_info:"))
async def process_astud_score_info(callback: CallbackQuery, db: Database):
    student_id = int(callback.data.split(":")[1])
    stats = await db.get_user_stats(student_id)
    
    has_score = await db.has_score_today(student_id)
    
    scores = stats.get('current_cycle_scores', [])
    total_score = stats.get('current_cycle_total', 0)
    lesson_num = len(scores)
    
    current_level_str = "Hali dars o'tilmagan ⚪️"
    if lesson_num > 0:
        max_possible = lesson_num * 25
        percentage = (total_score / max_possible) * 100
        if percentage >= 93.33:
            current_level_str = "Excellent 🥇"
        elif percentage >= 80.0:
            current_level_str = "Very Good 🟢"
        elif percentage >= 66.66:
            current_level_str = "Good 🟡"
        elif percentage >= 53.33:
            current_level_str = "Needs Improvement 🟠"
        else:
            current_level_str = "Weak 🔴"
    
    scores_list_text = ""
    if scores:
        scores_list_text = "\n".join([f"📖 {s['lesson_number']}-dars: {s['score']} ball" for s in scores]) + "\n"
        
    history_text = ""
    history_cycles = stats.get('history', [])[:3]
    if history_cycles:
        history_text = "\n🗂 **Oldingi natijalar tarixi:**\n"
        for idx, cycle in enumerate(history_cycles, 1):
            att_info = cycle.get('attendance_count', 0)
            history_text += f"{idx}-qism: {cycle['total_score']}/150 ball - {cycle['level']}\nDavomat: 6 darsdan {att_info} marta kelgan\n\n"
        
    text = (f"📊 **O'quvchi o'zlashtirishi:**\n\n"
            f"O'tilgan darslar soni: {lesson_num}/6\n\n"
            f"{scores_list_text}\n"
            f"Joriy sikl bo'yicha to'plangan ball: {total_score}/150\n"
            f"Hozirgi holati (darajasi): {current_level_str}\n"
            f"{history_text}")
    
    kb = []
    
    kb.append([InlineKeyboardButton(text="➕ Ball qo'yish (0-25)", callback_data=f"astud_score_add:{student_id}")])
        
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"astud_prof:{student_id}")])
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(lambda c: c.data.startswith("score:") or c.data.startswith("astud_score_add:"))
async def ask_for_score(callback: CallbackQuery, state: FSMContext, db: Database):
    data = callback.data.split(":")
    student_id = int(data[1])
    
    # Check if today is a class day
    student = await db.get_user(student_id)
    if not student:
        await callback.answer("O'quvchi topilmadi.", show_alert=True)
        return
        
    group_id = student.get('group_id')
    group_name = student.get('level')
    
    if group_id:
        group = await db.get_group(group_id)
        if not group:
            await callback.answer("Guruh topilmadi.", show_alert=True)
            return
    else:
        if not group_name:
            await callback.answer("O'quvchining guruhi belgilanmagan.", show_alert=True)
            return
        async with db.pool.acquire() as connection:
            group = await connection.fetchrow("SELECT days, name FROM groups WHERE name = $1", group_name)
        if not group:
            await callback.answer("Guruh topilmadi.", show_alert=True)
            return
    
    if not group or not group['days']:
        await callback.answer("Guruh yoki uning kunlari belgilanmagan.", show_alert=True)
        return
        
    import datetime
    import pytz
    WEEKDAYS_UZ = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
    tz = pytz.timezone('Asia/Tashkent')
    today_name = WEEKDAYS_UZ[datetime.datetime.now(tz).weekday()]
    
    if today_name not in group['days'].lower():
        await callback.answer(f"❌ Xatolik: Siz o'quvchiga faqat dars kunlarida baho qo'ya olasiz.\nBu guruhning dars kunlari: {group['days']}", show_alert=True)
        return

    back_to_list = callback.data.startswith("score:")
    group_param = data[2] if back_to_list and len(data) > 2 else (student.get('group_id') or group_name)
    
    await state.update_data(score_student_id=student_id, score_group_id=group_param, back_to_list=back_to_list)
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
    group_name = data.get('score_group_id')
    back_to_list = data.get('back_to_list', False)
    
    lesson_num, total_score = await db.add_score(student_id, score)
    await state.clear()
    
    reply_kb = None
    if back_to_list and group_name:
        reply_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"score_list:{group_name}")]])
    else:
        reply_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"astud_prof:{student_id}")]])
        
    await message.answer(f"✅ Ball muvaffaqiyatli saqlandi! (Dars {lesson_num}/6)", reply_markup=reply_kb)
    
    try:
        await message.bot.send_message(
            student_id,
            f"🔔 *Siz bugungi darsda {score}/25 ball to'pladingiz. Barakalla, izlanishdan to'xtamang!* 💪",
            parse_mode="Markdown"
        )
    except Exception:
        pass
        
    if lesson_num == 6:
        level, emoji, is_eligible = await db.complete_cycle(student_id, total_score)
        
        # Avtomatik maqom berish (Support faqat qo'lda)
        auto_level = None
        if level == "Excellent":
            auto_level = "Captain"
        elif level == "Very Good":
            auto_level = "Main"
        elif level == "Good":
            auto_level = "Learner"
        elif level in ["Needs Improvement", "Weak"]:
            auto_level = "Introductory"
            
        if auto_level:
            await db.set_student_level(student_id, auto_level)
            
        # Notify Teacher
        try:
            student = await db.get_user(student_id)
            student_name = f"{student['first_name']} {student['last_name']}" if student else "O'quvchi"
            msg_text = f"🏆 **Sikl yakunlandi!**\nO'quvchi {student_name} 6 ta dars yakuniga ko'ra **{total_score}/150** ball to'pladi. Darajasi: **{level} {emoji}**."
            if auto_level:
                msg_text += f"\nAvtomatik ravishda {auto_level} maqomi berildi."
            await message.bot.send_message(message.from_user.id, msg_text)
        except Exception:
            pass

        # Notify Student
        try:
            stud_msg = f"🎉 *Tabriklaymiz!*\nSiz ushbu siklda umumiy {total_score}/150 ball to'pladingiz.\n\n🏆 Darajangiz: **{level} {emoji}**.\n\nKeyingi siklda yanada yuqori natijaga harakat qiling!"
            if auto_level:
                stud_msg += f"\nSizga {auto_level} maqomi tayinlandi!"
            await message.bot.send_message(student_id, stud_msg, parse_mode="Markdown")
        except Exception:
            pass
            
        # Tekin premium tekshiruvi (3 marta Excellent)
        if is_eligible:
            from handlers.student import ask_for_free_premium
            import asyncio
            asyncio.create_task(ask_for_free_premium(message.bot, student_id))
    else:
        try:
            await message.bot.send_message(message.from_user.id, f"✅ Ball qo'yildi! (Joriy tsikl: {lesson_num}/6)")
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
    await callback.answer(f"✅ Ingliz tili darajasi {new_lvl} ga o'zgartirildi!", show_alert=True)
    
    # Delete the level-selection message and go back to profile
    await callback.message.delete()
    
    # Now send the refreshed student profile
    from utils import get_student_profile_text, get_student_profile_keyboard
    student = await db.get_user(student_id)
    if student:
        text = await get_student_profile_text(student, db=db)
        level = student.get('level')
        back_cb = f"admin_lvl:{level}" if level else "admin_levels_menu"
        kb = get_student_profile_keyboard(student_id, back_callback_data=back_cb)
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

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

from datetime import datetime

@router.callback_query(F.data.startswith("att_appr:"))
async def approve_attendance(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    student_id = int(parts[1])
    date_str = parts[2]
    today_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    success, msg = await db.mark_attendance(student_id, today_date, is_present=True)
    if success:
        await callback.message.edit_text(callback.message.text + "\n\n✅ Tasdiqlandi.")
        await callback.bot.send_message(student_id, "✅ Sizning bugun darsga kelganingiz ustoz tomonidan tasdiqlandi.")
    else:
        await callback.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("att_rej:"))
async def reject_attendance(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    student_id = int(parts[1])
    date_str = parts[2]
    today_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    success, msg = await db.mark_attendance(student_id, today_date, is_present=False, reason="Ustoz tomonidan rad etildi")
    if success:
        await callback.message.edit_text(callback.message.text + "\n\n❌ Rad etildi.")
        await callback.bot.send_message(student_id, "❌ Ustoz tomonidan bugun kelganingiz rad qilindi va davomatga yo'q qilindingiz.")
    else:
        await callback.answer(msg, show_alert=True)

@router.callback_query(F.data.startswith("astud_att_hist:"))
async def admin_student_attendance_history(callback: CallbackQuery, db: Database):
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) < 2: return
    student_id = int(parts[1])
    
    async with db.pool.acquire() as connection:
        records = await connection.fetch("""
            SELECT date, created_at, is_present, reason 
            FROM attendance 
            WHERE user_id = $1 AND date >= current_date - interval '30 days'
            ORDER BY date DESC
        """, student_id)
        
    student = await db.get_user(student_id)
    student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip() if student else str(student_id)
        
    if not records:
        await callback.message.answer(f"📅 {student_name} uchun oxirgi 30 kun ichida davomat tarixi topilmadi.")
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
        f"👤 **O'quvchi:** {student_name}\n"
        f"📅 **Oxirgi 30 kunlik davomat tarixi:**\n\n"
        f"📊 Umumiy darslar: {total_days}\n"
        f"✅ Kelgan / ❌ Kelmagan: {present_count}/{absent_count}\n\n"
        f"**Tarix (Sana va vaqt):**\n" + "\n".join(history_lines)
    )
    
    await callback.message.answer(text, parse_mode="Markdown")

