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

    async def add_user(self, telegram_id: int, first_name: str, last_name: str, age: int, phone_number: str, group_id: Optional[int] = None, level: str = None, days: str = None, username: str = None) -> None:
        query = """
            INSERT INTO users (telegram_id, first_name, last_name, age, phone_number, group_id, level, days, username)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (telegram_id) DO UPDATE SET 
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            age = EXCLUDED.age,
            phone_number = EXCLUDED.phone_number,
            group_id = EXCLUDED.group_id,
            level = EXCLUDED.level,
            days = EXCLUDED.days,
            username = EXCLUDED.username;
        """
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id, first_name, last_name, age, phone_number, group_id, level, days, username)

    async def get_user(self, telegram_id: int) -> Optional[asyncpg.Record]:
        query = "SELECT * FROM users WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, telegram_id)
            
    async def update_user_status(self, telegram_id: int, status: str) -> None:
        query = "UPDATE users SET status = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, telegram_id, status)
            
    async def get_active_users(self) -> List[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            return await connection.fetch("SELECT * FROM users WHERE status = 'active'")

    async def get_all_groups(self) -> List[asyncpg.Record]:
        query = "SELECT id, name, days, time, group_level, teacher_id, monthly_fee, fee_deadline, fee_comment FROM groups ORDER BY id ASC"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query)
            
    async def get_group_name(self, group_id: int) -> str:
        query = "SELECT name FROM groups WHERE id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, group_id)

    async def get_group(self, group_id: int) -> asyncpg.Record:
        query = "SELECT * FROM groups WHERE id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, group_id)

    async def create_group(self, name: str, days: str, time: str, teacher_id: int = None, group_level: str = None) -> int:
        query = "INSERT INTO groups (name, days, time, teacher_id, group_level) VALUES ($1, $2, $3, $4, $5) RETURNING id"
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, name, days, time, teacher_id, group_level)
            
    async def update_group(self, group_id: int, name: str, days: str, time: str, group_level: str = None) -> None:
        query = "UPDATE groups SET name = $2, days = $3, time = $4, group_level = $5 WHERE id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, group_id, name, days, time, group_level)

    async def delete_group(self, group_id: int) -> None:
        """Delete a group and unlink all students from it."""
        async with self.pool.acquire() as connection:
            # O'quvchilarni guruhdan uzib qo'yamiz (o'chirilmaydi, faqat group_id NULL bo'ladi)
            await connection.execute(
                "UPDATE users SET group_id = NULL WHERE group_id = $1", group_id
            )
            await connection.execute("DELETE FROM groups WHERE id = $1", group_id)


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
            total_count = await connection.fetchval("SELECT COUNT(*) FROM scores WHERE user_id = $1", user_id)
            lesson_num = (total_count % 6) + 1
            
            await connection.execute("INSERT INTO scores (user_id, lesson_number, score) VALUES ($1, $2, $3)", user_id, lesson_num, score)
            
            # Sum for current cycle (including the one just inserted)
            # The current cycle has `lesson_num` scores. We can fetch the last `lesson_num` scores.
            sum_query = f"SELECT SUM(score) FROM (SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT {lesson_num}) sub"
            total = await connection.fetchval(sum_query, user_id) or score
            
            return lesson_num, total
            
    async def can_send_teacher_message(self, user_id: int) -> bool:
        """Odatiy foydalanuvchi uchun kuniga 1 ta limit."""
        from datetime import date
        async with self.pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT COUNT(*) FROM message_logs WHERE user_id = $1 AND DATE(sent_at) = $2",
                user_id, date.today()
            )
            return count < 1


            if row['is_blocked'] and row['blocked_until']:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if row['blocked_until'] > now:
                    return True
                else:
                    # Expired
                    await connection.execute(
                        "UPDATE users SET is_blocked = FALSE, blocked_until = NULL WHERE telegram_id = $1",
                        user_id
                    )
                    return False
            return False




            
    async def has_score_today(self, user_id: int) -> bool:
        async with self.pool.acquire() as connection:
            count = await connection.fetchval("SELECT COUNT(*) FROM scores WHERE user_id = $1 AND date = CURRENT_DATE", user_id)
            return count > 0

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
            
            # Calculate attendance count for the last 6 lessons' time frame
            # We can simply fetch the number of presences since the last cycle completed_date
            last_cycle_date = await connection.fetchval("SELECT MAX(completed_date) FROM cycles WHERE user_id = $1", user_id)
            if last_cycle_date:
                att_count = await connection.fetchval("SELECT COUNT(*) FROM attendance WHERE user_id = $1 AND is_present = TRUE AND date > $2", user_id, last_cycle_date)
            else:
                att_count = await connection.fetchval("SELECT COUNT(*) FROM attendance WHERE user_id = $1 AND is_present = TRUE", user_id)
                
            att_count = att_count or 0
            
            await connection.execute(
                "INSERT INTO cycles (user_id, cycle_number, total_score, percentage, level, attendance_count) VALUES ($1, $2, $3, $4, $5, $6)",
                user_id, c_num, total_score, percentage, f"{level} {emoji}", att_count
            )
            
            # Check for 3 consecutive Excellent cycles
            recent_cycles = await connection.fetch("SELECT level FROM cycles WHERE user_id = $1 ORDER BY cycle_number DESC LIMIT 3", user_id)
            
            is_eligible_for_premium = False
            if len(recent_cycles) == 3 and all('Excellent' in c['level'] for c in recent_cycles) and (c_num % 3 == 0):
                is_eligible_for_premium = True
            
        return level, emoji, is_eligible_for_premium
        
    async def get_user_stats(self, user_id: int) -> dict:
        async with self.pool.acquire() as connection:
            last_score_rec = await connection.fetchrow("SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT 1", user_id)
            last_score = last_score_rec['score'] if last_score_rec else 0
            
            total_count = await connection.fetchval("SELECT COUNT(*) FROM scores WHERE user_id = $1", user_id)
            if total_count == 0:
                current_cycle_scores = []
                current_cycle_total = 0
            else:
                cycle_count = total_count % 6
                if cycle_count == 0:
                    cycle_count = 6
                current_cycle_scores = await connection.fetch(f"SELECT lesson_number, score FROM (SELECT id, lesson_number, score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT {cycle_count}) sub ORDER BY id ASC", user_id)
                current_cycle_total = sum(s['score'] for s in current_cycle_scores)
            
            cycles = await connection.fetch("SELECT cycle_number, total_score, level, attendance_count FROM cycles WHERE user_id = $1 ORDER BY cycle_number DESC", user_id)
            
            attendance_count = await connection.fetchval("SELECT COUNT(*) FROM attendance WHERE user_id = $1 AND is_present = TRUE", user_id) or 0
            
            user_info = await connection.fetchrow("SELECT student_level, teacher_bio, performance_grade FROM users WHERE telegram_id = $1", user_id)
            
            return {
                "last_score": last_score,
                "current_cycle_total": current_cycle_total,
                "history": cycles,
                "current_cycle_scores": current_cycle_scores,
                "attendance_count": attendance_count,
                "student_level": user_info['student_level'] if user_info else None,
                "teacher_bio": user_info['teacher_bio'] if user_info else None,
                "performance_grade": user_info['performance_grade'] if user_info else None
            }

    async def set_performance_grade(self, user_id: int, grade: str) -> None:
        query = "UPDATE users SET performance_grade = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, grade)

    async def update_teacher_bio(self, user_id: int, bio: str) -> None:
        query = "UPDATE users SET teacher_bio = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, bio)

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
        query = "UPDATE users SET student_level = $2, student_level_updated_at = CURRENT_TIMESTAMP WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, level)

    


    async def is_blocked(self, user_id: int) -> bool:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT is_blocked, blocked_until FROM users WHERE telegram_id = $1", 
                user_id
            )
            if not row:
                return False
            if row['is_blocked'] and row['blocked_until']:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if row['blocked_until'] > now:
                    return True
                else:
                    await connection.execute(
                        "UPDATE users SET is_blocked = FALSE, blocked_until = NULL WHERE telegram_id = $1",
                        user_id
                    )
                    return False
            return False

    async def get_expired_premium_users(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                "SELECT telegram_id FROM premium_users WHERE expires_at <= $1",
                now
            )

    async def get_blocked_users_to_unblock(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                "SELECT telegram_id FROM users WHERE is_blocked = TRUE AND blocked_until <= $1",
                now
            )
