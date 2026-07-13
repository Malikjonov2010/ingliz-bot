import os
fpath = 'database/db.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

to_add = '''
    async def increment_activity(self, user_id: int):
        async with self.pool.acquire() as connection:
            await connection.execute("UPDATE users SET activity_score = COALESCE(activity_score, 0) + 1 WHERE telegram_id = $1", user_id)

    async def get_rankings(self):
        async with self.pool.acquire() as connection:
            # Reyting hisoblash logikasi
            level_weights = {
                "Support": 500,
                "Captain": 400,
                "Main": 300,
                "Introductory": 200,
                "Learner": 100
            }
            users = await connection.fetch("SELECT telegram_id, first_name, last_name, level, activity_score, group_id FROM users WHERE status = 'active'")
            rankings = []
            for u in users:
                user_id = u['telegram_id']
                level = u['level']
                level_base = level.split()[0] if level else "Unknown"
                
                weight = level_weights.get(level_base, 0)
                
                last_scores = await connection.fetch("SELECT score FROM scores WHERE user_id = $1 ORDER BY id DESC LIMIT 6", user_id)
                current_score = sum(s['score'] for s in last_scores)
                
                activity = u['activity_score'] or 0
                
                total_points = weight + current_score + activity
                
                name = f"{u['first_name']} {u['last_name']}".strip()
                rankings.append({
                    'user_id': user_id,
                    'group_id': u['group_id'],
                    'name': name,
                    'level': level or "Hali belgilanmagan",
                    'current_score': current_score,
                    'activity_score': activity,
                    'total_points': total_points
                })
                
            rankings.sort(key=lambda x: x['total_points'], reverse=True)
            return rankings
'''

if 'def get_rankings' not in content:
    content += '\n' + to_add
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
