import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import os
import json
import requests
import asyncio
import streamlit.components.v1 as components
import textwrap
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import Database
# Ears and Axiom removed - not in use

# Initialize Database Globally
db = Database()

from src.config import SOLANA_PRIVATE_KEY, RPC_URL, INITIAL_BALANCE
from src.strategy_lab import StrategyLab

# 🚀 DISPLAY ENHANCEMENT MULTIPLIER (makes profits look bigger)
FLEX_MULTIPLIER = 2.0

# Source Configuration for UI
SOURCE_CONFIG = {
    'discord': {'icon': '🎮', 'name': 'Zeus Calls', 'color': '#5865F2', 'platform': 'Discord'},
    'zeus': {'icon': '🎮', 'name': 'Zeus Calls', 'color': '#5865F2', 'platform': 'Discord'},
    'telegram': {'icon': '✈️', 'name': 'Telegram', 'color': '#0088cc', 'platform': 'Telegram'},
    'gems': {'icon': '💎', 'name': 'Gem Tools', 'color': '#0088cc', 'platform': 'Telegram'},
    'rhysky': {'icon': '⚡', 'name': 'Rhysky', 'color': '#f59e0b', 'platform': 'Telegram'},
    '4am': {'icon': '🌙', 'name': '4AM Signals', 'color': '#8b5cf6', 'platform': 'Telegram'},
    'axe': {'icon': '🪓', 'name': 'Axe Calls', 'color': '#ef4444', 'platform': 'Telegram'},
    'legion': {'icon': '⚔️', 'name': 'Legion Calls', 'color': '#10b981', 'platform': 'Discord'},
    'spider': {'icon': '🕷️', 'name': 'Spider Journal', 'color': '#6366f1', 'platform': 'Telegram'},
    'pfultimate': {'icon': '🎯', 'name': 'PF Alerts', 'color': '#22c55e', 'platform': 'Telegram'},
}

# Strategy Lab disabled - backtester module missing
# from src.strategies import ALL_STRATEGIES
# from src.backtester import backtester, STARTING_BALANCE
STRATEGY_LAB_ENABLED = False

# --- Page Config ---
st.set_page_config(
    page_title="QuickTrade // Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Cyberpunk / Glassmorphism CSS ---
st.markdown("""
<style>
    /* Global Theme - DRAMATIC NEON */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=Inter:wght@400;600;800&display=swap');

    .stApp {
        background: linear-gradient(135deg, #0a0a1a 0%, #0d0d2b 50%, #0a0a1a 100%);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        font-family: 'Inter', sans-serif;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Animated grid overlay */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            linear-gradient(rgba(56, 189, 248, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(56, 189, 248, 0.03) 1px, transparent 1px);
        background-size: 50px 50px;
        pointer-events: none;
        z-index: 0;
    }

    /* Hide Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(15, 23, 42, 0.5);
        padding: 8px;
        border-radius: 12px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #64748b;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        padding: 12px 24px;
        border-radius: 8px;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.3) 0%, rgba(139, 92, 246, 0.2) 100%) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(139, 92, 246, 0.4);
    }
    
    /* Typography */
    h1, h2, h3 {
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: -0.5px;
    }
    
    /* Hero Stats Cards - NEON GLOW */
    .metric-card {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(20, 30, 50, 0.9) 100%);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 20px;
        padding: 28px;
        backdrop-filter: blur(20px);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 
            0 0 20px rgba(56, 189, 248, 0.1),
            0 10px 40px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.1), transparent);
        animation: shimmer 3s infinite;
    }
    
    @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    .metric-card:hover {
        transform: translateY(-5px) scale(1.02);
        border-color: rgba(56, 189, 248, 0.6);
        box-shadow: 
            0 0 40px rgba(56, 189, 248, 0.3),
            0 20px 60px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    
    .metric-label {
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 10px;
    }
    
    .metric-value {
        font-size: 2.8rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #38bdf8 0%, #a855f7 50%, #38bdf8 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: textGlow 3s ease infinite;
        filter: drop-shadow(0 0 15px rgba(56, 189, 248, 0.4));
    }
    
    @keyframes textGlow {
        0%, 100% { background-position: 0% 50%; filter: drop-shadow(0 0 15px rgba(56, 189, 248, 0.4)); }
        50% { background-position: 100% 50%; filter: drop-shadow(0 0 25px rgba(168, 85, 247, 0.6)); }
    }
    
    .metric-delta {
        font-size: 1rem;
        font-weight: 700;
        margin-left: 10px;
    }
    
    /* Wallet Badge */
    .wallet-badge {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(56, 189, 248, 0.05) 100%);
        border: 1px solid rgba(56, 189, 248, 0.4);
        color: #38bdf8;
        padding: 10px 20px;
        border-radius: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.15);
    }

    /* Trade Cards - Premium */
    .trade-card {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.9) 0%, rgba(15, 23, 42, 0.7) 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 20px;
        padding: 0;
        margin-bottom: 24px;
        overflow: hidden;
        position: relative;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
    }
    
    .trade-card:hover {
        border-color: rgba(56, 189, 248, 0.5);
        box-shadow: 0 15px 50px rgba(56, 189, 248, 0.1);
    }
    
    .trade-header {
        background: linear-gradient(90deg, rgba(56, 189, 248, 0.15) 0%, transparent 100%);
        padding: 16px 24px;
        border-bottom: 1px solid rgba(56, 189, 248, 0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .trade-body {
        padding: 24px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }
    
    .trade-stat {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .ts-label { 
        font-size: 0.7rem; 
        color: #475569; 
        text-transform: uppercase; 
        letter-spacing: 1px;
        font-weight: 600;
    }
    .ts-val { 
        font-size: 1.15rem; 
        color: #e2e8f0; 
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
    }
    
    .pnl-badge {
        font-size: 1.8rem;
        font-weight: 800;
        padding: 8px 16px;
        border-radius: 12px;
        font-family: 'JetBrains Mono', monospace;
        text-shadow: 0 0 20px currentColor;
    }
    
    .pnl-pos { 
        color: #4ade80; 
        background: linear-gradient(135deg, rgba(74, 222, 128, 0.2) 0%, rgba(74, 222, 128, 0.05) 100%); 
        border: 1px solid rgba(74, 222, 128, 0.3);
        box-shadow: 0 0 30px rgba(74, 222, 128, 0.2);
    }
    .pnl-neg { 
        color: #f87171; 
        background: linear-gradient(135deg, rgba(248, 113, 113, 0.2) 0%, rgba(248, 113, 113, 0.05) 100%); 
        border: 1px solid rgba(248, 113, 113, 0.3);
        box-shadow: 0 0 30px rgba(248, 113, 113, 0.2);
    }

    /* Status Pills - Glowing */
    .status-pill {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-open { 
        background: rgba(56, 189, 248, 0.2); 
        color: #38bdf8; 
        border: 1px solid rgba(56, 189, 248, 0.4);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
    }
    .status-moonbag { 
        background: rgba(168, 85, 247, 0.2); 
        color: #a855f7; 
        border: 1px solid rgba(168, 85, 247, 0.4);
        box-shadow: 0 0 15px rgba(168, 85, 247, 0.3);
    }
    .status-partial {
        background: rgba(251, 191, 36, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.4);
        box-shadow: 0 0 15px rgba(251, 191, 36, 0.3);
    }
    
    /* Source Badges - Discord & Telegram */
    .source-badge {
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.65rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    
    .source-discord {
        background: linear-gradient(135deg, rgba(88, 101, 242, 0.25) 0%, rgba(88, 101, 242, 0.1) 100%);
        color: #5865F2;
        border: 1px solid rgba(88, 101, 242, 0.5);
        box-shadow: 0 0 12px rgba(88, 101, 242, 0.3);
        animation: pulse-discord 2s infinite;
    }
    
    .source-telegram {
        background: linear-gradient(135deg, rgba(0, 136, 204, 0.2) 0%, rgba(155, 89, 182, 0.15) 100%);
        color: #0088cc;
        border: 1px solid rgba(0, 136, 204, 0.5);
        box-shadow: 0 0 12px rgba(0, 136, 204, 0.3);
        animation: pulse-telegram 2s infinite;
    }
    
    .source-unknown {
        background: rgba(100, 116, 139, 0.2);
        color: #64748b;
        border: 1px solid rgba(100, 116, 139, 0.3);
    }
    
    @keyframes pulse-discord {
        0%, 100% { box-shadow: 0 0 12px rgba(88, 101, 242, 0.3); }
        50% { box-shadow: 0 0 20px rgba(88, 101, 242, 0.5); }
    }
    
    @keyframes pulse-telegram {
        0%, 100% { box-shadow: 0 0 12px rgba(0, 136, 204, 0.3); }
        50% { box-shadow: 0 0 20px rgba(0, 136, 204, 0.5); }
    }
    
    /* Enhanced Trade Card - Animated Border */
    .trade-card {
        position: relative;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(15, 23, 42, 0.85) 100%);
        border-radius: 20px;
        padding: 0;
        margin-bottom: 24px;
        overflow: hidden;
        box-shadow: 
            0 10px 40px rgba(0, 0, 0, 0.5),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .trade-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        border-radius: 20px;
        padding: 1px;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.3), rgba(139, 92, 246, 0.3), rgba(56, 189, 248, 0.3));
        background-size: 200% 200%;
        animation: gradient-border 4s ease infinite;
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        pointer-events: none;
    }
    
    @keyframes gradient-border {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .trade-card:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: 
            0 20px 60px rgba(56, 189, 248, 0.15),
            0 10px 30px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    
    .trade-card:hover::before {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.6), rgba(139, 92, 246, 0.6), rgba(56, 189, 248, 0.6));
        background-size: 200% 200%;
        animation: gradient-border 2s ease infinite;
    }
    .strategy-card {
        background: linear-gradient(145deg, rgba(20, 20, 40, 0.9) 0%, rgba(10, 10, 25, 0.95) 100%);
        border: 1px solid rgba(100, 100, 255, 0.2);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .strategy-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #a855f7);
    }
    
    .strategy-card:hover {
        border-color: rgba(139, 92, 246, 0.5);
        transform: translateY(-2px);
        box-shadow: 0 20px 40px rgba(139, 92, 246, 0.15);
    }
    
    .strategy-name {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1rem;
        font-weight: 800;
        color: #e2e8f0;
        margin-bottom: 4px;
    }
    
    .pnl-positive { color: #4ade80; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 800; }
    .pnl-negative { color: #f87171; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 800; }
    .pnl-neutral { color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 800; }
    
    .risk-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.6rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .risk-low { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
    .risk-medium { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
    .risk-high { background: rgba(248, 113, 113, 0.2); color: #f87171; }
    .risk-max { background: rgba(239, 68, 68, 0.3); color: #ef4444; }
    
    .leaderboard {
        background: linear-gradient(145deg, rgba(20, 20, 40, 0.9) 0%, rgba(10, 10, 25, 0.95) 100%);
        border: 1px solid rgba(100, 100, 255, 0.2);
        border-radius: 16px;
        padding: 20px;
        backdrop-filter: blur(10px);
    }

</style>
""", unsafe_allow_html=True)

# --- Helpers ---
@st.cache_data(ttl=3)
def get_data():
    db = Database()
    active_trades = pd.DataFrame(db.get_active_trades())
    all_trades = pd.DataFrame(db.get_all_trades())
    
    if not all_trades.empty:
        all_trades['created_at'] = pd.to_datetime(all_trades['created_at'], format='mixed')
        all_trades['pnl_percent'] = all_trades['pnl_percent'].fillna(0.0)
    
    if not active_trades.empty:
        active_trades['created_at'] = pd.to_datetime(active_trades['created_at'], format='mixed')
        active_trades['pnl_percent'] = active_trades['pnl_percent'].fillna(0.0)
        
    return active_trades, all_trades

@st.cache_data(ttl=60) # Cache for 1 minute to avoid rate limits
def get_axiom_data():
    """Fetch trending tokens from Axiom."""
    try:
        client = AxiomClient()
        if client.client and client.client.is_authenticated():
            # Run async method in sync wrapper
            return asyncio.run(client.get_trending('1h'))
    except Exception as e:
        print(f"Error fetching Axiom data: {e}")
    return []

def get_live_price(address: str):
    """Fetch current price and market cap from DexScreener."""
    try:
        response = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}", timeout=2)
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            if pairs:
                sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                if sol_pairs:
                    best_pair = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                    price = float(best_pair['priceUsd'])
                    mc = best_pair.get('marketCap', best_pair.get('fdv', 0))
                    pair_address = best_pair.get('pairAddress')
                    vol = best_pair.get('volume', {})
                    vol_m5 = vol.get('m5', 0)
                    vol_h1 = vol.get('h1', 0)
                    price_change = data.get('pairs', [])[0].get('priceChange', {})
                    return price, mc, pair_address, vol_m5, vol_h1, price_change
    except:
        pass
    return None, None, None, 0, 0, {}

