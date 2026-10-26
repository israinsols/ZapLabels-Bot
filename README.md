# ZapLabels Bot

ZapLabels is a Telegram bot project. Label editing, tracking-data changes, label generation, order creation, and payment confirmation are currently disabled. Use the relevant carrier's official service to create or correct a shipping label.

## Features

- Telegram bot interface built with aiogram 3
- Carrier service availability guidance
- User-facing guidance to use official carrier services
- Docker support with required OCR and barcode system libraries

## Requirements

- Python 3.11 or newer
- A Telegram bot token from [BotFather](https://core.telegram.org/bots#botfather)
- PostgreSQL database
- PayPal API credentials

For local Linux installations, the application may also need Tesseract OCR, libdmtx, ZBar, and related OpenCV libraries. The included `Dockerfile` installs these dependencies automatically.

## Installation

1. Clone the repository:

	```bash
	git clone https://github.com/your-username/zaplabels-bot.git
	cd zaplabels-bot
	```

2. Create and activate a virtual environment:

	```bash
	python -m venv .venv
	```

	Windows PowerShell:

	```powershell
	.\.venv\Scripts\Activate.ps1
	```

	Linux/macOS:

	```bash
	source .venv/bin/activate
	```

3. Install Python dependencies:

	```bash
	pip install -r requirements.txt
	```

4. Create a `.env` file in the project root:

	```env
	BOT_TOKEN=your_telegram_bot_token
	ADMIN_ID=your_telegram_user_id

	PAYPAL_EMAIL=your_paypal_email
	PAYPAL_CLIENT_ID=your_paypal_client_id
	PAYPAL_SECRET=your_paypal_secret
	PAYPAL_MODE=sandbox

	DATABASE_URL=postgresql://username:password@localhost:5432/zaplabels
	```

	Alternatively, configure PostgreSQL with these variables instead of `DATABASE_URL`:

	```env
	DB_USER=postgres
	DB_PASSWORD=your_database_password
	DB_NAME=zaplabels
	DB_HOST=localhost
	DB_PORT=5432
	```

5. Start the bot:

	```bash
	python bot.py
	```

## Docker

Build and run the bot with Docker:

```bash
docker build -t zaplabels-bot .
docker run --env-file .env zaplabels-bot
```

Make sure the PostgreSQL database is reachable from the container. When using Docker Compose or a database container, use the database service name as `DB_HOST`.

## Usage

1. Open the bot in Telegram.
2. Send `/start` for the current service availability notice.
3. Create or correct labels through the relevant carrier's official website or support channel.

## Project Structure

```text
bot.py                 Telegram bot entry point
config.py              Environment variables and pricing configuration
database.py            PostgreSQL connection and order management
*_processor.py         Carrier, barcode, OCR, and label processors
handlers/              Telegram command handlers
downloads/             Temporary input and generated files
templates/             Label templates
Dockerfile             Container setup and system dependencies
requirements.txt       Python dependencies
```

## Security

- Never commit `.env` files, API credentials, bot tokens, or payment secrets.
- Add `.env` to `.gitignore` before uploading the repository.
- Use `PAYPAL_MODE=sandbox` while testing.
- If any credentials were previously committed, revoke and regenerate them before publishing the repository.

## Testing

Run an individual test script with:

```bash
python test_datamatrix.py
```

The repository contains legacy processor scripts, but label-editing workflows are not enabled through the bot.

## License

Add the license that applies to your project before publishing it publicly.
