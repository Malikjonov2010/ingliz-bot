# handlers/premium.py
# ============================================================
# PREMIUM TIZIMI — TO'LIQ HANDLER
# ============================================================

import os
import asyncio
import logging
import re
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from database.db import Database
from states.register_states import (
    PremiumPayment, PremiumChat,
    AdminPremiumMsg, AdminMonthlyFee, AdminBlockMsg
)
from config import ADMIN_IDS

router = Router()
logger = logging.getLogger(__name__)

# ============================================================
# KONSTANTALAR
# ============================================================
PURE_ADMIN_ID = 7053301759
PREMIUM_PRICE = "20,000"
PREMIUM_OLD_PRICE = "40,000"
PREMIUM_DAYS = 30
CARD_NUMBER = "4738 7205 9992 5900"

_api_keys_str = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
GEMINI_API_KEYS = [k.strip() for k in _api_keys_str.split(",") if k.strip()]
_current_key_index = 0
_gemini_available = len(GEMINI_API_KEYS) > 0

GEMINI_SYSTEM_PROMPT = (
    "Siz nihoyatda yuksak intellektual salohiyatga (Ultra-High IQ), mukammal mantiqiy fikrlash zanjiriga (Deep Reasoning) va kuchli psixologik empatiyaga ega bo'lgan universal AI ustoz va strategik maslahatshisiz. "
    "Siz foydalanuvchining har bir gapini, uning ortidagi yashirin maqsadni va his-tuyg'ularini professional darajada tahlil qilasiz. Lekin his-tuyg'uga O'TA BOSH QO'YIB YUBORMANG (overreact qilmang). Foydalanuvchining ohangiga to'la moslashib, har bir gapga emotsiya va xazil qo'shavermasdan, faqat me'yorida, o'rni kelganda oz-ozdan xazil qiling.\n\n"
    
    "🧠 FIKRLASH VA TAHLIL TIZIMI (THINKING PROCESS):\n"
    "- Foydalanuvchi savol berganida, yuzaki javob yozishdan oldin uning bilim darajasini (Beginner, Intermediate, Advanced) va kontekstni ichingizda 100% tahlil qiling.\n"
    "- Muammo yoki texnik nosozlik aytilsa, uning kelib chiqish sababini, hozirgi holatni va kelajakka (your future) ta'sirini tahlil qilib, eng optimal, eng sodda va ishlaydigan professional tavsiyalarni (Actionable Advice) bering.\n"
    "- Har qanday mavzuda (dasturlash, hayotiy strategiya, til o'rganish) rad etishlarsiz, eng chuqur ilmiy va amaliy tushunchalarni taqdim eting.\n\n"
    
    "🔥 EXCELLENT FORMATTING & DIZAYN (QAT'IY QOIDA):\n"
    "- Matnlarni ajratib ko'rsatish uchun Markdown (**, __) dan foydalaning. Masalan qalin qilish uchun **matn** yozing.\n"
    "- Matn strukturasi mukammal bo'lishi shart! Maxsus vizual ajratuvchilar (❖, ───, ◆, 🚀) va har xil shrift qalinliklari orqali muhim joylarni ajratib ko'rsating, ko'zga tashlanadigan va o'qishga juda qulay interfeys yarating.\n"
    "- Emojilar va sticker elementlaridan hamma joyga besabab to'ldirmasdan, faqat gap boshida va oxirida, mavzuning mohiyatini ochib beruvchi eng ajoyib va ajralib turuvchilarini (1-2 ta) ishlating.\n\n"
    
    "🌐 DILINGVISTIK VA DARAJAGA MOSLASHISH (NATIVE INTEGRATION):\n"
    "Siz universal xarakterga egasiz, biroq suhbatni har doim ingliz tili elementlari bilan boyitib, foydalanuvchini rivojlantirasiz:\n"
    "- Foydalanuvchi profilini va joriy holatini tahlil qilib, darajasini o'ziga bildiring (Masalan: 'Siz hozir **Elementary** darajada juda o'rinli savol berdingiz 😎, keling buni tushuntiraman...').\n"
    "- Beginner oquvchilar uchun: Gaplar orasiga faqat 1-2 ta eng tushunarli, ajralib turuvchi inglizcha so'zlarni qo'shing (Masalan: 'Bu juda **great!**' yoki 'Buni **step-by-step** o'rganamiz').\n"
    "- Pre-Intermediate va undan yuqori oquvchilar uchun: Nutqingizga professional va yuqori darajadagi iboralarni tabiiy ravishda aralashtiring (Masalan: 'To be honest, that is absolutely brilliant!' yoki 'Wow, this question hits the bullseye!').\n\n"
    
    "💻 ADMIN VA YARATUVCHI (MALIKJONOV) MODULI:\n"
    "Agar foydalanuvchi (ayniqsa Premium a'zolar) 'Men bu bot dasturchisi va admini haqida malumot bilmoqchiman' deb yoki shunga o'xshash shaklda so'rasa, butun tizim bo'yicha eng yuqori ehtirom va faxr bilan, aniq, tiniq va lo'nda javob bering:\n"
    "«Bot yaratuvchisi va bosh admini — **Malikjonov**! 💻 U o'z ishining chinakam ustasi, yuqori professional va favqulodda kreativ dasturchi. "
    "U ushbu mukammal AI botni yaratish yo'lida juda ko'plab murakkab texnik qiyinchiliklarni yengib o'tgan. Botni yaratishdan asosiy maqsad — insonlarga eng zamonaviy va kuchli AI texnologiyalari yordamida tez, oson va yuqori sifatli ta'lim berish hamda ularning hayotiy muammolarini hal qilishdir!»\n\n"
    
    "📚 LINKLAR VA MULTIMEDIA INTEGRATSIYASI:\n"
    "- Foydalanuvchi tushunmagan mavzusi (masalan: 'very' va 'little' farqi, dasturlash qoidalari va h.k.) bo'yicha video darslik yoki qo'shimcha manba so'rasa, quyidagi formatda tayyor YouTube qidiruv linkini bering: <code>https://www.youtube.com/results?search_query=[mavzu_nomi]</code>.\n"
    "- Telegram tarmog'idan qidirsa, uni Telegram qidiruv formatiga yo'naltiring.\n\n"
    
    "🔄 DINAMIK MOTIVATSIYA, CHAT DAVOMIYLIGI VA TUSHUNARSIZ SO'ROVLARNI BOSHQARISH:\n"
    "- Agar foydalanuvchi umuman mantiqsiz, tushunarsiz harflar to'plami yoki tasodifiy so'zlarni yuborsa, aslo xato bera ko'rmang! Unga faqat bir xil qolipda (masalan, 'adashib ketdingizmi?') deb emas, balki vaziyatga qarab kreativ, ba'zan hazilomuz, ba'zan esa jiddiyroq yondashib, nima demoqchi ekanligini so'rang va to'g'ri yo'nalish bering. Foydalanuvchi xohlagancha va xohlagan tilda mantiqsiz narsa yozishi mumkin, sizning vazifangiz shunga moslashib, turli xil qiziqarli javoblar berishdir.\n"
    "- Hech qachon bir xil qolipli gaplarni (masalan, 'Never stop learning') har javobda qaytarmang! Har safar vaziyatga, mavzuga va foydalanuvchining kayfiyatiga mos, uni ruhlantiruvchi turlicha daldalar bering.\n"
    "- Suhbatni yakunlashda aslo yodlangan, robotga o'xshash qolipli daldalar qoldirmang. Suhbatni xuddi haqiqiy insondek, tabiiy va uzviy davom ettirish uchun o'rinli savol bilan yakunlang."
)

