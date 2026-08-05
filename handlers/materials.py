# handlers/materials.py
# ============================================================
# KITOB MASHQLAR VA JAVOBLAR — Menu Builder uslubida
# ============================================================
#
# ADMIN FLOW:
#   📚 tugma bosadi → Bo'limlar chiqadi (ReplyKeyboard, pastda)
#   Bo'limni bosadi → Inline menyu: [📂 Kirish] [📝 Tarkib qo'sh] [✏️ O'zgartir] [🗑 O'chir]
#   "Tarkib qo'sh" bosadi → Fayl/matn yuboradi (bot saqlab qo'yadi)
#   Keyinchalik o'quvchi o'sha tugmani bosdi → saqlangan narsalar chiqadi
#
# FOYDALANUVCHI FLOW:
#   📚 tugma bosadi → Bo'limlar chiqadi
#   Bo'limni bosadi → Saqlangan tarkib + ichki bo'limlar chiqadi
# ============================================================

import logging
import html as html_lib

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import Database
from config import ADMIN_IDS

router = Router()
logger = logging.getLogger(__name__)


# ── FSM holatlari ──────────────────────────────────────────
class MatNav(StatesGroup):
    browsing      = State()   # Foydalanuvchi/admin daraxtta
    adding_button = State()   # Admin yangi tugma nomi kiritmoqda
    editing_name  = State()   # Admin tugma nomini o'zgartirmoqda
    adding_post   = State()   # Admin fayl/matn yuklayapti


# ═══════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════

