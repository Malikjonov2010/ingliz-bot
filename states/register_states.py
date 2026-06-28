from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_age = State()
    waiting_for_phone = State()
    waiting_for_level = State()
    waiting_for_days = State()
    waiting_for_confirmation = State()

class Deletion(StatesGroup):
    waiting_for_reason = State()
    waiting_for_code = State()

class AdminDeletion(StatesGroup):
    waiting_for_admin_code = State()

class AdminGroupCreation(StatesGroup):
    waiting_for_name = State()
    waiting_for_days = State()
    waiting_for_time = State()

class AdminBroadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirmation = State()

class AdminGroupLevel(StatesGroup):
    waiting_for_level = State()

class AdminStudentLevel(StatesGroup):
    waiting_for_level = State()

class StudentAttendance(StatesGroup):
    waiting_for_absence_reason = State()

class TeacherMessage(StatesGroup):
    waiting_for_message = State()

class AdminPersonalMessage(StatesGroup):
    waiting_for_message = State()
    student_id = State()

class AdminSetBio(StatesGroup):
    waiting_for_bio = State()
    student_id = State()

# ============================================================
# PREMIUM TIZIMI STATELARI
# ============================================================

class PremiumPayment(StatesGroup):
    waiting_for_amount = State()
    waiting_for_comment = State()
    waiting_for_photo = State()

class PremiumChat(StatesGroup):
    waiting_for_message = State()

class AdminPremiumMsg(StatesGroup):
    waiting_for_message = State()
    target_user_id = State()

class AdminMonthlyFee(StatesGroup):
    waiting_for_fee = State()
    waiting_for_deadline = State()
    waiting_for_comment = State()
    group_id = State()

class AdminBlockMsg(StatesGroup):
    waiting_for_message = State()
    target_user_id = State()