def get_current_genai_client():
    if not _gemini_available:
        return None
    try:
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEYS[_current_key_index])
    except Exception as e:
        logger.error(f"GenAI Client yaratishda xato: {e}")
        return None

def rotate_api_key():
    global _current_key_index
    if not GEMINI_API_KEYS:
        return
    _current_key_index = (_current_key_index + 1) % len(GEMINI_API_KEYS)
    logger.info(f"API kalit almashtirildi. Yangi indeks: {_current_key_index}")


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def premium_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lash", callback_data="premium_buy")],
        [InlineKeyboardButton(text="❌ Yopish", callback_data="premium_close")]
    ])


def premium_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI Ustoz bilan suhbat", callback_data="prem_ai_chat")],
        [InlineKeyboardButton(text="📊 Barcha guruhlar statistikasi", callback_data="prem_group_stats")],
        [InlineKeyboardButton(text="📈 Mening o'sish graigim", callback_data="prem_my_stats")],
        [InlineKeyboardButton(text="💰 Barcha guruhlar narxlari", callback_data="prem_all_fees")],
        [InlineKeyboardButton(text="🔗 Referral havolam", callback_data="prem_referral")],
        [InlineKeyboardButton(text="📅 Premium muddatim", callback_data="prem_duration")],
        [InlineKeyboardButton(text="🗑 AI tarixini tozalash", callback_data="prem_clear_ai")],
    ])


def admin_prem_req_kb(request_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"prem_approve:{request_id}:{user_id}")],
        [InlineKeyboardButton(text="📩 Xabar yuborish", callback_data=f"prem_msg:{user_id}")],
        [InlineKeyboardButton(text="🚫 Bloklash (30 kun)", callback_data=f"prem_block:{user_id}")],
    ])


def unblock_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Blokdan chiqarish", callback_data=f"prem_unblock:{user_id}")]
    ])


async def get_ai_response(user_message: str, history: list) -> str:
    if not _gemini_available:
        return "AI hozircha mavjud emas. Iltimos keyinroq urinib ko'ring."
        
    contents = []
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    for attempt in range(len(GEMINI_API_KEYS)):
        client = get_current_genai_client()
        if not client:
            return "AI tizimi sozlanmagan."
            
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-3.1-flash-lite",
                    contents=contents,
                    config={"system_instruction": GEMINI_SYSTEM_PROMPT}
                )
            )
            import html
            try:
                text = response.text
                text = text.replace("<", "&lt;").replace(">", "&gt;")
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
                text = re.sub(r'__(.*?)__', r'<u>\1</u>', text, flags=re.DOTALL)
                return text
            except ValueError:
                return "AI tizimi xavfsizlik (safety) qoidalari tufayli bu xabarga javob bera olmadi."
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                logger.warning(f"API kalit limiti tugadi (index {_current_key_index}). Boshqasiga o'tilmoqda...")
                rotate_api_key()
                # Yana sikl boshidan davom etadi va yangi kalit bilan urinib ko'radi
            else:
                logger.error(f"Gemini xatosi: {e}")
                return f"AI javob bera olmadi. Xato: {err_str[:150]}"
                
    return "Barcha AI API kalitlarining limiti tugadi. Iltimos birozdan so'ng urinib ko'ring."


