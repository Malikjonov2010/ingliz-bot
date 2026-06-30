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
            
            await connection.execute(
                "INSERT INTO cycles (user_id, cycle_number, total_score, percentage, level) VALUES ($1, $2, $3, $4, $5)",
                user_id, c_num, total_score, percentage, f"{level} {emoji}"
            )
            
        return level, emoji
        
    async def get_user_stats(self, user_id: int) -> dict:
        async with self.pool.acquire() as connection:
            last_score_rec = await connection.fetchrow("SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT 1", user_id)
            last_score = last_score_rec['score'] if last_score_rec else 0
            
            scores_query = "SELECT lesson_number, score FROM scores WHERE user_id = $1 AND id > COALESCE((SELECT MAX(id) FROM scores WHERE user_id = $1 AND lesson_number = 6), 0) ORDER BY lesson_number ASC"
            current_cycle_scores = await connection.fetch(scores_query, user_id)
            
            sum_query = "SELECT SUM(score) FROM scores WHERE user_id = $1 AND id > COALESCE((SELECT MAX(id) FROM scores WHERE user_id = $1 AND lesson_number = 6), 0)"
            current_cycle_total = await connection.fetchval(sum_query, user_id) or 0
            
            cycles = await connection.fetch("SELECT cycle_number, total_score, level FROM cycles WHERE user_id = $1 ORDER BY cycle_number DESC", user_id)
            
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

    async def can_send_teacher_message(self, user_id: int) -> bool:
        from datetime import date
        query = "SELECT COUNT(*) FROM teacher_message_logs WHERE user_id = $1 AND date = $2"
        async with self.pool.acquire() as connection:
            count = await connection.fetchval(query, user_id, date.today())
            return count < 3

    async def log_teacher_message(self, user_id: int) -> None:
        from datetime import date
        query = "INSERT INTO teacher_message_logs (user_id, date) VALUES ($1, $2)"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, date.today())

    async def set_teacher_bio(self, user_id: int, bio: str) -> None:
        query = "UPDATE users SET teacher_bio = $2 WHERE telegram_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id, bio)

    async def get_active_users(self) -> List[asyncpg.Record]:
        query = "SELECT * FROM users WHERE status = 'active'"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query)

    # ============================================================
    # PREMIUM TIZIMI METODLARI
    # ============================================================

    async def is_premium(self, user_id: int) -> bool:
        """Foydalanuvchi premium ekanligini tekshiradi (muddati o'tmagan bo'lsa)."""
        from datetime import datetime, timezone
        query = "SELECT expires_at FROM premium_users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(query, user_id)
        if not row:
            return False
        return row['expires_at'] > datetime.now(timezone.utc)

    async def get_premium_info(self, user_id: int) -> asyncpg.Record:
        """Premium ma'lumotlarini oladi."""
        query = "SELECT * FROM premium_users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, user_id)

    async def activate_premium(self, user_id: int, admin_id: int, days: int = 30) -> None:
        """Foydalanuvchiga premium beradi yoki muddatini uzaytiradi."""
        from datetime import datetime, timezone, timedelta
        async with self.pool.acquire() as connection:
            existing = await connection.fetchrow("SELECT expires_at FROM premium_users WHERE user_id = $1", user_id)
            now = datetime.now(timezone.utc)
            if existing and existing['expires_at'] > now:
                new_expires = existing['expires_at'] + timedelta(days=days)
            else:
                new_expires = now + timedelta(days=days)
            await connection.execute(
                """INSERT INTO premium_users (user_id, activated_at, expires_at, activated_by)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (user_id) DO UPDATE SET expires_at = $3, activated_by = $4""",
                user_id, now, new_expires, admin_id
            )

    async def deactivate_premium(self, user_id: int) -> None:
        """Premiumni o'chiradi."""
        query = "DELETE FROM premium_users WHERE user_id = $1"
        async with self.pool.acquire() as connection:
            await connection.execute(query, user_id)

    async def get_expired_premium_users(self) -> List[asyncpg.Record]:
        """Muddati o'tgan premium foydalanuvchilarni oladi."""
        from datetime import datetime, timezone
        query = "SELECT user_id FROM premium_users WHERE expires_at < $1"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, datetime.now(timezone.utc))

    # ---- Premium So'rovlar ----

    async def create_premium_request(self, user_id: int, amount: str, comment: str, photo_file_id: str) -> int:
        """Yangi premium so'rov yaratadi. Urinishlar soni hisoblanadi."""
        async with self.pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT COUNT(*) FROM premium_requests WHERE user_id = $1", user_id
            )
            attempt = int(count) + 1
            rid = await connection.fetchval(
                """INSERT INTO premium_requests (user_id, amount, comment, photo_file_id, attempt_count)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                user_id, amount, comment, photo_file_id, attempt
            )
            return rid

    async def get_premium_request(self, request_id: int) -> asyncpg.Record:
        async with self.pool.acquire() as connection:
            return await connection.fetchrow("SELECT * FROM premium_requests WHERE id = $1", request_id)

    async def get_user_premium_attempt_count(self, user_id: int) -> int:
        """Foydalanuvchining jami premium urinishlar sonini oladi."""
        async with self.pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT COUNT(*) FROM premium_requests WHERE user_id = $1", user_id
            ) or 0

    async def update_premium_request_status(self, request_id: int, status: str) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE premium_requests SET status = $2 WHERE id = $1", request_id, status
            )

    # ---- Bloklash ----

    async def block_user(self, user_id: int, reason: str, days: int = 30) -> None:
        """Foydalanuvchini bloklaydi."""
        from datetime import datetime, timezone, timedelta
        blocked_until = datetime.now(timezone.utc) + timedelta(days=days)
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE users SET is_blocked = TRUE, blocked_until = $2, block_reason = $3 WHERE telegram_id = $1",
                user_id, blocked_until, reason
            )

    async def unblock_user(self, user_id: int) -> None:
        """Foydalanuvchini blokdan chiqaradi."""
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE users SET is_blocked = FALSE, blocked_until = NULL, block_reason = NULL WHERE telegram_id = $1",
                user_id
            )

    async def is_blocked(self, user_id: int) -> bool:
        """Foydalanuvchi bloklanganmi tekshiradi."""
        from datetime import datetime, timezone
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT is_blocked, blocked_until FROM users WHERE telegram_id = $1", user_id
            )
        if not row or not row['is_blocked']:
            return False
        if row['blocked_until'] and row['blocked_until'] < datetime.now(timezone.utc):
            await self.unblock_user(user_id)
            return False
        return True

    async def get_blocked_users_to_unblock(self) -> List[asyncpg.Record]:
        """Muddati o'tgan bloklarni qaytaradi."""
        from datetime import datetime, timezone
        query = "SELECT telegram_id FROM users WHERE is_blocked = TRUE AND blocked_until < $1"
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, datetime.now(timezone.utc))

    # ---- Referral ----

    async def get_or_create_referral_code(self, user_id: int) -> str:
        """Foydalanuvchining referral kodini oladi yoki yangi yaratadi."""
        import random, string
        async with self.pool.acquire() as connection:
            code = await connection.fetchval(
                "SELECT referral_code FROM users WHERE telegram_id = $1", user_id
            )
            if code:
                return code
            new_code = f"ref_{user_id}_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            await connection.execute(
                "UPDATE users SET referral_code = $2 WHERE telegram_id = $1", user_id, new_code
            )
            return new_code

    async def record_referral(self, code: str, used_by: int) -> bool:
        """Referral kodni ishlatildi deb belgilaydi. Muvaffaqiyatli bo'lsa True."""
        async with self.pool.acquire() as connection:
            owner = await connection.fetchrow(
                "SELECT telegram_id FROM users WHERE referral_code = $1", code
            )
            if not owner or owner['telegram_id'] == used_by:
                return False
            try:
                await connection.execute(
                    """INSERT INTO referral_uses (referral_code, used_by, owner_id, is_staying)
                       VALUES ($1, $2, $3, FALSE) ON CONFLICT (used_by) DO NOTHING""",
                    code, used_by, owner['telegram_id']
                )
                return True
            except Exception:
                return False

    async def mark_referral_staying(self, user_id: int) -> None:
        """Referral orqali kelgan foydalanuvchi botda qoldi deb belgilaydi."""
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE referral_uses SET is_staying = TRUE WHERE used_by = $1", user_id
            )

    async def get_staying_referral_count(self, owner_id: int) -> int:
        """Referral orqali botda qolgan foydalanuvchilar sonini oladi."""
        async with self.pool.acquire() as connection:
            return await connection.fetchval(
                "SELECT COUNT(*) FROM referral_uses WHERE owner_id = $1 AND is_staying = TRUE",
                owner_id
            ) or 0

    async def get_referral_stats(self, owner_id: int) -> dict:
        """Referral statistikasini oladi."""
        async with self.pool.acquire() as connection:
            total = await connection.fetchval(
                "SELECT COUNT(*) FROM referral_uses WHERE owner_id = $1", owner_id
            ) or 0
            staying = await connection.fetchval(
                "SELECT COUNT(*) FROM referral_uses WHERE owner_id = $1 AND is_staying = TRUE", owner_id
            ) or 0
        return {"total": int(total), "staying": int(staying), "needed": max(0, 10 - int(staying))}

    # ---- AI Suhbat Tarixi ----

    async def get_ai_chat_history(self, user_id: int, limit: int = 10) -> List[asyncpg.Record]:
        """So'nggi AI suhbat tarixini oladi."""
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT role, content FROM ai_chat_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit
            )
        return list(reversed(rows))

    async def add_ai_chat_message(self, user_id: int, role: str, content: str) -> None:
        """AI suhbatga yangi xabar qo'shadi va 20 tadan ortiqlarini o'chiradi."""
        async with self.pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO ai_chat_history (user_id, role, content) VALUES ($1, $2, $3)",
                user_id, role, content
            )
            await connection.execute(
                """DELETE FROM ai_chat_history WHERE id IN (
                   SELECT id FROM ai_chat_history WHERE user_id = $1
                   ORDER BY created_at DESC OFFSET 20)""",
                user_id
            )

    async def clear_ai_chat_history(self, user_id: int) -> None:
        """AI suhbat tarixini tozalaydi."""
        async with self.pool.acquire() as connection:
            await connection.execute("DELETE FROM ai_chat_history WHERE user_id = $1", user_id)

    # ---- Oylik To'lov ----

    async def set_group_monthly_fee(self, group_id: int, fee: str, deadline: str, comment: str) -> None:
        """Guruhning oylik to'lov ma'lumotlarini yangilaydi."""
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE groups SET monthly_fee = $2, fee_deadline = $3, fee_comment = $4 WHERE id = $1",
                group_id, fee, deadline, comment
            )

    # ---- Guruh Statistikasi (Premium) ----

    async def get_all_groups_with_stats(self) -> List[dict]:
        """Barcha guruhlarni o'quvchilar soni va darajasi bilan oladi."""
        async with self.pool.acquire() as connection:
            groups = await connection.fetch(
                "SELECT id, name, group_level, monthly_fee, fee_deadline, fee_comment, days, time FROM groups ORDER BY id ASC"
            )
            result = []
            for g in groups:
                count = await connection.fetchval(
                    "SELECT COUNT(*) FROM users WHERE group_id = $1 AND status = 'active'", g['id']
                )
                result.append({**dict(g), "student_count": int(count or 0)})
            return result

    async def get_group_top_students(self, group_id: int, limit: int = 3) -> List[asyncpg.Record]:
        """Guruhning top o'quvchilarini oxirgi sikl bo'yicha oladi."""
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                """SELECT u.telegram_id, u.first_name, u.last_name, u.student_level,
                          COALESCE((
                            SELECT SUM(score) FROM scores s
                            WHERE s.user_id = u.telegram_id
                            AND s.id > COALESCE((
                                SELECT MAX(id) FROM scores s2
                                WHERE s2.user_id = u.telegram_id AND s2.lesson_number = 6), 0)
                          ), 0) as cycle_score
                   FROM users u
                   WHERE u.group_id = $1 AND u.status = 'active'
                   ORDER BY cycle_score DESC LIMIT $2""",
                group_id, limit
            )

    async def get_student_last_scores(self, user_id: int, limit: int = 6) -> List[asyncpg.Record]:
        """O'quvchining so'nggi N ta dars natijasini oladi."""
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                "SELECT lesson_number, score, date FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT $2",
                user_id, limit
            )

    async def get_group_students_with_scores(self, group_id: int) -> List[dict]:
        """Guruh o'quvchilarini so'nggi 6 dars natijalari bilan oladi."""
        async with self.pool.acquire() as connection:
            students = await connection.fetch(
                "SELECT telegram_id, first_name, last_name, student_level FROM users WHERE group_id = $1 AND status = 'active'",
                group_id
            )
            result = []
            for s in students:
                scores = await connection.fetch(
                    "SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT 6",
                    s['telegram_id']
                )
                total = sum(row['score'] for row in scores)
                count = len(scores)
                if count == 0:
                    grade = "Ma'lumot yo'q"
                elif total / (count * 25) >= 0.93:
                    grade = "Excellent 🥇"
                elif total / (count * 25) >= 0.80:
                    grade = "Very Good 🟢"
                elif total / (count * 25) >= 0.67:
                    grade = "Good 🟡"
                elif total / (count * 25) >= 0.53:
                    grade = "Needs Improvement 🟠"
                else:
                    grade = "Weak 🔴"
                result.append({**dict(s), "grade": grade, "recent_scores": [r['score'] for r in scores]})
            return result

    async def get_my_growth_stats(self, user_id: int) -> dict:
        """O'quvchining o'sish statistikasini oladi."""
        async with self.pool.acquire() as connection:
            cycles = await connection.fetch(
                "SELECT cycle_number, total_score, level, completed_date FROM cycles WHERE user_id = $1 ORDER BY cycle_number ASC",
                user_id
            )
            total_attended = await connection.fetchval(
                "SELECT COUNT(*) FROM attendance WHERE user_id = $1 AND is_present = TRUE", user_id
            ) or 0
            total_lessons = await connection.fetchval(
                "SELECT COUNT(*) FROM attendance WHERE user_id = $1", user_id
            ) or 0
            avg_score = await connection.fetchval(
                "SELECT AVG(score) FROM scores WHERE user_id = $1", user_id
            )
            group_rank_row = await connection.fetchrow(
                """WITH ranked AS (
                   SELECT u.telegram_id,
                          RANK() OVER (ORDER BY COALESCE((
                              SELECT SUM(s.score) FROM scores s
                              WHERE s.user_id = u.telegram_id
                              AND s.id > COALESCE((SELECT MAX(id) FROM scores s2
                                WHERE s2.user_id = u.telegram_id AND s2.lesson_number=6),0)
                          ),0) DESC) as rnk
                   FROM users u WHERE u.group_id = (
                       SELECT group_id FROM users WHERE telegram_id = $1
                   ) AND u.status = 'active'
                ) SELECT rnk FROM ranked WHERE telegram_id = $1""",
                user_id
            )
        return {
            "cycles": list(cycles),
            "total_attended": int(total_attended),
            "total_lessons": int(total_lessons),
            "attendance_pct": round(100 * total_attended / total_lessons, 1) if total_lessons > 0 else 0,
            "avg_score": round(float(avg_score), 1) if avg_score else 0,
            "group_rank": int(group_rank_row['rnk']) if group_rank_row else None,
        }

    async def can_send_teacher_message_premium(self, user_id: int) -> bool:
        """Premium foydalanuvchi uchun kuniga 10 ta limit."""
        from datetime import date
        async with self.pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT COUNT(*) FROM teacher_message_logs WHERE user_id = $1 AND date = $2",
                user_id, date.today()
            )
            return int(count) < 10

