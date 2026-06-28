import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Barcha adminlar (guruh boshqaruvi, tasdiqlash, xabar yuborish)
_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in _admin_ids.split(",") if id.strip().isdigit()]

# Ustoz-adminlar (@Mukhammad_diyor kabi - o'qituvchi va admin)
_teacher_ids = os.getenv("TEACHER_IDS", "")
TEACHER_IDS = [int(id.strip()) for id in _teacher_ids.split(",") if id.strip().isdigit()]

# Faqat admin (ustoz emas) — @Malikjonov_s kabi
PURE_ADMIN_IDS = [uid for uid in ADMIN_IDS if uid not in TEACHER_IDS]

# Foydali yordamchi funksiyalar
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_teacher(user_id: int) -> bool:
    return user_id in TEACHER_IDS

def is_pure_admin(user_id: int) -> bool:
    return user_id in PURE_ADMIN_IDS