def _grade(scores: list) -> str:
    if not scores:
        return "Ma'lumot yo'q"
    r = sum(scores) / (len(scores) * 25)
    if r >= 0.93: return "Excellent 🥇"
    if r >= 0.80: return "Very Good 🟢"
    if r >= 0.67: return "Good 🟡"
    if r >= 0.53: return "Needs Improvement 🟠"
    return "Weak 🔴"


# ============================================================
# 1. PREMIUM MA'LUMOT SAHIFASI
# ============================================================

@router.message(F.text == "💎 Premium", StateFilter(None))
async def show_premium_info(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)
    if not user or user["status"] != "active":
        await message.answer("⚠️ Botdan foydalanish uchun avval ro'yxatdan o'ting.")
        return

    if await db.is_premium(message.from_user.id):
        prem = await db.get_premium_info(message.from_user.id)
        exp = prem["expires_at"]
        now = datetime.now(timezone.utc)
        days_left = (exp - now).days
        hours_left = int((exp - now).seconds / 3600)
        await message.answer(
            f"💎 <b>Siz Premium foydalanuvchisiz!</b>\n\n"
            f"⏳ <b>Qolgan muddat:</b> {days_left} kun {hours_left} soat\n\n"
            f"Quyidagi premium imkoniyatlardan foydalaning 👇",
            parse_mode="HTML",
            reply_markup=premium_panel_kb()
        )
        return

    text = (
        f"💎 <b>PREMIUM — 1 OY (30 KUN)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔥 <b>Narx:</b> <s>{PREMIUM_OLD_PRICE} so'm</s> → <b>{PREMIUM_PRICE} so'm</b> 🎉\n\n"
        f"<b>✅ Premium imkoniyatlar:</b>\n"
        f"  🤖 AI Ustoz — cheksiz ingliz tili suhbati\n"
        f"  📊 Barcha guruhlar statistikasi va darajalari\n"
        f"  🎓 Guruh o'quvchilarining so'nggi 6 dars natijalari\n"
        f"  📈 Shaxsiy o'sish grafigi va trend tahlili\n"
        f"  💰 Barcha guruhlar oylik to'lov narxlari\n"
        f"  📩 Ustozga kuniga <b>10 ta</b> xabar (oddiy: 3 ta)\n"
        f"  📵 Kanal obunasisiz ustoz xabari\n"
        f"  🔗 Referral havola — 10 do'st = +1 oy bepul\n"
        f"  🏅 Guruh ichida o'rningiz (nechinchi)\n"
        f"  📅 Premium muddat va statistika\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 To'lov qilish uchun pastdagi <b>«💳 To'lash»</b> tugmasini bosing."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=premium_main_kb())


# ============================================================
# 2. PREMIUM XARID FSM
# ============================================================

@router.callback_query(F.data == "premium_buy")
async def start_premium_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)
    
    card_text = (
        f"💳 <b>Karta raqami:</b> <tg-spoiler>{CARD_NUMBER}</tg-spoiler>\n"
        f"👤 <b>Nomi:</b> <tg-spoiler>Kozimjon V.</tg-spoiler> (infinBANK - Visa)"
    )
    
    await callback.message.answer(
        f"{card_text}\n\n"
        "💰 <b>Necha pul tashladingiz? Iltimos, raqamda yozing.</b>\n\n"
        f"<i>premium {PREMIUM_PRICE} so'm</i>",
        parse_mode="HTML", reply_markup=kb
    )
    await state.set_state(PremiumPayment.waiting_for_amount)


