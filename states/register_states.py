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

class AdminBroadcast(StatesGroup):
    waiting_for_message = State()

class AdminGroupLevel(StatesGroup):
    waiting_for_level = State()

class AdminStudentLevel(StatesGroup):
    waiting_for_level = State()

class StudentAttendance(StatesGroup):
    waiting_for_absence_reason = State()
