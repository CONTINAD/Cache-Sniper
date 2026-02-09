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

async def process_token_data(data, engine):
    mint = data.get('mint')
    if not mint: return
    
    # Check if we already bought
    if mint in active_positions:
        return

    # Extract Mcap
    # PumpPortal 'new token' might not have mcap, it might just be 'initial'.
    # If we want to snipe at a specific Mcap, we need to watch TRADES.
    
    # Let's pivot: Subscribe to 'tradeCreated' for ALL tokens? That's too much.
    # Standard sniper: Buy immediately on create? 
    # User said: "Snipe at a certain market cap threshold".
    # This implies we watch a token, and when it hits X Mcap, we buy.
    # OR we watch global stream, and if ANY token hits X Mcap (and matches other criteria like "not rugged"), we buy.
    
    # Assuming 'market_cap' is in the data.
    # Note: PumpPortal `tradeCreated` often has `marketCapSol`.
    
    mcap = data.get('marketCapSol', 0)
    if mcap == 0:
        # Try calculating or fallback
        # vSolInBondingCurve = data.get('vSolInBondingCurve', 0)
        # For simplicity, if 'marketCapSol' is missing, skip.
        return

    # Logic
    # 1. Dev Sniping checks
    creator = data.get('traderPublicKey')
    if creator and creator in config.TARGET_DEVS:
        print(f"🚨 DEV SNIPE! Creator {creator} launched {mint}!")
        await execute_buy(mint, mcap, engine)
        return

    # 2. Mcap Strategy
    if config.TARGET_MCAP_MIN_SOL <= mcap <= config.TARGET_MCAP_MAX_SOL:
        print(f"🎯 Token {mint} matches Mcap req: {mcap} SOL")
        await execute_buy(mint, mcap, engine)

async def execute_buy(mint, current_mcap, engine):
    print(f"🚀 SNIPING {mint} at {current_mcap} SOL Mcap...")
    
    if config.DRY_RUN:
        print(f"[DRY RUN] Would buy {config.BUY_AMOUNT_SOL} SOL of {mint}")
        # Simulate buy for testing monitoring logic
        active_positions[mint] = {
            "entry_mcap": current_mcap,
            "timestamp": time.time(),
            "status": "BOUGHT"
        }
        asyncio.create_task(monitor_position(mint, engine))
        return

    # Buy
    sig = await engine.pumpportal_swap(mint, config.BUY_AMOUNT_SOL, is_buy=True, priority_fee=config.PRIORITY_FEE)
    
    if sig:
        print(f"✅ Buy Sent! Sig: {sig}")
        # Record position
        active_positions[mint] = {
            "entry_mcap": current_mcap,
            "timestamp": time.time(),
            "status": "BOUGHT"
        }
        # Start monitoring this specific token for sell
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
    
    if config.DRY_RUN:
        print(f"[DRY RUN] Would sell 100% of {mint}")
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
            # We could remove from active_positions or keep log
            # For now, keep it marked as SOLD so we don't rebuy immediately if logic loops
            # But the 'check if already bought' logic in process_token_data handles re-buys?
            # actually process_token_data checks `if mint in active_positions`, so we won't rebuy.
            # Perfect.
    else:
        print("❌ Sell Failed!")

if __name__ == "__main__":
    try:
        asyncio.run(subscribe_to_new_tokens())
    except KeyboardInterrupt:
        print("🛑 Bot Stopped.")