async def build_nav_kb(db: Database, node_id: int, user_id: int) -> ReplyKeyboardMarkup:
    """
    Pastki ReplyKeyboard:
      • Farzand tugmalar (2 tadan qatorda)
      • Navigatsiya: Orqaga / Bosh sahifa
      • Admin uchun: ➕ Yangi tugma qo'shish
    """
    parent_id = None if node_id == 0 else node_id
    children  = await db.get_material_nodes_by_parent(parent_id)

    rows: list = []
    row:  list = []
    for ch in children:
        btn = KeyboardButton(text=f"📂 {ch['title']}")
        if len(ch['title']) > 22:          # uzun nom → alohida qatorda
            if row:
                rows.append(row); row = []
            rows.append([btn])
        else:
            row.append(btn)
            if len(row) == 2:
                rows.append(row); row = []
    if row:
        rows.append(row)

    # Navigatsiya
    if node_id == 0:
        rows.append([KeyboardButton(text="❌ Yopish")])
    else:
        rows.append([
            KeyboardButton(text="🔙 Orqaga"),
            KeyboardButton(text="🏠 Bosh sahifa"),
        ])

    # Admin: yangi tugma qo'shish tugmasi
    if user_id in ADMIN_IDS:
        rows.append([KeyboardButton(text="➕ Yangi tugma qo'shish")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def send_material_item(bot, chat_id: int, post: dict):
    """Bitta materialni xavfsiz yuboradi (xato bo'lsa plain-text fallback)."""
    ptype   = post.get("post_type")
    fid     = post.get("file_id")
    caption = post.get("caption") or ""

    try:
        if ptype == "document":
            try:    await bot.send_document(chat_id, fid, caption=caption, parse_mode="HTML")
            except: await bot.send_document(chat_id, fid, caption=caption)
        elif ptype == "photo":
            try:    await bot.send_photo(chat_id, fid, caption=caption, parse_mode="HTML")
            except: await bot.send_photo(chat_id, fid, caption=caption)
        elif ptype == "video":
            try:    await bot.send_video(chat_id, fid, caption=caption, parse_mode="HTML")
            except: await bot.send_video(chat_id, fid, caption=caption)
        elif ptype == "audio":
            try:    await bot.send_audio(chat_id, fid, caption=caption, parse_mode="HTML")
            except: await bot.send_audio(chat_id, fid, caption=caption)
        elif ptype == "voice":
            await bot.send_voice(chat_id, fid, caption=caption)
        elif ptype == "video_note":
            await bot.send_video_note(chat_id, fid)
        elif ptype == "animation":
            try:    await bot.send_animation(chat_id, fid, caption=caption, parse_mode="HTML")
            except: await bot.send_animation(chat_id, fid, caption=caption)
        elif ptype == "sticker":
            await bot.send_sticker(chat_id, fid)
        elif ptype == "text":
            try:    await bot.send_message(chat_id, caption, parse_mode="HTML",
                                           disable_web_page_preview=False)
            except: await bot.send_message(chat_id, caption,
                                           disable_web_page_preview=False)
    except Exception as e:
        logger.error(f"Material yuborishda xatolik (chat={chat_id}): {e}")


async def show_node(message: Message, db: Database, state: FSMContext,
                    node_id: int, user_id: int, send_posts: bool = False):
    """
    Joriy tugunni ko'rsatadi.
    send_posts=True  → tugma bosilganda (oldinga kirish) → postlar yuboriladi
    send_posts=False → orqaga/root qaytishda → postlar yuborilmaydi
    """
    # Postlarni faqat oldinga kirganda yuborish
    if send_posts and node_id != 0:
        posts = await db.get_material_posts(node_id)
        for post in posts:
            await send_material_item(message.bot, user_id, post)

    # Yo'l matni
    if node_id == 0:
        path = "📚 <b>Kitoblar, mashqlar va javoblar</b>"
    else:
        crumbs = await db.get_material_node_breadcrumbs(node_id)
        path   = " ➔ ".join(f"<b>{html_lib.escape(b['title'])}</b>" for b in crumbs)

    children = await db.get_material_nodes_by_parent(None if node_id == 0 else node_id)

    if children:
        hint = "Kerakli bo'limni tanlang 👇"
    elif node_id != 0:
        posts_exist = await db.get_material_posts(node_id)
        hint = "📥 Materiallar yuborildi." if (send_posts and posts_exist) else \
               ("📌 Bu bo'limda materiallar bor. Kirish uchun bosing." if posts_exist else \
                "⚠️ Bu bo'limda hali materiallar yo'q.")
    else:
        hint = "Hali bo'limlar yo'q. ➕ Yangi tugma qo'shish orqali boshlang."

    # Admin uchun qisqa yo'riqnoma
    if user_id in ADMIN_IDS and children:
        hint += "\n\n<i>ℹ️ Tugmani bosing → tahrirlash menyusi chiqadi</i>"

    kb = await build_nav_kb(db, node_id, user_id)
    await state.set_state(MatNav.browsing)
    await state.update_data(current_node_id=node_id)
    await message.answer(f"{path}\n━━━━━━━━━━━━━━━━━━━━━━\n\n{hint}",
                         parse_mode="HTML", reply_markup=kb)


# ═══════════════════════════════════════════════════════════
# 1. KIRISH — asosiy tugma
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "📚 Kitob mashqlar va javoblar", StateFilter(None))
async def open_materials_root(message: Message, db: Database, state: FSMContext):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS and not await db.is_premium(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Premium olish", callback_data="premium_buy")]
        ])
        await message.answer(
            "🔒 <b>Bu bo'lim faqat Premium foydalanuvchilar uchun!</b>\n\n"
            "📚 Bu yerda:\n"
            "  • 📖 Barcha kitoblar (Student's Book, Workbook)\n"
            "  • 📝 Mashqlar va javoblar\n"
            "  • 🎧 Listening audiolari\n"
            "  • 📑 PDF materiallar\n\n"
            "Qulfni ochish uchun <b>💎 Premium</b> obunasini faollashtiring!",
            parse_mode="HTML", reply_markup=kb
        )
        return

    await show_node(message, db, state, node_id=0, user_id=user_id, send_posts=False)


# ═══════════════════════════════════════════════════════════
# 2. NAVIGATSIYA HANDLERLAR (MatNav.browsing holatida)
# ═══════════════════════════════════════════════════════════

