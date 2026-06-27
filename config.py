import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Convert comma-separated string to a list of integers
_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in _admin_ids.split(",") if id.strip().isdigit()]
