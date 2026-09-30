import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8896417856:AAG21QCyBN2BkADOPDcOPDQx1G-flDSNJOg"
ADMIN_ID = 1676674007

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== СОСТОЯНИЯ =====
class RegState(StatesGroup):
    waiting_username = State()
    waiting_role = State()

class SellerState(StatesGroup):
    waiting_nft = State()

class ChangeRoleState(StatesGroup):
    waiting_new_role = State()

# ===== БАЗА ДАННЫХ (в памяти) =====
users_db = {}

# ===== КЛАВИАТУРЫ =====
def role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💼 Я продавец"), KeyboardButton(text="🛒 Я покупатель")]],
        resize_keyboard=True
    )

def seller_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📤 Отправить NFT")], [KeyboardButton(text="👤 Мой профиль")]],
        resize_keyboard=True
    )

def buyer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="👤 Мой профиль")]],
        resize_keyboard=True
    )

def change_role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💼 Стать продавцом"), KeyboardButton(text="🛒 Стать покупателем")],
                  [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# ===== ОБРАБОТЧИКИ =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id in users_db:
        user = users_db[user_id]
        await message.answer(f"👋 Привет, {user['username']}! Ты уже зарегистрирован.")
        kb = seller_menu() if user['role'] == 'seller' else buyer_menu()
        await message.answer("Твое меню:", reply_markup=kb)
        return
    
    await message.answer("🎨 Добро пожаловать в NFT Bot!\n\nДля начала введи свое имя:")
    await state.set_state(RegState.waiting_username)

@dp.message(RegState.waiting_username)
async def process_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    await message.answer(f"✅ Аккаунт создан: {message.text}\n\nВыбери роль:", reply_markup=role_keyboard())
    await state.set_state(RegState.waiting_role)

@dp.message(RegState.waiting_role)
async def process_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    username = data.get('username', 'Неизвестно')
    
    if message.text == " Я продавец":
        users_db[user_id] = {"username": username, "role": "seller"}
        await message.answer("✅ Ты теперь ПРОДАВЕЦ! Можешь кидать NFT.", reply_markup=seller_menu())
    elif message.text == " Я покупатель":
        users_db[user_id] = {"username": username, "role": "buyer"}
        await message.answer("✅ Ты теперь ПОКУПАТЕЛЬ! Жди предложений.", reply_markup=buyer_menu())
    else:
        await message.answer("Пожалуйста, нажми на кнопку ниже 👇", reply_markup=role_keyboard())
        return
    
    await state.clear()

@dp.message(F.text == " Отправить NFT")
async def send_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in users_db or users_db[user_id]['role'] != 'seller':
        await message.answer("❌ Эта команда только для продавцов!")
        return
        
    await message.answer("📸 Скидывай фото или файл твоего NFT сюда:")
    await state.set_state(SellerState.waiting_nft)

@dp.message(SellerState.waiting_nft, F.photo | F.document)
async def process_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = users_db[user_id]['username']
    
    is_photo = bool(message.photo)
    file_id = message.photo[-1].file_id if is_photo else message.document.file_id
    file_type = "Фото" if is_photo else "Файл"

    admin_msg = (
        f"🔔 <b>НОВЫЙ NFT!</b>\n"
        f"👤 Продавец: {username} (ID: {user_id})\n"
        f"📦 Тип: {file_type}\n\n"
        f" Перешли этому юзеру оплату (звезды) в ЛС!"
    )
    
    try:
        if is_photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_msg, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=ADMIN_ID, document=file_id, caption=admin_msg, parse_mode="HTML")
            
        await message.answer("✅ Админ получил твой NFT! Жди оплату в личные сообщения.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        await message.answer(" Ты еще не зарегистрирован! Нажми /start")
        return
        
    u = users_db[user_id]
    role_emoji = "💼" if u['role'] == 'seller' else "🛒"
    role_name = "ПРОДАВЕЦ" if u['role'] == 'seller' else "ПОКУПАТЕЛЬ"
    
    await message.answer(
        f"👤 <b>Твой профиль:</b>\n\n"
        f"Имя: {u['username']}\n"
        f"Роль: {role_emoji} {role_name}\n"
        f"ID: {user_id}\n\n"
        f"Хочешь сменить роль? Нажми кнопку ниже!",
        reply_markup=change_role_keyboard(),
        parse_mode="HTML"
    )

@dp.message(F.text == "❌ Отмена")
async def cancel_change_role(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in users_db:
        kb = seller_menu() if users_db[user_id]['role'] == 'seller' else buyer_menu()
        await message.answer("✅ Отменено. Вернулся в главное меню.", reply_markup=kb)
    else:
        await message.answer("✅ Отменено.")

@dp.message(ChangeRoleState.waiting_new_role)
async def process_new_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in users_db:
        await message.answer("❌ Ты не зарегистрирован!")
        await state.clear()
        return
    
    old_role = users_db[user_id]['role']
    
    if message.text == "💼 Стать продавцом":
        new_role = "seller"
        role_name = "ПРОДАВЕЦ"
        emoji = "💼"
    elif message.text == "🛒 Стать покупателем":
        new_role = "buyer"
        role_name = "ПОКУПАТЕЛЬ"
        emoji = "🛒"
    else:
        await message.answer("❌ Выбери роль из кнопок!", reply_markup=change_role_keyboard())
        return
    
    # Обновляем роль
    users_db[user_id]['role'] = new_role
    
    await message.answer(
        f"✅ Роль изменена!\n\n"
        f"Было: {'💼 ПРОДАВЕЦ' if old_role == 'seller' else '🛒 ПОКУПАТЕЛЬ'}\n"
        f"Стало: {emoji} {role_name}",
        reply_markup=seller_menu() if new_role == 'seller' else buyer_menu()
    )
    
    await state.clear()

# Обработчик для кнопки смены роли из профиля
@dp.message(F.text.in_(["💼 Стать продавцом", "🛒 Стать покупателем"]))
async def start_change_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        await message.answer("❌ Сначала зарегистрируйтесь через /start")
        return
    
    current_role = users_db[user_id]['role']
    current_name = "ПРОДАВЕЦ" if current_role == 'seller' else "ПОКУПАТЕЛЬ"
    
    await message.answer(
        f" <b>Смена роли</b>\n\n"
        f"Сейчас ты: {current_name}\n"
        f"Кого хочешь стать?",
        reply_markup=change_role_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ChangeRoleState.waiting_new_role)

# ===== ЗАПУСК =====
async def main():
    print(" Бот запущен с функцией смены роли...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())