@router.message(MatNav.browsing, F.text == "❌ Yopish")
async def mat_close(message: Message, state: FSMContext, db: Database):
    await state.clear()
    from handlers.student import get_async_user_keyboard
    kb = await get_async_user_keyboard(message.from_user.id, db)
    await message.answer("✅ Bo'limdan chiqildi.", reply_markup=kb)


@router.message(MatNav.browsing, F.text == "🏠 Bosh sahifa")
async def mat_go_root(message: Message, state: FSMContext, db: Database):
    await show_node(message, db, state, node_id=0, user_id=message.from_user.id, send_posts=False)


@router.message(MatNav.browsing, F.text == "🔙 Orqaga")
async def mat_go_back(message: Message, state: FSMContext, db: Database):
    data   = await state.get_data()
    cur_id = data.get("current_node_id", 0)
    if cur_id == 0:
        await mat_close(message, state, db)
        return
    node      = await db.get_material_node(cur_id)
    parent_id = node['parent_id'] if (node and node.get('parent_id')) else 0
    await show_node(message, db, state, node_id=parent_id, user_id=message.from_user.id, send_posts=False)


# ── Admin: yangi tugma qo'shish ────────────────────────────
@router.message(MatNav.browsing, F.text == "➕ Yangi tugma qo'shish")
async def mat_new_btn_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data   = await state.get_data()
    cur_id = data.get("current_node_id", 0)
    await state.update_data(current_node_id=cur_id)
    await state.set_state(MatNav.adding_button)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]],
                              resize_keyboard=True)
    await message.answer(
        "➕ <b>Yangi tugma nomini yozing:</b>\n\n"
        "<i>Masalan: Starter, Elementary, Grammar, Unit 1, Workbook PDF va h.k.</i>",
        parse_mode="HTML", reply_markup=kb
    )


@router.message(MatNav.adding_button)
async def mat_new_btn_process(message: Message, state: FSMContext, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear(); return

    data   = await state.get_data()
    cur_id = data.get("current_node_id", 0)

    if message.text == "⬅️ Bekor qilish":
        await state.set_state(MatNav.browsing)
        kb = await build_nav_kb(db, cur_id, message.from_user.id)
        await message.answer("❌ Bekor qilindi.", reply_markup=kb)
        return

    title = (message.text or "").strip()
    if not title:
        await message.answer("⚠️ Nom bo'sh bo'lmaydi. Qayta yozing.")
        return

    db_parent = None if cur_id == 0 else cur_id
    await db.create_material_node(db_parent, title)
    await state.set_state(MatNav.browsing)
    kb = await build_nav_kb(db, cur_id, message.from_user.id)
    await message.answer(
        f"✅ <b>«{html_lib.escape(title)}»</b> tugmasi yaratildi!\n\n"
        f"<i>Endi uni bosib tahrirlash menyusini oching.</i>",
        parse_mode="HTML", reply_markup=kb
    )


# ── Farzand tugma bosildi (MatNav.browsing holatida) ──────
@router.message(MatNav.browsing)
async def mat_child_pressed(message: Message, state: FSMContext, db: Database):
    user_id = message.from_user.id
    text    = (message.text or "").strip()

    # Faqat "📂 Nom" shaklida keladi
    if not text.startswith("📂 "):
        await message.answer("⚠️ Iltimos, pastdagi tugmalardan foydalaning.")
        return

    clean = text[2:].strip()          # "📂 " ni olib tashlaymiz

    data          = await state.get_data()
    cur_id        = data.get("current_node_id", 0)
    parent_filter = None if cur_id == 0 else cur_id
    children      = await db.get_material_nodes_by_parent(parent_filter)

    found = next((ch for ch in children if ch['title'].strip() == clean), None)
    if not found:
        await message.answer("⚠️ Iltimos, pastdagi tugmalardan foydalaning.")
        return

    node_id = found['id']

    # ── ADMIN: inline tahrirlash menyusi chiqaradi ──
    if user_id in ADMIN_IDS:
        posts_count    = len(await db.get_material_posts(node_id))
        children_count = len(await db.get_material_nodes_by_parent(node_id))

        info = ""
        if posts_count:    info += f"📎 {posts_count} ta material biriktirilgan\n"
        if children_count: info += f"📁 {children_count} ta ichki bo'lim bor\n"
        if not info:       info  = "📭 Hali bo'sh (material va ichki bo'lim yo'q)\n"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📂 Ichiga kirish",
                                     callback_data=f"mat_enter:{node_id}:{cur_id}"),
            ],
            [
                InlineKeyboardButton(text="📝 Tarkib qo'shish",
                                     callback_data=f"mat_addpost:{node_id}:{cur_id}"),
                InlineKeyboardButton(text="👁 Ko'rish",
                                     callback_data=f"mat_preview:{node_id}:{cur_id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ Nomini o'zgartirish",
                                     callback_data=f"mat_rename:{node_id}:{cur_id}"),
                InlineKeyboardButton(text="🗑 O'chirish",
                                     callback_data=f"mat_delete:{node_id}:{cur_id}"),
            ],
        ])
        await message.answer(
            f"🗂 <b>«{html_lib.escape(found['title'])}»</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{info}\n"
            f"Nima qilmoqchisiz?",
            parse_mode="HTML", reply_markup=kb
        )
        return

    # ── FOYDALANUVCHI: to'g'ridan-to'g'ri ochadi ──
    await show_node(message, db, state, node_id=node_id, user_id=user_id, send_posts=True)


