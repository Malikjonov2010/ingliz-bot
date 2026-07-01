from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import Database
from config import ADMIN_IDS, TEACHER_IDS
import re

router = Router()

# ── States ──────────────────────────────────────────────────────────────────
class AdminGroupCreation(StatesGroup):
    waiting_for_name  = State()
    waiting_for_type  = State()
    waiting_for_days  = State()
    waiting_for_time  = State()

class AdminGroupEdit(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_days = State()
    waiting_for_time = State()

# ── Helpers ─────────────────────────────────────────────────────────────────
GROUP_LEVELS = [
    "Beginner",
    "Elementary",
    "Pre-Intermediate",
    "Intermediate",
    "Upper-Intermediate",
    "Advanced",
    "CEFR",
    "IELTS",
]

DAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

GROUP_LEVEL_LABELS = {
    "SMART GROUP":  "🧠 SMART GROUP",
    "MIDDLE CLASS": "📚 MIDDLE CLASS",
    "LAZY TEAM":    "😴 LAZY TEAM",
}

def _days_keyboard(selected: list, group_id=None):
    """Inline keyboard for day selection with checkboxes."""
    rows = []
    for day in DAYS_UZ:
        mark = "✅ " if day in selected else ""
        rows.append([InlineKeyboardButton(
            text=f"{mark}{day}",
            callback_data=f"toggle_day:{day}"
        )])
    rows.append([InlineKeyboardButton(text="➡️ Davom etish", callback_data="days_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _group_type_keyboard():
    rows = [
        [InlineKeyboardButton(text="🧠 SMART GROUP", callback_data="pick_grp_type:SMART GROUP")],
        [InlineKeyboardButton(text="📚 MIDDLE CLASS", callback_data="pick_grp_type:MIDDLE CLASS")],
        [InlineKeyboardButton(text="😴 LAZY TEAM", callback_data="pick_grp_type:LAZY TEAM")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _level_keyboard():
    rows = [[InlineKeyboardButton(text=lvl, callback_data=f"pick_grp_lvl:{lvl}")] for lvl in GROUP_LEVELS]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Entry points ─────────────────────────────────────────────────────────────
@router.message(F.text == "🏫 Guruhlarni boshqarish", StateFilter(None))
async def manage_groups_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Guruhlarni ko'rish",  callback_data="admin_view_groups")],
        [InlineKeyboardButton(text="➕ Guruh qo'shish",      callback_data="admin_add_group")],
    ])
    await message.answer("🏫 <b>Guruhlarni boshqarish:</b>", reply_markup=kb, parse_mode="HTML")


# ── View groups ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_view_groups")
async def admin_view_groups(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    if not groups:
        await callback.message.edit_text(
            "Hozircha guruhlar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="admin_add_group")
            ]])
        )
        return

    from utils import sort_groups, shorten_days
    groups = sort_groups(groups)

    text = f"📊 <b>Jami guruhlar soni:</b> {len(groups)}\n\n"
    for g in groups:
        lvl_raw = g['group_level'] or "Belgilanmagan"
        lvl     = GROUP_LEVEL_LABELS.get(lvl_raw, lvl_raw)
        short_d = shorten_days(g['days'])
        text   += (f"🏫 <b>{g['name']}</b>\n"
                   f"🗓 Kunlari: {short_d} | ⏰ Vaqti: {g['time']}\n"
                   f"📈 Darajasi: {lvl}\n\n")

    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(
            text=f"📈 {g['name']} darajasini o'zgartirish",
            callback_data=f"eval_grp:{g['name']}"
        )])
    kb.append([InlineKeyboardButton(text="✏️ Guruhni tahrirlash",  callback_data="edit_group_menu")])
    kb.append([InlineKeyboardButton(text="🗑 Guruhni o'chirish",   callback_data="delete_group_menu")])
    kb.append([InlineKeyboardButton(text="➕ Guruh qo'shish",      callback_data="admin_add_group")])

    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))



