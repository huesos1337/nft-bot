import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# ===== НАСТРОЙКИ =====
# Берем токен из настроек Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Безопасно получаем ID админа (если переменной нет или она пустая, берем значение по умолчанию)
try:
    admin_id_raw = os.environ.get('ADMIN_ID', '1676674007')
    # Если строка пустая, используем дефолт, иначе пробуем превратить в число
    ADMIN_ID = int(admin_id_raw) if admin_id_raw else 1676674007
except ValueError:
    ADMIN_ID = 1676674007

if not BOT_TOKEN:
    print(" ОШИБКА: Токен бота (BOT_TOKEN) не найден в настройках!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== СОСТОЯНИЯ (FSM) =====
class RegState(StatesGroup):
    waiting_username = State()
    waiting_role = State()

class SellerState(StatesGroup):
    waiting_nft = State()

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

# ===== ОБРАБОТЧИКИ =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Если уже зарегистрирован
    if user_id in users_db:
        user = users_db[user_id]
        await message.answer(f" Привет, {user['username']}! Ты уже зарегистрирован.")
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
    
    if message.text == "💼 Я продавец":
        users_db[user_id] = {"username": username, "role": "seller"}
        await message.answer("✅ Ты теперь ПРОДАВЕЦ! Можешь кидать NFT.", reply_markup=seller_menu())
    elif message.text == "🛒 Я покупатель":
        users_db[user_id] = {"username": username, "role": "buyer"}
        await message.answer("✅ Ты теперь ПОКУПАТЕЛЬ! Жди предложений.", reply_markup=buyer_menu())
    else:
        await message.answer("Пожалуйста, нажми на одну из кнопок ниже 👇", reply_markup=role_keyboard())
        return
    
    await state.clear()

@dp.message(F.text == "📤 Отправить NFT")
async def send_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверка роли
    if user_id not in users_db or users_db[user_id]['role'] != 'seller':
        await message.answer("❌ Эта команда доступна только продавцам!")
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

    # Сообщение для админа
    admin_msg = (
        f"🔔 <b>НОВЫЙ NFT!</b>\n"
        f"👤 Продавец: {username} (ID: {user_id})\n"
        f"📦 Тип: {file_type}\n\n"
        f"👉 Перешли этому юзеру оплату (звезды) в ЛС!"
    )
    
    try:
        # Отправляем уведомление и файл админу
        if is_photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_msg, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=ADMIN_ID, document=file_id, caption=admin_msg, parse_mode="HTML")
            
        await message.answer("✅ Админ получил твой NFT! Жди оплату в личные сообщения.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при отправке: {e}")
    
    await state.clear()

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        await message.answer("❌ Ты еще не зарегистрирован! Нажми /start")
        return
        
    u = users_db[user_id]
    role_emoji = "💼" if u['role'] == 'seller' else "🛒"
    await message.answer(f"👤 Твой профиль:\n\nИмя: {u['username']}\nРоль: {role_emoji} {u['role'].upper()}")

# ===== ЗАПУСК =====
async def main():
    print("🚀 Бот успешно запущен на Render...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())