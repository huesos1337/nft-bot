import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1676674007'))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class RegState(StatesGroup):
    waiting_username = State()
    waiting_role = State()

class SellerState(StatesGroup):
    waiting_nft = State()

users_db = {}

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

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in users_db:
        user = users_db[user_id]
        await message.answer(f"👋 Привет, {user['username']}!\nВы уже зарегистрированы.")
        kb = seller_menu() if user['role'] == 'seller' else buyer_menu()
        await message.answer("Меню:", reply_markup=kb)
        return
    await message.answer("🎨 Добро пожаловать в NFT Bot!\n\nСначала зарегистрируйтесь.\n\nВведите ваше имя:")
    await state.set_state(RegState.waiting_username)

@dp.message(RegState.waiting_username)
async def process_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    await message.answer(f"✅ Аккаунт создан!\nИмя: {message.text}\n\nКто вы?", reply_markup=role_keyboard())
    await state.set_state(RegState.waiting_role)

@dp.message(RegState.waiting_role)
async def process_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    username = data.get('username', 'Unknown')
    if message.text == "💼 Я продавец":
        users_db[user_id] = {"username": username, "role": "seller"}
        await message.answer("✅ Вы зарегистрированы как ПРОДАВЕЦ!", reply_markup=seller_menu())
    elif message.text == "🛒 Я покупатель":
        users_db[user_id] = {"username": username, "role": "buyer"}
        await message.answer("✅ Вы зарегистрированы как ПОКУПАТЕЛЬ!", reply_markup=buyer_menu())
    else:
        await message.answer("Выберите роль из кнопок:", reply_markup=role_keyboard())
        return
    await state.clear()

@dp.message(F.text == "📤 Отправить NFT")
async def send_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db or users_db[user_id]['role'] != 'seller':
        await message.answer("❌ Только продавцы могут отправлять NFT!")
        return
    await message.answer("📸 Отправьте фото/файл вашего NFT:")
    await state.set_state(SellerState.waiting_nft)

@dp.message(SellerState.waiting_nft, F.photo | F.document)
async def process_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = users_db[user_id]['username']
    is_photo = bool(message.photo)
    file_id = message.photo[-1].file_id if is_photo else message.document.file_id
    file_info = "Фото NFT" if is_photo else "Файл NFT"

    admin_msg = f"🔔 НОВЫЙ NFT ОТ ПРОДАВЦА!\n\n👤 Продавец: {username} (ID: {user_id})\n📦 Тип: {file_info}\n\nОтправьте звезды за NFT."
    try:
        if is_photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_msg)
        else:
            await bot.send_document(chat_id=ADMIN_ID, document=file_id, caption=admin_msg)
        await message.answer("✅ NFT успешно отправлено админу!\nОжидайте оплаты.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        await message.answer("❌ Вы не зарегистрированы! /start")
        return
    user = users_db[user_id]
    role_text = "💼 ПРОДАВЕЦ" if user['role'] == 'seller' else "🛒 ПОКУПАТЕЛЬ"
    await message.answer(f"👤 Профиль:\n\nИмя: {user['username']}\nРоль: {role_text}\nID: {user_id}")

async def main():
    print("🚀 Бот запущен на Render!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())