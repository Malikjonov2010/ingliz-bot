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
    user = await db.get_user(message.from_user.id)
    if user:
        if user['status'] == 'active':
            from handlers.student import get_user_keyboard
            await message.answer("✅ Siz botdan ro'yxatdan o'tgansiz va hisobingiz faol.\nBot faol ishlamoqda. Pastdagi menyudan tugmalar orqali o'zingizga kerakli narsani boshqarishingiz mumkin.", reply_markup=get_user_keyboard(message.from_user.id))
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
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text:
        phone_number = message.text
    else:
        await message.answer("⚠️ Iltimos, telefon raqamingizni yuboring yozib yuboring tugma orqali.")
        return
        
    await state.update_data(phone_number=phone_number)
    
    # Tugmani yo'qotish uchun vaqtinchalik xabar
    tmp_msg = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await tmp_msg.delete()
    except:
        pass
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔹 Beginner", callback_data="level:Beginner"), InlineKeyboardButton(text="🔹 Elementary", callback_data="level:Elementary")],
            [InlineKeyboardButton(text="🔸 Pre-Intermediate", callback_data="level:Pre-Intermediate"), InlineKeyboardButton(text="🔸 Intermediate", callback_data="level:Intermediate")],
            [InlineKeyboardButton(text="🔥 Upper-Intermediate", callback_data="level:Upper-Intermediate"), InlineKeyboardButton(text="🔥 Advanced", callback_data="level:Advanced")],
            [InlineKeyboardButton(text="🎓 IELTS", callback_data="level:IELTS"), InlineKeyboardButton(text="🏆 CEFR", callback_data="level:CEFR")]
        ]
    )
    
    await message.answer("📚 Qaysi guruhda o'qiysiz?\nIltimos, darajangizni tanlang:", reply_markup=keyboard)
    await state.set_state(Registration.waiting_for_level)

def get_days_keyboard(selected_days: list):
    days_map = {
        0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 
        3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"
    }
    
    kb = []
    row = []
    for i in range(7):
        mark = "✅ " if i in selected_days else ""
        btn = InlineKeyboardButton(text=f"{mark}{days_map[i]}", callback_data=f"toggle_day:{i}")
        row.append(btn)
        if len(row) == 2 or i == 6:
            kb.append(row)
            row = []
            
    kb.append([
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_level"),
        InlineKeyboardButton(text="💾 Saqlash (OK)", callback_data="confirm_days")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.callback_query(Registration.waiting_for_level, F.data.startswith("level:"))
async def process_level(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    level = callback.data.split(":")[1]
    await state.update_data(level=level)
    await state.update_data(selected_days=[])
    
    await callback.message.edit_text(
        f"✅ Siz **{level}** darajasini tanladingiz.\n\n"
        "🗓 Endi qachon o'qishingizni (kunlarni) tanlang va **Saqlash (OK)** tugmasini bosing:", 
        reply_markup=get_days_keyboard([]),
        parse_mode="Markdown"
    )
    await state.set_state(Registration.waiting_for_days)

@router.callback_query(Registration.waiting_for_days, F.data == "back_to_level")
async def back_to_level(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔹 Beginner", callback_data="level:Beginner"), InlineKeyboardButton(text="🔹 Elementary", callback_data="level:Elementary")],
            [InlineKeyboardButton(text="🔸 Pre-Intermediate", callback_data="level:Pre-Intermediate"), InlineKeyboardButton(text="🔸 Intermediate", callback_data="level:Intermediate")],
            [InlineKeyboardButton(text="🔥 Upper-Intermediate", callback_data="level:Upper-Intermediate"), InlineKeyboardButton(text="🔥 Advanced", callback_data="level:Advanced")],
            [InlineKeyboardButton(text="🎓 IELTS", callback_data="level:IELTS"), InlineKeyboardButton(text="🏆 CEFR", callback_data="level:CEFR")]
        ]
    )
    await callback.message.edit_text("📚 Qaysi guruhda o'qiysiz?\nIltimos, darajangizni tanlang:", reply_markup=keyboard)
    await state.set_state(Registration.waiting_for_level)

@router.callback_query(Registration.waiting_for_days, F.data.startswith("toggle_day:"))
async def toggle_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    day = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_days = data.get("selected_days", [])
    
    if day in selected_days:
        selected_days.remove(day)
    else:
        selected_days.append(day)
        
    await state.update_data(selected_days=selected_days)
    await callback.message.edit_reply_markup(reply_markup=get_days_keyboard(selected_days))

@router.callback_query(Registration.waiting_for_days, F.data == "confirm_days")
async def confirm_days(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_days = data.get("selected_days", [])
    
    if not selected_days:
        await callback.answer("⚠️ Kamida 1 ta kun tanlashingiz kerak!", show_alert=True)
        return
        
    await callback.answer()
    selected_days.sort()
    days_map = {
        0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 
        3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"
    }
    
    days_str = ", ".join([days_map[d] for d in selected_days])
    
    # Save the days as a JSON list in DB format
    await state.update_data(days_json=json.dumps(selected_days))
    
    confirm_text = f"📋 **Sizning ma'lumotlaringiz:**\n\n" \
                   f"👤 **Ism-familiya:** {data['first_name']} {data['last_name']}\n" \
                   f"📅 **Yosh:** {data['age']}\n" \
                   f"📞 **Raqam:** {data['phone_number']}\n" \
                   f"📚 **Daraja:** {data['level']}\n" \
                   f"🗓 **Dars kunlari:** Haftada {len(selected_days)} kun ({days_str})\n\n" \
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
            group_id=None,
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
