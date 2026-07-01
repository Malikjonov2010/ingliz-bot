from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from states.register_states import Registration
from database.db import Database
from config import ADMIN_IDS
import json
from datetime import datetime

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database):
    await state.clear()

    # Referral kod tekshiruvi: /start ref_XXXXX
    start_args = message.text.split(maxsplit=1)
    if len(start_args) > 1 and start_args[1].startswith("ref_"):
        referral_code = start_args[1]
        try:
            await db.record_referral(referral_code, message.from_user.id)
        except Exception:
            pass
    
    if message.from_user.id in ADMIN_IDS:
        from handlers.student import get_user_keyboard
        await message.answer(
            f"👋 Assalomu alaykum, <b>Ustoz (Admin)</b>!\n\n"
            f"Siz tizimga admin sifatida kirdingiz. Quyidagi panel orqali botni boshqarishingiz mumkin:",
            parse_mode="HTML",
            reply_markup=get_user_keyboard(message.from_user.id)
        )
        return

    user = await db.get_user(message.from_user.id)
    if user:
        if user['status'] == 'active':
            from handlers.student import get_user_keyboard
            
            bio = user.get('teacher_bio')
            bio_text = f"\n\n💡 **Ustozingizdan sizga maslahat/fikr:**\n_{bio}_\n" if bio else ""
            
            await message.answer(
                f"✅ Siz botdan ro'yxatdan o'tgansiz va hisobingiz faol.\n"
                f"Bot faol ishlamoqda. Pastdagi menyudan tugmalar orqali o'zingizga kerakli narsani boshqarishingiz mumkin."
                f"{bio_text}", 
                reply_markup=get_user_keyboard(message.from_user.id),
                parse_mode="Markdown"
            )
        elif user['status'] == 'pending':
            await message.answer("⏳ Sizning hisobingiz admin tomonidan tasdiqlanishini kutmoqda.")
        elif user['status'] == 'rejected':
            await message.answer("❌ Sizning ro'yxatdan o'tish so'rovingiz rad etilgan.")
        return

    welcome_text = f"👋 Assalomu alaykum, **{message.from_user.first_name}**!\n\n" \
                   f"🌟 **Muhammaddiyor courses** rasmiy botiga xush kelibsiz!\n\n" \
                   f"Bu bot orqali siz o'z davomatingizni belgilashingiz, natijalaringizni kuzatishingiz va o'qituvchilar bilan bog'lanishingiz mumkin. " \
                   f"Ro'yxatdan o'tish uchun pastdagi tugmani bosing! 👇"
                   
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Ro'yxatdan o'tish")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=keyboard)

