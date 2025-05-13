# Telegram Bot with OpenAI GPTS Integration

A production-ready Telegram bot that integrates with OpenAI's GPTS model, built with FastAPI and python-telegram-bot.

## Features

- 🤖 Telegram bot integration with webhook support
- 🧠 OpenAI GPTS model integration with retry logic
- 📊 Metrics tracking and status monitoring
- 🔄 Automatic keep-alive for free tier hosting
- ⚡️ Async request handling with proper timeouts
- 🛡️ Robust error handling and input validation

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with required variables:
   ```
   TELEGRAM_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=your_openai_api_key
   GPTS_MODEL_ID=your_gpts_model_id
   WEBHOOK_URL=your_webhook_url
   ```

## Deployment

The bot is configured for deployment on Render.com:

1. Create a new Web Service
2. Connect your repository
3. Set environment variables in Render dashboard
4. Deploy!

The service will automatically:
- Install dependencies
- Start with Gunicorn + Uvicorn workers
- Set up webhook
- Begin keep-alive pings

## Local Development

1. Install dependencies
2. Set up environment variables
3. Run with:
   ```bash
   uvicorn main:app --reload
   ```

## Bot Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/status` - Show bot metrics and status

## Error Handling

The bot implements:
- Exponential backoff for API retries
- User-friendly error messages
- Comprehensive logging
- Input validation
- HTTP timeout management

## Monitoring

Access `/` endpoint to view:
- Bot status
- Request metrics
- Error rates
- Processing times 