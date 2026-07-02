import re

with open('handlers/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. admin_groups_and_students
content = content.replace(
    'row = [InlineKeyboardButton(text=groups[i][\'name\'], callback_data=f"admin_lvl:{groups[i][\'name\']}")]',
    'row = [InlineKeyboardButton(text=groups[i][\'name\'], callback_data=f"admin_lvl:{groups[i][\'id\']}")]'
)
content = content.replace(
    'row.append(InlineKeyboardButton(text=groups[i+1][\'name\'], callback_data=f"admin_lvl:{groups[i+1][\'name\']}"))',
    'row.append(InlineKeyboardButton(text=groups[i+1][\'name\'], callback_data=f"admin_lvl:{groups[i+1][\'id\']}"))'
)

# 2. admin_level_menu
old_admin_level_menu = """@router.callback_query(F.data.startswith("admin_lvl:"))
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
    
    await callback.message.edit_text(f"📚 **{level} guruhi**\\n👥 O'quvchilar soni: {count}", parse_mode="Markdown", reply_markup=kb)"""

new_admin_level_menu = """@router.callback_query(F.data.startswith("admin_lvl:"))
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
    
    await callback.message.edit_text(f"📚 **{level_name} guruhi**\\n👥 O'quvchilar soni: {count}", parse_mode="Markdown", reply_markup=kb)"""

content = content.replace(old_admin_level_menu, new_admin_level_menu)

# 3. view_students_in_level
old_view_studs = """@router.callback_query(F.data.startswith("view_studs:"))
async def view_students_in_level(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    page = int(parts[2])
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)"""

new_view_studs = """@router.callback_query(F.data.startswith("view_studs:"))
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
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)"""

content = content.replace(old_view_studs, new_view_studs)

# 4. eval_students_list
old_eval_studs = """@router.callback_query(F.data.startswith("eval_studs:"))
async def eval_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)"""

new_eval_studs = """@router.callback_query(F.data.startswith("eval_studs:"))
async def eval_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE group_id = $1 AND status = 'active' ORDER BY created_at ASC", group_id)
    else:
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active' ORDER BY created_at ASC", level)"""

content = content.replace(old_eval_studs, new_eval_studs)

# 5. eval_grp_opts
old_eval_grp_opts = """@router.callback_query(F.data.startswith("eval_grp:"))
async def eval_grp_opts(callback: CallbackQuery):
    level = callback.data.split(":")[1]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 SMART GROUP",  callback_data=f"save_g_lvl:{level}:SMART GROUP")],
        [InlineKeyboardButton(text="📚 MIDDLE CLASS", callback_data=f"save_g_lvl:{level}:MIDDLE CLASS")],
        [InlineKeyboardButton(text="😴 LAZY TEAM",   callback_data=f"save_g_lvl:{level}:LAZY TEAM")],
        [InlineKeyboardButton(text="🔙 Orqaga",       callback_data=f"admin_lvl:{level}")]
    ])
    
    await callback.message.edit_text(
        f"🏫 <b>{level}</b> guruhi uchun nom/daraja tanlang:",
        parse_mode="HTML",
        reply_markup=kb
    )"""

new_eval_grp_opts = """@router.callback_query(F.data.startswith("eval_grp:"))
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
    )"""

content = content.replace(old_eval_grp_opts, new_eval_grp_opts)

# 6. save_grp_lvl
old_save_grp_lvl = """@router.callback_query(F.data.startswith("save_g_lvl:"))
async def save_grp_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    grp_level = parts[2]
    
    async with db.pool.acquire() as connection:
        await connection.execute(\"\"\"
            UPDATE groups SET group_level = $2 WHERE name = $1
        \"\"\", level, grp_level)"""

new_save_grp_lvl = """@router.callback_query(F.data.startswith("save_g_lvl:"))
async def save_grp_lvl(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    level = parts[1]
    grp_level = parts[2]
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            await connection.execute(\"\"\"
                UPDATE groups SET group_level = $2 WHERE id = $1
            \"\"\", group_id, grp_level)
    else:
        async with db.pool.acquire() as connection:
            await connection.execute(\"\"\"
                UPDATE groups SET group_level = $2 WHERE name = $1
            \"\"\", level, grp_level)"""

content = content.replace(old_save_grp_lvl, new_save_grp_lvl)

# 7. score_students_list
old_score_list = """@router.callback_query(F.data.startswith("score_list:"))
async def score_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    async with db.pool.acquire() as connection:
        students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active'", level)"""

new_score_list = """@router.callback_query(F.data.startswith("score_list:"))
async def score_students_list(callback: CallbackQuery, db: Database):
    level = callback.data.split(":")[1]
    
    if level.isdigit():
        group_id = int(level)
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE group_id = $1 AND status = 'active'", group_id)
    else:
        async with db.pool.acquire() as connection:
            students = await connection.fetch("SELECT * FROM users WHERE level = $1 AND status = 'active'", level)"""

content = content.replace(old_score_list, new_score_list)

# 8. astud_prof
old_astud_prof = """    level = student.get('level')
    back_cb = f"admin_lvl:{level}" if level else "admin_levels_menu\""""

new_astud_prof = """    level = student.get('group_id') or student.get('level')
    back_cb = f"admin_lvl:{level}" if level else "admin_levels_menu\""""

content = content.replace(old_astud_prof, new_astud_prof)

# 9. ask_for_score
old_ask_score = """    group_name = student.get('level')
    if not group_name:
        await callback.answer("O'quvchining guruhi belgilanmagan.", show_alert=True)
        return
        
    async with db.pool.acquire() as connection:
        group = await connection.fetchrow("SELECT days FROM groups WHERE name = $1", group_name)
    
    if not group or not group['days']:
        await callback.answer("Guruh yoki uning kunlari belgilanmagan.", show_alert=True)
        return"""

new_ask_score = """    group_id = student.get('group_id')
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
        return"""

content = content.replace(old_ask_score, new_ask_score)

# Update group_param for back button
old_group_param = """    group_param = data[2] if back_to_list and len(data) > 2 else group_name"""
new_group_param = """    group_param = data[2] if back_to_list and len(data) > 2 else (student.get('group_id') or group_name)"""
content = content.replace(old_group_param, new_group_param)


with open('handlers/admin.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Modified handlers/admin.py successfully.")
