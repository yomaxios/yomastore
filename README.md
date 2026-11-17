# YOMA BOT — Telegram Developer Admin Panel

## Included
- Telegram-only developer admin panel (`/admin`)
- Edit welcome message
- Add/list categories
- Add/list products
- Add plans and prices
- Add stock keys
- Basic inventory statistics
- Customer category/product browsing (`/buy`)

## Setup
1. Install Python 3.10+.
2. Create a bot with Telegram's official @BotFather and copy its token.
3. Copy `.env.example` to `.env` and fill in BOT_TOKEN and OWNER_ID.
4. Install dependencies: `pip install -r requirements.txt`
5. Set environment variables from `.env` in your hosting provider, then run: `python main.py`

For local testing, you can export the variables in your terminal:
- macOS/Linux: `export BOT_TOKEN='...'` and `export OWNER_ID='your numeric Telegram user ID'`
- Windows PowerShell: `$env:BOT_TOKEN='...'` and `$env:OWNER_ID='your numeric Telegram user ID'`

## Admin commands
- `/admin` — open developer panel
- `/plans` — list plan IDs
- `/addplan PRODUCT_ID | PLAN | PRICE | DURATION`
- `/addstock PLAN_ID | LICENSE_KEY`

## Important
- Never share your bot token publicly or commit it to GitHub.
- This starter does NOT yet connect to ABA/Bakong/Khmer System payment APIs.
- It does NOT mark orders paid or deliver keys automatically. Add a verified payment-provider integration and transaction verification before accepting real money.
- Keep a backup of `yoma_bot.db`.
