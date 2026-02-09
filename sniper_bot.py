import asyncio
import json
import ssl
import websockets
import time
from src.solana_utils import SolanaEngine
import sniper_config as config

# Store active positions: {mint: {"buy_price": float, "tokens": float, "mcap_entry": float}}
active_positions = {}

async def subscribe_to_new_tokens():
    uri = "wss://pumpportal.fun/api/data"
    
    # SSL context for secure websocket
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    engine = SolanaEngine()
    print(f"🎯 Sniper Bot Started! Wallet: {engine.pubkey}")
    print(f"🎯 Target Mcap: {config.TARGET_MCAP_MIN_SOL} - {config.TARGET_MCAP_MAX_SOL} SOL")
    print(f"🎯 Buy Amount: {config.BUY_AMOUNT_SOL} SOL")

    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        # Subscribe to new token creation events and trades
        # "tradeCreated" gives us Mcap data more frequently
        payload = {
            "method": "subscribeNewToken", 
        }
        await websocket.send(json.dumps(payload))
        
        # Also subscribe to trades to get updates on all tokens (high volume!)
        # Ideally we only subscribe to tokens we are watching, but for sniping we scan everything?
        # Let's start with 'subscribeNewToken' to get initial launch.
        # Check if 'subscribeNewToken' event has Mcap.
        
        print("✅ Subscribed to PumpPortal Data Stream...")

        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Handle New Token
                if 'mint' in data and 'marketCapSol' in data: # Hypothetical field, let's verify
                     await process_token_data(data, engine)
                
                # Also handle 'listing' or 'trade' if valid
                # For now, print keys to debug structure once
                # print(data.keys()) 

            except Exception as e:
                print(f"⚠️ Error processing message: {e}")

# ... (imports)
import os

TRADES_FILE = "trades.json"

def save_trade(trade):
    """Save trade to JSON file for dashboard analytics."""
    trades = []
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                trades = json.load(f)
        except: pass
    
    # Check if update or new
    # If partial update (like adding sell info), find by mint
    existing = next((t for t in trades if t['mint'] == trade['mint']), None)
    if existing:
        existing.update(trade)
    else:
        trades.append(trade)
        
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=4)

async def process_token_data(data, engine):
    mint = data.get('mint')
    if not mint: return
    
    # Check if we already bought
    if mint in active_positions:
        return

    mcap = data.get('marketCapSol', 0)
    if mcap == 0: return

    # --- Dev Sniping (Address OR Username) ---
    creator_key = data.get('traderPublicKey')
    # PumpPortal doesn't always send username, but let's check if it exists in data
    # Common fields: mint, traderPublicKey, txType, initialBuy, etc.
    # If 'user' or 'name' exists? 
    # NOTE: PumpPortal API documentation doesn't explicitly guarantee username in standard stream without extra calls.
    # However, if the user insists, we'll try to match against known fields.
    
    # Logic:
    # 1. Match Address
    if creator_key and creator_key in config.TARGET_DEVS:
        print(f"🚨 DEV SNIPE (Addr)! {creator_key} launched {mint}!")
        await execute_buy(mint, mcap, engine, creator=creator_key)
        return
        
    # 2. Match Username (Experimental - assuming 'traderName' might exist or we add it later)
    # The user wants "usernames". If config.TARGET_DEVS contains non-addresses (names), we check.
    # For now, we print data keys to discover if name exists.
    # print(f"DEBUG keys: {data.keys()}") 
    
    # 3. Mcap Strategy
    if config.TARGET_MCAP_MIN_SOL <= mcap <= config.TARGET_MCAP_MAX_SOL:
        print(f"🎯 Token {mint} matches Mcap req: {mcap} SOL")
        await execute_buy(mint, mcap, engine)

