# Import required libraries
import os
import re
import json
from curl_cffi import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerChannel
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the absolute path of the current directory
PATH = os.path.dirname(os.path.abspath(__file__))

# Set date limit to 1 year ago from current date
date_limit = (datetime.now() - timedelta(days=365)).replace(tzinfo=timezone.utc)

# Configuration constants
address_limit = 200  # Maximum number of contract addresses to analyze

# Load API credentials from environment variables
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE")
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
birdeye_api_key = os.getenv("BIRDEYE_API_KEY")

# Initialize Telegram client
client = TelegramClient("session", api_id, api_hash).start(phone=phone)

async def handle_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /scan command from Telegram.
    Analyzes a specified group and returns TP/SL statistics.
    
    Args:
        update (Update): The update object from Telegram
        context (ContextTypes.DEFAULT_TYPE): The context object from Telegram
    """
    try:
        # Check if group name is provided
        if len(context.args) < 1:
            await update.message.reply_text("Please provide a valid group name. Usage: /scan GROUPNAME", reply_to_message_id=update.message.id)
            return
        
        # Get and process group name
        group_name = " ".join(context.args).lower().strip()
        await update.message.reply_text(f"Generating TP&SL Analysis for {group_name}...")
        
        # Get TP/SL analysis for the group
        tp_sl = await get_tp_sl(group_name)
        
        if tp_sl:
            # Format response with TP/SL statistics
            response = (
                f"Group Name: {group_name}\n\n"
                f"TP (12h): {round(tp_sl['12h_tp'], 2)}%\n"
                f"SL (12h): {round(tp_sl['12h_sl'], 2)}%\n\n"
                f"TP (24h): {round(tp_sl['24h_tp'], 2)}%\n"
                f"SL (24h): {round(tp_sl['24h_sl'], 2)}%\n\n"
                f"TP (48h): {round(tp_sl['48h_tp'], 2)}%\n"
                f"SL (48h): {round(tp_sl['48h_sl'], 2)}%\n"
                f"\nAnalyzed calls: {tp_sl['calls']}"
            )
            
            # Send response with detailed calculations file
            await update.message.reply_document(
                caption=response,
                document=os.path.join(PATH, f"calculations/{group_name}.txt"),
                reply_to_message_id=update.message.id
            )
        else:
            await update.message.reply_text(f"Group '{group_name}' not found or no relevant data available.", reply_to_message_id=update.message.id)
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}", reply_to_message_id=update.message.id)

async def get_tp_sl(channel_username):
    """
    Calculate Take Profit and Stop Loss levels for a given channel.
    
    Args:
        channel_username (str): The username of the Telegram channel to analyze
        
    Returns:
        dict: Dictionary containing TP/SL statistics for different timeframes
    """
    # Load existing data
    data = load_data()
    
    # If channel not in data, perform new analysis
    if channel_username not in data:
        founded_cas = {}  # Dictionary to store found contract addresses
        calculations = f"\n\nGroup {channel_username} calculations: \n\n"
        
        # Get channel entity
        channel = await client.get_entity(channel_username)
        offset_id = 0
        
        # Fetch message history
        while True:
            history = await client(GetHistoryRequest(
                peer=PeerChannel(channel.id),
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=100,
                max_id=0,
                min_id=0,
                hash=0
            ))
            
            # Break if no more messages
            if not history.messages:
                log("No more messages to fetch.")
                break
            
            # Break if address limit reached
            if len(founded_cas) > address_limit:
                log(f"Exceeded {address_limit} CAs.")
                break

            # Process each message
            for message in history.messages:
                try:
                    # Skip old messages
                    if message.date < date_limit:
                        log("Reached old messages.")
                        break
                    
                    # Process message if it contains text
                    if message.message:
                        # Detect contract address and chain
                        ca = detect_ca_and_chain(message.message)
                        if ca:
                            # Confirm and store contract address
                            address, chain = confirm_ca(ca["address"], ca["chain"])
                            log(f"Found contract address: {address}")
                            founded_cas[address] = {
                                "address": address,
                                "chain": chain,
                                "timestamp": int(message.date.timestamp())
                            }
                except Exception as e:
                    log(e)
            
            # Update offset for next batch
            offset_id = history.messages[-1].id
            if history.messages[-1].date < date_limit:
                break

        # Initialize lists for price data
        _12h_highs = []
        _12h_lows = []
        _24h_highs = []
        _24h_lows = []
        _48h_highs = []
        _48h_lows = []

        log(f"Found {len(founded_cas)} contract addresses")
        
        # Process each contract address
        for datum in founded_cas.values():
            try:
                initial_timestamp = datum["timestamp"]
                address = datum["address"]
                chain = datum["chain"]
                
                # Skip Ethereum addresses (if needed)
                if chain == "ethereum":
                    continue
                
                calculations += f"\nCalculations for CA: {address}\n"
                
                # Get initial price
                initial = get_price(address, chain, initial_timestamp)
                if initial:
                    # Get price history for different timeframes
                    _12h_high, _12h_low = get_price_history(address, chain, initial_timestamp, 
                        int((datetime.fromtimestamp(initial_timestamp) + timedelta(hours=12)).timestamp()))
                    _24h_high, _24h_low = get_price_history(address, chain, initial_timestamp, 
                        int((datetime.fromtimestamp(initial_timestamp) + timedelta(hours=24)).timestamp()))
                    _48h_high, _48h_low = get_price_history(address, chain, initial_timestamp, 
                        int((datetime.fromtimestamp(initial_timestamp) + timedelta(hours=48)).timestamp()))

                    # Calculate percentage changes
                    _12h_highs.append(((_12h_high - initial)/initial)*100)
                    _12h_lows.append(((_12h_low - initial)/initial)*100)
                    _24h_highs.append(((_24h_high - initial)/initial)*100)
                    _24h_lows.append(((_24h_low - initial)/initial)*100)
                    _48h_highs.append(((_48h_high - initial)/initial)*100)
                    _48h_lows.append(((_48h_low - initial)/initial)*100)

                    # Add calculations to log
                    calculations += f"Initial Price at time of call: ${initial}\n"
                    calculations += f"12hour High Price: ${_12h_high} & 12hour Low Price: ${_12h_low}\n"
                    calculations += f"24hour High Price: ${_24h_high} & 24hour Low Price: ${_24h_low}\n"
                    calculations += f"48hour High Price: ${_48h_high} & 48hour Low Price: ${_48h_low}\n"
            except:
                pass
        
        # Calculate median values for each timeframe
        _12h_tp = calculate_median(_12h_highs)
        _12h_sl = calculate_median(_12h_lows)
        _24h_tp = calculate_median(_24h_highs)
        _24h_sl = calculate_median(_24h_lows)
        _48h_tp = calculate_median(_48h_highs)
        _48h_sl = calculate_median(_48h_lows)
        
        # Store results in data dictionary
        data[channel_username] = {
            "12h_tp": _12h_tp,
            "12h_sl": _12h_sl,
            "24h_tp": _24h_tp,
            "24h_sl": _24h_sl,
            "48h_tp": _48h_tp,
            "48h_sl": _48h_sl,
            "calls": len(founded_cas)
        }
        
        # Save updated data
        save_data(data)

        # Add final calculations to log
        calculations += "\n\nFinal Outcome:\n"
        calculations += f"12hour TP: {_12h_tp}%\n"
        calculations += f"12hour SL: {_12h_sl}%\n"
        calculations += f"24hour TP: {_24h_tp}%\n"
        calculations += f"24hour SL: {_24h_sl}%\n"
        calculations += f"48hour TP: {_48h_tp}%\n"
        calculations += f"48hour SL: {_48h_sl}%\n"
        
        # Save calculations to file
        create_calculation_file(channel_username, calculations)
    
    log("Sent")
    return data[channel_username]

def get_price(token, chain, time):
    """
    Get the price of a token at a specific time using Birdeye API.
    
    Args:
        token (str): Token contract address
        chain (str): Blockchain network
        time (int): Unix timestamp
        
    Returns:
        float: Token price at specified time
    """
    headers = {
        "accept": "application/json",
        "x-chain": chain,
        "x-api-key": birdeye_api_key
    }
    try:
        response = requests.get(f"https://public-api.birdeye.so/defi/historical_price_unix?address={token}&unixtime={time}", headers=headers).json()
        return response["data"]["value"]
    except Exception as e:
        return 0.00

def get_price_history(token, chain, from_time, to_time):
    """
    Get price history for a token within a time range.
    
    Args:
        token (str): Token contract address
        chain (str): Blockchain network
        from_time (int): Start timestamp
        to_time (int): End timestamp
        
    Returns:
        tuple: (highest_price, lowest_price) in the time range
    """
    headers = {
        "accept": "application/json",
        "x-chain": chain,
        "x-api-key": birdeye_api_key
    }
    try:
        prices = []
        response = requests.get(f"https://public-api.birdeye.so/defi/history_price?address={token}&address_type=token&type=1m&time_from={from_time}&time_to={to_time}", headers=headers).json()
        for price in response["data"]["items"]:
            prices.append(price["value"])
        return max(prices), min(prices)
    except Exception as e:
        return 0.00, 0.00

def detect_ca_and_chain(text):
    """
    Detect contract address and blockchain network from text.
    
    Args:
        text (str): Text to analyze
        
    Returns:
        dict: Dictionary containing address and chain information
    """
    eth_bsc_ca_pattern = r"\b0x[a-fA-F0-9]{40}\b"
    sol_ca_pattern = r"\b[A-HJ-NP-Za-km-z1-9]{32,44}\b"
    if re.search(sol_ca_pattern, text):
        result = {"address": re.search(sol_ca_pattern, text).group(0), "chain": "solana"}
    else:
        result = None
    return result

def confirm_ca(address, chain):
    """
    Confirm contract address validity using DexScreener API.
    
    Args:
        address (str): Contract address
        chain (str): Blockchain network
        
    Returns:
        tuple: (confirmed_address, confirmed_chain)
    """
    try:
        response = requests.get(f"https://io.dexscreener.com/dex/pair-details/v3/{chain}/{address}", impersonate="chrome").json()
        return response["ti"]["address"], response["ti"]["chain"]["id"]
    except Exception as e:
        return address, chain
    
def calculate_median(prices):
    """
    Calculate median value from a list of prices.
    
    Args:
        prices (list): List of price values
        
    Returns:
        float: Median value
    """
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    mid = n // 2
    if n % 2 == 0:
        m = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    else:
        m = sorted_prices[mid]
    return m

def calculate_tp_sl(initial_price, high, low):
    tp = (high*initial_price) + initial_price
    sl = (low*initial_price) + initial_price
    return tp, sl

def load_data(file_name="data.json", empty={}):
    """
    Load data from JSON file.
    
    Args:
        file_name (str): Name of the JSON file
        empty (dict): Default value if file doesn't exist
        
    Returns:
        dict: Loaded data
    """
    f = os.path.join(PATH, file_name)
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    else:
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(empty, file)
        return empty

def save_data(data, file_name="data.json"):
    """
    Save data to JSON file.
    
    Args:
        data (dict): Data to save
        file_name (str): Name of the JSON file
    """
    f = os.path.join(PATH, file_name)
    with open(f, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

def create_calculation_file(filename, content):
    """
    Create a file with calculation details.
    
    Args:
        filename (str): Name of the file
        content (str): Content to write
    """
    try:
        with open(os.path.join(PATH, f"calculations/{filename}.txt"), 'w') as file:
            file.write(content)
        log(f"File '{filename}' created successfully.")
    except Exception as e:
        log(f"An error occurred: {e}")

def log(*msg):
    """
    Log messages to file and console.
    
    Args:
        *msg: Variable number of message arguments
    """
    with open(os.path.join(PATH, "log.txt"), 'a') as log:
        log.write('[{:%d/%m/%Y - %H:%M:%S}] {}\n'.format(datetime.now(), *msg))
    print('[{:%d/%m/%Y - %H:%M:%S}] {}'.format(datetime.now(), *msg))

def main():
    """
    Main function to start the bot.
    """
    log("Bot is running...")
    application = Application.builder().token(telegram_bot_token).build()
    application.add_handler(CommandHandler("scan", handle_scan))
    application.run_polling()

if __name__ == "__main__":
    main()