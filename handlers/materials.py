# handlers/materials.py
# ============================================================
# KITOB, MASHQLAR VA JAVOBLAR (DYNAMIC MATERIAL TREE & POSTS)
# ============================================================

import logging
import html as html_lib
from typing import Optional, List

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from database.db import Database
from config import ADMIN_IDS
from states.register_states import MaterialState

router = Router()
logger = logging.getLogger(__name__)

# ============================================================
# HELPER: KEYBOARD BUILDERS
# ============================================================

async def build_material_keyboard(
    db: Database,
    node_id: int,
    user_id: int
) -> InlineKeyboardMarkup:
    """Tugmalar daraxti klaviaturasini yaratadi."""
    parent_id = None if node_id == 0 else node_id
    child_nodes = await db.get_material_nodes_by_parent(parent_id)
    
    keyboard = []
    
    # 1. Ichki bo'limlar / tugmalar (2 tadan yoki uzun bo'lsa 1 tadan)
    row = []
    for child in child_nodes:
        btn_text = f"📁 {child['title']}"
        # Agar bu tugmaga biriktirilgan postlar bo'lsa yoki ichki tugmalari bo'lsa
        btn = InlineKeyboardButton(
            text=btn_text,
            callback_data=f"mat_view:{child['id']}"
        )
        if len(child['title']) > 20:
            if row:
                keyboard.append(row)
                row = []
            keyboard.append([btn])
        else:
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)
        
    # 2. Navigatsiya tugmalari (Orqaga / Bosh sahifa)
    if node_id == 0:
        keyboard.append([
            InlineKeyboardButton(text="⬅️ Menyuni yopish", callback_data="mat_close")
        ])
    else:
        current_node = await db.get_material_node(node_id)
        prev_parent = current_node['parent_id'] if current_node and current_node['parent_id'] else 0
        keyboard.append([
            InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mat_view:{prev_parent}"),
            InlineKeyboardButton(text="🔝 Asosiy bo'lim", callback_data="mat_root")
        ])
        
    # 3. Admin Editor tugmalari (Faqat adminlar uchun - 3-rasmdagi uslubda!)
    if user_id in ADMIN_IDS:
        keyboard.append([
            InlineKeyboardButton(text="🎛 Buttons Editor", callback_data=f"mat_btn_editor:{node_id}"),
            InlineKeyboardButton(text="📝 Posts Editor", callback_data=f"mat_post_editor:{node_id}")
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================
# 1. ASOSIY KIRISH VA VIEW HANDLERLAR
# ============================================================

@router.message(F.text == "📚 Kitob mashqlar va javoblar", StateFilter(None))
async def open_materials_root_msg(message: Message, db: Database, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    # Premium tekshiruvi (Adminlar uchun avtomatik ochiq)
    if user_id not in ADMIN_IDS and not await db.is_premium(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Premium olish", callback_data="premium_buy")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="mat_close")]
        ])
        await message.answer(
            "🔒 <b>Ushbu bo'lim faqat Premium foydalanuvchilar uchun!</b>\n\n"
            "📚 <b>Bu bo'limda siz:</b>\n"
            "• 📖 Barcha darajadagi kitoblar (Student's Book, Workbook)\n"
            "• 📝 Barcha mashqlar va ularning to'liq yechimlari/javoblari\n"
            "• 🎧 Listening audiolari va grammatik qo'llanmalar\n"
            "• 📑 PDF va maxsus o'quv materiallariga ega bo'lasiz!\n\n"
            "Qulfni ochish uchun <b>«💎 Premium»</b> obunasini faollashtiring!",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    kb = await build_material_keyboard(db, node_id=0, user_id=user_id)
    await message.answer(
        "📚 <b>Kitoblar, mashqlar va javoblar bo'limi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kerakli daraja yoki mavzuni tanlang 👇",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data == "mat_root")
async def open_materials_root_cb(callback: CallbackQuery, db: Database, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS and not await db.is_premium(user_id):
        await callback.answer("❌ Faqat Premium foydalanuvchilar uchun!", show_alert=True)
        return

    kb = await build_material_keyboard(db, node_id=0, user_id=user_id)
    text = (
        "📚 <b>Kitoblar, mashqlar va javoblar bo'limi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kerakli daraja yoki mavzuni tanlang 👇"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "mat_close")
async def close_materials(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


async def send_material_item(bot, chat_id: int, post: dict):
    """Bitta materialni xavfsiz yuboradi (HTML xatosi bo'lsa plain text da yuboradi)."""
    ptype = post.get("post_type")
    fid = post.get("file_id")
    caption = post.get("caption") or ""
    
    try:
        if ptype == "document":
            try:
                await bot.send_document(chat_id, fid, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_document(chat_id, fid, caption=caption)
        elif ptype == "photo":
            try:
                await bot.send_photo(chat_id, fid, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_photo(chat_id, fid, caption=caption)
        elif ptype == "video":
            try:
                await bot.send_video(chat_id, fid, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_video(chat_id, fid, caption=caption)
        elif ptype == "audio":
            try:
                await bot.send_audio(chat_id, fid, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_audio(chat_id, fid, caption=caption)
        elif ptype == "voice":
            await bot.send_voice(chat_id, fid, caption=caption)
        elif ptype == "video_note":
            await bot.send_video_note(chat_id, fid)
        elif ptype == "animation":
            try:
                await bot.send_animation(chat_id, fid, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_animation(chat_id, fid, caption=caption)
        elif ptype == "sticker":
            await bot.send_sticker(chat_id, fid)
        elif ptype == "text":
            try:
                await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=False)
            except Exception:
                await bot.send_message(chat_id, caption, disable_web_page_preview=False)
    except Exception as e:
        logger.error(f"Material yuborishda xatolik (chat_id: {chat_id}, post_id: {post.get('id')}): {e}")


@router.callback_query(F.data.startswith("mat_view:"))
async def view_material_node(callback: CallbackQuery, db: Database, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS and not await db.is_premium(user_id):
        await callback.answer("❌ Faqat Premium foydalanuvchilar uchun!", show_alert=True)
        return

    node_id_str = callback.data.split(":")[1]
    node_id = int(node_id_str)
    
    if node_id == 0:
        await open_materials_root_cb(callback, db, state)
        return
        
    current_node = await db.get_material_node(node_id)
    if not current_node:
        await callback.answer("⚠️ Ushbu bo'lim topilmadi yoki o'chirilgan.", show_alert=True)
        await open_materials_root_cb(callback, db, state)
        return

    # Breadcrumbs (Yo'l tarixi)
    breadcrumbs = await db.get_material_node_breadcrumbs(node_id)
    path_str = " ➔ ".join([f"<b>{b['title']}</b>" for b in breadcrumbs])

    # 1. Ushbu tugmaga biriktirilgan postlar (fayllar/xabarlar) mavjud bo'lsa, ularni ketma-ket yuboramiz
    posts = await db.get_material_posts(node_id)
    if posts:
        for post in posts:
            await send_material_item(callback.bot, user_id, post)

    # 2. Menyuni ko'rsatamiz
    kb = await build_material_keyboard(db, node_id=node_id, user_id=user_id)
    
    post_count_info = f"\n📄 <i>Mavjud materiallar: {len(posts)} ta</i>\n" if posts else ""
    text = (
        f"📍 {path_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{post_count_info}\n"
        f"Quyidagilardan birini tanlang 👇"
    )
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


# ============================================================
# 2. ADMIN: BUTTONS EDITOR
# ============================================================

@router.callback_query(F.data.startswith("mat_btn_editor:"))
async def open_buttons_editor(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    
    title = "Asosiy bo'lim (Root)"
    if node_id != 0:
        node = await db.get_material_node(node_id)
        if node:
            title = node['title']
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi tugma qo'shish", callback_data=f"mat_add_btn:{node_id}")],
        [
            InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"mat_edit_btn_list:{node_id}"),
            InlineKeyboardButton(text="🗑 Tugmani o'chirish", callback_data=f"mat_del_btn_list:{node_id}")
        ],
        [InlineKeyboardButton(text="🔙 Bo'limga qaytish", callback_data=f"mat_view:{node_id}")]
    ])
    
    await callback.message.edit_text(
        f"🎛 <b>Tugmalar boshqaruvi (Buttons Editor)</b>\n"
        f"📁 Joriy bo'lim: <b>{html_lib.escape(title)}</b>\n\n"
        f"Kerakli amalni tanlang:",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("mat_add_btn:"))
async def start_add_button(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    await state.update_data(current_node_id=node_id)
    await state.set_state(MaterialState.waiting_for_new_button_name)
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True)
    await callback.message.answer(
        "➕ <b>Yangi tugma nomini yozib yuboring:</b>\n\n"
        "<i>Masalan: Starter, Elementary, Grammar, Student's Book PDF, Workbook va h.k.</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.message(MaterialState.waiting_for_new_button_name)
async def process_new_button_name(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Bekor qilish":
        data = await state.get_data()
        node_id = data.get("current_node_id", 0)
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        kb = await build_material_keyboard(db, node_id=node_id, user_id=message.from_user.id)
        await message.answer("📁 Bo'limga qaytdingiz:", reply_markup=kb)
        return
        
    btn_title = message.text.strip()
    if not btn_title:
        await message.answer("⚠️ Iltimos, tugma nomini to'g'ri kiriting.")
        return
        
    data = await state.get_data()
    parent_id = data.get("current_node_id", 0)
    db_parent = None if parent_id == 0 else parent_id
    
    new_id = await db.create_material_node(db_parent, btn_title)
    await state.clear()
    
    from handlers.student import get_user_keyboard
    await message.answer(
        f"✅ <b>«{html_lib.escape(btn_title)}»</b> tugmasi muvaffaqiyatli yaratildi!",
        parse_mode="HTML",
        reply_markup=get_user_keyboard(message.from_user.id)
    )
    
    kb = await build_material_keyboard(db, node_id=parent_id, user_id=message.from_user.id)
    await message.answer("📁 Bo'lim ko'rinishi yangilandi:", reply_markup=kb)


@router.callback_query(F.data.startswith("mat_edit_btn_list:"))
async def list_buttons_to_edit(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    parent_id = None if node_id == 0 else node_id
    children = await db.get_material_nodes_by_parent(parent_id)
    
    if not children:
        await callback.answer("Bu bo'limda o'zgartirish uchun tugmalar yo'q.", show_alert=True)
        return
        
    buttons = []
    for c in children:
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"mat_edit_btn_prompt:{c['id']}:{node_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mat_btn_editor:{node_id}")])
    
    await callback.message.edit_text(
        "✏️ <b>Nomini o'zgartirmoqchi bo'lgan tugmani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("mat_edit_btn_prompt:"))
async def prompt_edit_button(callback: CallbackQuery, state: FSMContext, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    parts = callback.data.split(":")
    target_node_id = int(parts[1])
    current_node_id = int(parts[2])
    
    node = await db.get_material_node(target_node_id)
    if not node:
        await callback.answer("Tugma topilmadi.", show_alert=True)
        return
        
    await state.update_data(target_node_id=target_node_id, current_node_id=current_node_id)
    await state.set_state(MaterialState.waiting_for_edit_button_name)
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True)
    await callback.message.answer(
        f"✏️ <b>Eski nom:</b> «{html_lib.escape(node['title'])}»\n\n"
        f"<b>Yangi nomni yozib yuboring:</b>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.message(MaterialState.waiting_for_edit_button_name)
async def process_edit_button_name(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Bekor qilish":
        data = await state.get_data()
        node_id = data.get("current_node_id", 0)
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        kb = await build_material_keyboard(db, node_id=node_id, user_id=message.from_user.id)
        await message.answer("📁 Bo'lim:", reply_markup=kb)
        return
        
    new_title = message.text.strip()
    if not new_title:
        await message.answer("⚠️ Iltimos, to'g'ri nom kiriting.")
        return
        
    data = await state.get_data()
    target_node_id = data.get("target_node_id")
    current_node_id = data.get("current_node_id", 0)
    
    await db.update_material_node_title(target_node_id, new_title)
    await state.clear()
    
    from handlers.student import get_user_keyboard
    await message.answer(
        f"✅ Tugma nomi <b>«{html_lib.escape(new_title)}»</b> ga o'zgartirildi!",
        parse_mode="HTML",
        reply_markup=get_user_keyboard(message.from_user.id)
    )
    kb = await build_material_keyboard(db, node_id=current_node_id, user_id=message.from_user.id)
    await message.answer("📁 Bo'lim ko'rinishi yangilandi:", reply_markup=kb)


@router.callback_query(F.data.startswith("mat_del_btn_list:"))
async def list_buttons_to_delete(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    parent_id = None if node_id == 0 else node_id
    children = await db.get_material_nodes_by_parent(parent_id)
    
    if not children:
        await callback.answer("Bu bo'limda o'chirish uchun tugmalar yo'q.", show_alert=True)
        return
        
    buttons = []
    for c in children:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"mat_del_btn_confirm:{c['id']}:{node_id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mat_btn_editor:{node_id}")])
    
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan tugmani tanlang:</b>\n"
        "⚠️ <i>Tugma o'chirilganda uning ichidagi barcha fayllar va quyi bo'limlar ham o'chib ketadi!</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("mat_del_btn_confirm:"))
async def delete_button_confirm(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    parts = callback.data.split(":")
    target_node_id = int(parts[1])
    current_node_id = int(parts[2])
    
    node = await db.get_material_node(target_node_id)
    title = node['title'] if node else "Tugma"
    
    await db.delete_material_node(target_node_id)
    await callback.answer(f"✅ «{title}» o'chirildi!", show_alert=True)
    
    kb = await build_material_keyboard(db, node_id=current_node_id, user_id=callback.from_user.id)
    await callback.message.edit_text(
        f"✅ <b>«{html_lib.escape(title)}»</b> tugmasi va uning tarkibi to'liq o'chirildi.",
        parse_mode="HTML",
        reply_markup=kb
    )


# ============================================================
# 3. ADMIN: POSTS EDITOR (MULTIMEDIA / PDF / VIDEO / TEXT)
# ============================================================

@router.callback_query(F.data.startswith("mat_post_editor:"))
async def open_posts_editor(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    
    title = "Asosiy bo'lim (Root)"
    if node_id != 0:
        node = await db.get_material_node(node_id)
        if node:
            title = node['title']
            
    posts = await db.get_material_posts(node_id)
    count = len(posts)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Material / Fayl qo'shish", callback_data=f"mat_add_post:{node_id}")],
        [
            InlineKeyboardButton(text=f"👀 Ko'rish ({count} ta)", callback_data=f"mat_view_posts:{node_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"mat_del_post_list:{node_id}")
        ],
        [InlineKeyboardButton(text="🔥 Barchasini tozalash", callback_data=f"mat_clear_posts:{node_id}")],
        [InlineKeyboardButton(text="🔙 Bo'limga qaytish", callback_data=f"mat_view:{node_id}")]
    ])
    
    await callback.message.edit_text(
        f"📝 <b>Postlar va fayllar boshqaruvi (Posts Editor)</b>\n"
        f"📁 Joriy bo'lim: <b>{html_lib.escape(title)}</b>\n"
        f"📊 Biriktirilgan materiallar soni: <b>{count} ta</b>\n\n"
        f"<i>Ushbu tugma bosilganda o'quvchilarga qaysi PDF, video, audio, rasm yoki xabarlar chiqishini sozlang.</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("mat_add_post:"))
async def start_add_post(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    await state.update_data(current_node_id=node_id, post_count=0)
    await state.set_state(MaterialState.waiting_for_post_content)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Saqlash va yakunlash")]],
        resize_keyboard=True
    )
    
    await callback.message.answer(
        "📥 <b>Material / Fayllarni yuboring:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Siz istalgan formatdagi fayl yoki xabarlarni yuborishingiz mumkin:\n"
        "• 📄 <b>PDF / Hujjat</b> (Kitoblar, workbook, javoblar, testlar)\n"
        "• 🖼 <b>Rasm</b> (Jadvallar, qoidalar, mashqlar)\n"
        "• 🎬 <b>Video / Kino</b>\n"
        "• 🎵 <b>Audio / MP3 / Musiqa</b> (Listening fayllari)\n"
        "• 🎙 <b>Ovozli xabar (Voice)</b>\n"
        "• 📹 <b>Dumaloq video (Video note)</b>\n"
        "• ✍️ <b>Matnli xabar</b> (Izoh, linklar yoki dars matni)\n"
        "• 🎭 <b>Sticker</b>\n\n"
        "<i>Bir nechta fayl yuborishingiz mumkin. Barcha fayllarni yuborib bo'lgach, «✅ Saqlash va yakunlash» tugmasini bosing.</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.message(MaterialState.waiting_for_post_content)
async def process_incoming_post_material(message: Message, state: FSMContext, db: Database):
    if message.text == "✅ Saqlash va yakunlash" or message.text == "⬅️ Bekor qilish":
        data = await state.get_data()
        node_id = data.get("current_node_id", 0)
        saved_count = data.get("post_count", 0)
        await state.clear()
        
        from handlers.student import get_user_keyboard
        await message.answer(
            f"✅ <b>Jami {saved_count} ta yangi material muvaffaqiyatli saqlandi va biriktirildi!</b>",
            parse_mode="HTML",
            reply_markup=get_user_keyboard(message.from_user.id)
        )
        
        kb = await build_material_keyboard(db, node_id=node_id, user_id=message.from_user.id)
        await message.answer("📁 Bo'lim:", reply_markup=kb)
        return

    data = await state.get_data()
    node_id = data.get("current_node_id", 0)
    current_count = data.get("post_count", 0)

    # Content turini aniqlaymiz
    ptype = None
    file_id = None
    caption = message.caption or message.text or ""

    if message.document:
        ptype = "document"
        file_id = message.document.file_id
    elif message.photo:
        ptype = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        ptype = "video"
        file_id = message.video.file_id
    elif message.audio:
        ptype = "audio"
        file_id = message.audio.file_id
    elif message.voice:
        ptype = "voice"
        file_id = message.voice.file_id
    elif message.video_note:
        ptype = "video_note"
        file_id = message.video_note.file_id
    elif message.animation:
        ptype = "animation"
        file_id = message.animation.file_id
    elif message.sticker:
        ptype = "sticker"
        file_id = message.sticker.file_id
    elif message.text:
        ptype = "text"
        file_id = None
        caption = message.text

    if not ptype:
        await message.answer("⚠️ Ushbu format qo'llab-quvvatlanmaydi.")
        return

    await db.add_material_post(node_id, ptype, file_id, caption)
    new_count = current_count + 1
    await state.update_data(post_count=new_count)

    type_names = {
        "document": "📄 Hujjat / PDF",
        "photo": "🖼 Rasm",
        "video": "🎬 Video",
        "audio": "🎵 Audio / MP3",
        "voice": "🎙 Ovozli xabar",
        "video_note": "📹 Dumaloq video",
        "animation": "🎞 GIF",
        "sticker": "🎭 Sticker",
        "text": "✍️ Matn"
    }
    
    await message.answer(
        f"✅ <b>{type_names.get(ptype, 'Fayl')}</b> biriktirildi! (Jami: {new_count} ta)\n\n"
        f"<i>Yana yuborishingiz yoki «✅ Saqlash va yakunlash» tugmasini bosishingiz mumkin.</i>",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("mat_view_posts:"))
async def preview_attached_posts(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    posts = await db.get_material_posts(node_id)
    
    if not posts:
        await callback.answer("Ushbu bo'limda materiallar mavjud emas.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    await callback.message.answer(f"👀 <b>Jami {len(posts)} ta material namoyish qilinmoqda:</b>", parse_mode="HTML")
    
    for i, post in enumerate(posts, 1):
        cap = post.get("caption") or ""
        header = f"📌 <b>{i}-material:</b>\n"
        post_copy = dict(post)
        post_copy["caption"] = f"{header}{cap}" if cap else header
        await send_material_item(callback.bot, user_id, post_copy)


@router.callback_query(F.data.startswith("mat_del_post_list:"))
async def list_posts_to_delete(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    posts = await db.get_material_posts(node_id)
    
    if not posts:
        await callback.answer("O'chirish uchun materiallar yo'q.", show_alert=True)
        return
        
    buttons = []
    type_icons = {
        "document": "📄", "photo": "🖼", "video": "🎬",
        "audio": "🎵", "voice": "🎙", "video_note": "📹",
        "animation": "🎞", "sticker": "🎭", "text": "✍️"
    }
    
    for i, p in enumerate(posts, 1):
        icon = type_icons.get(p.get("post_type"), "📌")
        title_snippet = (p.get("caption") or p.get("post_type"))[:20]
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {i}-material: {icon} {title_snippet}",
                callback_data=f"mat_del_single_post:{p['id']}:{node_id}"
            )
        ])
        
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mat_post_editor:{node_id}")])
    
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan materialni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("mat_del_single_post:"))
async def delete_single_post(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    parts = callback.data.split(":")
    post_id = int(parts[1])
    node_id = int(parts[2])
    
    await db.delete_material_post(post_id)
    await callback.answer("✅ Material o'chirildi!", show_alert=True)
    
    # Qayta ro'yxatni ochamiz
    posts = await db.get_material_posts(node_id)
    if posts:
        await list_posts_to_delete(callback, db)
    else:
        await open_posts_editor(callback, db)


@router.callback_query(F.data.startswith("mat_clear_posts:"))
async def clear_all_posts(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
        
    await callback.answer()
    node_id = int(callback.data.split(":")[1])
    
    await db.delete_all_material_posts(node_id)
    await callback.answer("✅ Barcha materiallar tozalandi!", show_alert=True)
    await open_posts_editor(callback, db)
