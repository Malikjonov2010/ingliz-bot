import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, DATABASE_URL
from database.db import Database
from handlers import registration, admin, student

async def main():
    logging.basicConfig(level=logging.INFO)
    
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is missing in the .env file.")
        return
    if not DATABASE_URL:
        logging.error("DATABASE_URL is missing in the .env file.")
        return

    # Initialize Database
    db = Database(DATABASE_URL)
    await db.connect()
    
    # Uncomment the next line to automatically create tables on startup
    await db.create_tables()

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Pass db to handlers via workflow_data (Dependency Injection)
    dp.workflow_data.update({'db': db})

    from handlers import registration, student, admin, admin_groups
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(admin_groups.router)
    dp.include_router(student.router)

    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish / Qayta ro'yxatdan o'tish"),
        BotCommand(command="delete_account", description="Akkauntni o'chirish")
    ]
    await bot.set_my_commands(commands)

    logging.info("Bot is starting...")
    
    import os
    port = os.getenv("PORT")
    if port:
        from aiohttp import web
        async def dummy_handler(request):
            return web.Response(text="English Bot is running smoothly!")
        app = web.Application()
        app.router.add_get('/', dummy_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', int(port))
        await site.start()
        logging.info(f"Dummy web server started on port {port} for Render.")

    try:
        await dp.start_polling(bot)
    finally:
        await db.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