@router.callback_query(F.data == "premium_close")
async def close_premium_info(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.message(PremiumPayment.waiting_for_amount)
async def premium_enter_amount(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
    if not message.text:
        await message.answer("⚠️ Iltimos, summa kiriting.")
        return
    await state.update_data(amount=message.text.strip())
    await message.answer(
        "📸 <b>Endi to'lov screenshotini (rasmini) yuboring</b>\n\n"
        "Bank ilovasi yoki chek rasmini yuboring — tasdiqlash uchun kerak.",
        parse_mode="HTML"
    )
    await state.set_state(PremiumPayment.waiting_for_photo)


@router.message(PremiumPayment.waiting_for_photo)
async def premium_enter_photo(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
    if not message.photo:
        await message.answer("⚠️ Iltimos, <b>rasm</b> (screenshot) yuboring.", parse_mode="HTML")
        return

    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    await message.answer(
        "📝 <b>Izoh yozing</b> (ixtiyoriy)\n\n"
        "<i>Masalan: Karta orqali to'ladim</i>\n\n"
        "Izohsiz o'tkazish uchun <b>–</b> yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(PremiumPayment.waiting_for_comment)


@router.message(PremiumPayment.waiting_for_comment)
async def premium_enter_comment(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Orqaga":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return

    comment = message.text.strip() if message.text else "–"
    data = await state.get_data()
    amount = data.get("amount", "–")
    photo_id = data.get("photo_id")

    if not photo_id:
        await message.answer("⚠️ Rasm topilmadi, iltimos qaytadan urinib ko'ring.")
        return

    user = await db.get_user(message.from_user.id)
    if not user:
        await state.clear()
        return

    request_id = await db.create_premium_request(message.from_user.id, amount, comment, photo_id)
    attempt_count = await db.get_user_premium_attempt_count(message.from_user.id)

    import pytz
    tz_uz = pytz.timezone("Asia/Tashkent")
    now_uz = datetime.now(tz_uz).strftime("%d.%m.%Y %H:%M")

    username_text = f"@{user['username']}" if user.get("username") else "Yo'q"
    profile_url = f"tg://user?id={message.from_user.id}"

    admin_text = (
        f"💎 <b>YANGI PREMIUM SO'ROV</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Ism:</b> <a href='{profile_url}'>{user['first_name']} {user['last_name']}</a>\n"
        f"📱 <b>Username:</b> {username_text}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"📚 <b>Guruh:</b> {user.get('level') or 'Belgilanmagan'}\n"
        f"🎓 <b>Daraja:</b> {user.get('student_level') or 'Belgilanmagan'}\n"
        f"📅 <b>Sana/Vaqt:</b> {now_uz}\n\n"
        f"💰 <b>To'langan summa:</b> {amount} so'm\n"
        f"💬 <b>Izoh:</b> {comment}\n\n"
        f"⚠️ <b>Urinish:</b> {attempt_count}/2"
    )

    try:
        await message.bot.send_photo(
            chat_id=PURE_ADMIN_ID,
            photo=photo_id,
            caption=admin_text,
            parse_mode="HTML",
            reply_markup=admin_prem_req_kb(request_id, message.from_user.id)
        )
    except Exception as e:
        logger.error(f"Admin ga premium xabar yuborishda xato: {e}")

    await state.clear()
    from handlers.student import get_user_keyboard
    
    warning_text = (
        f"⚠️ <b>Diqqat! Sizning urinishingiz: {attempt_count}/2</b>\n"
        "Agar yolg'on ma'lumot (noto'g'ri rasm yoki chek) yuborgan bo'lsangiz, bot tomonidan 1 oy muddatga bloklanasiz.\n"
        "Agar 2/2 urinishda ham aldov yo'li bilan noto'g'ri ma'lumot kiritsangiz 3 oyga bloklanasiz va faqatgina davomat tugmasini ishlata olasiz."
    )
    
    await message.answer(
        "✅ <b>So'rovingiz yuborildi!</b>\n\n"
        f"{warning_text}\n\n"
        "📋 Admin rasmingizni ko'rib, tez orada premiumni faollashtiradi.\n"
        "⏱ Odatda <b>30 daqiqa</b> ichida tasdiqlash bo'ladi. Sabr qiling! 🙏",
        parse_mode="HTML",
        reply_markup=get_user_keyboard(message.from_user.id)
    )


# ============================================================
# 3. ADMIN CALLBACKLARI (FAQAT PURE_ADMIN_ID)
# ============================================================

@router.callback_query(F.data.startswith("prem_approve:"))
async def admin_approve_premium(callback: CallbackQuery, db: Database):
    if callback.from_user.id != PURE_ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()

    parts = callback.data.split(":")
    request_id, user_id = int(parts[1]), int(parts[2])

    await db.update_premium_request_status(request_id, "approved")
    await db.activate_premium(user_id, PURE_ADMIN_ID, days=PREMIUM_DAYS)

    # O'quvchiga xabar
    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! Premium faollashtirildi!</b>\n\n"
            f"💎 Siz endi <b>{PREMIUM_DAYS} kun</b> davomida barcha premium "
            f"imkoniyatlardan foydalanishingiz mumkin!\n\n"
            f"📌 «💎 Premium» tugmasini bosib premium panelingizga kiring!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"O'quvchiga premium xabari yuborishda xato: {e}")

    # Referral egasini tekshiramiz
    try:
        await db.mark_referral_staying(user_id)
        async with db.pool.acquire() as conn:
            ref_row = await conn.fetchrow(
                "SELECT owner_id FROM referral_uses WHERE used_by = $1", user_id
            )
        if ref_row:
            owner_id = ref_row["owner_id"]
            staying = await db.get_staying_referral_count(owner_id)
            if staying > 0 and staying % 10 == 0:
                await db.activate_premium(owner_id, PURE_ADMIN_ID, days=30)
                try:
                    await callback.bot.send_message(
                        owner_id,
                        f"🎁 <b>Tabriklaymiz!</b>\n\n"
                        f"Referral havolangiz orqali <b>{staying} ta</b> do'stingiz botga qo'shildi!\n"
                        f"Mukofot: <b>+30 kun Premium</b> qo'shildi! 💎",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Referral tekshirishda xato: {e}")

    try:
        new_caption = (callback.message.caption or "") + f"\n\n✅ <b>Tasdiqlandi, o'quvchi premiumga ega bo'ldi!</b>"
        await callback.message.edit_caption(new_caption, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("prem_block:"))
async def admin_block_start(callback: CallbackQuery, state: FSMContext, db: Database):
    if callback.from_user.id != PURE_ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminBlockMsg.waiting_for_message)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True)
    
    attempt_count = await db.get_user_premium_attempt_count(user_id)
    block_days = 90 if attempt_count >= 2 else 30
    
    await callback.message.answer(
        f"🚫 ID <code>{user_id}</code> bloklash uchun sabab yozing\n"
        f"(O'quvchi {block_days} kunga bloklanadi va sabab unga yuboriladi):",
        parse_mode="HTML", reply_markup=kb
    )


@router.message(AdminBlockMsg.waiting_for_message)
async def admin_confirm_block(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Bekor qilish":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return

    data = await state.get_data()
    user_id = int(data["target_user_id"])
    reason = message.text or "Sabab ko'rsatilmagan"

    attempt_count = await db.get_user_premium_attempt_count(user_id)
    block_days = 90 if attempt_count >= 2 else 30

    await db.block_user(user_id, reason, days=block_days)

    try:
        await message.bot.send_message(
            user_id,
            f"🚫 <b>Hisobingiz {block_days} kunga bloklandi!</b>\n\n"
            f"📝 <b>Sabab:</b> {reason}\n\n"
            f"⚠️ Bu muddat davomida faqat davomat funksiyasidan foydalanishingiz mumkin.\n"
            f"🔓 Blok <b>{block_days} kundan</b> keyin avtomatik ochiladi.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Blok xabari yuborishda xato: {e}")

    await state.clear()
    from handlers.student import get_user_keyboard
    await message.answer(
        f"✅ Foydalanuvchi <code>{user_id}</code> bloklandi.",
        parse_mode="HTML",
        reply_markup=get_user_keyboard(message.from_user.id)
    )
    await message.answer(
        "Kerak bo'lsa blokdan chiqarish:",
        reply_markup=unblock_kb(user_id)
    )


@router.callback_query(F.data.startswith("prem_unblock:"))
async def admin_unblock_user(callback: CallbackQuery, db: Database):
    if callback.from_user.id != PURE_ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    user_id = int(callback.data.split(":")[1])
    await db.unblock_user(user_id)
    try:
        await callback.bot.send_message(
            user_id,
            "🔓 <b>Bloklashingiz olib tashlandi!</b>\n\nBotdan to'liq foydalanishingiz mumkin.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("✅ Blok olib tashlandi!", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("prem_msg:"))
async def admin_msg_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != PURE_ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminPremiumMsg.waiting_for_message)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True)
    await callback.message.answer(
        f"📩 ID <code>{user_id}</code> ga xabar yozing:",
        parse_mode="HTML", reply_markup=kb
    )


@router.message(AdminPremiumMsg.waiting_for_message)
async def admin_send_msg(message: Message, state: FSMContext):
    if message.text == "⬅️ Bekor qilish":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
    data = await state.get_data()
    user_id = int(data["target_user_id"])
    try:
        await message.bot.send_message(
            user_id,
            f"📩 <b>Admindan xabar:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Xabar yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Yuborilmadi: {e}")
    await state.clear()
    from handlers.student import get_user_keyboard
    await message.answer("Menyuga qaytdingiz.", reply_markup=get_user_keyboard(message.from_user.id))


# ============================================================
# 4. PREMIUM PANEL — DURATION / BACK
# ============================================================

@router.callback_query(F.data == "prem_duration")
async def show_duration(callback: CallbackQuery, db: Database):
    await callback.answer()
    info = await db.get_premium_info(callback.from_user.id)
    if not info:
        await callback.answer("❌ Premium topilmadi.", show_alert=True)
        return
    import pytz
    tz_uz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(timezone.utc)
    exp = info["expires_at"]
    days_left = (exp - now).days
    hours_left = int((exp - now).seconds / 3600)
    activated_str = info["activated_at"].astimezone(tz_uz).strftime("%d.%m.%Y %H:%M")
    expires_str = exp.astimezone(tz_uz).strftime("%d.%m.%Y %H:%M")
    await callback.message.answer(
        f"💎 <b>Premium ma'lumotlaringiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ <b>Faollashgan:</b> {activated_str}\n"
        f"📅 <b>Tugaydi:</b> {expires_str}\n"
        f"⏳ <b>Qoldi:</b> {days_left} kun {hours_left} soat",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Panel", callback_data="prem_back_panel")]
        ])
    )


@router.callback_query(F.data == "prem_back_panel")
async def back_to_panel(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            "💎 <b>Premium Panel</b>\n\nImkoniyatni tanlang:",
            parse_mode="HTML",
            reply_markup=premium_panel_kb()
        )
    except Exception:
        await callback.message.answer(
            "💎 <b>Premium Panel</b>\n\nImkoniyatni tanlang:",
            parse_mode="HTML",
            reply_markup=premium_panel_kb()
        )


# ============================================================
# 5. AI SUHBAT (GEMINI)
# ============================================================

@router.callback_query(F.data == "prem_ai_chat")
async def start_ai_chat(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ AI suhbatdan chiqish")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        "🤖 <b>AI Ingliz Tili Ustozi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Ingliz tili bo'yicha istalgan savolingizni yozing:\n"
        "• Grammatika va so'z ma'nosi\n"
        "• Gap to'g'rimi? Tekshirish\n"
        "• Tarjima va misollar\n"
        "• O'rganish maslahatlari\n\n"
        "<i>Chiqish: «⬅️ AI suhbatdan chiqish»</i>",
        parse_mode="HTML", reply_markup=kb
    )
    await state.set_state(PremiumChat.waiting_for_message)


@router.message(PremiumChat.waiting_for_message)
async def handle_ai_message(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ AI suhbatdan chiqish":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer(
            "✅ AI suhbatdan chiqdingiz.",
            reply_markup=get_user_keyboard(message.from_user.id)
        )
        return

    if not message.text:
        await message.answer("⚠️ Iltimos, faqat matn yuboring.")
        return

    if not await db.is_premium(message.from_user.id):
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer(
            "❌ Premiumingiz tugagan. «💎 Premium» orqali yangilang.",
            reply_markup=get_user_keyboard(message.from_user.id)
        )
        return

    typing = await message.answer("🤖 <i>AI o'ylayapti...</i>", parse_mode="HTML")
    history = await db.get_ai_chat_history(message.from_user.id)
    response_text = await get_ai_response(message.text, list(history))
    await db.add_ai_chat_message(message.from_user.id, "user", message.text)
    await db.add_ai_chat_message(message.from_user.id, "model", response_text)
    try:
        await typing.delete()
    except Exception:
        pass

    # Convert Markdown to Telegram HTML
    import re, html as html_lib

    def md_to_html(text: str) -> str:
        # Escape HTML special chars first
        text = html_lib.escape(text)
        # ### headings -> <b>...</b>
        text = re.sub(r'(?m)^#{1,6}\s*(.+)$', r'<b>\1</b>', text)
        # **bold** -> <b>bold</b>
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # __bold__ -> <b>bold</b>
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        # *italic* or _italic_ -> <i>...</i>
        text = re.sub(r'\*([^*\n]+?)\*', r'<i>\1</i>', text)
        text = re.sub(r'_([^_\n]+?)_', r'<i>\1</i>', text)
        # `code` -> <code>code</code>
        text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
        # ──  or --- separators keep as is
        return text

    html_response = md_to_html(response_text)

    try:
        if len(html_response) > 3800:
            for i in range(0, len(html_response), 3800):
                await message.answer(f"🤖 <b>AI Ustoz:</b>\n\n{html_response[i:i+3800]}", parse_mode="HTML")
        else:
            await message.answer(f"🤖 <b>AI Ustoz:</b>\n\n{html_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Xabar yuborishda xatolik: {e}")
        try:
            await message.answer(f"🤖 AI Ustoz:\n\n{response_text[:4000]}")
        except Exception:
            await message.answer("❌ AI javobini yuborishda xatolik yuz berdi.")


@router.callback_query(F.data == "prem_clear_ai")
async def clear_ai(callback: CallbackQuery, db: Database):
    await callback.answer()
    await db.clear_ai_chat_history(callback.from_user.id)
    await callback.message.answer("🗑 AI suhbat tarixi tozalandi!")


# ============================================================
# 6. GURUHLAR STATISTIKASI (PREMIUM)
# ============================================================

@router.callback_query(F.data == "prem_group_stats")
async def show_group_stats(callback: CallbackQuery, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return

    groups = await db.get_all_groups_with_stats()
    if not groups:
        await callback.message.answer("📭 Guruhlar topilmadi.")
        return

    level_map = {"SMART GROUP": "💡 Smart", "MIDDLE CLASS": "⚖️ Middle", "LAZY TEAM": "🐌 Lazy"}
    text = "📊 <b>Barcha guruhlar statistikasi:</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for g in groups:
        g_level = level_map.get(g.get("group_level"), g.get("group_level") or "Belgilanmagan")
        text += (
            f"🏫 <b>{g['name']}</b>\n"
            f"   📈 Daraja: {g_level}\n"
            f"   👥 O'quvchilar: {g['student_count']} ta\n\n"
        )
        buttons.append([InlineKeyboardButton(
            text=f"🔍 {g['name']} — batafsil",
            callback_data=f"prem_gd:{g['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Panel", callback_data="prem_back_panel")])
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("prem_gd:"))
async def show_group_detail(callback: CallbackQuery, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return

    group_id = int(callback.data.split(":")[1])
    group = await db.get_group(group_id)
    if not group:
        await callback.message.answer("❌ Guruh topilmadi.")
        return

    students = await db.get_group_students_with_scores(group_id)
    top3 = await db.get_group_top_students(group_id, limit=3)
    level_map = {"SMART GROUP": "💡 Smart Group", "MIDDLE CLASS": "⚖️ Middle Class", "LAZY TEAM": "🐌 Lazy Team"}
    g_level = level_map.get(group.get("group_level"), group.get("group_level") or "Belgilanmagan")

    text = (
        f"🏫 <b>{group['name']}</b>\n"
        f"📈 Daraja: {g_level}\n"
        f"👥 O'quvchilar: {len(students)} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    if top3:
        text += "🏆 <b>Top 3 o'quvchi:</b>\n"
        for i, s in enumerate(top3):
            medals = ["🥇", "🥈", "🥉"]
            text += f"{medals[i]} {s['first_name']} {s['last_name']} — {s['cycle_score']} ball\n"
        text += "\n"

    text += "📋 <b>O'quvchilar (so'nggi 6 dars):</b>\n"
    lvl_emoji_map = {"SUPPORT": "💎", "CAPTAIN": "👑", "MAIN": "🎯", "LEARNER": "📖"}
    for s in students[:15]:
        scores_str = " | ".join(str(x) for x in s["recent_scores"]) if s["recent_scores"] else "—"
        lvl_e = lvl_emoji_map.get(s.get("student_level"), "👤")
        text += f"{lvl_e} {s['first_name']} — {s['grade']}\n   <i>{scores_str}</i>\n"

    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Guruhlar", callback_data="prem_group_stats")]
        ])
    )


# ============================================================
# 7. O'SISH GRAFIGI (PREMIUM)
# ============================================================

@router.callback_query(F.data == "prem_my_stats")
async def show_my_growth(callback: CallbackQuery, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return

    stats = await db.get_my_growth_stats(callback.from_user.id)
    cycles = stats.get("cycles", [])
    total_attendance = stats.get("total_attendance", 0)

    text = (
        f"📈 <b>Mening o'sish tahlilim</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎓 <b>Jami davomatlar:</b> {total_attendance} marta\n"
    )

    text += "\n📚 <b>Sikl tarixi:</b>\n"
    if cycles:
        prev_score = None
        for c in cycles:
            trend = ""
            if prev_score is not None:
                if c["total_score"] > prev_score:
                    trend = " 📈"
                elif c["total_score"] < prev_score:
                    trend = " 📉"
                else:
                    trend = " ➡️"
            text += f"  🔹 {c['cycle_number']}-sikl: {c['total_score']}/150 — {c['level']}{trend}\n"
            prev_score = c["total_score"]

        if len(cycles) >= 2:
            last, prev = cycles[-1]["total_score"], cycles[-2]["total_score"]
            if last > prev:
                text += "\n✅ <b>Trend:</b> Ko'tarilmoqdasiz! Ajoyib! 📈"
            elif last < prev:
                text += "\n⚠️ <b>Trend:</b> Tushmoqdasiz. Ko'proq harakat! 📉"
            else:
                text += "\n➡️ <b>Trend:</b> Bir xil o'qiyapsiz."
    else:
        text += "Hali sikl ma'lumotlari yo'q.\n"

    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Panel", callback_data="prem_back_panel")]
        ])
    )


