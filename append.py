import os

content = """
@router.message()
async def catch_all_messages(message: Message, state: FSMContext, db: Database):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("⚠️ Kechirasiz, men bu xabarni tushunmadim. Iltimos, menyudagi tugmalardan foydalaning.")
    else:
        await message.answer("⚠️ Noto'g'ri buyruq yoki format. Bekor qilish uchun /start ni bosing.")
"""

with open("handlers/student.py", "a", encoding="utf-8") as f:
    f.write(content)
print("Done")
