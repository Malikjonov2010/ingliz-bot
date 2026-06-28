import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DATABASE_URL')
ADMIN_IDS = [int(i.strip()) for i in os.getenv('ADMIN_IDS', '').split(',') if i.strip()]

async def main():
    pool = await asyncpg.create_pool(dsn=DB_URL)
    async with pool.acquire() as conn:
        # Hozir bazada qanday userlar bor ko'ramiz
        users = await conn.fetch("SELECT telegram_id, first_name, last_name, status, is_admin FROM users")
        print("Hozirgi userlar:")
        for u in users:
            print(f"  id={u['telegram_id']} | {u['first_name']} {u['last_name']} | status={u['status']} | is_admin={u['is_admin']}")
        
        # is_admin=FALSE va admin_ids da yo'q bo'lganlarni o'chiramiz
        res = await conn.execute(
            "DELETE FROM users WHERE is_admin = FALSE AND telegram_id != ALL($1::bigint[])",
            ADMIN_IDS
        )
        print(f"\nO'chirildi: {res}")
        
        # Tekshiramiz
        remaining = await conn.fetch("SELECT telegram_id, first_name, last_name, status, is_admin FROM users")
        print("\nQolgan userlar:")
        for u in remaining:
            print(f"  id={u['telegram_id']} | {u['first_name']} {u['last_name']} | status={u['status']} | is_admin={u['is_admin']}")
    await pool.close()

asyncio.run(main())
