import asyncio
from database.db import Database
from config import DATABASE_URL

async def insert_admins():
    db = Database(DATABASE_URL)
    await db.connect()
    
    admins = [
        (7053301759, "Admin", "1", "active", True),
        (1031009770, "Admin", "2", "active", True)
    ]
    
    async with db.pool.acquire() as conn:
        for telegram_id, first_name, last_name, status, is_admin in admins:
            await conn.execute("""
                INSERT INTO users (telegram_id, first_name, last_name, age, phone_number, status, is_admin)
                VALUES ($1, $2, $3, 0, '0', $4, $5)
                ON CONFLICT (telegram_id) DO UPDATE SET is_admin = $5, status = $4
            """, telegram_id, first_name, last_name, status, is_admin)
            print(f"Inserted/Updated admin: {telegram_id}")
            
    await db.close()

if __name__ == "__main__":
    asyncio.run(insert_admins())