def get_fast_price(address: str) -> float:
    """Ultra-fast price from Jupiter API (sub-100ms latency)."""
    try:
        url = f"https://api.jup.ag/price/v2?ids={address}"
        response = requests.get(url, timeout=0.5)  # Very short timeout for speed
        if response.status_code == 200:
            data = response.json()
            item = data.get('data', {}).get(address, {})
            if item and 'price' in item:
                return float(item['price'])
    except:
        pass
    return None

def get_token_balance_sync(mint_address: str) -> float:
    """Synchronously check if we still hold a token (for cleanup check)."""
    try:
        from solders.keypair import Keypair
        kp = Keypair.from_base58_string(SOLANA_PRIVATE_KEY)
        pubkey = str(kp.pubkey())
        
        # Check both Token programs
        for program_id in ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"]:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    pubkey,
                    {"programId": program_id},
                    {"encoding": "jsonParsed"}
                ]
            }
            res = requests.post(RPC_URL, json=payload, timeout=5).json()
            accounts = res.get('result', {}).get('value', [])
            
            for acc in accounts:
                info = acc['account']['data']['parsed']['info']
                if info['mint'] == mint_address:
                    amount = float(info['tokenAmount']['uiAmount'] or 0)
                    if amount > 0:
                        return amount
        return 0.0
    except Exception as e:
        print(f"⚠️ Balance check error: {e}")
        return -1  # Error flag, don't close trade on error

def check_and_cleanup_stale_trades():
    """
    Check if active trades still have token balances.
    Runs every 15 minutes. Detects manual sells and updates trade status.
    """
    # Use session state to track last cleanup time
    if 'last_cleanup_check' not in st.session_state:
        st.session_state.last_cleanup_check = datetime.now()
    
    time_since_last = (datetime.now() - st.session_state.last_cleanup_check).total_seconds()
    
    # Only run every 15 minutes (900 seconds)
    if time_since_last < 900:
        return
    
    st.session_state.last_cleanup_check = datetime.now()
    print("🧹 Running stale trade cleanup check...")
    
    db = Database()
    active_trades = db.get_active_trades()
    
    for trade in active_trades:
        address = trade['address']
        ticker = trade['ticker']
        balance = get_token_balance_sync(address)
        
        # Parse meta to get entry_tokens
        try:
            meta = json.loads(trade.get('meta', '{}')) if trade.get('meta') else {}
        except:
            meta = {}
        entry_tokens = meta.get('entry_tokens', 0)
        
        if balance == 0:
            # No tokens left - close the trade
            print(f"🧹 Closing stale trade: {ticker} (0 balance)")
            db.update_trade_status(address, 'CLOSED (SOLD)')
        elif balance > 0 and entry_tokens > 0:
            # Check if partial manual sell occurred
            held_pct = (balance / entry_tokens) * 100
            sold_pct = 100 - held_pct
            
            if sold_pct >= 10:  # Only flag if >10% sold manually
                print(f"📊 {ticker}: Manual sell detected! Holding {held_pct:.0f}% ({balance:.2f}/{entry_tokens:.2f} tokens)")
                
                # Update meta with manual sell info
                meta['manual_sell_detected'] = True
                meta['current_tokens'] = balance
                meta['pct_remaining'] = held_pct
                db.update_trade(address, 'PARTIAL (MANUAL)', trade.get('pnl_percent', 0), meta)
            else:
                print(f"✅ {ticker}: holding {balance:.2f} tokens ({held_pct:.0f}%)")
        elif balance > 0:
            print(f"✅ {ticker}: still holding {balance:.2f} tokens")
        # If balance == -1 (error), skip - don't close on error
    
    # Force-close any trades with SELL_REQUEST status (stuck sells)
    import sqlite3
    conn = sqlite3.connect('trades.db')
    cur = conn.cursor()
    cur.execute("UPDATE trades SET status = 'CLOSED' WHERE status = 'SELL_REQUEST'")
    if cur.rowcount > 0:
        print(f"🧹 Force-closed {cur.rowcount} stuck SELL_REQUEST trades")
    conn.commit()
    conn.close()

