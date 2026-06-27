import asyncpg
import logging
from typing import Optional, List
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=1,
                max_size=10,
                command_timeout=60,
                statement_cache_size=0
            )
            logger.info("Database connection pool created successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to the database: {e}")
            raise

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed.")

    async def create_tables(self):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        
        models_path = os.path.join(os.path.dirname(__file__), 'models.sql')
        with open(models_path, 'r') as file:
            sql = file.read()
            
        async with self.pool.acquire() as connection:
            await connection.execute(sql)
            logger.info("Database tables initialized.")
            
            rows = await connection.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'attendance'")
            cols = [r[0] for r in rows]
            logger.info(f"DEBUG: attendance table columns are: {cols}")

    async def add_user(self, telegram_id: int, first_name: str, last_name: str, age: int, phone_number: str, group_id: Optional[int] = None, level: str = None, days: str = None) -> None:
        query = """
            INSERT INTO users (telegram_id, first_name, last_name, age, phone_number, group_id, level, days)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (telegram_id) DO UPDATE SET 
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            age = EXCLUDED.age,
            phone_number = EXCLUDED.phone_number,
            group_id = EXCLUDED.group_id,
            level = EXCLUDED.level,
            days = EXCLUDED.days;
        """
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id, first_name, last_name, age, phone_number, group_id, level, days)

    async def get_user(self, telegram_id: int) -> Optional[asyncpg.Record]:
        query = "SELECT * FROM users WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, telegram_id)
            
    async def update_user_status(self, telegram_id: int, status: str) -> None:
        query = "UPDATE users SET status = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id, status)
            
    async def get_all_groups(self) -> List[asyncpg.Record]:
        query = "SELECT id, name FROM groups"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query)
            
    async def get_group_name(self, group_id: int) -> str:
        query = "SELECT name FROM groups WHERE id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, group_id)

    async def create_group(self, name: str, teacher_id: int = None) -> int:
        query = "INSERT INTO groups (name, teacher_id) VALUES ($1, $2) RETURNING id"
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, name, teacher_id)

    async def mark_attendance(self, user_id: int, today_date, is_present: bool = True, reason: str = None) -> tuple[bool, str]:
        """Attempts to mark attendance. Returns (Success, Message)."""
        async with self.pool.acquire() as connection:
            check_query = "SELECT 1 FROM attendance WHERE user_id = $1 AND date = $2"
            exists = await connection.fetchval(check_query, user_id, today_date)
            
            if exists:
                return False, "❌ Siz bugun davomatdan o'tgansiz."
                
            insert_query = """
                INSERT INTO attendance (user_id, date, is_present, reason) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, date) DO NOTHING
                RETURNING id;
            """
            result = await connection.fetchval(insert_query, user_id, today_date, is_present, reason)
            
            if result:
                status_str = "Keldi" if is_present else "Kelmadi"
                return True, f"✅ Davomat belgilandi ({status_str})."
            else:
                return False, "❌ Siz bugun davomatdan o'tgansiz."

    async def get_group_students(self, group_id: int) -> List[asyncpg.Record]:
        query = "SELECT telegram_id, first_name, last_name FROM users WHERE group_id = $1 AND status = 'active'"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, group_id)
            
    async def add_score(self, user_id: int, score: int) -> tuple[int, int]:
        """Returns (lesson_number, total_cycle_score). Calculates if cycle is complete."""
        async with self.pool.acquire() as connection:
            # Determine lesson number for the current cycle
            # Using subquery limits correctly
            count_query = "SELECT COUNT(*) FROM scores WHERE user_id = $1 AND id > COALESCE((SELECT MAX(id) FROM scores WHERE user_id = $1 AND lesson_number = 6), 0)"
            current_count = await connection.fetchval(count_query, user_id)
            lesson_num = current_count + 1
            
            # Insert score
            await connection.execute("INSERT INTO scores (user_id, lesson_number, score) VALUES ($1, $2, $3)", user_id, lesson_num, score)
            
            # Sum for current cycle
            sum_query = "SELECT SUM(score) FROM scores WHERE user_id = $1 AND id > COALESCE((SELECT MAX(id) FROM scores WHERE user_id = $1 AND lesson_number = 6), 0)"
            total = await connection.fetchval(sum_query, user_id) or score
            
            return lesson_num, total
            
    async def complete_cycle(self, user_id: int, total_score: int) -> tuple[str, str]:
        """Completes a cycle and returns (Badge Name, Emoji)."""
        percentage = (total_score / 150) * 100
        level = "Weak"
        emoji = "🔴"
        if 140 <= total_score <= 150:
            level = "Excellent"
            emoji = "🥇"
        elif 120 <= total_score <= 139:
            level = "Very Good"
            emoji = "🟢"
        elif 100 <= total_score <= 119:
            level = "Good"
            emoji = "🟡"
        elif 80 <= total_score <= 99:
            level = "Needs Improvement"
            emoji = "🟠"
            
        async with self.pool.acquire() as connection:
            cycle_num_query = "SELECT COALESCE(MAX(cycle_number), 0) + 1 FROM cycles WHERE user_id = $1"
            c_num = await connection.fetchval(cycle_num_query, user_id)
            
            await connection.execute(
                "INSERT INTO cycles (user_id, cycle_number, total_score, percentage, level) VALUES ($1, $2, $3, $4, $5)",
                user_id, c_num, total_score, percentage, f"{level} {emoji}"
            )
            
        return level, emoji
        
    async def get_user_stats(self, user_id: int) -> dict:
        async with self.pool.acquire() as connection:
            last_score_rec = await connection.fetchrow("SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT 1", user_id)
            last_score = last_score_rec['score'] if last_score_rec else 0
            
            sum_query = "SELECT SUM(score) FROM scores WHERE user_id = $1 AND id > COALESCE((SELECT MAX(id) FROM scores WHERE user_id = $1 AND lesson_number = 6), 0)"
            current_cycle_total = await connection.fetchval(sum_query, user_id) or 0
            
            cycles = await connection.fetch("SELECT cycle_number, total_score, level FROM cycles WHERE user_id = $1 ORDER BY cycle_number DESC", user_id)
            
            return {
                "last_score": last_score,
                "current_cycle_total": current_cycle_total,
                "history": cycles
            }

    async def set_deletion_code(self, telegram_id: int, code: str) -> None:
        query = "UPDATE users SET deletion_code = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id, code)
            
    async def delete_user(self, telegram_id: int) -> None:
        query = "DELETE FROM users WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id)

    async def set_group_level(self, group_id: int, level: str) -> None:
        query = "UPDATE groups SET group_level = $2 WHERE id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, group_id, level)

    async def set_student_level(self, user_id: int, level: str) -> None:
        query = "UPDATE users SET student_level = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, level)

    async def get_active_users(self) -> List[asyncpg.Record]:
        query = "SELECT telegram_id FROM users WHERE status = 'active'"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query)