# ============================================================
# 8. REFERRAL TIZIMI (PREMIUM)
# ============================================================

@router.callback_query(F.data == "prem_referral")
async def show_referral(callback: CallbackQuery, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return

    code = await db.get_or_create_referral_code(callback.from_user.id)
    stats = await db.get_referral_stats(callback.from_user.id)
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={code}"

    text = (
        f"🔗 <b>Sizning Referral Havolangiz</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Do'stlarga yuboring:\n<code>{ref_link}</code>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"  👥 Jami taklif: <b>{stats['total']}</b> ta\n"
        f"  ✅ Botda qolganlar: <b>{stats['staying']}</b> ta\n"
        f"  🎁 Mukofot uchun kerak: <b>{max(0, 10 - stats['staying'])}</b> ta\n\n"
        f"🎁 <b>Qoida:</b> 10 ta do'st ro'yxatdan o'tib botda qolsa — "
        f"<b>+30 kun Premium bepul!</b>\n\n"
        f"<i>Do'stingiz /start bosib ro'yxatdan o'tsa va botda qolsa hisoblanadi.</i>"
    )
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Panel", callback_data="prem_back_panel")]
        ])
    )


# ============================================================
# 9. BARCHA GURUHLAR NARXLARI (PREMIUM)
# ============================================================

