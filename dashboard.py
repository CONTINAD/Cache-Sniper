import streamlit as st
import subprocess
import os
import signal
import time
import sys
import pandas as pd

# Set page config
st.set_page_config(page_title="Cache Sniper", page_icon="🎯", layout="wide")

# Custom CSS for "Good UI"
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .metric-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    h1 {
        color: #FF4B4B;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Cache Sniper Dashboard")

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Load current config (simple parsing)
    # Ideally, use importlib but let's read/write file for persistence
    config_path = "sniper_config.py"
    
    # Read existing config values
    # For simplicity, we'll just overwrite with defaults/user inputs
    # In production, parse the python file.
    
    target_min = st.number_input("Min Market Cap (SOL)", value=5.0)
    target_max = st.number_input("Max Market Cap (SOL)", value=20.0)
    buy_amount = st.number_input("Buy Amount (SOL)", value=0.05)
    take_profit = st.number_input("Take Profit Multiplier (x)", value=2.0)
    stop_loss = st.number_input("Stop Loss % (0.5 = 50%)", value=0.5)
    dry_run = st.toggle("Dry Run Mode", value=True)
    
    if st.button("Save Configuration"):
        with open(config_path, "w") as f:
            f.write("import os\n")
            f.write("from dotenv import load_dotenv\n\n")
            f.write("load_dotenv()\n\n")
            f.write(f'SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")\n')
            f.write(f'RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")\n')
            f.write(f'PRIORITY_FEE = float(os.getenv("PRIORITY_FEE", "0.001"))\n\n')
            f.write(f"TARGET_MCAP_MIN_SOL = {target_min}\n")
            f.write(f"TARGET_MCAP_MAX_SOL = {target_max}\n")
            f.write(f"BUY_AMOUNT_SOL = {buy_amount}\n")
            f.write(f"TAKE_PROFIT_MULTIPLIER = {take_profit}\n")
            f.write(f"STOP_LOSS_PERCENTAGE = {stop_loss}\n")
            f.write(f"CHECK_INTERVAL = 2.0\n")
            f.write(f"DRY_RUN = {dry_run}\n")
        st.success("Configuration Saved!")

# --- Main Area ---

# Bot Control
col1, col2 = st.columns(2)

# Check if bot is running (pid file)
PID_FILE = "bot.pid"

def is_bot_running():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read())
            os.kill(pid, 0) # Check if process exists
            return True, pid
        except:
            return False, None
    return False, None

running, pid = is_bot_running()

with col1:
    if not running:
        if st.button("🚀 Start Sniper Bot", type="primary"):
            # Start process
            process = subprocess.Popen([sys.executable, "sniper_bot.py"], stdout=open("bot_output.log", "w"), stderr=subprocess.STDOUT)
            with open(PID_FILE, "w") as f:
                f.write(str(process.pid))
            st.rerun()
    else:
        st.info(f"Bot is Running (PID: {pid})")

with col2:
    if running:
        if st.button("🛑 Stop Sniper Bot", type="secondary"):
            try:
                os.kill(pid, signal.SIGTERM)
            except:
                pass
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            st.rerun()

# Logs
st.subheader("📜 Live Logs")
log_placeholder = st.empty()

if os.path.exists("bot_output.log"):
    with open("bot_output.log", "r") as f:
        # Read last 20 lines
        lines = f.readlines()[-20:]
        log_content = "".join(lines)
        log_placeholder.code(log_content)
else:
    log_placeholder.info("No logs yet.")

# Auto-refresh logic (hacky for streamlit, but works)
if running:
    time.sleep(1)
    st.rerun()