# ── Edit existing group ───────────────────────────────────────────────────────
@router.callback_query(F.data == "edit_group_menu")
async def edit_group_menu(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    from utils import sort_groups
    groups = sort_groups(groups)
    kb = [[InlineKeyboardButton(text=f"✏️ {g['name']}", callback_data=f"edit_grp:{g['id']}")] for g in groups]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_view_groups")])
    await callback.message.edit_text("Tahrirlash uchun guruhni tanlang:",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("edit_grp:"))
async def edit_grp_menu_start(callback: CallbackQuery, state: FSMContext, db: Database):
    try:
        await callback.answer()
    except:
        pass
    group_id = int(callback.data.split(":")[1])
    group    = await db.get_group(group_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📛 Nomini (darajasini) tahrirlash", callback_data=f"edit_grp_name:{group_id}")],
        [InlineKeyboardButton(text="📈 Maqomini tahrirlash", callback_data=f"edit_grp_type:{group_id}")],
        [InlineKeyboardButton(text="🗓 Kunlarini tahrirlash", callback_data=f"edit_grp_days:{group_id}")],
        [InlineKeyboardButton(text="⏰ Vaqtini tahrirlash", callback_data=f"edit_grp_time:{group_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="edit_group_menu")]
    ])
    lvl = GROUP_LEVEL_LABELS.get(group['group_level'], group['group_level'] or "Belgilanmagan")
    text = (f"✏️ <b>{group['name']}</b> guruhini tahrirlash:\n\n"
            f"📈 Maqomi: {lvl}\n"
            f"🗓 Kunlari: {group['days']}\n"
            f"⏰ Vaqti: {group['time']}\n\n"
            f"Nimani o'zgartirmoqchisiz?")
    
    # Try to edit the message. If we come from a message (like edit_group_time_entry), we can't always edit.
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("edit_grp_name:"))
async def edit_grp_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    await state.update_data(edit_group_id=group_id)
    await callback.message.edit_text(
        "📛 <b>Guruhning yangi nomini (darajasini) tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_level_keyboard()
    )
    await state.set_state(AdminGroupEdit.waiting_for_name)

@router.callback_query(AdminGroupEdit.waiting_for_name, F.data.startswith("pick_grp_lvl:"))
async def edit_pick_grp_lvl(callback: CallbackQuery, state: FSMContext, db: Database):
    lvl = callback.data.split(":")[1]
    data = await state.get_data()
    edit_id = data["edit_group_id"]
    group = await db.get_group(edit_id)
    old_name = group["name"]
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET level = $1 WHERE level = $2", lvl, old_name)
    await db.update_group(edit_id, lvl, group['days'], group['time'], group['group_level'])
    await callback.answer(f"✅ Guruh nomi {lvl} etib o'zgartirildi!", show_alert=True)
    await state.clear()
    callback.data = f"edit_grp:{edit_id}"
    await edit_grp_menu_start(callback, state, db)

@router.callback_query(F.data.startswith("edit_grp_type:"))
async def edit_grp_type_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    await state.update_data(edit_group_id=group_id)
    await callback.message.edit_text(
        "📈 <b>Guruh maqomini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_group_type_keyboard()
    )
    await state.set_state(AdminGroupEdit.waiting_for_type)

@router.callback_query(AdminGroupEdit.waiting_for_type, F.data.startswith("pick_grp_type:"))
async def edit_pick_grp_type(callback: CallbackQuery, state: FSMContext, db: Database):
    grp_type = callback.data.split(":")[1]
    data = await state.get_data()
    edit_id = data["edit_group_id"]
    group = await db.get_group(edit_id)
    await db.update_group(edit_id, group['name'], group['days'], group['time'], grp_type)
    await callback.answer(f"✅ Guruh maqomi o'zgartirildi!", show_alert=True)
    await state.clear()
    callback.data = f"edit_grp:{edit_id}"
    await edit_grp_menu_start(callback, state, db)

@router.callback_query(F.data.startswith("edit_grp_days:"))
async def edit_grp_days(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    await state.update_data(edit_group_id=group_id, selected_days=[])
    await callback.message.edit_text(
        "📅 <b>Yangi dars kunlarini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_days_keyboard([])
    )
    await state.set_state(AdminGroupEdit.waiting_for_days)

@router.callback_query(AdminGroupEdit.waiting_for_days, F.data.startswith("toggle_day:"))
async def edit_toggle_day(callback: CallbackQuery, state: FSMContext):
    day  = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("selected_days", [])
    if day in selected: selected.remove(day)
    else: selected.append(day)
    await state.update_data(selected_days=selected)
    await callback.message.edit_reply_markup(reply_markup=_days_keyboard(selected))

@router.callback_query(AdminGroupEdit.waiting_for_days, F.data == "days_done")
async def edit_days_done(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    selected = data.get("selected_days", [])
    if not selected:
        await callback.answer("Kamida bitta kun tanlang!", show_alert=True)
        return
    days_str = " ".join(selected).lower()
    edit_id = data["edit_group_id"]
    group = await db.get_group(edit_id)
    await db.update_group(edit_id, group['name'], days_str, group['time'], group['group_level'])
    await callback.answer(f"✅ Kunlar o'zgartirildi!", show_alert=True)
    await state.clear()
    callback.data = f"edit_grp:{edit_id}"
    await edit_grp_menu_start(callback, state, db)

@router.callback_query(F.data.startswith("edit_grp_time:"))
async def edit_grp_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    await state.update_data(edit_group_id=group_id)
    await callback.message.edit_text(
        "⏰ <b>Yangi dars vaqtini kiriting</b> (masalan: <code>14:00</code>):\n\n"
        "Format: SS:MM — 24 soatlik ko'rinishda.\n",
        parse_mode="HTML"
    )
    await state.set_state(AdminGroupEdit.waiting_for_time)

@router.message(AdminGroupEdit.waiting_for_time)
async def edit_group_time_entry(message: Message, state: FSMContext, db: Database):
    time_text = message.text.strip()
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", time_text):
        await message.answer("❌ Noto'g'ri format! Vaqtni SS:MM ko'rinishida kiriting. (masalan: 09:00 yoki 8:30)")
        return
    hours, minutes = map(int, time_text.split(":"))
    if hours < 8 or hours > 18 or (hours == 18 and minutes > 0):
        await message.answer("⚠️ Vaqt 08:00 dan 18:00 gacha bo'lishi kerak. Iltimos qaytadan kiriting:")
        return
    
    time_text = f"{hours:02d}:{minutes:02d}"
    data = await state.get_data()
    edit_id = data["edit_group_id"]
    group = await db.get_group(edit_id)
    await db.update_group(edit_id, group['name'], group['days'], time_text, group['group_level'])
    
    await message.answer(f"✅ Vaqt {time_text} etib o'zgartirildi!")
    await state.clear()
    
    # Mock a callback to reload the menu
    class FakeMessage:
        async def answer(self, *args, **kwargs):
            return await message.answer(*args, **kwargs)
        async def edit_text(self, *args, **kwargs):
            return await message.answer(*args, **kwargs)
    class FakeCallback:
        data = f"edit_grp:{edit_id}"
        message = FakeMessage()
        async def answer(self, *args, **kwargs):
            pass
    await edit_grp_menu_start(FakeCallback(), state, db)


# ── Add new group ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_add_group")
async def start_add_group(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_group_id=None, selected_days=[])
    await callback.message.edit_text(
        "🏫 <b>Yangi guruh nomini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_level_keyboard()
    )
    await state.set_state(AdminGroupCreation.waiting_for_name)


# ── Step 1: level picked → go to days ────────────────────────────────────────
@router.callback_query(AdminGroupCreation.waiting_for_name, F.data.startswith("pick_grp_lvl:"))
async def pick_grp_lvl(callback: CallbackQuery, state: FSMContext):
    lvl = callback.data.split(":")[1]
    await state.update_data(group_name=lvl)
    await callback.message.edit_text(
        "📈 <b>Guruh darajasini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_group_type_keyboard()
    )
    await state.set_state(AdminGroupCreation.waiting_for_type)


@router.callback_query(AdminGroupCreation.waiting_for_type, F.data.startswith("pick_grp_type:"))
async def pick_grp_type(callback: CallbackQuery, state: FSMContext):
    grp_type = callback.data.split(":")[1]
    await state.update_data(group_level=grp_type, selected_days=[])
    await callback.message.edit_text(
        "📅 <b>Dars kunlarini tanlang</b> (bir nechta tanlanadi):",
        parse_mode="HTML",
        reply_markup=_days_keyboard([])
    )
    await state.set_state(AdminGroupCreation.waiting_for_days)


# ── Step 2: toggling days ─────────────────────────────────────────────────────
@router.callback_query(AdminGroupCreation.waiting_for_days, F.data.startswith("toggle_day:"))
async def toggle_day(callback: CallbackQuery, state: FSMContext):
    day  = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("selected_days", [])

    if day in selected:
        selected.remove(day)
    else:
        selected.append(day)

    await state.update_data(selected_days=selected)
    await callback.message.edit_reply_markup(reply_markup=_days_keyboard(selected))
    await callback.answer()


@router.callback_query(AdminGroupCreation.waiting_for_days, F.data == "days_done")
async def days_done(callback: CallbackQuery, state: FSMContext):
    data     = await state.get_data()
    selected = data.get("selected_days", [])
    if not selected:
        await callback.answer("Kamida bitta kun tanlang!", show_alert=True)
        return

    days_str = " ".join(selected).lower()
    await state.update_data(group_days=days_str)
    await callback.message.edit_text(
        "⏰ <b>Dars vaqtini kiriting</b> (masalan: <code>14:00</code>):\n\n"
        "Format: SS:MM — 24 soatlik ko'rinishda.\n"
        "<i>(Vaqt 08:00 dan 18:00 gacha bo'lishi kerak)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminGroupCreation.waiting_for_time)


# ── Step 3: time entry with validation ───────────────────────────────────────
@router.message(AdminGroupCreation.waiting_for_time)
async def add_group_time(message: Message, state: FSMContext, db: Database):
    time_text = message.text.strip()

    # Validate HH:MM format, 24-hour
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", time_text):
        await message.answer(
            "❌ <b>Noto'g'ri format!</b>\n\n"
            "Vaqtni <b>SS:MM</b> ko'rinishida kiriting.\n"
            "Misol: <code>09:00</code> yoki <code>8:30</code>\n\n"
            "⚠️ 24 soatlik tizimda, soat va daqiqa orasi ikki nuqta bo'lishi shart.",
            parse_mode="HTML"
        )
        return

    # Validate time range (08:00 - 18:00)
    hours, minutes = map(int, time_text.split(":"))
    if hours < 8 or hours > 18 or (hours == 18 and minutes > 0):
        await message.answer(
            "⚠️ <b>Ruxsat etilmagan vaqt!</b>\n\n"
            "Dars vaqti faqat <b>08:00</b> dan <b>18:00</b> gacha oraliqda bo'lishi kerak.\n"
            "Iltimos, qaytadan kiriting:",
            parse_mode="HTML"
        )
        return

    time_text = f"{hours:02d}:{minutes:02d}"
    data    = await state.get_data()
    name    = data["group_name"]
    grp_lvl = data.get("group_level")
    days    = data["group_days"]
    edit_id = data.get("edit_group_id")

    try:
        # Creation flow does not have edit_id anymore since edit is handled separately.
        # Keeping if edit_id just in case, but it's basically create flow.
        if edit_id:
            pass # We removed edit from here
        else:
            await db.create_group(name, days, time_text, message.from_user.id, grp_lvl)
            await message.answer(
                f"✅ <b>Yangi guruh qo'shildi!</b>\n\n"
                f"📛 Nomi: {name}\n📈 Darajasi: {grp_lvl}\n🗓 Kunlari: {days}\n⏰ Vaqti: {time_text}",
                parse_mode="HTML"
            )
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

    await state.clear()


# ── Group eval level labels with emoji ───────────────────────────────────────
# (used from admin.py eval_grp_opts — override here to keep labels consistent)


# ── Students list ─────────────────────────────────────────────────────────────
@router.message(F.text == "👤 O'quvchilarni ko'rish", StateFilter(None))
async def view_students_menu(message: Message, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        return

    students = await db.get_active_users()
    students = [s for s in students if s['telegram_id'] not in ADMIN_IDS and s['telegram_id'] not in TEACHER_IDS]
    if not students:
        await message.answer("Hozircha ro'yxatdan o'tgan o'quvchilar yo'q.")
        return

    kb = []
    for s in students[:90]:
        kb.append([InlineKeyboardButton(
            text=f"👤 {s['first_name']} {s['last_name']}",
            callback_data=f"astud:{s['telegram_id']}"
        )])

    await message.answer(
        f"👤 <b>Barcha o'quvchilar ro'yxati ({len(students)} ta):</b>\nBatafsil ma'lumot va boshqarish uchun o'quvchini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "astud_list")
async def back_to_astud_list(callback: CallbackQuery, db: Database):
    students = await db.get_active_users()
    students = [s for s in students if s['telegram_id'] not in ADMIN_IDS and s['telegram_id'] not in TEACHER_IDS]
    kb = []
    for s in students[:90]:
        kb.append([InlineKeyboardButton(
            text=f"👤 {s['first_name']} {s['last_name']}",
            callback_data=f"astud:{s['telegram_id']}"
        )])
    await callback.message.edit_text(
        f"👤 <b>Barcha o'quvchilar ro'yxati ({len(students)} ta):</b>\nBatafsil ma'lumot va boshqarish uchun o'quvchini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("astud:"))
async def view_astud_details(callback: CallbackQuery, db: Database):
    stud_id = int(callback.data.split(":")[1])
    student = await db.get_user(stud_id)
    if not student:
        await callback.answer("O'quvchi topilmadi.", show_alert=True)
        return

    from utils import get_student_profile_text_and_keyboard
    text, kb = await get_student_profile_text_and_keyboard(db, stud_id)
    if not text:
        await callback.answer("O'quvchi topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("astud_set_lvl:"))
async def astud_set_lvl(callback: CallbackQuery):
    stud_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="SUPPORT",       callback_data=f"astud_save_lvl:{stud_id}:SUPPORT")],
        [InlineKeyboardButton(text="CAPTAIN",       callback_data=f"astud_save_lvl:{stud_id}:CAPTAIN")],
        [InlineKeyboardButton(text="MAIN",          callback_data=f"astud_save_lvl:{stud_id}:MAIN")],
        [InlineKeyboardButton(text="LEARNER",       callback_data=f"astud_save_lvl:{stud_id}:LEARNER")],
        [InlineKeyboardButton(text="INTRODUCTORY",  callback_data=f"astud_save_lvl:{stud_id}:INTRODUCTORY")],
        [InlineKeyboardButton(text="🔙 Orqaga",     callback_data=f"astud:{stud_id}")],
    ])
    await callback.message.edit_text("O'quvchi uchun darajani (maqomini) tanlang:", reply_markup=kb)


@router.callback_query(F.data.startswith("astud_save_lvl:"))
async def astud_save_lvl(callback: CallbackQuery, db: Database):
    parts      = callback.data.split(":")
    stud_id    = int(parts[1])
    stud_level = parts[2]

    await db.set_student_level(stud_id, stud_level)
    await callback.answer(f"✅ O'quvchi darajasi {stud_level} etib belgilandi!", show_alert=True)

    from utils import get_student_profile_text_and_keyboard
    text, kb = await get_student_profile_text_and_keyboard(db, stud_id)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


# ── Personal message ──────────────────────────────────────────────────────────
from states.register_states import AdminPersonalMessage

@router.callback_query(F.data.startswith("astud_msg:"))
async def astud_msg(callback: CallbackQuery, state: FSMContext):
    stud_id = int(callback.data.split(":")[1])
    await state.update_data(student_id=stud_id)

    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)
    await callback.message.delete()
    await callback.message.answer(
        "📩 <b>O'quvchiga yuboriladigan xabarni kiriting:</b>\n(Bekor qilish uchun '⬅️ Orqaga' ni bosing)",
        parse_mode="HTML", reply_markup=keyboard
    )
    await state.set_state(AdminPersonalMessage.waiting_for_message)


@router.message(AdminPersonalMessage.waiting_for_message)
async def process_admin_personal_message(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return

    data    = await state.get_data()
    stud_id = data.get("student_id")

    try:
        await message.bot.send_message(
            chat_id=stud_id,
            text=f"👨‍🏫 <b>Ustozdan shaxsiy xabar:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("✅ Xabar o'quvchiga muvaffaqiyatli yuborildi!",
                             reply_markup=get_user_keyboard(message.from_user.id))
    except Exception as e:
        await message.answer(f"❌ Xabar yuborishda xatolik: {e}")


# ── Set bio ───────────────────────────────────────────────────────────────────
from states.register_states import AdminSetBio

@router.callback_query(F.data.startswith("astud_bio:"))
async def astud_bio(callback: CallbackQuery, state: FSMContext):
    stud_id = int(callback.data.split(":")[1])
    await state.update_data(student_id=stud_id)

    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)
    await callback.message.delete()
    await callback.message.answer(
        "📝 <b>O'quvchi uchun qisqacha ustoz fikrini (bio) kiriting (max 250 harf):</b>\n\n"
        "<i>(Ushbu fikr o'quvchi botga har safar kirganida ko'rinib turadi. Bekor qilish uchun '⬅️ Orqaga' ni bosing)</i>",
        parse_mode="HTML", reply_markup=keyboard
    )
    await state.set_state(AdminSetBio.waiting_for_bio)


@router.message(AdminSetBio.waiting_for_bio)
async def process_admin_set_bio(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("Amal bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return

    bio_text = message.text[:250]
    data     = await state.get_data()
    stud_id  = data.get("student_id")

    await db.set_teacher_bio(stud_id, bio_text)

    try:
        await message.bot.send_message(
            chat_id=stud_id,
            text=f"💡 <b>Ustozingiz profilingizni yangiladi va sizga maslahat qoldirdi!</b>\n\n"
                 f"\"{bio_text}\"\n\n<i>(Buni har doim botga kirganda ko'rasiz)</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await state.clear()
    from handlers.student import get_user_keyboard
    await message.answer("✅ Ustoz fikri saqlandi va o'quvchiga yuborildi!",
                         reply_markup=get_user_keyboard(message.from_user.id))


# ── Delete group ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "delete_group_menu")
async def delete_group_menu(callback: CallbackQuery, db: Database):
    groups = await db.get_all_groups()
    if not groups:
        await callback.answer("Guruhlar yo'q.", show_alert=True)
        return
    from utils import sort_groups
    groups = sort_groups(groups)
    kb = [[InlineKeyboardButton(
               text=f"🗑 {g['name']}",
               callback_data=f"del_grp_confirm:{g['id']}"
           )] for g in groups]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_view_groups")])
    await callback.message.edit_text(
        "🗑 <b>Qaysi guruhni o'chirmoqchisiz?</b>\n"
        "<i>O'chirilgan guruh o'quvchilar ro'yxatidan ham chiqariladi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@router.callback_query(F.data.startswith("del_grp_confirm:"))
async def del_grp_confirm(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split(":")[1])
    group    = await db.get_group(group_id)
    if not group:
        await callback.answer("Guruh topilmadi.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish",  callback_data=f"del_grp_do:{group_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="delete_group_menu")],
    ])
    await callback.message.edit_text(
        f"⚠️ <b>{group['name']}</b> guruhini o'chirishni tasdiqlaysizmi?\n\n"
        "Bu guruhga biriktirilgan barcha o'quvchilar guruhsiz qoladi (o'chirilmaydi).",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("del_grp_do:"))
async def del_grp_do(callback: CallbackQuery, db: Database):
    group_id = int(callback.data.split(":")[1])
    group    = await db.get_group(group_id)
    name     = group['name'] if group else str(group_id)
    await db.delete_group(group_id)
    await callback.answer(f"✅ '{name}' guruhi o'chirildi!", show_alert=True)
    # Guruhlar ro'yxatiga qaytamiz
    await admin_view_groups(callback, db)