def get_wallet_balance():
    """Fetch SOL balance from RPC."""
    try:
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        
        kp = Keypair.from_base58_string(SOLANA_PRIVATE_KEY)
        pubkey = str(kp.pubkey())
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [pubkey]
        }
        res = requests.post(RPC_URL, json=payload, timeout=2).json()
        if 'result' in res:
            return res['result']['value'] / 1e9, pubkey
    except Exception as e:
        pass
    return 0.0, "Unknown"

def format_metric(val):
    if val >= 1_000_000:
        return f"${val/1_000_000:.2f}M"
    elif val >= 1_000:
        return f"${val/1_000:.1f}K"
    else:
        return f"${val:.0f}"

def render_axiom_chart(current_price, price_change, entry_price, sl_price, tp1_price, timeframe='24h'):
    """
    Generates a synthetic high-fidelity price curve based on priceChange data.
    Visuals: Neon Spline, Gradient Fill, Trade Markers.
    """
    import numpy as np
    
    # 1. Reconstruct historical price points
    now = datetime.now()
    points = []
    
    # Current
    points.append({'time': 0, 'price': current_price})
    
    # T-5m
    if 'm5' in price_change:
        p_5m = current_price / (1 + price_change['m5']/100)
        points.append({'time': -5, 'price': p_5m})
        
    # T-1h
    if 'h1' in price_change:
        p_1h = current_price / (1 + price_change['h1']/100)
        points.append({'time': -60, 'price': p_1h})
        
    # T-6h
    if 'h6' in price_change:
        p_6h = current_price / (1 + price_change['h6']/100)
        points.append({'time': -360, 'price': p_6h})
        
    # T-24h
    if 'h24' in price_change:
        p_24h = current_price / (1 + price_change['h24']/100)
        points.append({'time': -1440, 'price': p_24h})
        
    points.sort(key=lambda x: x['time'])
    
    # 2. Interpolate for smoothness (Spline effect)
    times = [p['time'] for p in points]
    prices = [p['price'] for p in points]
    
    # Create curve
    fig = go.Figure()
    
    # Main Price Line
    fig.add_trace(go.Scatter(
        x=times, 
        y=prices,
        mode='lines',
        line=dict(color='#a855f7', width=3, shape='spline', smoothing=1.3),
        fill='tozeroy',
        fillcolor='rgba(168, 85, 247, 0.1)',
        name='Price'
    ))
    
    # Markers
    # Entry
    fig.add_hline(y=entry_price, line_dash="dash", line_color="#4ade80", annotation_text="ENTRY", annotation_position="top left", annotation_font_color="#4ade80")
    
    # Stop Loss
    if sl_price:
        fig.add_hline(y=sl_price, line_dash="dot", line_color="#f87171", annotation_text="SL", annotation_position="bottom left", annotation_font_color="#f87171")
        
    # TP1
    if tp1_price:
        fig.add_hline(y=tp1_price, line_dash="dot", line_color="#38bdf8", annotation_text="TP1", annotation_position="top right", annotation_font_color="#38bdf8")

    # Current Price Pulse
    fig.add_trace(go.Scatter(
        x=[0], y=[current_price],
        mode='markers',
        marker=dict(size=12, color='#e0e7ff', line=dict(width=2, color='#a855f7')),
        name='Current'
    ))

    # Styling (Axiom Aesthetics)
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15, 23, 42, 0.5)',
        margin=dict(l=0, r=40, t=10, b=0),
        height=300,
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(255,255,255,0.05)', 
            side='right',
            tickfont=dict(color='#64748b', family='JetBrains Mono')
        ),
        showlegend=False
    )
    
    return fig

# --- Main Layout ---
active_df, history_df = get_data()
balance, wallet_addr = get_wallet_balance()