# ═══════════════════════════════════════════════════════════
# 3. ADMIN INLINE AMALLAR (callback_query)
# ═══════════════════════════════════════════════════════════

# 3-a. Ichiga kirish
@router.callback_query(F.data.startswith("mat_enter:"))
async def cb_enter_node(callback: CallbackQuery, db: Database, state: FSMContext):
    await callback.answer()
    parts   = callback.data.split(":")
    node_id = int(parts[1])
    await callback.message.delete()
    await show_node(callback.message, db, state,
                    node_id=node_id, user_id=callback.from_user.id, send_posts=True)


# 3-b. Tarkib qo'shish (post)
@router.callback_query(F.data.startswith("mat_addpost:"))
async def cb_addpost_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True); return

    await callback.answer()
    parts   = callback.data.split(":")
    node_id = int(parts[1])
    par_id  = int(parts[2])          # Parent node (orqaga qaytish uchun)

    node    = await db.get_material_node(node_id)
    title   = node['title'] if node else str(node_id)

    await state.update_data(current_node_id=par_id,
                             editing_node_id=node_id,
                             post_count=0)
    await state.set_state(MatNav.adding_post)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Saqlash va tugatish")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        f"📥 <b>«{html_lib.escape(title)}»</b> tugmasiga material qo'shish\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Quyidagilarni yuboring (bir nechta bo'lsa ketma-ket):\n"
        f"  📄 PDF / Hujjat    🖼 Rasm    🎬 Video\n"
        f"  🎵 Audio / MP3     🎙 Ovozli xabar\n"
        f"  📹 Dumaloq video   ✍️ Matn / Link\n\n"
        f"<i>Hammasini yuborgach «✅ Saqlash va tugatish» bosing.</i>",
        parse_mode="HTML", reply_markup=kb
    )


