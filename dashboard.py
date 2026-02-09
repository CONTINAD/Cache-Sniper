import streamlit as st
import subprocess
import os
import signal
import time
import sys
import pandas as pd
import json
from dotenv import load_dotenv

# --- Setup & Style ---
st.set_page_config(page_title="Cache Sniper Pro", page_icon="⚡", layout="wide")

# Modern Premium UI
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background: linear-gradient(to bottom right, #0F172A, #1E293B);
        color: #F8FAFC;
    }
    
    /* Headings */
    h1, h2, h3 {
        color: #38BDF8 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Metrics */
    div[data-testid="stMetric"] {
        background-color: #334155;
        border: 1px solid #475569;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Inputs */
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: #1E293B;
        color: white;
        border: 1px solid #475569;
        border-radius: 8px;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #3B82F6, #8B5CF6);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
    
    /* Logs Container */
    .log-box {
        background-color: #000000;
        color: #00FF41;
        font-family: 'Courier New', monospace;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        height: 400px;
        overflow-y: scroll;
    }
</style>
""", unsafe_allow_html=True)

# --- State Management ---
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False

# --- Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/7541/7541334.png", width=60)
    st.title("⚡ Cache Sniper")
    st.caption("v2.0.0 | Enterprise Edition")
    
    st.markdown("---")
    
    # 🔐 Wallet Config
    st.subheader("🔐 Wallet")
    # Load .env for private key if exists
    load_dotenv()
    current_key = os.getenv("SOLANA_PRIVATE_KEY", "")
    
    private_key_input = st.text_input("Solana Private Key", value=current_key, type="password", help="Stored locally in .env")
    rpc_input = st.text_input("RPC URL", value=os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com"))
    
    if st.button("💾 Save Credentials"):
        # Save to .env
        with open(".env", "w") as f:
            f.write(f"SOLANA_PRIVATE_KEY={private_key_input}\n")
            f.write(f"RPC_URL={rpc_input}\n")
            f.write(f"PRIORITY_FEE=0.001\n") # Default
        st.success("Credentials updated!")

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Dashboard", "⚙️ Sniper Config", "📊 Analytics"])

# Load Config Logic
CONFIG_PATH = "sniper_config.py"

def load_config():
    # Simple parsing or import
    # For UI, we often want read-write safe.
    # Let's read defaults from the file content we know
    defaults = {
        "TARGET_MCAP_MIN_SOL": 5.0,
        "TARGET_MCAP_MAX_SOL": 20.0,
        "BUY_AMOUNT_SOL": 0.05,
        "TAKE_PROFIT_MULTIPLIER": 2.0,
        "STOP_LOSS_PERCENTAGE": 0.5,
        "TARGET_DEVS": [],
        "DRY_RUN": True
    }
    # In a real app, use AST or importlib. 
    # For now, we rely on the user having formatted it cleanly or us overwriting.
    return defaults

# --- Tab 1: Dashboard ---
with tab1:
    col_status, col_control = st.columns([2, 1])
    
    # Check Process
    PID_FILE = "bot.pid"
    running = False
    pid = None
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read())
            os.kill(pid, 0)
            running = True
        except:
            pass

    with col_status:
        st.subheader("📡 Live Activity")
        
        # Status Badge
        if running:
            st.success(f"● Bot is Active (PID: {pid})")
        else:
            st.error("● Bot is Stopped")
            
        # Live Logs
        log_placeholder = st.empty()
        if os.path.exists("bot_output.log"):
            with open("bot_output.log", "r") as f:
                lines = f.readlines()[-30:]
                log_content = "".join(lines)
                st.code(log_content, language="bash")
        else:
            st.info("No logs found. Start the bot to see activity.")

    with col_control:
        st.subheader("🕹️ Controls")
        if not running:
            if st.button("▶️ START BOT", use_container_width=True):
                # Ensure credentials exist
                if not private_key_input:
                    st.toast("❌ Please set Private Key in Sidebar first!", icon="⚠️")
                else:
                    process = subprocess.Popen([sys.executable, "sniper_bot.py"], stdout=open("bot_output.log", "w"), stderr=subprocess.STDOUT)
                    with open(PID_FILE, "w") as f:
                        f.write(str(process.pid))
                    st.rerun()
        else:
            if st.button("⏹️ STOP BOT", type="primary", use_container_width=True):
                try:
                    os.kill(pid, signal.SIGTERM)
                except:
                    pass
                if os.path.exists(PID_FILE):
                    os.remove(PID_FILE)
                st.rerun()
        
        st.markdown("---")
        st.metric("Total Snipes", "0", "+0 today")
        st.metric("Active Positions", "0")

# --- Tab 2: Config ---
with tab2:
    st.subheader("🎯 Sniper Strategy")
    
    c1, c2 = st.columns(2)
    
    # We will read values from config file logic or just use UI state to overwrite
    # For this demo, we assume defaults or overwrite.
    
    with c1:
        st.markdown("#### 💰 Entry Settings")
        min_mcap = st.number_input("Min Market Cap (SOL)", 0.0, 1000.0, 5.0)
        max_mcap = st.number_input("Max Market Cap (SOL)", 0.0, 1000.0, 20.0)
        buy_amt = st.number_input("Buy Amount (SOL)", 0.01, 10.0, 0.05)
        
    with c2:
        st.markdown("#### 🛡️ Exit Settings")
        tp = st.number_input("Take Profit (x)", 1.1, 100.0, 2.0, help="2.0 means 2x (100% profit)")
        sl = st.number_input("Stop Loss %", 0.1, 0.99, 0.5, help="0.5 means 50% loss")
        
    st.markdown("---")
    st.markdown("#### 👨‍💻 Dev Sniping")
    st.caption("Automatically buy any token launched by these addresses.")
    
    devs_str = st.text_area("Target Dev Addresses (One per line)", height=100, placeholder="Address1\nAddress2...")
    
    st.markdown("---")
    dry_run_mode = st.toggle("🧪 Dry Run Mode (Simulation)", value=True, help="Disable to trade real money.")
    
    if st.button("💾 Save Strategy"):
        # Parse devs
        dev_list = [d.strip() for d in devs_str.split('\n') if d.strip()]
        
        with open(CONFIG_PATH, "w") as f:
            f.write("import os\n")
            f.write("from dotenv import load_dotenv\n\n")
            f.write("load_dotenv()\n\n")
            f.write(f'SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")\n')
            f.write(f'RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")\n')
            f.write(f'PRIORITY_FEE = float(os.getenv("PRIORITY_FEE", "0.001"))\n\n')
            f.write(f"TARGET_MCAP_MIN_SOL = {min_mcap}\n")
            f.write(f"TARGET_MCAP_MAX_SOL = {max_mcap}\n")
            f.write(f"BUY_AMOUNT_SOL = {buy_amt}\n")
            f.write(f"TAKE_PROFIT_MULTIPLIER = {tp}\n")
            f.write(f"STOP_LOSS_PERCENTAGE = {sl}\n")
            f.write(f"TARGET_DEVS = {json.dumps(dev_list)}\n")
            f.write(f"CHECK_INTERVAL = 2.0\n")
            f.write(f"DRY_RUN = {dry_run_mode}\n")
        st.success("Configuration saved! Restart bot to apply changes.")

# --- Tab 3: Analytics ---
with tab3:
    st.subheader("📈 Performance Analytics")
    
    # Mock Data for Visuals
    # In real app, read from 'trades.json' or database
    
    a1, a2, a3 = st.columns(3)
    a1.metric("Win Rate", "65%", "+5%")
    a2.metric("Total Profit", "12.4 SOL", "+1.2 SOL")
    a3.metric("Best Snipe", "8.5x", "User32...99")
    
    st.markdown("### Recent Trades")
    
    mock_data = {
        "Token": ["HitlerCoin", "ChillGuy", "BasedAI", "PepeFrog", "Doge2"],
        "Entry (Mcap)": ["12 SOL", "8 SOL", "15 SOL", "10 SOL", "18 SOL"],
        "Result": ["+2.1x", "+1.5x", "-50% (SL)", "+3.0x", "+0.2x"],
        "Status": ["SOLD", "SOLD", "SOLD", "SOLD", "HELD"]
    }
    df = pd.DataFrame(mock_data)
    
    st.dataframe(
        df,
        column_config={
            "Result": st.column_config.TextColumn(
                "PnL",
                help="Profit/Loss Multiplier",
                validate="^[0-9]",
            ),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.caption("Analytics data is currently mocked. Connect database to see real history.")

# Auto-Refresh logs
if running:
    time.sleep(2)
    st.rerun()
