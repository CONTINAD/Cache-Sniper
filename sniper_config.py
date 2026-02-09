import os
from dotenv import load_dotenv

load_dotenv()

# --- Wallet & RPC ---
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
PRIORITY_FEE = float(os.getenv("PRIORITY_FEE", "0.001"))

# --- Sniper Settings ---
# Target Market Cap to buy (in SOL)
# Example: Buy when Mcap is between 10 and 20 SOL
TARGET_MCAP_MIN_SOL = 5.0
TARGET_MCAP_MAX_SOL = 20.0

# Buy Amount in SOL
BUY_AMOUNT_SOL = 0.05

# --- Selling Parameters ---
# Take Profit (TP) Multiplier (e.g., 2.0 = 2x, 100% gain)
TAKE_PROFIT_MULTIPLIER = 2.0

# Stop Loss (SL) Percentage (e.g., 0.5 = 50% loss)
STOP_LOSS_PERCENTAGE = 0.5

# Trailing Stop? (Advanced, maybe later)
USE_TRAILING_STOP = False

# --- Auto-Sell Settings ---
# Check position every X seconds
CHECK_INTERVAL = 2.0

# --- Safety ---
DRY_RUN = True # Set to False to trade with real money