# 3-c. Ko'rish (preview)
@router.callback_query(F.data.startswith("mat_preview:"))
async def cb_preview_posts(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    await callback.answer()
    parts   = callback.data.split(":")
    node_id = int(parts[1])
    par_id  = int(parts[2])

    posts = await db.get_material_posts(node_id)
    if not posts:
        await callback.answer("Bu tugmada hali material yo'q.", show_alert=True)
        return

    user_id = callback.from_user.id
    await callback.message.answer(
        f"👁 <b>Jami {len(posts)} ta material (namoyish):</b>",
        parse_mode="HTML"
    )
    for i, post in enumerate(posts, 1):
        cap  = post.get("caption") or ""
        copy = dict(post)
        copy["caption"] = f"<b>{i}.</b> {cap}" if cap else f"<b>{i}.</b>"
        await send_material_item(callback.bot, user_id, copy)

    # O'chirish tugmalari
    icons = {"document":"📄","photo":"🖼","video":"🎬","audio":"🎵",
             "voice":"🎙","video_note":"📹","animation":"🎞","sticker":"🎭","text":"✍️"}
    del_rows = []
    for p in posts:
        snippet = (p.get("caption") or p.get("post_type") or "")[:20]
        icon    = icons.get(p.get("post_type"), "📌")
        del_rows.append([InlineKeyboardButton(
            text=f"🗑 {icon} {snippet}",
            callback_data=f"mat_dpost:{p['id']}:{node_id}:{par_id}"
        )])
    del_rows.append([InlineKeyboardButton(
        text="🔥 Barchasini tozalash",
        callback_data=f"mat_dpost_all:{node_id}:{par_id}"
    )])
    await callback.message.answer(
        "O'chirish uchun quyidan tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=del_rows)
    )


@router.callback_query(F.data.startswith("mat_dpost:"))
async def cb_delete_one_post(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    parts   = callback.data.split(":")
    post_id = int(parts[1])
    node_id = int(parts[2])
    par_id  = int(parts[3])
    await db.delete_material_post(post_id)
    await callback.answer("✅ O'chirildi!", show_alert=True)
    try: await callback.message.delete()
    except: pass


@router.callback_query(F.data.startswith("mat_dpost_all:"))
async def cb_delete_all_posts(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    parts   = callback.data.split(":")
    node_id = int(parts[1])
    await db.delete_all_material_posts(node_id)
    await callback.answer("✅ Barchasi tozalandi!", show_alert=True)
    try: await callback.message.delete()
    except: pass


# 3-d. Nomini o'zgartirish
@router.callback_query(F.data.startswith("mat_rename:"))
async def cb_rename_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    await callback.answer()
    parts   = callback.data.split(":")
    node_id = int(parts[1])
    par_id  = int(parts[2])
    node    = await db.get_material_node(node_id)

    await state.update_data(editing_node_id=node_id, current_node_id=par_id)
    await state.set_state(MatNav.editing_name)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        f"✏️ Eski nom: <b>{html_lib.escape(node['title'])}</b>\n\n"
        f"Yangi nomni yozing:",
        parse_mode="HTML", reply_markup=kb
    )


@router.message(MatNav.editing_name)
async def cb_rename_process(message: Message, state: FSMContext, db: Database):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear(); return

    data    = await state.get_data()
    node_id = data.get("editing_node_id")
    cur_id  = data.get("current_node_id", 0)

    if message.text == "⬅️ Bekor qilish":
        await state.set_state(MatNav.browsing)
        kb = await build_nav_kb(db, cur_id, message.from_user.id)
        await message.answer("❌ Bekor qilindi.", reply_markup=kb)
        return

    new_title = (message.text or "").strip()
    if not new_title:
        await message.answer("⚠️ Nom bo'sh bo'lmaydi.")
        return

    await db.update_material_node_title(node_id, new_title)
    await state.set_state(MatNav.browsing)
    kb = await build_nav_kb(db, cur_id, message.from_user.id)
    await message.answer(
        f"✅ Nom <b>«{html_lib.escape(new_title)}»</b> ga o'zgartirildi!",
        parse_mode="HTML", reply_markup=kb
    )


# 3-e. O'chirish
@router.callback_query(F.data.startswith("mat_delete:"))
async def cb_delete_node(callback: CallbackQuery, db: Database, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    parts   = callback.data.split(":")
    node_id = int(parts[1])
    par_id  = int(parts[2])
    node    = await db.get_material_node(node_id)
    title   = node['title'] if node else "Tugma"

    # Tasdiqlash
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chir",
                                 callback_data=f"mat_del_yes:{node_id}:{par_id}"),
            InlineKeyboardButton(text="❌ Yo'q",
                                 callback_data=f"mat_del_no:{par_id}"),
        ]
    ])
    await callback.answer()
    await callback.message.edit_text(
        f"⚠️ <b>«{html_lib.escape(title)}»</b> tugmasini o'chirasizmi?\n"
        f"Uning ichidagi barcha materiallar ham o'chib ketadi!",
        parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data.startswith("mat_del_yes:"))
