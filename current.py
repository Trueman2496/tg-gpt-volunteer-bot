import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientSession

# Токен бота от BotFather
TOKEN = "7675457263:AAE73KFO1r8I0_OZQcwocgHS1asS0E0Clds"

# Ключ API (обязателен для запросов)
API_KEY = "bf91b1f1f2d67593b50e9c89779a787e"

# Твой Telegram ID (замени на свой)
ADMIN_ID = 7522319330  # <--- сюда вставь свой ID

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранилище задачи polling
polling_task = None

# Клавиатура с выбором валют, добавлены RUB и UAH
currency_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="USD", callback_data="currency_USD"),
            InlineKeyboardButton(text="EUR", callback_data="currency_EUR"),
            InlineKeyboardButton(text="GEL", callback_data="currency_GEL"),
            InlineKeyboardButton(text="PLN", callback_data="currency_PLN"),
        ],
        [
            InlineKeyboardButton(text="RUB", callback_data="currency_RUB"),
            InlineKeyboardButton(text="UAH", callback_data="currency_UAH"),
            InlineKeyboardButton(
                text="TRY", callback_data="currency_TRY"
            ),  # Турецкая лира
            InlineKeyboardButton(
                text="CZK", callback_data="currency_CZK"
            ),  # Чешская крона
        ],
    ]
)

# Словарь для хранения выбранной валюты пользователя
user_data = {}


# Обработчик команды /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот-конвертер валют.\nВыбери валюту для конвертации:",
        reply_markup=currency_keyboard,
    )


# Обработка выбора валюты кнопками
@dp.callback_query()
async def currency_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    currency_map = {
        "currency_USD": "USD",
        "currency_EUR": "EUR",
        "currency_GEL": "GEL",
        "currency_PLN": "PLN",
        "currency_RUB": "RUB",
        "currency_UAH": "UAH",
        "currency_TRY": "TRY",
        "currency_CZK": "CZK",
    }

    if data in currency_map:
        from_currency = currency_map[data]
        user_data[user_id] = {"from_currency": from_currency}
        text = f"Выбрана валюта: {from_currency}\nТеперь отправьте сумму для конвертации, например:\n100 to USD"
    else:
        text = "Неизвестная валюта."

    await callback.message.answer(text)
    await callback.answer()


# Получение курса конвертации через exchangerate.host
async def get_conversion(amount: float, from_currency: str, to_currency: str):
    url = f"https://api.exchangerate.host/convert?access_key={API_KEY}&from={from_currency}&to={to_currency}&amount={amount}"
    async with ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data.get("success"):
                return data.get("result")
            return None


# Обработка сообщения с суммой и валютой для конвертации
@dp.message()
async def amount_to_currency_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_data or "from_currency" not in user_data[user_id]:
        await message.answer(
            "Пожалуйста, выберите валюту для конвертации с помощью кнопок ниже.",
            reply_markup=currency_keyboard,
        )
        return

    try:
        parts = text.split()
        if len(parts) != 3 or parts[1].lower() != "to":
            raise ValueError("Неверный формат")
        amount = float(parts[0])
        from_currency = user_data[user_id]["from_currency"]
        to_currency = parts[2].upper()

        result = await get_conversion(amount, from_currency, to_currency)
        if result is not None:
            await message.answer(
                f"{amount} {from_currency} = {result:.2f} {to_currency}"
            )
        else:
            await message.answer("❌ Не удалось получить курс валют.")

    except Exception:
        await message.answer("❗ Неверный формат. Пример: 100 to EUR")


# Команда для запуска polling (только для админа)
@dp.message(Command("start_bot"))
async def cmd_start_bot(message: types.Message):
    global polling_task
    if message.from_user.id != ADMIN_ID:
        return  # Игнорируем неадминов
    if polling_task and not polling_task.done():
        await message.answer("Бот уже запущен.")
        return
    polling_task = asyncio.create_task(dp.start_polling(bot))
    await message.answer("Бот запущен.")


# Команда для остановки polling (только для админа)
@dp.message(Command("stop_bot"))
async def cmd_stop_bot(message: types.Message):
    global polling_task
    if message.from_user.id != ADMIN_ID:
        return  # Игнорируем неадминов
    if polling_task:
        polling_task.cancel()
        polling_task = None
        await message.answer("Бот остановлен.")
    else:
        await message.answer("Бот не был запущен.")


async def main():
    print("✅ Бот готов к работе.")
    global polling_task
    polling_task = asyncio.create_task(dp.start_polling(bot))
    await polling_task


if __name__ == "__main__":
    asyncio.run(main())
