import asyncio, os
from database.db import Database
from dotenv import load_dotenv

load_dotenv()

async def test():
    db = Database(os.getenv('DATABASE_URL'))
    await db.connect()
    try:
        res = await db.create_group('test2', 'mon', '12', 123)
        print('ok', res)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
