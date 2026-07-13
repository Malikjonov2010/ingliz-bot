from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from database.db import Database

class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        db: Database = data.get('db')
        user_id = event.from_user.id
        
        if db:
            try:
                await db.increment_activity(user_id)
            except Exception:
                pass
                
        return await handler(event, data)