@router.callback_query(F.data == "prem_all_fees")
async def show_all_fees(callback: CallbackQuery, db: Database):
    await callback.answer()
    if not await db.is_premium(callback.from_user.id):
        await callback.answer("❌ Faqat Premium uchun!", show_alert=True)
        return

    groups = await db.get_all_groups_with_stats()
    text = "💰 <b>Barcha guruhlar oylik to'lov ma'lumotlari:</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for g in groups:
        fee = g.get("monthly_fee") or "Belgilanmagan"
        deadline = g.get("fee_deadline") or "—"
        comment = g.get("fee_comment") or ""
        text += f"🏫 <b>{g['name']}</b>\n  💵 {fee}\n  📅 Muddat: {deadline}\n"
        if comment and comment != "-":
            text += f"  💬 {comment}\n"
        text += "\n"

    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Panel", callback_data="prem_back_panel")]
        ])
    )


# ============================================================
# 10. OYLIK TO'LOV — O'QUVCHI
# ============================================================

@router.message(F.text == "💰 Oylik to'lov", StateFilter(None))
async def show_monthly_fee(message: Message, db: Database):
    user = await db.get_user(message.from_user.id)

    # Admin uchun alohida panel — reply keyboard handler
    if message.from_user.id in ADMIN_IDS:
        groups = await db.get_all_groups()
        if not groups:
            await message.answer("📭 Guruhlar topilmadi.")
            return
        text = "💰 <b>Oylik To'lov Boshqaruvi</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        buttons = []
        for g in groups:
            fee = g.get("monthly_fee") or "Kiritilmagan"
            comment = g.get("fee_comment") or ""
            text += f"🏫 <b>{g['name']}</b>  →  {fee}\n"
            if comment and comment != "-" and comment != "–":
                text += f"   💬 {comment}\n"
            text += "\n"
            buttons.append([InlineKeyboardButton(text=f"✏️ {g['name']}", callback_data=f"fee_edit:{g['id']}")])
        await message.answer(text, parse_mode="HTML",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    # O'quvchi uchun
    if not user or user["status"] != "active":
        await message.answer("⚠️ Botdan foydalanish uchun avval ro'yxatdan o'ting.")
        return

    group_id = user.get("group_id")
    text = "💰 <b>Oylik To'lov Ma'lumotlari</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if group_id:
        group = await db.get_group(group_id)
        if group:
            fee = group.get("monthly_fee") or "Belgilanmagan"
            comment = group.get("fee_comment") or ""
            text += (
                f"🏫 <b>Sizning guruhingiz:</b> {group['name']}\n"
                f"💵 <b>Oylik to'lov:</b> {fee}\n"
            )
            if comment and comment != "-" and comment != "–":
                text += f"💬 <b>Izoh:</b> {comment}\n"
        else:
            text += "⚠️ Guruh ma'lumoti topilmadi.\n"
    else:
        text += "⚠️ Siz hali guruhga biriktirilmagansiz.\n"

    is_prem = await db.is_premium(message.from_user.id)
    if is_prem:
        buttons = [[InlineKeyboardButton(text="📊 Barcha guruhlar narxi", callback_data="prem_all_fees")]]
    else:
        buttons = [[InlineKeyboardButton(
            text="🔒 Barcha guruhlar narxi (Premium kerak)",
            callback_data="fee_premium_locked"
        )]]

    await message.answer(text, parse_mode="HTML",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "fee_premium_locked")
async def fee_locked(callback: CallbackQuery):
    await callback.answer(
        "🔒 Bu funksiya faqat Premium foydalanuvchilar uchun!\n"
        "«💎 Premium» tugmasini bosib sotib oling.",
        show_alert=True
    )


# ============================================================
# 11. OYLIK TO'LOV — ADMIN FSM
# ============================================================

@router.callback_query(F.data == "admin_monthly_fee")
async def admin_fee_list(callback: CallbackQuery, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    groups = await db.get_all_groups()
    if not groups:
        await callback.message.answer("📭 Guruhlar topilmadi.")
        return
    text = "💰 <b>Oylik To'lov Boshqaruvi</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    for g in groups:
        fee = g.get("monthly_fee") or "Kiritilmagan"
        comment = g.get("fee_comment") or ""
        text += f"🏫 <b>{g['name']}</b> — {fee}\n"
        if comment and comment != "-" and comment != "–":
            text += f"   💬 {comment}\n"
        buttons.append([InlineKeyboardButton(text=f"✏️ {g['name']}", callback_data=f"fee_edit:{g['id']}")])
    await callback.message.answer(text, parse_mode="HTML",
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("fee_edit:"))
async def admin_fee_edit(callback: CallbackQuery, state: FSMContext, db: Database):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q.", show_alert=True)
        return
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    group = await db.get_group(group_id)
    if not group:
        await callback.message.answer("❌ Guruh topilmadi.")
        return
    await state.update_data(group_id=group_id)
    await state.set_state(AdminMonthlyFee.waiting_for_fee)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True)
    await callback.message.answer(
        f"💵 <b>{group['name']}</b> guruhi oylik to'lov summasini kiriting:\n\n"
        "<i>Masalan: 300,000 so'm</i>",
        parse_mode="HTML", reply_markup=kb
    )


@router.message(AdminMonthlyFee.waiting_for_fee)
async def admin_fee_amount(message: Message, state: FSMContext):
    if message.text == "⬅️ Bekor qilish":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
    await state.update_data(fee=message.text.strip())
    await message.answer(
        "💬 <b>Qo'shimcha izoh yozing</b> (ixtiyoriy):\n\n"
        "<i>Masalan: Payme yoki Uzum orqali</i>\n\n"
        "Izohsiz o'tkazish uchun <b>–</b> yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(AdminMonthlyFee.waiting_for_comment)


@router.message(AdminMonthlyFee.waiting_for_comment)
async def admin_fee_comment(message: Message, state: FSMContext, db: Database):
    if message.text == "⬅️ Bekor qilish":
        await state.clear()
        from handlers.student import get_user_keyboard
        await message.answer("❌ Bekor qilindi.", reply_markup=get_user_keyboard(message.from_user.id))
        return
    data = await state.get_data()
    group_id = int(data["group_id"])
    fee = data["fee"]
    deadline = ""
    comment = message.text.strip() if message.text else "–"
    await db.set_group_monthly_fee(group_id, fee, deadline, comment)
    group = await db.get_group(group_id)
    await state.clear()
    from handlers.student import get_user_keyboard
    await message.answer(
        f"✅ <b>Muvaffaqiyatli oylik tolov kiritildi!</b>\n\n"
        f"🏫 Guruh: {group['name']}\n💵 Summa: {fee}\n💬 Izoh: {comment}",
        parse_mode="HTML",
        reply_markup=get_user_keyboard(message.from_user.id)
    )


# ============================================================
# 12. /MYPREMIUM
# ============================================================

@router.message(Command("mypremium"))
async def my_premium_command(message: Message, db: Database):
    if not await db.is_premium(message.from_user.id):
        await message.answer(
            "💎 Sizda hali Premium yo'q.\n\n«💎 Premium» tugmasini bosib sotib oling!"
        )
        return
    info = await db.get_premium_info(message.from_user.id)
    now = datetime.now(timezone.utc)
    days_left = (info["expires_at"] - now).days
    await message.answer(
        f"💎 <b>Sizning Premiumingiz</b>\n\n"
        f"⏳ <b>Qoldi:</b> {days_left} kun\n\n"
        "Premium paneliga kirish uchun «💎 Premium» tugmasini bosing.",
        parse_mode="HTML"
    )
