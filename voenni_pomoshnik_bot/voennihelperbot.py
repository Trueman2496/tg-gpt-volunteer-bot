from dotenv import load_dotenv
load_dotenv()

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from openai import AsyncOpenAI
import aiohttp
import os

# =======🔐 КЛЮЧИ И НАСТРОЙКИ =======
BOT_TOKEN = os.getenv("BOT_TOKEN")
GPT_API_KEY = os.getenv("GPT_API_KEY")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
MODERATOR_ID = int(os.getenv("MODERATOR_ID", "0"))

# ========== FSM ==========
class RequestState(StatesGroup):
    waiting_for_request_text = State()

class SubmitState(StatesGroup):
    waiting_for_name = State()
    waiting_for_city = State()
    waiting_for_services = State()
    waiting_for_contact = State()

# ========== CORE ==========
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ======= Airtable approved only =======
async def get_approved_businesses():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {
        "filterByFormula": "{Проверено}=TRUE()"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            return data.get("records", [])

# ======= GPT logic =======
client = AsyncOpenAI(api_key=GPT_API_KEY)

async def generate_gpt_response(user_request: str, businesses: list):
    context = ""
    for record in businesses:
        fields = record["fields"]
        context += f"- {fields.get('Название', '—')} ({fields.get('Город', '—')}): {fields.get('Услуги', '—')} | {fields.get('Контакт', '—')}\n"

    prompt = f"""Ты — помощник для украинских военных. Ответь на запрос на основе базы предложений от бизнеса.

Запрос: {user_request}

Предложения:
{context}

Ответ:"""

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content

# ======= Command handlers =======
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Я бот-помощник. Используй /request или /submit.")

@dp.message(Command("request"))
async def cmd_request(message: Message, state: FSMContext):
    await message.answer("✏️ Опишите ваш запрос:")
    await state.set_state(RequestState.waiting_for_request_text)

@dp.message(RequestState.waiting_for_request_text)
async def process_request_text(message: Message, state: FSMContext):
    user_request = message.text
    await message.answer("🔍 Ищу подходящие предложения...")
    businesses = await get_approved_businesses()
    gpt_reply = await generate_gpt_response(user_request, businesses)
    await message.answer(f"📢 Ответ:\n{gpt_reply}")
    await state.clear()

@dp.message(Command("submit"))
async def cmd_submit(message: Message, state: FSMContext):
    await state.update_data(user_id=message.from_user.id)
    await message.answer("📛 Название вашей компании:")
    await state.set_state(SubmitState.waiting_for_name)

@dp.message(SubmitState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🏙️ Город:")
    await state.set_state(SubmitState.waiting_for_city)

@dp.message(SubmitState.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("🛠️ Услуги / скидки:")
    await state.set_state(SubmitState.waiting_for_services)

@dp.message(SubmitState.waiting_for_services)
async def process_services(message: Message, state: FSMContext):
    await state.update_data(services=message.text)
    await message.answer("📞 Контакт:")
    await state.set_state(SubmitState.waiting_for_contact)

@dp.message(SubmitState.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    data["contact"] = message.text

    record = {
        "fields": {
            "Название": data["name"],
            "Город": data["city"],
            "Услуги": data["services"],
            "Контакт": data["contact"],
            "Проверено": False,
            "User_id": str(data["user_id"]),
        }
    }

    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
        async with session.post(url, headers=headers, json=record) as resp:
            result = await resp.json()
            if resp.status in [200, 201]:
                record_id = result["id"]
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Одобрить",
                                callback_data=f"approve:{record_id}:{data['user_id']}",
                            ),
                            InlineKeyboardButton(
                                text="❌ Отклонить",
                                callback_data=f"reject:{record_id}:{data['user_id']}",
                            ),
                        ]
                    ]
                )
                await message.answer(
                    "✅ Анкета добавлена! Ожидайте проверки.", reply_markup=keyboard
                )
            else:
                await message.answer("❌ Ошибка при добавлении анкеты.")
                print("Airtable error:", await resp.text())
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_record(callback: CallbackQuery):
    if callback.from_user.id != MODERATOR_ID:
        await callback.answer("🚫 У вас нет прав", show_alert=True)
        return

    _, record_id, user_id = callback.data.split(":")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"fields": {"Проверено": True}}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=payload) as response:
            if response.status == 200:
                await callback.message.edit_text("✅ Анкета одобрена.")
                await bot.send_message(
                    int(user_id), "✅ Ваша анкета одобрена и теперь доступна военным."
                )
            else:
                await callback.message.answer("⚠️ Ошибка при подтверждении.")
                print("Airtable approve error:", await response.text())

@dp.callback_query(lambda c: c.data.startswith("reject:"))
async def reject_record(callback: CallbackQuery):
    if callback.from_user.id != MODERATOR_ID:
        await callback.answer("🚫 У вас нет прав", show_alert=True)
        return

    _, record_id, user_id = callback.data.split(":")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"fields": {"Проверено": False, "Отклонено": True}}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=payload) as response:
            if response.status == 200:
                await callback.message.edit_text("❌ Анкета отклонена.")
                await bot.send_message(
                    int(user_id), "❌ Ваша анкета отклонена модератором."
                )
            else:
                await callback.message.answer("⚠️ Ошибка при отклонении.")
                print("Airtable reject error:", await response.text())

@dp.message(Command("list_pending"))
async def list_pending(message: Message):
    if message.from_user.id != MODERATOR_ID:
        await message.answer("🚫 У вас нет прав.")
        return

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {"filterByFormula": "NOT({Проверено})"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()

    records = data.get("records", [])
    if not records:
        await message.answer("📭 Нет неподтверждённых анкет.")
        return

    for record in records:
        f = record["fields"]
        record_id = record["id"]
        user_id = f.get("User_id", "0")
        text = (
            f"📛 {f.get('Название', '-')}\n"
            f"🏙️ {f.get('Город', '-')}\n"
            f"🛠️ {f.get('Услуги', '-')}\n"
            f"📞 {f.get('Контакт', '-')}"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"approve:{record_id}:{user_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject:{record_id}:{user_id}",
                    ),
                ]
            ]
        )
        await message.answer(text, reply_markup=keyboard)

# ======= СТАРТ =======
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())