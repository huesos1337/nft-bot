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

class ChangeRoleState(StatesGroup):
    waiting_new_role = State()

class DealState(StatesGroup):
    waiting_target_user = State()  # Кому кидаем сделку
    waiting_nft_from_seller = State() # Ожидание NFT от продавца

# ===== БАЗА ДАННЫХ =====
users_db = {} 
# {user_id: {"username": "...", "role": "seller/buyer", "tg_username": "@name"}}

# ===== КЛАВИАТУРЫ =====
def role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💼 Я продавец"), KeyboardButton(text="🛒 Я покупатель")]],
        resize_keyboard=True
    )

def seller_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚡️ Создать сделку (/sdelka)")], 
            [KeyboardButton(text="👤 Мой профиль")]
        ],
        resize_keyboard=True
    )

def buyer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="👤 Мой профиль")]],
        resize_keyboard=True
    )

def change_role_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💼 Стать продавцом"), KeyboardButton(text="🛒 Стать покупателем")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# ===== ПОМОЩНИКИ =====
def find_user_by_username(username_input):
    """Ищет пользователя в базе по юзернейму (с @ или без)"""
    clean_name = username_input.lower().replace("@", "")
    for uid, data in users_db.items():
        db_uname = data.get("tg_username", "").lower().replace("@", "")
        if db_uname == clean_name:
            return uid, data
    return None, None

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
    tg_uname = message.from_user.username or ""
    await state.update_data(tg_username=tg_uname)
    
    await message.answer(f"✅ Аккаунт создан: {message.text}\n\nВыбери роль:", reply_markup=role_keyboard())
    await state.set_state(RegState.waiting_role)

@dp.message(RegState.waiting_role)
async def process_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    username = data.get('username', 'Неизвестно')
    tg_username = data.get('tg_username', '')
    
    if message.text == "💼 Я продавец":
        users_db[user_id] = {"username": username, "role": "seller", "tg_username": tg_username}
        await message.answer("✅ Ты теперь ПРОДАВЕЦ! Можешь создавать сделки.", reply_markup=seller_menu())
    elif message.text == "🛒 Я покупатель":
        users_db[user_id] = {"username": username, "role": "buyer", "tg_username": tg_username}
        await message.answer("✅ Ты теперь ПОКУПАТЕЛЬ! Жди предложений.", reply_markup=buyer_menu())
    else:
        await message.answer("Пожалуйста, нажми на кнопку ниже 👇", reply_markup=role_keyboard())
        return
    
    await state.clear()

# --- ЛОГИКА СДЕЛОК (ПРОДАВЕЦ КИДАЕТ NFT) ---

@dp.message(Command("sdelka") | F.text.startswith("/sdelka"))
async def start_deal_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверка: только продавец может инициировать
    if user_id not in users_db or users_db[user_id]['role'] != 'seller':
        await message.answer("❌ Только продавцы могут создавать сделки!")
        return

    text = message.text.strip()
    target_input = text.replace("/sdelka", "").strip()
    
    if not target_input:
        await message.answer(
            "⚠️ Укажите юзернейм покупателя.\n"
            "Пример: `/sdelka @ivan_ivanov` или `/sdelka ivan_ivanov`", 
            parse_mode="Markdown"
        )
        return

    target_uid, target_data = find_user_by_username(target_input)
    
    if not target_uid:
        await message.answer(f" Пользователь '{target_input}' не найден в базе бота.\nУбедитесь, что он запускал /start.")
        return
        
    if target_uid == user_id:
        await message.answer("❌ Нельзя создать сделку с самим собой!")
        return

    # Сохраняем ID покупателя во временное состояние продавца
    await state.update_data(target_user_id=target_uid)
    await state.set_state(DealState.waiting_nft_from_seller)
    
    await message.answer(
        f"✅ Вы выбрали покупателя: {target_data['username']} (@{target_data.get('tg_username', 'no_username')}).\n\n"
        f"📸 <b>Теперь отправьте фото или файл NFT прямо сюда!</b>\n"
        f"Бот перешлет его покупателю и админу.",
        parse_mode="HTML"
    )

# Обработчик получения NFT от ПРОДАВЦА
@dp.message(DealState.waiting_nft_from_seller, F.photo | F.document)
async def handle_seller_nft(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    target_uid = data.get('target_user_id')
    
    if not target_uid:
        await message.answer("❌ Ошибка сделки. Попробуйте начать заново через /sdelka")
        await state.clear()
        return

    seller_name = users_db[user_id]['username']
    is_photo = bool(message.photo)
    file_id = message.photo[-1].file_id if is_photo else message.document.file_id
    file_type = "Фото" if is_photo else "Файл"
    
    # 1. Отправляем NFT ПОКУПАТЕЛЮ
    buyer_msg = (
        f" <b>НОВАЯ СДЕЛКА!</b>\n\n"
        f"Продавец <b>{seller_name}</b> отправил вам NFT.\n"
        f"Проверьте файл выше. Если всё верно, напишите админу для оплаты."
    )
    
    try:
        if is_photo:
            await bot.send_photo(chat_id=target_uid, photo=file_id, caption=buyer_msg, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=target_uid, document=file_id, caption=buyer_msg, parse_mode="HTML")
            
        await message.answer("✅ NFT успешно отправлен покупателю!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить покупателю (возможно, он заблокировал бота): {e}")

    # 2. Отправляем уведомление АДМИНУ (тебе)
    admin_msg = (
        f"🔥 <b>СДЕЛКА: NFT ОТПРАВЛЕНО!</b>\n\n"
        f"👤 Продавец: {seller_name} (ID: {user_id})\n"
        f"👤 Покупатель ID: {target_uid}\n"
        f" Тип: {file_type}\n\n"
        f"👉 Админ, проверь файл и переведи ЗВЕЗДЫ/оплату ПОКУПАТЕЛЮ в ЛС!"
    )
    
    try:
        if is_photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=admin_msg, parse_mode="HTML")
        else:
            await bot.send_document(chat_id=ADMIN_ID, document=file_id, caption=admin_msg, parse_mode="HTML")
    except Exception:
        pass # Если админ заблокировал бота, ничего страшного
        
    await state.clear()

# --- ПРОФИЛЬ И СМЕНА РОЛИ ---

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
        f"Telegram: @{u.get('tg_username', 'не указан')}\n"
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

@dp.message(ChangeRoleState.waiting_new_role)
async def process_new_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        await state.clear()
        return
    
    old_role = users_db[user_id]['role']
    
    if message.text == "💼 Стать продавцом":
        new_role = "seller"
    elif message.text == "🛒 Стать покупателем":
        new_role = "buyer"
    else:
        await message.answer("❌ Выбери роль из кнопок!", reply_markup=change_role_keyboard())
        return
    
    users_db[user_id]['role'] = new_role
    kb = seller_menu() if new_role == 'seller' else buyer_menu()
    
    await message.answer(f"✅ Роль изменена на {new_role.upper()}!", reply_markup=kb)
    await state.clear()

@dp.message(F.text.in_(["💼 Стать продавцом", "🛒 Стать покупателем"]))
async def start_change_role(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        return
    await message.answer("Выберите новую роль:", reply_markup=change_role_keyboard())
    await state.set_state(ChangeRoleState.waiting_new_role)

# ===== ЗАПУСК =====
async def main():
    print("🚀 Бот запущен (версия: Продавец кидает NFT)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())