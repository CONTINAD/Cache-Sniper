import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '0'))

# Axiom Configuration
AXIOM_EMAIL = os.getenv('AXIOM_EMAIL', '').strip()
AXIOM_PASSWORD = os.getenv('AXIOM_PASSWORD', '').strip()
AXIOM_ACCESS_TOKEN = os.getenv('AXIOM_ACCESS_TOKEN', '').strip()
AXIOM_REFRESH_TOKEN = os.getenv('AXIOM_REFRESH_TOKEN', '').strip()

# Solana Configuration
SOLANA_PRIVATE_KEY = os.getenv('SOLANA_PRIVATE_KEY')
RPC_URL = os.getenv('RPC_URL', 'https://api.mainnet-beta.solana.com')

# Trading Settings
REAL_MODE = True  # LIVE TRADING ENABLED
PAPER_TRADE_AMOUNT = 0.05  # 0.05 SOL per trade (live)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
STRATEGY_LAB_WEBHOOK_URL = "https://discord.com/api/webhooks/1448451803170607164/D42fs15bIVMfYbWuTXBfkYLhzQ2G7YnYD8XhHIT1am4hiq5d6ArvAWFgbcY_QyYzM4GJ"
# Dynamic Position Sizing (based on balance)
def get_position_size(balance_sol: float) -> float:
    """Fixed 0.05 SOL per trade for live trading."""
    RESERVE = 0.005  # Keep this much for fees
    BUY_SIZE = 0.05  # Live trade size
    
    available = balance_sol - RESERVE
    if available < BUY_SIZE:
        return 0  # Not enough balance
    
    return BUY_SIZE

# Risk Management (SNIPER MODE: CAPITAL PRESERVATION)
HARD_STOP_LOSS = 0.70  # -30% (User defined standard)
TRAILING_STOP_PERCENT = 0.35  # 35% trail

# Entry Filters (Sniper Config: AVOID THE TRAPS)
MAX_ENTRY_MC = 60000        # $60k Max (Strict limit to avoid -99% rugs)
MIN_ENTRY_MC = 12000        # $12k Min
MAX_TOKEN_AGE_MINUTES = 45  # Fresh launches only

# Multi-Tier Take Profit Strategy (Approved Config)
TP1_FACTOR = 1.8   # 1.8x
TP1_AMOUNT = 0.50  # Sell 50% (Secure capital + Profit)
TP1_SL = 1.4       # Move SL to entry * 1.4

TP2_FACTOR = 3.0   # 3x
TP2_AMOUNT = 0.20  # Sell 20%
TP2_SL = 2.0       # Move SL to 2x

# Extended Take Profits
TP3_FACTOR = 5.0   # 5x
TP3_AMOUNT = 0.15  # Sell 15%
TP3_SL = 3.0       # Move SL to 3x

TP4_FACTOR = 10.0  # 10x
TP4_AMOUNT = 0.10  # Sell 10%
# Final 5% moonbag trails

# Solana Execution
PRIORITY_FEE = 0.0003  # SOL - increased for faster execution
SLIPPAGE_BPS = 1500  # 15%
SIMULATED_SLIPPAGE = 0.02  # 2% for paper trading= 0.0001
INITIAL_BALANCE = 10.0

# Telegram Configuration (for signal listening)
# Get these from https://my.telegram.org
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID', '')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
# List of channel usernames or IDs to monitor (comma-separated in .env)
TELEGRAM_CHANNELS_RAW = os.getenv('TELEGRAM_CHANNELS', '')
TELEGRAM_CHANNELS = [c.strip() for c in TELEGRAM_CHANNELS_RAW.split(',') if c.strip()]

# Telegram Broadcast Channel (for sending calls after buys)
TELEGRAM_BROADCAST_CHANNEL = os.getenv('TELEGRAM_BROADCAST_CHANNEL', '@JimmyCalls100x')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
AXIOM_REFERRAL_CODE = os.getenv('AXIOM_REFERRAL_CODE', 'cache')
GARDEN_CALLS_DISCORD_WEBHOOK = os.getenv('GARDEN_CALLS_DISCORD_WEBHOOK', '')

# Caller Tracking Webhooks
ZEUS_CALLS_WEBHOOK = os.getenv('ZEUS_CALLS_WEBHOOK', '')
ZEUS_RESULTS_WEBHOOK = os.getenv('ZEUS_RESULTS_WEBHOOK', '')

GEMS_CALLS_WEBHOOK = os.getenv('GEMS_CALLS_WEBHOOK', '')
GEMS_RESULTS_WEBHOOK = os.getenv('GEMS_RESULTS_WEBHOOK', '')

RHYSKY_CALLS_WEBHOOK = os.getenv('RHYSKY_CALLS_WEBHOOK', '')
RHYSKY_RESULTS_WEBHOOK = os.getenv('RHYSKY_RESULTS_WEBHOOK', '')

FOURAM_CALLS_WEBHOOK = os.getenv('FOURAM_CALLS_WEBHOOK', '')
FOURAM_RESULTS_WEBHOOK = os.getenv('FOURAM_RESULTS_WEBHOOK', '')

AXE_CALLS_WEBHOOK = os.getenv('AXE_CALLS_WEBHOOK', '')
AXE_RESULTS_WEBHOOK = os.getenv('AXE_RESULTS_WEBHOOK', '')

LEGION_CALLS_WEBHOOK = os.getenv('LEGION_CALLS_WEBHOOK', '')
LEGION_RESULTS_WEBHOOK = os.getenv('LEGION_RESULTS_WEBHOOK', '')

SPIDER_CALLS_WEBHOOK = os.getenv('SPIDER_CALLS_WEBHOOK', '')
SPIDER_RESULTS_WEBHOOK = os.getenv('SPIDER_RESULTS_WEBHOOK', '')

# PFUltimate Configuration (Primary Source)
PFULTIMATE_CALLS_WEBHOOK = os.getenv('PFULTIMATE_CALLS_WEBHOOK', '')
PFULTIMATE_RESULTS_WEBHOOK = os.getenv('PFULTIMATE_RESULTS_WEBHOOK', '')

# Multi-Source Signal Settings
SIGNAL_BOOST_WINDOW_MINS = 5  # Time window for second source to boost
SIGNAL_BOOST_AMOUNT = 0.0     # DISABLED - set to 0.50 to re-enable (50% boost)

# Twitter/X Narrative Scanner Configuration
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME', '')
TWITTER_EMAIL = os.getenv('TWITTER_EMAIL', '')
TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD', '')
TWITTER_SCANNER_ENABLED = os.getenv('TWITTER_SCANNER_ENABLED', 'false').lower() == 'true'

# X Sentiment Analysis Configuration (Pre-Buy Check)
X_SENTIMENT_ENABLED = os.getenv('X_SENTIMENT_ENABLED', 'true').lower() == 'true'
X_SENTIMENT_MIN_MENTIONS = int(os.getenv('X_SENTIMENT_MIN_MENTIONS', '5'))
X_SENTIMENT_TIME_WINDOW_MINS = int(os.getenv('X_SENTIMENT_TIME_WINDOW_MINS', '15'))
X_SENTIMENT_MIN_ACCOUNT_QUALITY = float(os.getenv('X_SENTIMENT_MIN_ACCOUNT_QUALITY', '0.4'))
X_SENTIMENT_MAX_BOT_RATIO = float(os.getenv('X_SENTIMENT_MAX_BOT_RATIO', '0.30'))
X_SENTIMENT_BYPASS_HIGH_MC = int(os.getenv('X_SENTIMENT_BYPASS_HIGH_MC', '100000'))

