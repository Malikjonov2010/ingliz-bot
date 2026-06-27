from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from states.register_states import Registration
from database.db import Database
from config import ADMIN_IDS
import json

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database):
    await state.clear()
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
        
    kb = []
    for g in groups:
        kb.append([InlineKeyboardButton(text=f"🏫 {g['name']} ({g['days']} | {g['time']})", callback_data=f"level:{g['id']}")])
        
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
    
    confirm_text = f"📋 **Sizning ma'lumotlaringiz:**\n\n" \
                   f"👤 **Ism-familiya:** {data['first_name']} {data['last_name']}\n" \
                   f"📅 **Yosh:** {data['age']}\n" \
                   f"📞 **Raqam:** {data['phone_number']}\n" \
                   f"🏫 **Guruh:** {group['name']}\n" \
                   f"🗓 **Dars vaqti:** {group['days']} | {group['time']}\n\n" \
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
            days=data.get('days_json', '[]')
        )
        
        # Set status to active so they can use the bot immediately
        await db.update_user_status(user_id, 'active')
        
        await state.clear()
        
        from handlers.student import get_user_keyboard
        
        success_text = "🎉 **Tasdiqlangandan so'ng sizning profilingiz ochildi va pastdagi tugmalar orqali foydalanishingiz mumkin.**"
        
        await callback.message.delete()
        await callback.message.answer(success_text, reply_markup=get_user_keyboard(callback.from_user.id), parse_mode="Markdown")
    except Exception as e:
        await callback.message.answer(f"⚠️ Xatolik yuz berdi: {str(e)}\nIltimos, qaytadan urinib ko'ring yoki adminga murojaat qiling.")
        return
    
    # Notify admins asynchronously
    profile_url = f"tg://user?id={user_id}"
    admin_text = f"🆕 **Yangi O'quvchi**\n\n" \
                 f"👤 **O'quvchi:** [{data['first_name']} {data['last_name']}]({profile_url})\n" \
                 f"📅 **Yosh:** {data['age']}\n" \
                 f"📞 **Raqam:** {data['phone_number']}\n" \
                 f"🆔 **ID:** `{user_id}`\n" \
                 f"📚 **Guruh (Kurs):** {data['level']}\n" \
                 f"⚠️ **O'quvchi darajasi:** Hali belgilanmagan\n"
    
    import asyncio
    from utils import notify_admins_async
    asyncio.create_task(notify_admins_async(callback.bot, admin_text, ADMIN_IDS))