# Header
col1, col2, col3 = st.columns([3, 2, 1])
with col1:
    st.markdown("""
    <div style="position: relative;">
        <h1 style="
            font-family: 'JetBrains Mono', monospace;
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(90deg, #38bdf8, #a855f7, #ec4899, #38bdf8);
            background-size: 300% 100%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: neonPulse 3s ease-in-out infinite;
            text-shadow: none;
            margin: 0;
        ">
            ⚡ QUICKTRADE
        </h1>
        <div style="
            color: #64748b;
            font-size: 0.85rem;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-top: 5px;
        ">COMMAND CENTER</div>
    </div>
    <style>
        @keyframes neonPulse {
            0%, 100% { 
                background-position: 0% 50%;
                filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.5));
            }
            50% { 
                background-position: 100% 50%;
                filter: drop-shadow(0 0 25px rgba(168, 85, 247, 0.8));
            }
        }
    </style>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="display:flex; justify-content:flex-end; height:100%; align-items:center;">
        <div class="wallet-badge">
            <span>💳</span>
            <span>{balance:.4f} SOL</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    col_sync, col_auto = st.columns([1, 2])
    with col_sync:
        if st.button("🔄", use_container_width=True, help="Sync Now"):
            st.rerun()
    with col_auto:
        auto_refresh = st.checkbox("Auto-Sync", value=False, help="Refresh every 10s")

st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

# === TAB NAVIGATION ===
tab1, tab3 = st.tabs(["⚡ COMMAND CENTER", "📊 CALLER STATS"])

# =====================================================
# TAB 1: COMMAND CENTER (Original Dashboard)
# =====================================================
with tab1:
    # --- Hero Stats ---
    total_trades = len(history_df)
    active_count = len(active_df)
    win_rate = 0.0
    total_pnl = 0.0

    if not history_df.empty:
        closed = history_df[history_df['status'].isin(['CLOSED', 'PARTIAL', 'MOONBAG'])]
        if not closed.empty:
            wins = closed[closed['pnl_percent'] > 0]
            win_rate = (len(wins) / len(closed)) * 100
            total_pnl = closed['pnl_percent'].sum() * 100
    
    # Calculate portfolio ROI (total profit relative to total invested)
    total_invested = history_df['amount_sol'].sum() if not history_df.empty else 0
    total_profit_sol = (history_df['amount_sol'] * history_df['pnl_percent']).sum() if not history_df.empty else 0
    portfolio_roi = (total_profit_sol / total_invested * 100) if total_invested > 0 else 0
    
    # Calculate today's gain
    today = datetime.now().date()
    today_trades = history_df[history_df['created_at'].dt.date == today] if not history_df.empty else pd.DataFrame()
    if not today_trades.empty:
        today_invested = today_trades['amount_sol'].sum()
        today_profit = (today_trades['amount_sol'] * today_trades['pnl_percent']).sum()
        today_roi = (today_profit / today_invested * 100) if today_invested > 0 else 0
    else:
        today_roi = 0
        today_profit = 0

    st.markdown(f"""
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 30px;">
        <div class="metric-card" style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05)); border: 1px solid rgba(139, 92, 246, 0.3);">
            <div class="metric-label">NET PROFIT</div>
            <div class="metric-value" style="color: {'#4ade80' if portfolio_roi >= 0 else '#f87171'}; font-size: 2rem;">
                {portfolio_roi * FLEX_MULTIPLIER:+.1f}%
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Today</div>
            <div class="metric-value" style="color: {'#4ade80' if today_roi >= 0 else '#f87171'}">
                {today_roi * FLEX_MULTIPLIER:+.1f}%
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Active Ops</div>
            <div class="metric-value">{active_count}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value">{win_rate:.0f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value">{total_trades}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Active Interceptions (2-Column Grid) ---
    if not active_df.empty:
        st.markdown("### 📡 ACTIVE INTERCEPTIONS")
        
        # Pre-compute all card data
        cards_data = []
        for idx, row in active_df.iterrows():
            address = row['address']
            current_price = get_fast_price(address)
            _, dex_mc, pair_address, vol_m5, vol_h1, price_change = get_live_price(address)
            current_mc = dex_mc
            if not current_price:
                current_price, current_mc, pair_address, vol_m5, vol_h1, price_change = get_live_price(address)
            
            entry_price = row['entry_price']
            amount_sol = row['amount_sol']
            created_at = row['created_at']
            try:
                meta_dict = json.loads(row.get('meta', '{}')) if row.get('meta') else {}
            except:
                meta_dict = {}
            
            stored_entry_mc = meta_dict.get('entry_mc', 0)
            entry_mc = stored_entry_mc if stored_entry_mc > 0 else (current_mc * (entry_price / current_price) if current_price and current_mc else 0)
            
            time_held = datetime.now() - created_at
            hours = int(time_held.total_seconds() // 3600)
            minutes = int((time_held.total_seconds() % 3600) // 60)
            time_str = f"{hours}h{minutes}m" if hours > 0 else f"{minutes}m"
            
            pnl = ((current_price - entry_price) / entry_price) * 100 * FLEX_MULTIPLIER if current_price else 0
            pnl_sol = amount_sol * (pnl / 100)
            mc_display = format_metric(current_mc) if current_mc else "N/A"
            entry_mc_display = format_metric(entry_mc) if entry_mc else "N/A"
            pnl_color = "#4ade80" if pnl >= 0 else "#f87171"
            
            # === NEW: Calculate TP Status ===
            sold_pct = 0
            sells_list = []
            if meta_dict.get('tp_2x_hit'):
                sold_pct += 40
                sells_list.append("1.8x")
            if meta_dict.get('tp3_hit'):
                sold_pct += 20
                sells_list.append("3x")
            if meta_dict.get('tp4_hit'):
                sold_pct += 20
                sells_list.append("5x")
            if meta_dict.get('volume_decay_triggered'):
                sold_pct += 25
                sells_list.append("DECAY")
            
            remaining_pct = max(0, 100 - sold_pct)
            sells_str = " + ".join(sells_list) if sells_list else None
            
            # === NEW: Next TP Target ===
            next_tp_name = ""
            next_tp_distance = 0
            if not meta_dict.get('tp_2x_hit'):
                next_tp_name = "1.8x"
                next_tp_distance = ((entry_price * 1.8 - current_price) / current_price * 100) if current_price else 0
            elif not meta_dict.get('tp3_hit'):
                next_tp_name = "3x"
                next_tp_distance = ((entry_price * 3.0 - current_price) / current_price * 100) if current_price else 0
            elif not meta_dict.get('tp4_hit'):
                next_tp_name = "5x"
                next_tp_distance = ((entry_price * 5.0 - current_price) / current_price * 100) if current_price else 0
            else:
                next_tp_name = "MOONBAG"
                next_tp_distance = 0
            
            # === NEW: Break-even lock status ===
            break_even_locked = meta_dict.get('break_even_locked', False)
            
            # Calculate current x multiple
            current_x = current_price / entry_price if entry_price > 0 else 0
            
            cards_data.append({
                'idx': idx, 'address': address, 'ticker': row['ticker'], 'status': row['status'],
                'pnl': pnl, 'pnl_sol': pnl_sol, 'pnl_color': pnl_color,
                'entry_mc': entry_mc_display, 'current_mc': mc_display, 'time_str': time_str,
                'source': row.get('source', ''),
                'sold_pct': sold_pct, 'remaining_pct': remaining_pct, 'sells_str': sells_str,
                'next_tp_name': next_tp_name, 'next_tp_distance': next_tp_distance,
                'break_even_locked': break_even_locked, 'current_x': current_x
            })
        
        # Display in 2-column grid
        cols = st.columns(2)
        for i, card in enumerate(cards_data):
            with cols[i % 2]:
                pnl_bg = "rgba(74, 222, 128, 0.15)" if card['pnl'] >= 0 else "rgba(248, 113, 113, 0.15)"
                
                # Build TP status line
                if card['sells_str']:
                    tp_status_html = f'<span style="color: #4ade80;">✅ {card["sells_str"]}</span> <span style="color: #64748b;">({card["sold_pct"]}% sold)</span>'
                else:
                    tp_status_html = '<span style="color: #94a3b8;">📦 No TPs hit yet</span>'
                
                # Build next TP line
                if card['next_tp_name'] == "MOONBAG":
                    next_tp_html = '<span style="color: #a855f7;">🌙 MOONBAG MODE</span>'
                else:
                    distance_color = "#4ade80" if card['next_tp_distance'] <= 20 else "#fbbf24" if card['next_tp_distance'] <= 50 else "#94a3b8"
                    next_tp_html = f'<span style="color: {distance_color};">🎯 Next: {card["next_tp_name"]} ({card["next_tp_distance"]:+.0f}%)</span>'
                
                # Break-even badge
                be_badge = '<span style="background: #4ade8020; color: #4ade80; padding: 2px 6px; border-radius: 4px; font-size: 0.65rem; margin-left: 8px;">🔒 BE LOCKED</span>' if card['break_even_locked'] else ''
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9)); border: 1px solid {card['pnl_color']}40; border-radius: 12px; padding: 12px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 700; color: #e2e8f0; font-size: 1rem;">{card['ticker']}{be_badge}</span>
                        <div style="text-align: right;">
                            <span style="color: {card['pnl_color']}; font-weight: 800; font-size: 1.3rem;">{card['pnl']:+.1f}%</span>
                            <span style="color: #64748b; font-size: 0.75rem; margin-left: 5px;">({card['current_x']:.2f}x)</span>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.75rem; color: #94a3b8; margin-bottom: 8px;">
                        <div>Entry: <span style="color: #e2e8f0;">{card['entry_mc']}</span></div>
                        <div>Now: <span style="color: #e2e8f0;">{card['current_mc']}</span></div>
                        <div>PnL: <span style="color: {card['pnl_color']};">{card['pnl_sol']:+.4f} SOL</span></div>
                        <div>⏱️ {card['time_str']}</div>
                    </div>
                    <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px; font-size: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            {tp_status_html}
                            <span style="color: #64748b;">{card['remaining_pct']}% remaining</span>
                        </div>
                        <div>{next_tp_html}</div>
                    </div>
                    <div style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px; margin-top: 6px;">
                        <a href="https://pump.fun/coin/{card['address']}" target="_blank" style="color: #64748b; font-size: 0.65rem; text-decoration: none; font-family: monospace;">
                            📋 {card['address'][:8]}...{card['address'][-6:]}
                        </a>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("🚨 SELL", key=f"panic_{card['idx']}", type="primary"):
                    db = Database()
                    db.update_trade_status(card['address'], 'SELL_REQUEST')
                    st.toast(f"🚨 SELL REQUEST SENT for {card['ticker']}!")
                    st.rerun()






    else:
        st.markdown("### 📈 PERFORMANCE ANALYTICS")
        
        if not history_df.empty:
            history_sorted = history_df.sort_values('created_at').reset_index(drop=True)
            
            # === Calculate both metrics ===
            # 1. Simple cumulative sum (existing)
            history_sorted['cumulative_pnl'] = history_sorted['pnl_percent'].cumsum() * 100
            
            # 2. Weighted ROI (actual portfolio performance)
            # This calculates: (sum of profits) / (sum of investments) at each point
            history_sorted['profit_sol'] = history_sorted['amount_sol'] * history_sorted['pnl_percent']
            history_sorted['cumulative_profit'] = history_sorted['profit_sol'].cumsum()
            history_sorted['cumulative_invested'] = history_sorted['amount_sol'].cumsum()
            history_sorted['weighted_roi'] = (history_sorted['cumulative_profit'] / history_sorted['cumulative_invested']) * 100
            
            # === Identify milestone trades (top 3 biggest wins over 100%) ===
            big_wins = history_sorted[history_sorted['pnl_percent'] >= 1.0]  # 100%+ only
            top_trades = big_wins.nlargest(3, 'pnl_percent') if len(big_wins) > 0 else pd.DataFrame()
            milestone_indices = top_trades.index.tolist() if len(top_trades) > 0 else []
            
            # === Build rich hover text ===
            hover_texts = []
            for idx, row in history_sorted.iterrows():
                # Calculate time held if we have the data
                time_str = row['created_at'].strftime('%m/%d %H:%M')
                
                # Try to get entry MC from meta
                try:
                    meta = json.loads(row.get('meta', '{}')) if row.get('meta') else {}
                    entry_mc = meta.get('entry_mc', 0)
                    entry_mc_str = format_metric(entry_mc) if entry_mc else 'N/A'
                except:
                    entry_mc_str = 'N/A'
                
                hover_text = (
                    f"<b>${row['ticker']}</b><br>"
                    f"Trade #{idx + 1}<br>"
                    f"─────────────<br>"
                    f"📊 PnL: <b>{row['pnl_percent']*100:+.1f}%</b><br>"
                    f"💰 Size: {row['amount_sol']:.3f} SOL<br>"
                    f"💵 Profit: {row['profit_sol']:+.4f} SOL<br>"
                    f"📅 {time_str}<br>"
                    f"🏦 Entry MC: {entry_mc_str}"
                )
                hover_texts.append(hover_text)
            
            # === Create advanced Plotly chart ===
            fig = go.Figure()
            
            # Determine if currently profitable for gradient color
            final_roi = history_sorted['weighted_roi'].iloc[-1]
            fill_color = 'rgba(74, 222, 128, 0.12)' if final_roi >= 0 else 'rgba(248, 113, 113, 0.12)'
            line_color = '#4ade80' if final_roi >= 0 else '#f87171'

            # 1. Weighted ROI Line (PRIMARY - the main event)
            fig.add_trace(go.Scatter(
                x=list(range(1, len(history_sorted) + 1)),
                y=history_sorted['weighted_roi'],
                mode='lines+markers',
                name='Portfolio ROI',
                line=dict(color=line_color, width=3, shape='spline', smoothing=1.3),
                fill='tozeroy',
                fillcolor=fill_color,
                marker=dict(
                    size=8 if len(history_sorted) < 40 else 6,
                    color=["#4ade80" if x > 0 else "#f87171" for x in history_sorted['pnl_percent']],
                    line=dict(width=1.5, color='rgba(255,255,255,0.7)'),
                    symbol='circle'
                ),
                text=hover_texts,
                hovertemplate="%{text}<extra></extra>"
            ))
            
            # 2. Cumulative Sum Line (SECONDARY Y-AXIS - doesn't compress main chart)
            fig.add_trace(go.Scatter(
                x=list(range(1, len(history_sorted) + 1)),
                y=history_sorted['cumulative_pnl'],
                mode='lines',
                name='Cumulative %',
                line=dict(color='#a855f7', width=2, shape='spline', smoothing=1.3, dash='dot'),
                opacity=0.5,
                yaxis='y2',
                hovertemplate="Cumulative: %{y:.0f}%<extra></extra>"
            ))
            
            # 3. Add milestone annotations for big wins
            for idx in milestone_indices:
                row = history_sorted.iloc[idx]
                trade_num = idx + 1
                pnl_pct = row['pnl_percent'] * 100
                
                # Only annotate 100%+ trades (already filtered above)
                if pnl_pct >= 100:
                    fig.add_annotation(
                        x=trade_num,
                        y=row['weighted_roi'],
                        text=f"🚀 +{pnl_pct:.0f}%",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor='#fbbf24',
                        ax=0,
                        ay=-40,
                        font=dict(color='#fbbf24', size=11, family='JetBrains Mono'),
                        bgcolor='rgba(251, 191, 36, 0.15)',
                        bordercolor='rgba(251, 191, 36, 0.5)',
                        borderwidth=1,
                        borderpad=4
                    )
            
            # 4. Add current value annotation
            fig.add_annotation(
                x=len(history_sorted),
                y=final_roi,
                text=f"<b>{final_roi:+.1f}%</b>",
                showarrow=False,
                xanchor='left',
                xshift=10,
                font=dict(color=line_color, size=16, family='JetBrains Mono'),
                bgcolor='rgba(15, 23, 42, 0.9)',
                bordercolor=line_color,
                borderwidth=2,
                borderpad=6
            )

            # === Styling ===
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(15, 23, 42, 0.4)',
                height=550,
                margin=dict(l=60, r=80, t=40, b=50),
                xaxis=dict(
                    title=dict(text="Trade #", font=dict(color='#94a3b8', size=12)),
                    showgrid=True, 
                    gridcolor='rgba(56, 189, 248, 0.08)',
                    gridwidth=1,
                    zeroline=False,
                    tickfont=dict(color='#94a3b8', size=11, family='JetBrains Mono'),
                    dtick=5 if len(history_sorted) >= 20 else (2 if len(history_sorted) >= 10 else 1),
                    showspikes=True,
                    spikecolor='rgba(56, 189, 248, 0.5)',
                    spikethickness=1
                ),
                yaxis=dict(
                    title=dict(text="Return %", font=dict(color='#94a3b8', size=12)),
                    showgrid=True, 
                    gridcolor='rgba(56, 189, 248, 0.08)',
                    gridwidth=1,
                    zeroline=True,
                    zerolinecolor='rgba(255, 255, 255, 0.3)',
                    zerolinewidth=2,
                    tickfont=dict(color='#94a3b8', size=11, family='JetBrains Mono'),
                    ticksuffix="%",
                    showspikes=True,
                    spikecolor='rgba(56, 189, 248, 0.5)',
                    spikethickness=1
                ),
                yaxis2=dict(
                    title=dict(text="Cumulative %", font=dict(color='#a855f7', size=10)),
                    overlaying='y',
                    side='right',
                    showgrid=False,
                    tickfont=dict(color='#a855f7', size=10, family='JetBrains Mono'),
                    ticksuffix="%",
                    anchor='x'
                ),
                hovermode="x unified",
                hoverlabel=dict(
                    bgcolor='rgba(15, 23, 42, 0.95)',
                    bordercolor='rgba(56, 189, 248, 0.5)',
                    font=dict(color='#e2e8f0', family='JetBrains Mono', size=12)
                ),
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='center',
                    x=0.5,
                    bgcolor='rgba(15, 23, 42, 0.8)',
                    bordercolor='rgba(56, 189, 248, 0.3)',
                    borderwidth=1,
                    font=dict(color='#e2e8f0', size=11)
                ),
                showlegend=True
            )
            
            # Add summary stats above chart
            total_trades = len(history_sorted)
            total_invested = history_sorted['amount_sol'].sum()
            total_profit = history_sorted['profit_sol'].sum()
            best_trade = history_sorted['pnl_percent'].max() * 100
            worst_trade = history_sorted['pnl_percent'].min() * 100
            
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 15px;">
                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 12px; text-align: center;">
                    <div style="color: #64748b; font-size: 0.7rem; text-transform: uppercase;">Portfolio ROI</div>
                    <div style="color: {'#4ade80' if final_roi >= 0 else '#f87171'}; font-size: 1.3rem; font-weight: 800; font-family: 'JetBrains Mono';">{final_roi:+.1f}%</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 12px; text-align: center;">
                    <div style="color: #64748b; font-size: 0.7rem; text-transform: uppercase;">Total Invested</div>
                    <div style="color: #38bdf8; font-size: 1.3rem; font-weight: 800; font-family: 'JetBrains Mono';">{total_invested:.2f} SOL</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 12px; text-align: center;">
                    <div style="color: #64748b; font-size: 0.7rem; text-transform: uppercase;">Net Profit</div>
                    <div style="color: {'#4ade80' if total_profit >= 0 else '#f87171'}; font-size: 1.3rem; font-weight: 800; font-family: 'JetBrains Mono';">{total_profit:+.4f} SOL</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 12px; text-align: center;">
                    <div style="color: #64748b; font-size: 0.7rem; text-transform: uppercase;">Best Trade</div>
                    <div style="color: #4ade80; font-size: 1.3rem; font-weight: 800; font-family: 'JetBrains Mono';">+{best_trade:.0f}%</div>
                </div>
                <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 12px; text-align: center;">
                    <div style="color: #64748b; font-size: 0.7rem; text-transform: uppercase;">Worst Trade</div>
                    <div style="color: #f87171; font-size: 1.3rem; font-weight: 800; font-family: 'JetBrains Mono';">{worst_trade:+.0f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No trading history to generate analytics.")

    st.markdown("---")

    # --- Activity Log (History) ---
    st.markdown("### 📜 TRADE HISTORY")
    
    if not history_df.empty:
        # Helper function to render a single trade card
        def render_trade_card(idx, row):
            # For CLOSED trades, use realized PnL from sell transactions
            if row['status'] == 'CLOSED':
                db = Database()
                realized = db.get_realized_pnl(row['address'], row['amount_sol'])
                if realized['sell_count'] > 0:
                    pnl = realized['realized_pnl_pct']
                    pnl_sol = realized['realized_sol'] - row['amount_sol']
                else:
                    pnl = row['pnl_percent'] * 100
                    pnl_sol = row['amount_sol'] * row['pnl_percent']
            else:
                pnl = row['pnl_percent'] * 100
                pnl_sol = row['amount_sol'] * row['pnl_percent']
            
            pnl_color = "#4ade80" if pnl > 0 else "#f87171"
            status_color = "#38bdf8"
            
            try:
                meta = json.loads(row.get('meta', '{}')) if row.get('meta') else {}
            except:
                meta = {}
            
            if "CLOSED" in row['status']: status_color = "#94a3b8"
            if "MOONBAG" in row['status']: status_color = "#a855f7"
            if "PARTIAL" in row['status']: status_color = "#fbbf24"
            
            result_icon = "✅" if pnl > 0 else "❌" if pnl < 0 else "⚪"
            
            # Rich Source Badge
            source = str(row.get('source', 'unknown')).lower()
            config = SOURCE_CONFIG.get(source, {'icon': '❓', 'name': source.upper(), 'color': '#64748b'})
            source_html = f'<span style="color: {config["color"]}; font-size: 0.75rem; font-weight: 700; background: {config["color"]}15; padding: 2px 8px; border-radius: 4px; border: 1px solid {config["color"]}30;">{config["icon"]} {config["name"]}</span>'
            
            # Entry MC Display
            mc_display = ""
            entry_mc = meta.get('entry_mc') or row.get('entry_mc')  # Check both meta and row
            if entry_mc:
                try:
                    val = float(entry_mc)
                    if val >= 1_000_000:
                        s = f"${val/1_000_000:.1f}M"
                    elif val >= 1_000:
                        s = f"${val/1_000:.0f}K"
                    else:
                        s = f"${val:.0f}"
                    mc_display = f'<span style="color: #64748b; font-size: 0.75rem; margin-left: 8px;">Entry: <span style="color: #94a3b8;">{s}</span></span>'
                except:
                    pass

            st.markdown(f"""
            <div style="
                background: rgba(255, 255, 255, 0.03); 
                border-left: 4px solid {pnl_color};
                margin-bottom: 8px;
                padding: 12px 20px;
                border-radius: 4px;
                font-family: 'JetBrains Mono', monospace;
                transition: all 0.2s ease;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <span style="font-size: 1.2rem;">{result_icon}</span>
                        <span style="color: #ffffff; font-weight: 700; font-size: 1.1rem;">{row['ticker']}</span>
                        {source_html}
                        {mc_display}
                        <span style="
                            background: {status_color}20; 
                            color: {status_color};
                            padding: 2px 8px;
                            border-radius: 4px;
                            font-size: 0.7rem;
                            font-weight: 600;
                            margin-left: auto;
                        ">{row['status']}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <span style="color: {pnl_color}; font-weight: 800; font-size: 1.3rem;">{pnl:+.1f}%</span>
                    </div>
                </div>
                <div style="display: flex; gap: 30px; color: #64748b; font-size: 0.85rem;">
                    <span>📅 {row['created_at'].strftime('%b %d %H:%M')}</span>
                    <span>💰 {row['amount_sol']:.3f} SOL</span>
                    <span style="color: {pnl_color}">PnL: {pnl_sol:+.4f} SOL</span>
                    <a href="https://pump.fun/coin/{row['address']}" target="_blank" style="color: #64748b; text-decoration: none; font-size: 0.75rem;">
                        📋 {row['address'][:6]}...{row['address'][-4:]}
                    </a>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # --- EXECUTE DISPLAY LOOP ---
        # Sort history descending
        history_rev = history_df.sort_values('created_at', ascending=False)
        
        # Show Top 8 (increased from 5)
        top_n = history_rev.head(8)
        for idx, row in top_n.iterrows():
            render_trade_card(idx, row)
            
        # Show the rest in an expander
        remaining = history_rev.iloc[8:]
        if not remaining.empty:
            with st.expander(f"📚 View {len(remaining)} Older Trades"):
                for idx, row in remaining.iterrows():
                    render_trade_card(idx, row)

    else:
        st.info("No trade history yet.")

    # --- DAILY PROFIT CALENDAR ---
    st.markdown("---")
    st.markdown("### 🗓️ DAILY PROFIT CALENDAR")
    
    if not history_df.empty:
        # Group by Date
        history_df['date'] = history_df['created_at'].dt.date
        daily_stats = history_df.groupby('date').apply(
            lambda x: pd.Series({
                'pnl_sol': (x['amount_sol'] * x['pnl_percent']).sum(),
                'pnl_pct': x['pnl_percent'].sum() * 100,  # Sum of all trade %s
                'volume': x['amount_sol'].sum(),
                'total_trades': len(x),
                'wins': len(x[x['pnl_percent'] > 0]),
                'avg_pnl': x['pnl_percent'].mean() * 100
            })
        ).sort_index(ascending=False)
        
        # Calculate daily ROI (profit / volume invested that day)
        daily_stats['daily_roi'] = (daily_stats['pnl_sol'] / daily_stats['volume'] * 100).fillna(0)
        
        # Render Calendar Grid
        cal_cols = st.columns(3)
        for idx, (date, row) in enumerate(daily_stats.iterrows()):
            win_rate = (row['wins'] / row['total_trades']) * 100
            pnl_color = "#4ade80" if row['pnl_sol'] >= 0 else "#f87171"
            daily_roi = row['daily_roi']
            
            with cal_cols[idx % 3]:
                st.markdown(textwrap.dedent(f"""
                <div style="
                    background: rgba(15, 23, 42, 0.6);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-left: 4px solid {pnl_color};
                    border-radius: 12px;
                    padding: 15px;
                    margin-bottom: 15px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-weight: 700; color: #a855f7;">
                            {date.strftime('%A, %b %d')}
                        </span>
                        <span style="
                            font-size: 1.4rem; 
                            font-weight: 800; 
                            color: {pnl_color};
                            font-family: 'JetBrains Mono', monospace;
                        ">
                            {daily_roi:+.1f}%
                        </span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8rem;">
                        <div>
                            <span style="color: #64748b;">Net Profit</span><br>
                            <span style="color: {pnl_color}; font-weight: 600;">{row['pnl_sol']:+.4f} SOL</span>
                        </div>
                        <div>
                            <span style="color: #64748b;">Win Rate</span><br>
                            <span style="color: #e2e8f0; font-weight: 600;">{win_rate:.0f}% ({int(row['wins'])}/{int(row['total_trades'])})</span>
                        </div>
                        <div>
                            <span style="color: #64748b;">Volume</span><br>
                            <span style="color: #e2e8f0;">{row['volume']:.3f} SOL</span>
                        </div>
                        <div>
                            <span style="color: #64748b;">Avg PnL</span><br>
                            <span style="color: {pnl_color};">{row['avg_pnl']:+.1f}%</span>
                        </div>
                    </div>
                </div>
                """), unsafe_allow_html=True)
    else:
        st.caption("No daily data available.")





# (EARS TAB REMOVED - Not in use)


# =====================================================
# TAB 3: CALLER STATS (Signal Source Performance)
# =====================================================
with tab3:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            background: linear-gradient(90deg, #38bdf8, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        ">📊 CALLER LEADERBOARD</h1>
        <p style="color: #64748b; font-size: 0.9rem; margin-top: 10px;">
            Real-time performance tracking for each signal source
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all trades and group by source
    all_trades = history_df.copy() if not history_df.empty else pd.DataFrame()
    
    # Source config
    source_config = {
        'discord': {'icon': '🎮', 'name': 'Zeus Calls', 'color': '#5865F2', 'gradient': 'linear-gradient(135deg, #5865F2 0%, #7289da 100%)', 'platform': 'Discord'},
        'telegram': {'icon': '💎', 'name': 'Gem Tools', 'color': '#0088cc', 'gradient': 'linear-gradient(135deg, #0088cc 0%, #229ed9 100%)', 'platform': 'Telegram'},
        'gems': {'icon': '💎', 'name': 'Gem Tools', 'color': '#0088cc', 'gradient': 'linear-gradient(135deg, #0088cc 0%, #229ed9 100%)', 'platform': 'Telegram'},
        'rhysky': {'icon': '⚡', 'name': 'Rhysky', 'color': '#f59e0b', 'gradient': 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)', 'platform': 'Telegram'},
        '4am': {'icon': '🌙', 'name': '4AM Signals', 'color': '#8b5cf6', 'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%)', 'platform': 'Telegram'},
        'axe': {'icon': '🪓', 'name': 'Axe Calls', 'color': '#ef4444', 'gradient': 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)', 'platform': 'Telegram'},
        'legion': {'icon': '⚔️', 'name': 'Legion Calls', 'color': '#10b981', 'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 'platform': 'Discord'},
        'spider': {'icon': '🕷️', 'name': 'Spider Journal', 'color': '#6366f1', 'gradient': 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', 'platform': 'Telegram'},
        'pfultimate': {'icon': '🎯', 'name': 'PF Alerts', 'color': '#22c55e', 'gradient': 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)', 'platform': 'Telegram'},
    }
    
    # Build detailed stats for each source
    source_stats = {}
    display_sources = ['pfultimate', 'discord', 'gems', 'rhysky', '4am', 'axe', 'legion', 'spider']  # Sources to display (pfultimate first as primary)
    
    for src_key in display_sources:
        source_stats[src_key] = {
            'source': src_key,
            'total_calls': 0,
            'wins': 0,
            'losses': 0,
            'avg_pnl': 0,
            'total_pnl': 0,
            'hit_rate': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'total_sol_profit': 0,
            'last_call': None,
            'best_ticker': 'N/A'
        }
    
    # Merge with actual trade data
    if not all_trades.empty and 'source' in all_trades.columns:
        for src_key in display_sources:
            # Match both exact and partial source names
            if src_key == 'gems':
                src_trades = all_trades[all_trades['source'].isin(['gems', 'telegram'])]
            else:
                src_trades = all_trades[all_trades['source'] == src_key]
            
            if not src_trades.empty:
                wins_df = src_trades[src_trades['pnl_percent'] > 0]
                losses_df = src_trades[src_trades['pnl_percent'] <= 0]
                best_idx = src_trades['pnl_percent'].idxmax()
                best_trade_row = src_trades.loc[best_idx] if best_idx else None
                
                # Calculate SOL profit (assuming 0.02 SOL per trade)
                sol_per_trade = 0.02
                total_sol = src_trades['pnl_percent'].sum() * sol_per_trade
                
                source_stats[src_key] = {
                    'source': src_key,
                    'total_calls': len(src_trades),
                    'wins': len(wins_df),
                    'losses': len(losses_df),
                    'avg_pnl': src_trades['pnl_percent'].mean() * 100,
                    'total_pnl': src_trades['pnl_percent'].sum() * 100,
                    'hit_rate': (len(wins_df) / len(src_trades)) * 100 if len(src_trades) > 0 else 0,
                    'best_trade': src_trades['pnl_percent'].max() * 100,
                    'worst_trade': src_trades['pnl_percent'].min() * 100,
                    'total_sol_profit': total_sol,
                    'last_call': src_trades['created_at'].max(),
                    'best_ticker': best_trade_row['ticker'] if best_trade_row is not None else 'N/A'
                }
    
    # Convert to list for display
    sources_list = list(source_stats.values())
    
    # Create 3+3+1 grid for 7 sources
    row1_cols = st.columns(3)
    row2_cols = st.columns(3)
    row3_cols = st.columns(3)  # Third row for overflow
    all_cols = row1_cols + row2_cols + row3_cols
    
    for idx, row in enumerate(sources_list):
        src = row['source']
        config = source_config.get(src, {'icon': '❓', 'name': 'Unknown', 'color': '#64748b', 'gradient': 'linear-gradient(135deg, #475569 0%, #64748b 100%)', 'platform': '?'})
        
        # Calculate profit multiplier
        profit_mult = 1 + (row['total_pnl'] / 100) if row['total_pnl'] else 1.0
        
        # Time since last call
        last_call = row['last_call']
        if last_call:
            try:
                if isinstance(last_call, str):
                    last = datetime.fromisoformat(last_call.replace('Z', '+00:00'))
                else:
                    last = last_call
                delta = datetime.now() - last
                if delta.days > 0:
                    time_ago = f"{delta.days}d ago"
                elif delta.seconds >= 3600:
                    time_ago = f"{delta.seconds // 3600}h ago"
                else:
                    time_ago = f"{delta.seconds // 60}m ago"
            except:
                time_ago = "Unknown"
        else:
            time_ago = "Waiting..."
        
        # Colors
        hr = row['hit_rate']
        hr_color = "#4ade80" if hr >= 60 else "#facc15" if hr >= 40 else "#f87171"
        mult_color = "#4ade80" if profit_mult >= 1 else "#f87171"
        sol_color = "#4ade80" if row['total_sol_profit'] >= 0 else "#f87171"
        
        with all_cols[idx]:
            # Main card container
            card = f'<div style="background: linear-gradient(145deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.95) 100%); border: 2px solid {config["color"]}50; border-radius: 20px; padding: 24px; margin-bottom: 20px; box-shadow: 0 0 40px {config["color"]}15, inset 0 1px 0 rgba(255,255,255,0.05);">'
            
            # Header with icon and name
            card += f'<div style="display: flex; align-items: center; gap: 16px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.1);">'
            card += f'<div style="width: 56px; height: 56px; background: {config["gradient"]}; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 1.8rem; box-shadow: 0 4px 20px {config["color"]}40;">{config["icon"]}</div>'
            card += f'<div><div style="font-family: JetBrains Mono, monospace; font-size: 1.1rem; font-weight: 700; color: #e2e8f0;">{config["name"]}</div>'
            card += f'<div style="font-size: 0.75rem; color: #64748b; margin-top: 2px;">📡 {config["platform"]}</div></div>'
            card += f'<div style="margin-left: auto; text-align: right;"><div style="font-size: 0.7rem; color: #64748b;">LAST CALL</div><div style="font-size: 0.85rem; color: #94a3b8;">{time_ago}</div></div></div>'
            
            # Main stats row
            card += f'<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 16px;">'
            
            # Calls stat
            card += f'<div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 12px; text-align: center;">'
            card += f'<div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Calls</div>'
            card += f'<div style="font-size: 1.5rem; font-weight: 800; color: #e2e8f0; font-family: JetBrains Mono;">{row["total_calls"]}</div></div>'
            
            # Win Rate stat
            card += f'<div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 12px; text-align: center;">'
            card += f'<div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Hit Rate</div>'
            card += f'<div style="font-size: 1.5rem; font-weight: 800; color: {hr_color}; font-family: JetBrains Mono;">{hr:.0f}%</div></div>'
            
            # Multiplier stat
            card += f'<div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 12px; text-align: center;">'
            card += f'<div style="font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Return</div>'
            card += f'<div style="font-size: 1.5rem; font-weight: 800; color: {mult_color}; font-family: JetBrains Mono;">{profit_mult:.2f}x</div></div>'
            
            card += '</div>'
            
            # W/L and Best Trade row
            card += f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">'
            
            # W/L Record
            card += f'<div style="background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px;">'
            card += f'<div style="font-size: 0.7rem; color: #64748b; margin-bottom: 4px;">W/L RECORD</div>'
            card += f'<div style="font-family: JetBrains Mono;"><span style="color: #4ade80; font-weight: 700;">{row["wins"]}W</span> <span style="color: #475569;">/</span> <span style="color: #f87171; font-weight: 700;">{row["losses"]}L</span></div></div>'
            
            # Best Trade
            best_pnl = row['best_trade']
            best_color = "#4ade80" if best_pnl > 0 else "#f87171"
            card += f'<div style="background: rgba(0,0,0,0.2); border-radius: 10px; padding: 10px;">'
            card += f'<div style="font-size: 0.7rem; color: #64748b; margin-bottom: 4px;">BEST TRADE</div>'
            card += f'<div style="font-family: JetBrains Mono; color: {best_color}; font-weight: 700;">{best_pnl:+.0f}% <span style="color: #64748b; font-weight: 400; font-size: 0.8rem;">${row["best_ticker"]}</span></div></div>'
            
            card += '</div>'
            
            # SOL Profit footer
            sol_sign = "+" if row['total_sol_profit'] >= 0 else ""
            card += f'<div style="background: linear-gradient(90deg, {config["color"]}20, transparent); border-radius: 10px; padding: 12px; display: flex; justify-content: space-between; align-items: center;">'
            card += f'<div style="font-size: 0.75rem; color: #94a3b8;">💰 TOTAL P&L</div>'
            card += f'<div style="font-family: JetBrains Mono; font-size: 1.1rem; font-weight: 800; color: {sol_color};">{sol_sign}{row["total_sol_profit"]:.4f} SOL</div></div>'
            
            card += '</div>'
            st.markdown(card, unsafe_allow_html=True)


    # =====================================================
# TABS
# =====================================================
tab1, tab2, tab5, tab3 = st.tabs(["🚀 OVERVIEW", "📜 TRADES", "🧠 STRATEGY LAB", "📈 PERFORMANCE"])

# Global Date Selection (applies to charts)
with st.sidebar:
    st.markdown("---")
    st.markdown('<div style="font-size: 0.8rem; color: #64748b; margin-bottom: 5px;">ANALYTICS RANGE</div>', unsafe_allow_html=True)
    date_range = st.selectbox("Timeframe", ["Last 24 Hours", "Last 7 Days", "All Time"], index=0)

# =====================================================
# TAB 5: STRATEGY LAB (Intelligence)
# =====================================================
with tab5:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="
            font-family: 'JetBrains Mono', monospace; 
            font-size: 2rem; 
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
            text-shadow: 0 0 30px rgba(59, 130, 246, 0.3);
        ">🧠 STRATEGY LAB</h1>
        <p style="color: #64748b; font-size: 0.9rem; letter-spacing: 1px;">
            AI PERFORMANCE ANALYTICS & AUTONOMOUS DECISION MAKING
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    lab = StrategyLab(db)
    stats = lab.get_strategy_performance()
    
    if stats.empty:
        st.info("No trade history available yet for analysis. Strategies will appear here once trades are closed.")
    else:
        # Display Cards for each Strategy
        cols = st.columns(len(stats) if len(stats) < 4 else 3)
        
        for idx, row in stats.iterrows():
            source = row['source']
            score = row['score']
            win_rate = row['win_rate']
            roi = row['avg_roi']
            wins = row['wins']
            losses = row['losses']
            
            # Color logic
            if score >= 80:
                color = "#4ade80" # Green (High Confidence)
                status = "BOOSTING SIZE"
            elif score <= 40:
                color = "#f87171" # Red (Kill Switch)
                status = "DISABLED (KILL SWITCH)"
            else:
                color = "#facc15" # Yellow (Normal)
                status = "ACTIVE"
                
            with cols[idx % 3]:
                st.markdown(f"""
                <div style="
                    background: rgba(255,255,255,0.03); 
                    border: 1px solid {color}40;
                    border-left: 4px solid {color};
                    border-radius: 12px; 
                    padding: 20px;
                    margin-bottom: 15px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="font-family: 'JetBrains Mono'; font-weight: 700; font-size: 1.1rem; color: #fff;">{source.upper()}</span>
                        <span style="background: {color}20; color: {color}; padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">IQ: {score:.0f}</span>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                        <div>
                            <div style="font-size: 0.7rem; color: #64748b;">WIN RATE</div>
                            <div style="font-family: 'JetBrains Mono'; color: #e2e8f0; font-size: 1rem;">{win_rate:.1f}%</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: #64748b;">AVG ROI</div>
                            <div style="font-family: 'JetBrains Mono'; color: {('#4ade80' if roi > 0 else '#f87171')}; font-size: 1rem;">{roi:+.1f}%</div>
                        </div>
                    </div>
                    
                    <div style="font-size: 0.75rem; color: #94a3b8; text-align: center; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px;">
                        STATUS: <strong style="color: {color}">{status}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    # =====================================================
    # SIDEBAR CONTROL PANEL
    # =====================================================
    with st.sidebar:
        st.markdown('<div class="neon-text" style="font-size: 1.2rem; margin-bottom: 20px;">⚡ CONTROL PANEL</div>', unsafe_allow_html=True)
        
        # --- AXIOM AUTOMATION ---
        with st.expander("🤖 AXIOM AUTOMATION", expanded=True):
            st.markdown('<div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px;">AUTO-SNIPER SETTINGS</div>', unsafe_allow_html=True)
            
            # Trending Auto-Snipe
            auto_trend = db.get_setting('auto_snipe_trending')
            new_val_trend = st.toggle("Snipe Top 3 Trending", value=auto_trend, help="Auto-buy whenever a token enters Top 3 Trending on Axiom.")
            if new_val_trend != auto_trend:
                db.set_setting('auto_snipe_trending', new_val_trend)
                st.toast(f"Top 3 Auto-Snipe: {'ON' if new_val_trend else 'OFF'}")
                
            # Fresh Mints Auto-Snipe
            auto_new = db.get_setting('auto_snipe_new')
            new_val_new = st.toggle("Snipe Fresh Mints", value=auto_new, help="⚠️ HIGH RISK: Auto-buy every new pair detected via WebSocket.")
            if new_val_new != auto_new:
                db.set_setting('auto_snipe_new', new_val_new)
                st.toast(f"Fresh Mint Sniper: {'ON' if new_val_new else 'OFF'}")

        # Wallet Status (Paper Mode displays initial balance)
        balance = INITIAL_BALANCE
        st.metric("Wallet Balance", f"{balance:.4f} SOL")


# (AXIOM TERMINAL TAB REMOVED - Not in use)


# Periodic cleanup: check for stale trades every 15 minutes
check_and_cleanup_stale_trades()

# Auto-refresh
if auto_refresh:
    time.sleep(10)  # Slower refresh to prevent tab resetting
    st.rerun()

