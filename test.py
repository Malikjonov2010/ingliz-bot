import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv('.env')

async def run():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    try:
        await conn.execute('ALTER TABLE attendance ADD UNIQUE (user_id, date);')
        print("Unique constraint added.")
    except Exception as e:
        print("Error adding constraint:", e)
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
