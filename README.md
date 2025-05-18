# voenni_pomoshnik_bot

A Telegram bot for collecting requests, generating answers via OpenAI GPT, and saving data to Airtable.

## Features

- Collect requests from users in Telegram
- Automatic answers generation using OpenAI GPT
- Save all requests and answers to Airtable database
- FSM (Finite State Machine) for user flow control

## How to run

1. Clone this repository:
git clone https://github.com/Trueman2496/tg-gpt-volunteer-bot.git
2. Install dependencies:
pip install -r requirements.txt
3. Create a `.env` file and fill it with your keys:
BOT_TOKEN=your_telegram_bot_token
GPT_API_KEY=your_openai_api_key
AIRTABLE_TOKEN=your_airtable_api_key
AIRTABLE_BASE_ID=your_airtable_base_id
AIRTABLE_TABLE_NAME=your_airtable_table_name
MODERATOR_ID=your_telegram_user_id
4. Run the bot:
## To Do

- Add more commands and features
- Deploy the bot to cloud hosting (Render, Railway, etc.)
- Add tests

## License

MIT License
