# Telegram Bot with OpenAI GPTS Integration

This is a Telegram bot that uses OpenAI's GPTS models to generate responses to user messages. The bot is built using FastAPI and python-telegram-bot.

## Features

- Integrates with Telegram Bot API via webhooks
- Forwards user messages to specified OpenAI GPTS model
- Handles OpenAI API errors with retry logic
- Includes keep-alive mechanism to prevent free tier sleep on Render.com
- Provides health check endpoint
- Compatible with different versions of OpenAI SDK

## Setup

1. Create a Telegram bot via BotFather and get your token
2. Set up an OpenAI account and get your API key
3. Create or get access to a GPTS model
4. Set the following environment variables:
   - `TELEGRAM_TOKEN`: Your Telegram bot token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `GPTS_MODEL_ID`: The ID of your GPTS model
   - `WEBHOOK_URL`: Your deployment URL (e.g., https://your-app.onrender.com)

## Deployment

This project is configured for deployment on Render.com.

1. Fork this repository or push to your own Git repository
2. Create a new Web Service on Render
3. Connect to your repository
4. Ensure the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app --bind 0.0.0.0:$PORT -k uvicorn.workers.UvicornWorker --timeout 120 --workers 2`
5. Add the required environment variables in the Render dashboard

## Local Development

1. Clone the repository
2. Create a `.env` file with the required environment variables
3. Install dependencies: `pip install -r requirements.txt`
4. Run the server: `uvicorn main:app --reload`

For local development, you can use a tool like ngrok to expose your local server to the internet and receive webhook updates from Telegram.

## License

MIT 