async def cb_delete_node_yes(callback: CallbackQuery, db: Database, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌", show_alert=True); return

    parts   = callback.data.split(":")
    node_id = int(parts[1])
    par_id  = int(parts[2])
    node    = await db.get_material_node(node_id)
    title   = node['title'] if node else "Tugma"

    await db.delete_material_node(node_id)
    await callback.answer(f"✅ «{title}» o'chirildi!", show_alert=True)

    try: await callback.message.delete()
    except: pass

    # Klaviaturani yangilash
    await state.set_state(MatNav.browsing)
    await state.update_data(current_node_id=par_id)
    kb = await build_nav_kb(db, par_id, callback.from_user.id)
    await callback.message.answer(
        f"✅ <b>«{html_lib.escape(title)}»</b> o'chirildi.",
        parse_mode="HTML", reply_markup=kb
    )


@router.callback_query(F.data.startswith("mat_del_no:"))
async def cb_delete_node_no(callback: CallbackQuery):
    await callback.answer()
    try: await callback.message.delete()
    except: pass


# ═══════════════════════════════════════════════════════════
# 4. POST QO'SHISH — MatNav.adding_post holati
# ═══════════════════════════════════════════════════════════

@router.message(MatNav.adding_post)
async def mat_receive_post(message: Message, state: FSMContext, db: Database):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await state.clear(); return

    data      = await state.get_data()
    node_id   = data.get("editing_node_id")     # Post biriktirilayotgan tugun
    cur_id    = data.get("current_node_id", 0)  # Orqaga qaytish uchun parent
    count_now = data.get("post_count", 0)

    # Yakunlash
    if message.text in ("✅ Saqlash va tugatish", "⬅️ Bekor qilish"):
        await state.set_state(MatNav.browsing)
        await state.update_data(current_node_id=cur_id)
        kb = await build_nav_kb(db, cur_id, user_id)
        if message.text == "✅ Saqlash va tugatish":
            await message.answer(
                f"✅ <b>Jami {count_now} ta material</b> biriktirildi!\n"
                f"<i>Endi o'quvchilar u tugmani bosganida shu materiallar chiqadi.</i>",
                parse_mode="HTML", reply_markup=kb
            )
        else:
            await message.answer("❌ Bekor qilindi.", reply_markup=kb)
        return

    # Fayl turini aniqlash
    ptype   = None
    file_id = None
    caption = message.caption or ""

    if   message.document:   ptype, file_id = "document",   message.document.file_id
    elif message.photo:      ptype, file_id = "photo",      message.photo[-1].file_id
    elif message.video:      ptype, file_id = "video",      message.video.file_id
    elif message.audio:      ptype, file_id = "audio",      message.audio.file_id
    elif message.voice:      ptype, file_id = "voice",      message.voice.file_id
    elif message.video_note: ptype, file_id = "video_note", message.video_note.file_id
    elif message.animation:  ptype, file_id = "animation",  message.animation.file_id
    elif message.sticker:    ptype, file_id = "sticker",    message.sticker.file_id
    elif message.text:
        ptype    = "text"
        file_id  = None
        caption  = message.text

    if not ptype:
        await message.answer("⚠️ Bu format qabul qilinmaydi. Boshqa fayl yuboring.")
        return

    await db.add_material_post(node_id, ptype, file_id, caption)
    new_count = count_now + 1
    await state.update_data(post_count=new_count)

    icons = {"document":"📄","photo":"🖼","video":"🎬","audio":"🎵",
             "voice":"🎙","video_note":"📹","animation":"🎞","sticker":"🎭","text":"✍️"}
    await message.answer(
        f"{icons.get(ptype,'📌')} Qabul qilindi! Jami: <b>{new_count} ta</b>\n"
        f"<i>Davom eting yoki «✅ Saqlash va tugatish» bosing.</i>",
        parse_mode="HTML"
    )
