# Crypto Call Analyzer Bot

A Telegram bot that analyzes cryptocurrency call groups and calculates Take Profit (TP) and Stop Loss (SL) levels based on historical performance.

## Description

This bot monitors specified Telegram groups for cryptocurrency contract addresses, tracks their price movements, and calculates statistical TP/SL levels for different timeframes (12h, 24h, 48h). It uses the Birdeye API for price data and provides detailed analysis of call group performance.

## Features

- Monitors Telegram groups for cryptocurrency contract addresses
- Tracks price movements across multiple timeframes
- Calculates statistical TP/SL levels
- Generates detailed analysis reports
- Supports multiple blockchain networks
- Provides historical performance data

## Installation

1. Clone the repository:
```bash
git clone https://github.com/OkoyaUsman/TelegramCryptoCallAnalyzer.git
cd TelegramCryptoCallAnalyzer
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following variables:
```
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number
TELEGRAM_BOT_TOKEN=your_bot_token
BIRDEYE_API_KEY=your_birdeye_api_key
```

## Usage

1. Start the bot:
```bash
python bot.py
```

2. In Telegram, use the following commands:
- `/scan GROUPNAME` - Analyzes the specified group and returns TP/SL statistics

## Requirements

- Python 3.7+
- python-telegram-bot
- telethon
- curl-cffi
- python-dotenv
- requests

## Project Structure

- `bot.py` - Main bot implementation
- `.env` - Environment variables and API keys
- `data.json` - Stores historical analysis data
- `calculations/` - Directory for storing detailed calculation files
- `log.txt` - Bot operation logs

## Security

- All sensitive credentials are stored in the `.env` file
- The `.env` file should never be committed to version control
- API keys should be kept secure and not shared

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For custom modifications, assistance, or support, please contact:
- Telegram: [@OkoyaUsman](https://t.me/OkoyaUsman) 