@router.message(F.text == "📝 Ro'yxatdan o'tish")
async def start_registration(message: Message, state: FSMContext):
    await message.answer("✍️ Iltimos, ism va familiyangizni to'liq kiriting:\n(Masalan: Aliyev Vali)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.waiting_for_full_name)

@router.message(Registration.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer("⚠️ Iltimos, ism va familiyangizni to'liq kiriting (kamida 2 ta so'z)!")
        return
        
    parts = name.split(maxsplit=1)
    await state.update_data(first_name=parts[0], last_name=parts[1])
    
    await message.answer("📅 Yoshingizni kiriting (masalan: 16):")
    await state.set_state(Registration.waiting_for_age)

@router.message(Registration.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, yoshingizni faqat raqamlarda kiriting!")
        return
        
    age = int(message.text)
    if age < 10 or age > 60:
        await message.answer("⚠️ Kechirasiz, yosh 10 dan 60 gacha bo'lishi kerak. Iltimos to'g'ri yoshni kiriting:")
        return
        
    await state.update_data(age=age)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("📞 Telefon raqamingizni pastdagi tugma orqali yuboring:", reply_markup=keyboard)
    await state.set_state(Registration.waiting_for_phone)

@router.message(Registration.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext, db: Database):
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text:
        phone_number = message.text
    else:
        await message.answer("⚠️ Iltimos, telefon raqamingizni yuboring yozib yuboring tugma orqali.")
        return
        
    await state.update_data(phone_number=phone_number)
    
    tmp_msg = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await tmp_msg.delete()
    except:
        pass
    
    groups = await db.get_all_groups()
    if not groups:
        await message.answer("Hozircha guruhlar mavjud emas. Iltimos, keyinroq urinib ko'ring yoki adminga murojaat qiling.")
        await state.clear()
        return
        
    from utils import sort_groups, shorten_days
    groups = sort_groups(groups)
    
    kb = []
    from handlers.admin_groups import GROUP_LEVEL_LABELS
    for g in groups:
        lvl_raw = g['group_level']
        lvl = GROUP_LEVEL_LABELS.get(lvl_raw, lvl_raw) if lvl_raw else ""
        lvl_text = f" | {lvl}" if lvl else ""
        short_d = shorten_days(g['days'])
        kb.append([InlineKeyboardButton(text=f"🏫 {g['name']}{lvl_text} ({short_d} | {g['time']})", callback_data=f"level:{g['id']}")])

        
    await message.answer("📚 Qaysi guruhda o'qiysiz?\nIltimos, guruhingizni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(Registration.waiting_for_level)

@router.callback_query(Registration.waiting_for_level, F.data.startswith("level:"))
async def process_level(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    group_id = int(callback.data.split(":")[1])
    group = await db.get_group(group_id)
    
    await state.update_data(level=group['name'])
    await state.update_data(days_json=group['days'])
    await state.update_data(group_id=group_id)
    
    data = await state.get_data()
    
    confirm_text = f"📋 **Sizning ma'lumotlaringiz:**\n" \
                   f"━━━━━━━━━━━━━━━━━━━\n" \
                   f"📛 **Ism-familiya:** {data['first_name']} {data['last_name']}\n" \
                   f"🎂 **Yosh:** {data['age']}\n" \
                   f"📞 **Raqam:** {data['phone_number']}\n" \
                   f"━━━━━━━━━━━━━━━━━━━\n" \
                   f"🏫 **Guruh:** {group['name']}\n" \
                   f"🗓 **Kunlar:** {group['days']}\n" \
                   f"⏰ **Vaqti:** {group['time']}\n" \
                   f"━━━━━━━━━━━━━━━━━━━\n\n" \
                   f"Hamma ma'lumotlar to'g'rimi?"
                   
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="final_confirm")],
            [InlineKeyboardButton(text="🔄 Qaytadan kiritish", callback_data="restart_reg")]
        ]
    )
    
    await callback.message.edit_text(confirm_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Registration.waiting_for_confirmation)

@router.callback_query(Registration.waiting_for_confirmation, F.data == "restart_reg")
async def restart_reg(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    # Mocking a message to restart
    fake_msg = callback.message
    fake_msg.text = "📝 Ro'yxatdan o'tish"
    await start_registration(fake_msg, state)
    await callback.message.delete()

@router.callback_query(Registration.waiting_for_confirmation, F.data == "final_confirm")
async def final_confirm(callback: CallbackQuery, state: FSMContext, db: Database):
    await callback.answer()
    data = await state.get_data()
    user_id = callback.from_user.id
    
    try:
        await db.add_user(
            telegram_id=user_id,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            age=data.get('age', 0),
            phone_number=data.get('phone_number', ''),
            group_id=data.get('group_id'),
            level=data.get('level', ''),
            days=data.get('days_json', '[]'),
            username=callback.from_user.username
        )
        
        # Set status to active so they can use the bot immediately
        await db.update_user_status(user_id, 'active')
        
        # Ro'yxatdan o'tgach referral staying ni belgilaymiz
        try:
            await db.mark_referral_staying(user_id)
        except Exception:
            pass

        await state.clear()
        
        from handlers.student import get_user_keyboard
        
        success_text = "🎉 **Tabriklaymiz! Botga xush kelibsiz!**\n\nPastdagi menyudan foydalanishingiz mumkin."
        
        await callback.message.delete()
        await callback.message.answer(success_text, reply_markup=get_user_keyboard(callback.from_user.id), parse_mode="Markdown")
    except Exception as e:
        await callback.message.answer(f"⚠️ Xatolik yuz berdi: {str(e)}\nIltimos, qaytadan urinib ko'ring yoki adminga murojaat qiling.")
        return
    
    group = await db.get_group(data.get('group_id'))
    group_time = group['time'] if group else 'Noma`lum'
    
    from utils import shorten_days
    short_d = shorten_days(data.get('days_json', '[]'))
    
    # Notify admins asynchronously
    profile_url = f"tg://user?id={user_id}"
    reg_username = "@" + callback.from_user.username if callback.from_user.username else "Yo'q"
    admin_text = (
        f"🆕 **Yangi O'quvchi**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📛 **O'quvchi:** {data['first_name']} {data['last_name']}\n"
        f"🔗 **Username:** {reg_username}\n"
        f"🎂 **Yosh:** {data['age']}\n"
        f"📞 **Raqam:** {data['phone_number']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏫 **Guruh:** {data.get('level', '')}\n"
        f"🗓 **Kunlar:** {short_d}\n"
        f"⏰ **Guruh vaqti:** {group_time}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"👤 **Profil:** [{data['first_name']}]({profile_url})\n"
        f"🎓 **O'quvchi maqomi:** Hali belgilanmagan\n"
        f"⏳ **Ro'yxatdan o'tgan vaqti:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    
    from utils import notify_admins_async
    await notify_admins_async(callback.bot, admin_text, ADMIN_IDS)
