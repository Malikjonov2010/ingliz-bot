import os
import re

fpath = 'database/db.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# First, restore has_score_today
if 'def has_score_today' not in content:
    has_score_code = '''
    async def has_score_today(self, user_id: int) -> bool:
        async with self.pool.acquire() as connection:
            count = await connection.fetchval("SELECT COUNT(*) FROM scores WHERE user_id = $1 AND date = CURRENT_DATE", user_id)
            return count > 0
'''
    # Put it before complete_cycle
    content = content.replace('async def complete_cycle', has_score_code.strip() + '\n\n    async def complete_cycle')

# Now make sure is_blocked, get_expired_premium_users, get_blocked_users_to_unblock exist
to_add = '''
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
'''

# ensure we don't have duplicates
if 'def is_blocked' in content:
    content = re.sub(r'    async def is_blocked.*?return False', '', content, flags=re.DOTALL)
if 'def get_expired_premium_users' in content:
    content = re.sub(r'    async def get_expired_premium_users.*?now\n            \)', '', content, flags=re.DOTALL)
if 'def get_blocked_users_to_unblock' in content:
    content = re.sub(r'    async def get_blocked_users_to_unblock.*?now\n            \)', '', content, flags=re.DOTALL)

content = content + '\n' + to_add

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