async def execute_buy(mint, current_mcap, engine, creator=None):
    print(f"🚀 SNIPING {mint} at {current_mcap} SOL Mcap...")
    
    if config.DRY_RUN:
        print(f"[DRY RUN] Would buy {config.BUY_AMOUNT_SOL} SOL of {mint}")
        
        trade_record = {
            "mint": mint,
            "entry_mcap": current_mcap,
            "timestamp": time.time(),
            "status": "OPEN",
            "type": "PAPER",
            "buy_amount": config.BUY_AMOUNT_SOL,
            "creator": creator
        }
        active_positions[mint] = trade_record
        save_trade(trade_record)
        
        asyncio.create_task(monitor_position(mint, engine))
        return

    # Buy
    sig = await engine.pumpportal_swap(mint, config.BUY_AMOUNT_SOL, is_buy=True, priority_fee=config.PRIORITY_FEE)
    
    if sig:
        print(f"✅ Buy Sent! Sig: {sig}")
        
        trade_record = {
            "mint": mint,
            "entry_mcap": current_mcap,
            "timestamp": time.time(),
            "status": "OPEN",
            "type": "LIVE",
            "buy_amount": config.BUY_AMOUNT_SOL,
            "tx_sig": sig,
            "creator": creator
        }
        active_positions[mint] = trade_record
        save_trade(trade_record)
        
        asyncio.create_task(monitor_position(mint, engine))

async def monitor_position(mint, engine):
    print(f"👀 Monitoring position: {mint}")
    
    # We need to subscribe to TRADES for this specific token to track price/mcap
    uri = "wss://pumpportal.fun/api/data"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        payload = {
            "method": "subscribeTokenTrade",
            "keys": [mint]
        }
        await websocket.send(json.dumps(payload))
        
        async for message in websocket:
            try:
                data = json.loads(message)
                if 'marketCapSol' not in data: continue
                
                current_mcap = data['marketCapSol']
                entry_mcap = active_positions[mint]['entry_mcap']
                
                # Calculate PnL
                pnl_mult = current_mcap / entry_mcap
                
                print(f"📉 {mint} | Mcap: {current_mcap:.2f} | PnL: {pnl_mult:.2f}x")
                
                # Take Profit
                if pnl_mult >= config.TAKE_PROFIT_MULTIPLIER:
                    print(f"🤑 Take Profit Triggered! {pnl_mult:.2f}x")
                    await execute_sell(mint, engine)
                    break
                
                # Stop Loss
                # if pnl_mult <= (1.0 - config.STOP_LOSS_PERCENTAGE):
                # Using straightforward percentage of entry
                if current_mcap <= (entry_mcap * (1.0 - config.STOP_LOSS_PERCENTAGE)):
                    print(f"🛑 Stop Loss Triggered! {pnl_mult:.2f}x")
                    await execute_sell(mint, engine)
                    break
                    
            except Exception as e:
                print(f"Error monitoring {mint}: {e}")

async def execute_sell(mint, engine):
    print(f"🔥 SELLING {mint} (100%)...")
    
    # Calculate simulated result for Paper Trading
    # In real logic, we'd wait for confirm.
    
    if config.DRY_RUN:
        print(f"[DRY RUN] Would sell 100% of {mint}")
        if mint in active_positions:
            active_positions[mint]['status'] = "SOLD_PAPER"
            active_positions[mint]['exit_time'] = time.time()
            save_trade(active_positions[mint])
        return

    # Sell 100% using PumpPortal
    sig = await engine.pumpportal_swap(
        mint_address=mint,
        amount="100%", 
        is_buy=False, 
        priority_fee=config.PRIORITY_FEE,
        slippage=25
    )
    
    if sig:
        print(f"✅ Sell Sent! Sig: {sig}")
        if mint in active_positions:
            active_positions[mint]['status'] = "SOLD"
            active_positions[mint]['exit_sig'] = sig
            active_positions[mint]['exit_time'] = time.time()
            save_trade(active_positions[mint])
    else:
        print("❌ Sell Failed!")

if __name__ == "__main__":
    try:
        asyncio.run(subscribe_to_new_tokens())
    except KeyboardInterrupt:
        print("🛑 Bot Stopped.")
