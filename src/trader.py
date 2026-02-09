from src.database import Database
import json
import logging
import asyncio
import aiohttp
import time
from typing import Optional

from src.config import (
    get_position_size, HARD_STOP_LOSS, TRAILING_STOP_PERCENT,
    TP1_FACTOR, TP1_AMOUNT, TP1_SL,
    TP2_FACTOR, TP2_AMOUNT, TP2_SL,
    TP3_FACTOR, TP3_AMOUNT, TP3_SL,
    TP4_FACTOR, TP4_AMOUNT,
    WEBHOOK_URL, SIMULATED_SLIPPAGE, PRIORITY_FEE,
    INITIAL_BALANCE,
    REAL_MODE, PAPER_TRADE_AMOUNT,
    ZEUS_CALLS_WEBHOOK, ZEUS_RESULTS_WEBHOOK,
    GEMS_CALLS_WEBHOOK, GEMS_RESULTS_WEBHOOK,
    RHYSKY_CALLS_WEBHOOK, RHYSKY_RESULTS_WEBHOOK,
    FOURAM_CALLS_WEBHOOK, FOURAM_RESULTS_WEBHOOK,
    AXE_CALLS_WEBHOOK, AXE_RESULTS_WEBHOOK,
    LEGION_CALLS_WEBHOOK, LEGION_RESULTS_WEBHOOK,
    SPIDER_CALLS_WEBHOOK, SPIDER_RESULTS_WEBHOOK,
    PFULTIMATE_CALLS_WEBHOOK, PFULTIMATE_RESULTS_WEBHOOK,
    SIGNAL_BOOST_WINDOW_MINS, SIGNAL_BOOST_AMOUNT,
    MAX_ENTRY_MC, MIN_ENTRY_MC, MAX_TOKEN_AGE_MINUTES
)
from datetime import datetime, timedelta
from src.solana_utils import SolanaEngine

from src.telegram_broadcaster import broadcast_call, broadcast_profit



# X Sentiment Analyzer (optional)
try:
    from src.x_sentiment import get_sentiment_analyzer, X_SENTIMENT_AVAILABLE
    from src.config import (
        X_SENTIMENT_ENABLED, X_SENTIMENT_BYPASS_HIGH_MC,
        X_SENTIMENT_MIN_MENTIONS, X_SENTIMENT_MIN_ACCOUNT_QUALITY, X_SENTIMENT_MAX_BOT_RATIO
    )
except ImportError:
    X_SENTIMENT_AVAILABLE = False
    X_SENTIMENT_ENABLED = False

class PaperTrader:
    def __init__(self):
        self.db = Database()
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex/tokens/"
        # We still keep a light in-memory tracker for asyncio tasks, but state is in DB
        self.active_monitors = set() 
        self.pending_buys = set()  # Track addresses being bought to prevent double-buy
        self.pending_sells = set()  # Track addresses being sold to prevent duplicate sells
        self.balance = INITIAL_BALANCE # This is for Paper Tracking display only now
        
        # SPEED OPTIMIZATION: Shared aiohttp session (reuses connections)
        self._session = None  # Lazy initialized
        
        # Multi-source signal coordination
        # {address: {'time': datetime, 'source': str, 'ticker': str, 'amount': float}}
        self.signal_registry = {}
        
        # Caller success tracking by source
        # {source: {'wins': int, 'losses': int, 'total_pnl': float}}
        self.caller_stats = {
            'discord': {'wins': 0, 'losses': 0, 'total_pnl': 0.0},
            'telegram': {'wins': 0, 'losses': 0, 'total_pnl': 0.0}
        }
        
        # Sell cooldown to prevent rapid successive sells (wasting fees)
        # {address: last_sell_time}
        self.sell_cooldowns = {}

        # Initialize Real Engine
        try:
            self.engine = SolanaEngine()
            self.real_mode = REAL_MODE # Use config setting
            print(f"🔥 {'REAL' if self.real_mode else 'PAPER'} TRADING MODE ENGAGED 🔥")
        except Exception as e:
            print(f"⚠️ Could not init Solana Engine: {e}")
            self.real_mode = False

        if not WEBHOOK_URL:
            print("⚠️ WEBHOOK_URL not set. Notifications will be skipped.")
        
        # Initialize X Sentiment Analyzer (optional)
        self.x_sentiment = None
        if X_SENTIMENT_AVAILABLE and X_SENTIMENT_ENABLED:
            try:
                self.x_sentiment = get_sentiment_analyzer()
                print("🐦 X Sentiment Analyzer ENABLED")
            except Exception as e:
                print(f"⚠️ X Sentiment init failed: {e}")
        elif X_SENTIMENT_AVAILABLE:
            print("🐦 X Sentiment available but disabled (set X_SENTIMENT_ENABLED=true in .env)")

    async def scan_axiom_trending(self):
        """
        DISABLED - Axiom integration removed.
        """
        print("⚠️ Axiom trending scan disabled.")
        return

    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create shared aiohttp session for faster API calls."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session
    
    async def close_session(self):
        """Close the shared session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _handle_ears_signal(self, signal: dict):
        """
        Handle incoming signal from Ears smart money tracker.
        Decides whether to auto-buy or just log based on config.
        """
        token = signal.get('token_address')
        ticker = signal.get('ticker', '$UNKNOWN')
        confidence = signal.get('confidence', 0)
        num_wallets = signal.get('num_wallets', 0)
        
        print(f"🦻 EARS SIGNAL: {ticker} | Confidence: {confidence:.1%} | {num_wallets} smart wallets")
        
        # Send Discord notification
        if WEBHOOK_URL:
            try:
                embed = {
                    "title": f"🦻 SMART MONEY ALERT: {ticker}",
                    "description": f"**{num_wallets} tracked wallets** are buying this token!",
                    "color": 0x9B59B6,  # Purple for Ears
                    "fields": [
                        {"name": "Confidence", "value": f"{confidence:.1%}", "inline": True},
                        {"name": "Signal Type", "value": signal.get('signal_type', 'smart_buy'), "inline": True},
                        {"name": "Address", "value": f"`{token[:8]}...{token[-6:]}`", "inline": False}
                    ]
                }
                async with aiohttp.ClientSession() as session:
                    await session.post(WEBHOOK_URL, json={"embeds": [embed]})
            except Exception as e:
                print(f"⚠️ Ears webhook failed: {e}")
        
        # Auto-buy if enabled and confidence is high enough
        if EARS_AUTO_BUY and confidence >= EARS_MIN_SIGNAL_CONFIDENCE:
            print(f"🦻 AUTO-BUY triggered for {ticker}")
            await self.buy(token, ticker, source='ears')
        else:
            print(f"🦻 Signal logged. Enable EARS_AUTO_BUY=true to auto-trade")

    def _cleanup_trade_attrs(self, address: str):
        """Clean up dynamic attributes created for a trade to prevent memory leaks."""
        attrs_to_clean = [
            f'_loop_{address}',
            f'_cached_data_{address}',
            f'_tp_lock_{address}'
        ]
        for attr in attrs_to_clean:
            if hasattr(self, attr):
                delattr(self, attr)

    async def get_momentum_data(self, address: str) -> dict:
        """Fetch buy/sell transaction counts from DexScreener."""
        session = await self.get_session()
        try:
            async with session.get(f"{self.dexscreener_api}{address}", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                        if sol_pairs:
                            best = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                            txns = best.get('txns', {}).get('m5', {})
                            return {
                                'buys_5m': txns.get('buys', 0),
                                'sells_5m': txns.get('sells', 0),
                                'price_change_5m': best.get('priceChange', {}).get('m5', 0)
                            }
        except:
            pass
        return {'buys_5m': 0, 'sells_5m': 0, 'price_change_5m': 0}

    async def monitor_position(self, address: str, ticker: str, entry_price: float):
        """
        Advanced Multi-Tier Sell Strategy with MOMENTUM CLIPPING:
        - Detects strong buy pressure (buys >>> sells)
        - Clips 15% of position during momentum spikes
        - Still respects fixed TPs as backstops
        - PANIC MODE for rapid losses
        """
        print(f"👀 Monitoring {ticker} (Momentum Clip Mode)...")
        
        highest_price = entry_price
        stop_loss_price = entry_price * HARD_STOP_LOSS  # -40%
        last_clip_price = 0  # Track last clip to avoid rapid re-clips
        previous_price = entry_price  # For volatility detection
        rapid_pump_sold = False  # Track if we already sold on rapid pump
        
        while address in self.active_monitors:
            try:
                # Initialize loop_count at start of each iteration
                loop_count = getattr(self, f'_loop_{address}', 0) + 1
                setattr(self, f'_loop_{address}', loop_count)
                
                # Fetch trade state
                trade = self.db.get_trade(address)
                if not trade or trade['status'] == 'CLOSED':
                    break
                
                # === EXTERNAL SELL DETECTION ===
                # Every 60 loops (~30-60 seconds), check if user sold externally
                if loop_count % 60 == 0 and self.real_mode:
                    token_balance = await self.engine.get_token_balance(address)
                    if token_balance <= 0:
                        print(f"🔍 {ticker} balance is ZERO - detecting external sell...")
                        
                        # Use current price for P&L (best available data)
                        current_price = await self.get_realtime_price(address)
                        if current_price <= 0:
                            current_price = await self.get_helius_price(address)
                        
                        if current_price > 0:
                            pnl_percent = (current_price - entry_price) / entry_price
                        else:
                            pnl_percent = 0  # Unknown
                        
                        # Log and close the trade
                        print(f"📤 External sell detected for {ticker}! Closing trade with {pnl_percent*100:+.1f}% P&L")
                        
                        meta = json.loads(trade['meta']) if trade['meta'] else {}
                        meta['external_sell'] = True
                        meta['full_exit_time'] = str(datetime.now())
                        
                        # Estimate SOL received based on P&L
                        entry_sol = trade['amount_sol']
                        sol_received = entry_sol * (1 + pnl_percent)
                        
                        self.db.log_sell(
                            address=address,
                            sell_price=current_price,
                            sell_mc=0,
                            amount_sol_received=sol_received,
                            percentage_sold=1.0,
                            reason="EXTERNAL SELL (Axiom/Wallet)"
                        )
                        self.db.update_trade(address, 'CLOSED', pnl_percent, meta)
                        print(f"✅ Trade {ticker} closed from external sell")
                        break
                
                # 1. Get REAL-TIME price from Jupiter FIRST (FAST - <100ms)
                current_price = await self.get_realtime_price(address)
                    
                # DYNAMIC POLLING - faster during volatility
                price_change_rate = abs(current_price - previous_price) / previous_price if previous_price > 0 and current_price > 0 else 0
                if price_change_rate > 0.05:  # >5% change = high volatility
                    await asyncio.sleep(0.25)  # Ultra-fast mode
                else:
                    await asyncio.sleep(0.5)  # Normal mode
                previous_price = current_price if current_price > 0 else previous_price  # Update for next iteration
                
                
                # 2. Get DexScreener data with SMART CACHING based on volatility
                # High volatility = refresh more often, Low volatility = cache longer
                
                # Smart cache refresh: every 5 loops during volatility, every 30 during calm
                cache_refresh_interval = 5 if price_change_rate > 0.02 else 30
                
                # Get the DEX where we bought - use SAME DEX for monitoring to avoid price mismatch
                trade_dex = trade.get('dex_id') or None
                
                if loop_count % cache_refresh_interval == 1 or not hasattr(self, f'_cached_data_{address}'):
                    token_data = await self.get_token_data(address, preferred_dex=trade_dex)
                    if token_data:
                        setattr(self, f'_cached_data_{address}', token_data)
                
                token_data = getattr(self, f'_cached_data_{address}', None)
                
                # Fallback chain: Jupiter -> Helius -> FRESH DexScreener -> Cached price
                if not current_price or current_price == 0:
                    current_price = await self.get_helius_price(address)
                
                # CRITICAL FIX: If still no price, fetch FRESH from DexScreener (not cached!)
                if not current_price or current_price == 0:
                    print(f"⚠️ {ticker}: Jupiter+Helius failed, fetching FRESH DexScreener price...")
                    fresh_data = await self.get_token_data(address, preferred_dex=trade_dex)
                    if fresh_data:
                        current_price = fresh_data.get('price', 0)
                        token_data = fresh_data  # Update cached data too
                        setattr(self, f'_cached_data_{address}', fresh_data)
                        print(f"📊 {ticker}: Got fresh DexScreener price: ${current_price:.8f}")
                
                # Last resort: use cached token_data price
                if (not current_price or current_price == 0) and token_data:
                    current_price = token_data.get('price', 0)
                
                # SAFETY: If still no price, use last known valid price
                last_price_attr = f'_last_valid_price_{address}'
                price_fail_attr = f'_price_fail_count_{address}'
                
                if not current_price or current_price == 0:
                    # Track consecutive failures
                    fail_count = getattr(self, price_fail_attr, 0) + 1
                    setattr(self, price_fail_attr, fail_count)
                    
                    # Log at key thresholds
                    if fail_count == 10:
                        print(f"⚠️ {ticker}: 10 consecutive price fetch failures")
                    elif fail_count == 50:
                        print(f"🚨 {ticker}: 50 consecutive price fetch failures - potential dead token?")
                    elif fail_count == 100:
                        print(f"💀 {ticker}: 100+ consecutive failures - TOKEN LIKELY DEAD (tp_hit: {meta.get('tp_2x_hit', False)}, be_locked: {meta.get('break_even_locked', False)})")
                    elif fail_count % 100 == 0:
                        print(f"💀 {ticker}: {fail_count} consecutive failures - STILL STUCK")
                    
                    # Use last known valid price instead of skipping
                    last_valid = getattr(self, last_price_attr, 0)
                    if last_valid > 0:
                        current_price = last_valid
                        print(f"⚠️ Using cached price for {ticker}: ${current_price:.8f}")
                    else:
                        # No cached price yet, must skip
                        continue
                else:
                    # Reset failure counter on successful price fetch
                    setattr(self, price_fail_attr, 0)
                    # === STALE PRICE DETECTION ===
                    # If new price is significantly different from cached, log warning
                    last_valid = getattr(self, last_price_attr, 0)
                    if last_valid > 0:
                        price_change = (current_price - last_valid) / last_valid
                        if abs(price_change) > 0.20:  # >20% change
                            print(f"🚨 {ticker} MAJOR PRICE MOVE: {price_change*100:+.1f}% (${last_valid:.8f} -> ${current_price:.8f})")
                    # Cache this valid price for next iteration
                    setattr(self, last_price_attr, current_price)
                    

                current_mc = 0
                if token_data:
                    current_mc = token_data.get('fdv', 0)
                    # Rescale MC if we have fresher Jupiter price
                    dex_price = token_data.get('price', 0)
                    if current_price > 0 and dex_price > 0:
                        current_mc = current_mc * (current_price / dex_price)

                pnl_percent = (current_price - entry_price) / entry_price
                
                # Update highest price
                if current_price > highest_price:
                    highest_price = current_price
                
                # === ENHANCED DATA COLLECTION ===
                # Capture snapshot every ~5 seconds (every 10 loops)
                if loop_count % 10 == 0:
                    momentum = await self.get_momentum_data(address)
                    self.db.add_snapshot(
                        address=address,
                        price=current_price,
                        mc=current_mc,
                        buys_5m=momentum.get('buys_5m', 0),
                        sells_5m=momentum.get('sells_5m', 0),
                        pnl_percent=pnl_percent
                    )
                
                # Update peak MC in database
                if current_mc > 0:
                    self.db.update_peak_mc(address, current_mc)
                
                # === DETAILED STATUS LOG (every ~30 seconds) ===
                if loop_count % 60 == 0:
                    meta_temp = json.loads(trade['meta']) if trade['meta'] else {}
                    
                    # Calculate sold percentage based on TPs hit
                    sold_pct = 0
                    sells_list = []
                    if meta_temp.get('tp_2x_hit'):
                        sold_pct += 40
                        sells_list.append("TP1.8x:40%")
                    if meta_temp.get('tp3_hit'):
                        sold_pct += 20
                        sells_list.append("TP3x:20%")
                    if meta_temp.get('tp4_hit'):
                        sold_pct += 20
                        sells_list.append("TP5x:20%")
                    if meta_temp.get('volume_decay_triggered'):
                        sold_pct += 25
                        sells_list.append("DECAY:25%")
                    
                    remaining_pct = max(0, 100 - sold_pct)
                    
                    # Determine next TP target
                    next_tp = "NONE (moonbag mode)"
                    next_tp_price = 0
                    if not meta_temp.get('tp_2x_hit'):
                        next_tp = "1.8x (+80%)"
                        next_tp_price = entry_price * 1.8
                    elif not meta_temp.get('tp3_hit'):
                        next_tp = "3x (+200%)"
                        next_tp_price = entry_price * 3.0
                    elif not meta_temp.get('tp4_hit'):
                        next_tp = "5x (+400%)"
                        next_tp_price = entry_price * 5.0
                    
                    # Format market cap
                    mc_str = f"${current_mc/1000:.1f}K" if current_mc < 1_000_000 else f"${current_mc/1_000_000:.2f}M"
                    entry_mc = meta_temp.get('entry_mc', 0)
                    entry_mc_str = f"${entry_mc/1000:.1f}K" if entry_mc < 1_000_000 else f"${entry_mc/1_000_000:.2f}M"
                    
                    # Time held
                    created_at_temp = trade.get('created_at')
                    if isinstance(created_at_temp, str):
                        try:
                            created_at_temp = datetime.fromisoformat(created_at_temp.replace('Z', '+00:00'))
                        except:
                            created_at_temp = datetime.now()
                    mins_held = (datetime.now() - created_at_temp).total_seconds() / 60 if created_at_temp else 0
                    time_str = f"{int(mins_held)}m" if mins_held < 60 else f"{mins_held/60:.1f}h"
                    
                    # Current multiple
                    current_x = current_price / entry_price if entry_price > 0 else 0
                    
                    # Build status line
                    print(f"\n{'='*60}")
                    print(f"📊 {ticker} STATUS | {time_str} held | MC: {mc_str}")
                    print(f"   💰 Entry: {entry_mc_str} → Now: {mc_str} | {current_x:.2f}x ({pnl_percent*100:+.1f}%)")
                    
                    if sells_list:
                        print(f"   ✅ SOLD: {' + '.join(sells_list)} = {sold_pct}% sold | {remaining_pct}% remaining")
                    else:
                        print(f"   📦 POSITION: 100% (no TPs hit yet)")
                    
                    if next_tp_price > 0:
                        distance_to_tp = ((next_tp_price - current_price) / current_price) * 100
                        print(f"   🎯 Next TP: {next_tp} | Need +{distance_to_tp:.1f}% to trigger")
                    else:
                        print(f"   🌙 MOONBAG MODE - riding with {remaining_pct}%")
                    
                    print(f"   🛑 Stop Loss: ${stop_loss_price:.8f} ({((stop_loss_price - current_price) / current_price)*100:+.1f}% away)")
                    
                    if meta_temp.get('break_even_locked'):
                        print(f"   🔒 BREAK-EVEN LOCKED (can't lose money)")
                    print(f"{'='*60}\n")
                
                status = trade['status']
                meta = json.loads(trade['meta']) if trade['meta'] else {}
                
                # Get trade creation time for time-based logic
                created_at = trade.get('created_at')
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.now()
                time_held_mins = (datetime.now() - created_at).total_seconds() / 60 if created_at else 0
                
                # Check for Manual Sell Command
                if status == 'SELL_REQUEST':
                    print(f"🚨 MANUAL SELL REQUEST RECEIVED for {ticker}")
                    await self.sell(address, current_price, 1.0, "Manual Panic Sell")
                    break  # Exit loop so cleanup runs
                
                # Track max MC hit for caller success tracking
                max_mc = meta.get('max_mc_hit', 0)
                if current_mc > max_mc:
                    meta['max_mc_hit'] = current_mc
                    self.db.update_trade(address, status, pnl_percent, meta)
                
                tp1_hit = meta.get('tp1_hit', False)
                tp2_hit = meta.get('tp2_hit', False)
                clip_count = meta.get('clip_count', 0)
                
                # === SMART BUNDLING EXECUTION ===
                # Instead of selling immediately and returning (which causes double-sells on spikes),
                # we accumulate all triggered sell conditions and execute ONE transaction.
                
                total_sell_pct = 0.0
                sell_reasons = []
                triggered_something = False
                
                # === ZOMBIE TRADE PROTECTION (6 hours max for losers) ===
                if time_held_mins > 360 and pnl_percent < 0:  # 6 hours
                    print(f"💀 {ticker} ZOMBIE KILL! Held {time_held_mins/60:.1f}h at {pnl_percent*100:.1f}%")
                    await self.sell(address, current_price, 1.0, f"ZOMBIE KILL ({time_held_mins/60:.1f}h)")
                    break
                
                # === BREAK-EVEN LOCK (Once at +50%, can't lose money) ===
                if pnl_percent >= 0.50 and not meta.get('break_even_locked'):
                    # Lock stop-loss at entry price (break-even)
                    if entry_price > stop_loss_price:
                        stop_loss_price = entry_price
                        meta['break_even_locked'] = True
                        print(f"🔒 {ticker} BREAK-EVEN LOCKED! Can't lose money now.")
                        self.db.update_trade(address, status, pnl_percent, meta)
                
                # === TRAILING STOP LOGIC ===
                # Under +50%: Hard stop at -30%
                # Above +50%: Trail 35% below highest price
                if pnl_percent >= 0.50:
                    # Trailing mode: SL = 35% below high
                    trailing_sl = highest_price * 0.65
                    if trailing_sl > stop_loss_price:
                        stop_loss_price = trailing_sl
                        print(f"📈 {ticker} Trailing SL updated to ${stop_loss_price:.8f}")

                # === CUSTOM TPs ===
                tp_2x_hit = meta.get('tp_2x_hit', False)
                tp3_hit = meta.get('tp3_hit', False)
                tp4_hit = meta.get('tp4_hit', False)
                
                # In-memory lock to prevent duplicate TP triggers during fast polling
                # DB updates happen AFTER sell, so we need immediate memory lock
                tp_lock_key = f'_tp_lock_{address}'
                if not hasattr(self, tp_lock_key):
                    setattr(self, tp_lock_key, set())
                tp_locks = getattr(self, tp_lock_key)
                
                # TP1 (1.8x) - Sell User Defined %
                if current_price >= (entry_price * TP1_FACTOR) and not tp_2x_hit and '2x' not in tp_locks:
                    tp_locks.add('2x')  # IMMEDIATE lock before async sell
                    print(f"🚀 {ticker} Hit {TP1_FACTOR}x! Selling {TP1_AMOUNT*100:.0f}%")
                    total_sell_pct += TP1_AMOUNT
                    sell_reasons.append(f"TP ({TP1_FACTOR}x)")
                    # Update Stop Loss to TP1_SL (e.g., 1.4x)
                    new_sl = entry_price * TP1_SL
                    if new_sl > stop_loss_price:
                        stop_loss_price = new_sl
                        print(f"🛑 Stop Loss moved up to ${stop_loss_price:.8f} ({TP1_SL}x)")
                    meta['tp_2x_hit'] = True
                    triggered_something = True
                
                # TP2 (3x) - Sell User Defined %
                if current_price >= (entry_price * TP2_FACTOR) and not tp3_hit and '3x' not in tp_locks:
                    tp_locks.add('3x')
                    print(f"🎯 {ticker} Hit {TP2_FACTOR}x! Selling {TP2_AMOUNT*100:.0f}%")
                    total_sell_pct += TP2_AMOUNT
                    sell_reasons.append(f"TP ({TP2_FACTOR}x)")
                    # Update Stop Loss to TP2_SL (e.g., 2.0x)
                    new_sl = entry_price * TP2_SL
                    if new_sl > stop_loss_price:
                        stop_loss_price = new_sl
                        print(f"🛑 Stop Loss moved up to ${stop_loss_price:.8f} ({TP2_SL}x)")
                    meta['tp3_hit'] = True
                    triggered_something = True
                
                # TP3 (5x) - Sell User Defined % + Discord Alert
                if current_price >= (entry_price * TP3_FACTOR) and not tp4_hit and '5x' not in tp_locks:
                    tp_locks.add('5x')
                    print(f"🔥 {ticker} Hit {TP3_FACTOR}x! Selling {TP3_AMOUNT*100:.0f}%")
                    total_sell_pct += TP3_AMOUNT
                    sell_reasons.append(f"TP ({TP3_FACTOR}x)")
                    # Update SL to TP3_SL
                    new_sl = max(stop_loss_price, entry_price * TP3_SL)
                    stop_loss_price = new_sl
                    meta['tp4_hit'] = True
                    triggered_something = True
                    
                    try:
                        alert_msg = f"<@&cache100x> 🔥🔥🔥 **{ticker} HIT {TP3_FACTOR}X!** 🔥🔥🔥\n\n💰 Entry: ${entry_price*1000000:.2f}\n📈 Current: ${current_price*1000000:.2f}\n🚀 **+{(TP3_FACTOR-1)*100:.0f}% PROFIT**\n\nMOONBAG STILL RIDING! 🌙"
                        async with aiohttp.ClientSession() as session:
                            await session.post(WEBHOOK_URL, json={"content": alert_msg})
                        print(f"📢 5x Alert sent to Discord!")
                    except Exception as e:
                        print(f"⚠️ Discord alert failed: {e}")
                
                # === GRANULAR PROFIT ALERTS (Every X Integer) ===
                # Calculate current multiple
                current_x = current_price / entry_price if entry_price > 0 else 0
                last_x_alert = meta.get('last_x_alert', 1)
                
                # Only alert if we crossed a new integer threshold >= 2
                # Loop through all integers crossed to ensure "no skipping"
                if int(current_x) > last_x_alert and current_x >= 2:
                    start_alert = last_x_alert + 1
                    end_alert = int(current_x)
                    
                    for milestone in range(start_alert, end_alert + 1):
                         print(f"👑 {ticker} Hit {milestone}x! (Previous: {last_x_alert}x)")
                         asyncio.create_task(broadcast_profit(ticker, address, float(milestone), time_held_mins, current_mc))
                         # Small sleep to prevent rate limits/spam block if huge jump?
                         # Or just fire them all async. Telegram rate limits might be an issue if we jump 2x->10x instantly.
                         # But for "no skipping", this is what is requested.
                    
                    meta['last_x_alert'] = end_alert
                    # Update DB immediately to avoid duplicate alerts
                    self.db.update_trade(address, status, pnl_percent, meta)
                
                # === EXECUTE BUNDLED SELL ===
                if total_sell_pct > 0:
                    # Cap at 100% just in case
                    total_sell_pct = min(total_sell_pct, 1.0)
                    reason_str = " + ".join(sell_reasons)
                    print(f"🌪️ BUNDLED SELL: {reason_str} = {total_sell_pct*100:.0f}%")
                    await self.sell(address, current_price, total_sell_pct, reason_str)
                    
                    # Update DB only once
                    new_status = 'MOONBAG' if meta.get('tp2_hit') else 'PARTIAL'
                    self.db.update_trade(address, new_status, pnl_percent, meta)
                    continue

                if triggered_something:
                     # e.g. just Break-even lock with no sell
                     self.db.update_trade(address, status, pnl_percent, meta)
                
                # === TRAILING STOP (Final 10% moonbag) ===
                if tp4_hit or clip_count >= 3:
                    # Use configured trailing stop percent (35% from config)
                    trail_mult = 1.0 - TRAILING_STOP_PERCENT
                    potential_new_stop = highest_price * trail_mult
                    if potential_new_stop > stop_loss_price:
                        stop_loss_price = potential_new_stop
                
                # === VOLUME DECAY DETECTION ===
                # If volume drops 50%+ from peak and we're in profit, sell 25%
                volume_decay_triggered = meta.get('volume_decay_triggered', False)
                if not volume_decay_triggered and pnl_percent > 0.20:  # Only if up 20%+
                    momentum = await self.get_momentum_data(address)
                    current_vol = momentum['buys_5m'] + momentum['sells_5m']
                    
                    # Track peak volume
                    peak_vol = meta.get('peak_volume', 0)
                    if current_vol > peak_vol:
                        meta['peak_volume'] = current_vol
                        peak_vol = current_vol
                    
                    # Check for decay (volume dropped 50%+ from peak)
                    if peak_vol > 50 and current_vol < peak_vol * 0.5:
                        print(f"📉 {ticker} VOLUME DECAY! {current_vol} txns vs peak {peak_vol}")
                        await self.sell(address, current_price, 0.25, f"VOLUME DECAY ({current_vol}/{peak_vol} txns)")
                        meta['volume_decay_triggered'] = True
                        self.db.update_trade(address, status, pnl_percent, meta)
                        continue
                
                # === STOP LOSS ===
                pnl_now = pnl_percent * 100
                if pnl_now <= -25:
                    print(f"⚠️ {ticker} CRITICAL: {pnl_now:.1f}%")

                if current_price <= stop_loss_price:
                    print(f"🛑 {ticker} STOP LOSS! ${current_price:.8f} <= ${stop_loss_price:.8f}")
                    await self.sell(address, current_price, 1.0, f"STOP LOSS at {pnl_now:.1f}%")
                    break
                
                # Update PnL
                if abs(pnl_percent - trade['pnl_percent']) > 0.01:
                    self.db.update_trade(address, status, pnl_percent)
            
            except Exception as e:
                print(f"⚠️ Monitor error for {ticker}: {e}")
                await asyncio.sleep(1)
        
        # Cleanup dynamic attributes when monitoring ends
        self._cleanup_trade_attrs(address)
        self.active_monitors.discard(address)

    async def send_webhook(self, title: str, description: str, color: int, address: str = None, entry_price: float = None, current_price: float = None, fee: float = None):
        """Sends a rich Discord embed webhook."""
        if not WEBHOOK_URL:
            return
        
        # Fetch Real Wallet Balance
        footer_text = "QuickTrade"
        if self.real_mode:
            try:
                sol_bal = await self.engine.get_sol_balance()
                footer_text = f"💰 {sol_bal:.4f} SOL"
            except:
                footer_text = "Real Mode"
        else:
            footer_text = f"Paper: {self.balance:.4f} SOL"

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "footer": {"text": footer_text},
            "fields": []
        }

        # Add Fee Field if provided
        if fee is not None:
            embed["fields"].append({
                "name": "Network Fee",
                "value": f"{fee:.5f} SOL",
                "inline": True
            })
        
        # Add Market Cap if we have address
        if address:
            try:
                token_data = await self.get_token_data(address)
                if token_data:
                    price = token_data['price']
                    symbol = token_data['symbol']
                    # Calculate Estimated Global Fees (Volume * Fee Rate)
                    # Pump.fun = 1%, Raydium/Orca = 0.25%
                    vol_24h = token_data.get('volume_h24', 0)
                    dex_id = token_data.get('dex_id', 'unknown')
                    fee_rate = 0.01 if dex_id == 'pumpfun' else 0.0025
                    est_global_fees = vol_24h * fee_rate
                    
                    # Convert to SOL (Approximation using price)
                    # Vol is USD, Fees USD.
                    # We want Fees in SOL. 
                    # Fee USD / Price USD = Fee in Tokens ... No.
                    # Fee USD / SOL Price = Fee in SOL. 
                    # We need SOL price. Approximation: 1 SOL = $140 (hardcoded or fetched?)
                    # Better: Volume is usually Quote Token Volume? DexScreener vol is USD.
                    # Let's show Estimated Fees in USD for clarity, or try to convert.
                    # User asked for "global fees below .2" (SOL).
                    # Let's use the priceNative (SOL) vs priceUsd relation to find SOL price.
                    # 1 Token = priceNative SOL = priceUsd USD
                    # -> 1 SOL = priceUsd / priceNative
                    
                    sol_price_est = 150 # Fallback
                    if token_data.get('price_native') and token_data.get('price'):
                         sol_price_est = token_data['price'] / token_data['price_native']
                    
                    est_global_fees_sol = est_global_fees / sol_price_est if sol_price_est else 0

                    if fee is not None:
                        embed["fields"].append({
                            "name": "Network Fee",
                            "value": f"{fee:.5f} SOL",
                            "inline": True
                        })
                    
                    embed["fields"].append({
                        "name": "Global Fees (Est)",
                        "value": f"{est_global_fees_sol:.2f} SOL",
                        "inline": True
                    })
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.dexscreener_api}{address}") as response:
                            if response.status == 200:
                                data = await response.json()
                                pairs = data.get('pairs', [])
                                if pairs:
                                    sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                                    if sol_pairs:
                                        best_pair = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                                        mcap = best_pair.get('fdv', 0)
                                        if mcap:
                                            mcap_k = mcap / 1000
                                            embed["fields"].append({
                                                "name": "Market Cap",
                                                "value": f"${mcap_k:.1f}K",
                                                "inline": True
                                            })
            except:
                pass
        
        # Add entry/current as Market Cap instead of raw price
        if entry_price and address:
            try:
                # Calculate entry MC from current MC and price ratio
                token_data = await self.get_token_data(address)
                if token_data:
                    current_price_live = token_data['price']
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.dexscreener_api}{address}") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                pairs = data.get('pairs', [])
                                if pairs:
                                    sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                                    if sol_pairs:
                                        best = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                                        current_mc = best.get('fdv', 0)
                                        if current_mc and current_price_live:
                                            # Calculate entry MC based on price ratio
                                            entry_mc = current_mc * (entry_price / current_price_live)
                                            
                                            def fmt_mc(val):
                                                if val >= 1_000_000: return f"${val/1_000_000:.2f}M"
                                                elif val >= 1_000: return f"${val/1_000:.1f}K"
                                                else: return f"${val:.0f}"
                                            
                                            embed["fields"].append({
                                                "name": "Entry MC",
                                                "value": fmt_mc(entry_mc),
                                                "inline": True
                                            })
                                            
                                            if current_price:
                                                current_mc_at_sell = current_mc * (current_price / current_price_live)
                                                embed["fields"].append({
                                                    "name": "Exit MC",
                                                    "value": fmt_mc(current_mc_at_sell),
                                                    "inline": True
                                                })
                                                
                                                pnl = ((current_price - entry_price) / entry_price) * 100
                                                embed["fields"].append({
                                                    "name": "PnL",
                                                    "value": f"{pnl:+.1f}%",
                                                    "inline": True
                                                })
            except Exception as e:
                # Fallback to raw prices if MC calc fails
                embed["fields"].append({"name": "Entry", "value": f"${entry_price:.8f}", "inline": True})
                if current_price:
                    embed["fields"].append({"name": "Current", "value": f"${current_price:.8f}", "inline": True})
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(WEBHOOK_URL, json={"embeds": [embed]}) as response:
                    if response.status not in [200, 204]:
                        print(f"Webhook failed: {response.status}")
            except Exception as e:
                print(f"Webhook Exception: {e}")

    async def get_realtime_price(self, address: str) -> float:
        """Fetches real-time price from Jupiter API v2 (Low Latency)."""
        url = f"https://api.jup.ag/price/v2?ids={address}"
        session = await self.get_session()
        try:
            async with session.get(url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    # Structure: {'data': {'ADDRESS': {'id': '...', 'type': 'derivedPrice', 'price': '123.45'}}}
                    item = data.get('data', {}).get(address, {})
                    if item and 'price' in item:
                        return float(item['price'])
        except Exception as e:
            pass # Fail silently, fallback to Helius
        return 0.0

    async def get_helius_price(self, address: str) -> float:
        """Fetches price from Helius DAS API (getAsset with fungible pricing)."""
        # Ears disabled - skip Helius price fetch
        HELIUS_API_KEY = None  # ears_config removed
        if not HELIUS_API_KEY:
            return 0.0
        
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
        session = await self.get_session()
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "helius-price",
                "method": "getAsset",
                "params": {"id": address}
            }
            async with session.post(url, json=payload, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {})
                    # Check for token_info.price_info
                    token_info = result.get('token_info', {})
                    price_info = token_info.get('price_info', {})
                    if price_info.get('price_per_token'):
                        return float(price_info['price_per_token'])
        except Exception as e:
            pass  # Fail silently
        return 0.0

    async def parse_swap_transaction(self, tx_sig: str) -> dict:
        """
        Parses a swap transaction using Helius Enhanced Transactions API.
        Returns exact SOL amounts for accurate P&L calculation.
        
        Returns:
            {
                'sol_in': float,      # SOL spent (for buys) or 0
                'sol_out': float,     # SOL received (for sells) or 0
                'tokens_in': float,   # Tokens received (for buys) or 0
                'tokens_out': float,  # Tokens spent (for sells) or 0
                'success': bool
            }
        """
        # Ears disabled - skip transaction parsing
        HELIUS_API_KEY = None  # ears_config removed
        if not HELIUS_API_KEY or not tx_sig:
            return {'sol_in': 0, 'sol_out': 0, 'tokens_in': 0, 'tokens_out': 0, 'success': False}
        
        url = f"https://api.helius.xyz/v0/transactions?api-key={HELIUS_API_KEY}"
        session = await self.get_session()
        
        try:
            payload = {"transactions": [tx_sig]}
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        tx = data[0]
                        events = tx.get('events', {})
                        swap = events.get('swap', {})
                        
                        if swap:
                            # Parse native SOL amounts (in lamports -> convert to SOL)
                            native_input = swap.get('nativeInput', {})
                            native_output = swap.get('nativeOutput', {})
                            
                            sol_in = int(native_input.get('amount', 0)) / 1_000_000_000
                            sol_out = int(native_output.get('amount', 0)) / 1_000_000_000
                            
                            # Parse token amounts
                            token_inputs = swap.get('tokenInputs', [])
                            token_outputs = swap.get('tokenOutputs', [])
                            
                            tokens_in = 0
                            tokens_out = 0
                            
                            for t in token_outputs:
                                raw = t.get('rawTokenAmount', {})
                                amount = float(raw.get('tokenAmount', 0))
                                decimals = int(raw.get('decimals', 0))
                                tokens_in += amount / (10 ** decimals) if decimals > 0 else amount
                            
                            for t in token_inputs:
                                raw = t.get('rawTokenAmount', {})
                                amount = float(raw.get('tokenAmount', 0))
                                decimals = int(raw.get('decimals', 0))
                                tokens_out += amount / (10 ** decimals) if decimals > 0 else amount
                            
                            print(f"📊 Helius parsed TX: SOL in={sol_in:.4f}, SOL out={sol_out:.4f}, Tokens in={tokens_in:.2f}, Tokens out={tokens_out:.2f}")
                            
                            return {
                                'sol_in': sol_in,
                                'sol_out': sol_out,
                                'tokens_in': tokens_in,
                                'tokens_out': tokens_out,
                                'success': True
                            }
                        else:
                            # Not a swap, check nativeTransfers for direct SOL movement
                            transfers = tx.get('nativeTransfers', [])
                            sol_out = 0
                            for t in transfers:
                                if t.get('toUserAccount') == self.wallet_address:
                                    sol_out += t.get('amount', 0) / 1_000_000_000
                            return {'sol_in': 0, 'sol_out': sol_out, 'tokens_in': 0, 'tokens_out': 0, 'success': True}
        except Exception as e:
            print(f"⚠️ Helius parse error: {e}")
        
        return {'sol_in': 0, 'sol_out': 0, 'tokens_in': 0, 'tokens_out': 0, 'success': False}

    async def get_token_data(self, address: str, preferred_dex: str = None) -> Optional[dict]:
        """Fetches comprehensive token data (Price, Symbol, Volume, Liquidity, DexID).
        
        If preferred_dex is specified, tries to use that DEX's pair first.
        Falls back to highest liquidity pair if preferred DEX not found.
        """
        session = await self.get_session()
        try:
            async with session.get(f"{self.dexscreener_api}{address}", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                        if sol_pairs:
                            # If preferred_dex specified, try to find that pair first
                            # BUT only if it has liquidity (tokens can migrate DEXes)
                            best_pair = None
                            if preferred_dex:
                                matching = [p for p in sol_pairs if p.get('dexId') == preferred_dex]
                                if matching:
                                    preferred_pair = matching[0]
                                    preferred_liq = preferred_pair.get('liquidity', {}).get('usd', 0)
                                    if preferred_liq > 100:  # Min $100 liquidity to use preferred
                                        best_pair = preferred_pair
                                        print(f"📍 Using preferred DEX: {preferred_dex} (liq: ${preferred_liq:.0f})")
                                    else:
                                        print(f"⚠️ Preferred DEX {preferred_dex} has $0 liquidity - token migrated? Falling back to best DEX.")
                            
                            # Fallback to highest liquidity
                            if not best_pair:
                                best_pair = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                            
                            return {
                                'price': float(best_pair.get('priceUsd', 0)),
                                'price_native': float(best_pair.get('priceNative', 0)),
                                'symbol': best_pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                                'volume_h24': best_pair.get('volume', {}).get('h24', 0),
                                'liquidity_usd': best_pair.get('liquidity', {}).get('usd', 0),
                                'dex_id': best_pair.get('dexId', 'unknown'),
                                'fdv': best_pair.get('fdv', 0),
                                'pair_address': best_pair.get('pairAddress'),
                                'created_at': best_pair.get('pairCreatedAt', 0)
                            }
        except Exception as e:
            print(f"Error fetching data for {address}: {e}")
        return None

    async def check_wash_trading(self, address: str) -> dict:
        """
        Detects potential wash trading / bot activity by analyzing:
        - Volume-per-transaction ratio (high volume, low txns = wash trading)
        - Transaction count patterns
        
        Returns: {'safe': bool, 'reason': str, 'suspicion_score': float}
        """
        result = {'safe': True, 'reason': 'Unknown', 'suspicion_score': 0}
        
        try:
            session = await self.get_session()
            async with session.get(f"{self.dexscreener_api}{address}", timeout=3) as response:
                if response.status != 200:
                    result['reason'] = 'Could not fetch data'
                    return result
                    
                data = await response.json()
                pairs = data.get('pairs', [])
                if not pairs:
                    result['reason'] = 'No pairs found'
                    return result
                    
                sol_pairs = [p for p in pairs if p.get('chainId') == 'solana']
                if not sol_pairs:
                    result['reason'] = 'No Solana pairs'
                    return result
                    
                best = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                
                # Get volume and transaction data
                volume_24h = best.get('volume', {}).get('h24', 0)
                volume_1h = best.get('volume', {}).get('h1', 0)
                txns_24h = best.get('txns', {}).get('h24', {})
                txns_1h = best.get('txns', {}).get('h1', {})
                
                total_txns_24h = txns_24h.get('buys', 0) + txns_24h.get('sells', 0)
                total_txns_1h = txns_1h.get('buys', 0) + txns_1h.get('sells', 0)
                
                mcap = best.get('marketCap', best.get('fdv', 0))
                liquidity = best.get('liquidity', {}).get('usd', 0)
                
                # Calculate "volume per transaction" - organic trading has 50-500$ per tx
                # Wash trading has very high volume per tx (thousands per "trade")
                vol_per_tx_1h = volume_1h / total_txns_1h if total_txns_1h > 0 else 0
                vol_per_tx_24h = volume_24h / total_txns_24h if total_txns_24h > 0 else 0
                
                suspicion = 0
                reasons = []
                
                # RED FLAG 1: High volume per transaction (> $5000 avg)
                if vol_per_tx_1h > 5000:
                    suspicion += 40
                    reasons.append(f"Vol/TX 1h: ${vol_per_tx_1h:,.0f}")
                elif vol_per_tx_1h > 2000:
                    suspicion += 20
                    reasons.append(f"Vol/TX 1h: ${vol_per_tx_1h:,.0f}")
                    
                # RED FLAG 2: Very low transaction count for the volume
                if volume_1h > 10000 and total_txns_1h < 20:
                    suspicion += 30
                    reasons.append(f"${volume_1h:,.0f} vol, only {total_txns_1h} txns")
                    
                # RED FLAG 3: High volume but low liquidity (easy to manipulate)
                if volume_24h > 0 and liquidity > 0:
                    vol_liq_ratio = volume_24h / liquidity
                    if vol_liq_ratio > 50:  # 50x volume vs liquidity is sus
                        suspicion += 25
                        reasons.append(f"Vol/Liq: {vol_liq_ratio:.0f}x")
                
                # Final verdict
                result['suspicion_score'] = min(suspicion, 100)
                if suspicion >= 50:
                    result['safe'] = False
                    result['reason'] = f"🚨 WASH TRADING SUSPECTED: {', '.join(reasons)}"
                elif suspicion >= 30:
                    result['reason'] = f"⚠️ CAUTION: {', '.join(reasons)}"
                else:
                    result['reason'] = "✅ Trading patterns appear organic"
                    
                print(f"🔍 Wash Check {address[:8]}: Score={suspicion} | {result['reason']}")
                
        except Exception as e:
            result['reason'] = f"Check failed: {e}"
            
        return result

    async def buy(self, address: str, ticker: str, source: str = None, amount_sol: float = None):
        """
        Execute buy with dynamic position sizing and multi-source signal coordination.
        - If first source: full buy, register signal
        - If second source within 5 mins: 50% boost buy
        - If duplicate or outside window: skip
        """
        now = datetime.now()
        is_boost = False
        
        # ATOMIC: Check and add to pending_buys immediately to prevent race conditions
        if address in self.pending_buys:
            print(f"⚠️ Already processing buy for {ticker}")
            return
        self.pending_buys.add(address)  # Lock immediately
        
        # 🔍 WASH TRADING / RUG DETECTION CHECK
        wash_result = await self.check_wash_trading(address)
        if not wash_result['safe']:
            print(f"🛑 BLOCKED: {ticker} - {wash_result['reason']}")
            self.pending_buys.discard(address)
            # Send webhook alert for blocked rug
            if WEBHOOK_URL:
                try:
                    embed = {
                        "title": f"🛑 RUG DETECTED: {ticker}",
                        "description": wash_result['reason'],
                        "color": 0xFF0000,  # Red
                        "fields": [
                            {"name": "Suspicion Score", "value": f"{wash_result['suspicion_score']}/100", "inline": True},
                            {"name": "Action", "value": "BUY BLOCKED", "inline": True}
                        ]
                    }
                    async with aiohttp.ClientSession() as session:
                        await session.post(WEBHOOK_URL, json={"embeds": [embed]})
                except:
                    pass
            return
        
        # 🐦 X SENTIMENT CHECK (Optional - Pre-Buy Filter)
        if self.x_sentiment and X_SENTIMENT_ENABLED:
            # Fetch token data first to check MC for bypass
            token_data_for_sentiment = await self.get_token_data(address)
            mc_for_check = token_data_for_sentiment.get('fdv', 0) if token_data_for_sentiment else 0
            
            # ALWAYS update ticker from DexScreener to get the real symbol (fixes $PF etc being used for different tokens)
            if token_data_for_sentiment:
                fetched_symbol = token_data_for_sentiment.get('symbol', '')
                if fetched_symbol and fetched_symbol != 'UNKNOWN':
                    original_ticker = ticker
                    ticker = f"${fetched_symbol}"
                    if original_ticker != ticker:
                        print(f"📛 Ticker resolved from DexScreener: {original_ticker} -> {ticker}")
            
            # Skip sentiment check for high MC tokens (already validated by market)
            if mc_for_check < X_SENTIMENT_BYPASS_HIGH_MC:
                print(f"🐦 Running X sentiment check for {ticker}...")
                sentiment_result = await self.x_sentiment.check_sentiment(address, ticker)
                
                if not sentiment_result['passed']:
                    print(f"🐦 SENTIMENT FAIL: {ticker} - {sentiment_result['reason']}")
                    self.pending_buys.discard(address)
                    
                    # Send webhook alert for low sentiment
                    if WEBHOOK_URL:
                        try:
                            embed = {
                                "title": f"🐦 LOW SENTIMENT: {ticker}",
                                "description": sentiment_result['reason'],
                                "color": 0xFFA500,  # Orange
                                "fields": [
                                    {"name": "Unique Mentions", "value": str(sentiment_result.get('unique_mentions', 0)), "inline": True},
                                    {"name": "Avg Quality", "value": f"{sentiment_result.get('avg_quality', 0):.1%}", "inline": True},
                                    {"name": "Bot Ratio", "value": f"{sentiment_result.get('bot_ratio', 0):.1%}", "inline": True},
                                    {"name": "Action", "value": "BUY SKIPPED", "inline": True},
                                    {"name": "CA", "value": f"`{address}`", "inline": False}
                                ]
                            }
                            async with aiohttp.ClientSession() as session:
                                await session.post(WEBHOOK_URL, json={"embeds": [embed]})
                        except:
                            pass
                    return
                else:
                    print(f"✅ {ticker} SENTIMENT PASSED: {sentiment_result['unique_mentions']} mentions, {sentiment_result['avg_quality']:.1%} quality")
            else:
                print(f"🐦 Bypassing sentiment check for {ticker} (MC ${mc_for_check/1000:.1f}k > ${X_SENTIMENT_BYPASS_HIGH_MC/1000:.0f}k threshold)")

        # Check existing trade in DB
        existing_trade = self.db.get_trade(address)
        if existing_trade:
            # Check if this is a valid boost (different source, within window)
            meta = json.loads(existing_trade.get('meta', '{}')) if existing_trade.get('meta') else {}
            original_source = existing_trade.get('source')
            created_at = existing_trade.get('created_at')
            
            # Parse created_at to datetime
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    created_at = datetime.now() - timedelta(hours=1)  # Assume old
            
            age = now - created_at if created_at else timedelta(hours=1)
            
            # Boost conditions: different source, within window, not already boosted
            if (source and original_source and source != original_source and 
                age <= timedelta(minutes=SIGNAL_BOOST_WINDOW_MINS) and
                not meta.get('boosted', False)):
                
                is_boost = True
                print(f"🚀 SIGNAL BOOST: {ticker} confirmed by {source} (original: {original_source})")
            else:
                print(f"⚠️ Trade for {ticker} already exists (source: {original_source}). Skipping.")
                self.pending_buys.discard(address)
                return
        
        # Also check signal registry for in-flight buys
        if not is_boost and address in self.signal_registry:
            reg = self.signal_registry[address]
            age = now - reg['time']
            if age <= timedelta(minutes=SIGNAL_BOOST_WINDOW_MINS) and source != reg['source']:
                # This will become a boost once original completes
                print(f"⏳ {ticker} already signaled by {reg['source']}. Waiting for boost window...")
                self.pending_buys.discard(address)
                return
        
        
        # Register signal for coordination (before async operations)
        if not is_boost:
            self.signal_registry[address] = {
                'time': now,
                'source': source,
                'ticker': ticker
            }

        # Dynamic Position Sizing
        current_balance = await self.engine.get_sol_balance() if self.real_mode else self.balance
        
        if not self.real_mode:
            # User Requested Simulation Override
            base_amount = PAPER_TRADE_AMOUNT
            print(f"📄 Paper Simulation: Forcing {base_amount} SOL size (ignoring requested {amount_sol})")
        elif amount_sol:
            base_amount = amount_sol
            print(f"🎯 Override buy size: {base_amount} SOL")
        else:
            base_amount = get_position_size(current_balance)
        
        # Boost buys are 50% of normal size
        buy_amount = base_amount * SIGNAL_BOOST_AMOUNT if is_boost else base_amount
        
        if current_balance < buy_amount:
            print(f"⚠️ Insufficient balance. Need {buy_amount:.4f} SOL, have {current_balance:.4f} SOL")
            self.pending_buys.discard(address)
            if not is_boost:
                self.signal_registry.pop(address, None)
            return

        # Fetch initial price and data
        token_data = await self.get_token_data(address)
        if not token_data:
            print(f"⚠️ Could not fetch price/data for {ticker}. Buy failed.")
            self.pending_buys.discard(address)
            if not is_boost:
                self.signal_registry.pop(address, None)
            return

        # 🛑 DEGEN CONFIG ENFORCEMENT 🛑
        # 1. Market Cap Check
        mc = token_data.get('fdv', 0)
        if mc > MAX_ENTRY_MC:
            print(f"🛑 BLOCKED: {ticker} MC ${mc:,.0f} > Limit ${MAX_ENTRY_MC:,.0f}")
            self.pending_buys.discard(address)
            if not is_boost:
                self.signal_registry.pop(address, None)
            return

        # 2. Age Check
        creation_time = token_data.get('pairCreatedAt', 0)
        if creation_time:
            age_mins = (datetime.now().timestamp() * 1000 - creation_time) / (1000 * 60)
            if age_mins > MAX_TOKEN_AGE_MINUTES:
                print(f"🛑 BLOCKED: {ticker} Age {age_mins:.0f}m > Limit {MAX_TOKEN_AGE_MINUTES}m")
                self.pending_buys.discard(address)
                if not is_boost:
                    self.signal_registry.pop(address, None)
                return
        
        # Skip filters for boost buys (already validated on first buy)
        if is_boost:
            print(f"🚀 Boost buy - skipping filters (already validated)")
        else:
            # --- PLATFORM SAFETY CAP (User Requested) ---
            # If not Pump.fun or Moonshot/Bonk, cap at 0.015 SOL
            dex_id = token_data.get('dex_id', 'unknown')
            is_pump = dex_id == 'pumpfun' or address.endswith('pump')
            is_bonk = dex_id == 'moonshot' or address.endswith('bonk') 
            
            if not (is_pump or is_bonk):
                print(f"⚠️ Standard DEX (Raydium/etc) detected. Capping buy at 0.02 SOL (Safety Mode)")
                buy_amount = min(buy_amount, 0.02)
            
            # --- ADVANCED FILTERS (User Requested) ---
            
            # 1. Global Fees Check (RUGCHECK)
            # Calc fee rate (1% pump, 0.25% raydium) * Volume
            vol_24h = token_data.get('volume_h24', 0)
            dex_id = token_data.get('dex_id', 'unknown')
            fee_rate = 0.01 if dex_id == 'pumpfun' else 0.0025
            global_fees_usd = vol_24h * fee_rate
            
            # Est SOL price to convert fees to SOL
            sol_price = 150.0 
            if token_data.get('price_native') and token_data.get('price_native') > 0:
                sol_price = token_data['price'] / token_data['price_native']
                
            global_fees_sol = global_fees_usd / sol_price
            
            # === ENHANCED RUGCHECK ===
            # High MC + Low Fees = Fake volume = Rug
            fdv = token_data.get('fdv', 0)
            
            # Calculate MC/Fee ratio (lower = more real volume)
            # Real tokens: ~$5-10k MC per 1 SOL fees
            # Rug tokens: ~$50k+ MC per 1 SOL fees
            mc_per_fee = fdv / global_fees_sol if global_fees_sol > 0 else float('inf')
            
            # Dynamic threshold based on MC
            # Low MC (<50k): more lenient, allow 100k per fee SOL
            # Mid MC (50-200k): stricter, need 50k per fee SOL
            # High MC (>200k): very strict, need 30k per fee SOL
            if fdv < 50000:
                max_mc_per_fee = 100000  # $100k MC per 1 SOL fees for small tokens
            elif fdv < 200000:
                max_mc_per_fee = 50000   # $50k MC per 1 SOL fees for mid tokens
            else:
                max_mc_per_fee = 30000   # $30k MC per 1 SOL fees for large tokens
            
            if mc_per_fee > max_mc_per_fee:
                print(f"⛔ RUG ALERT {ticker}: MC/Fee ratio too high!")
                print(f"   MC: ${fdv/1000:.1f}k | Est Fees: {global_fees_sol:.2f} SOL | Ratio: ${mc_per_fee/1000:.1f}k per fee SOL")
                print(f"   Max allowed: ${max_mc_per_fee/1000:.1f}k per fee SOL")
                self.pending_buys.discard(address)
                self.signal_registry.pop(address, None)
                return

            # 2. Liquidity Check (<$12.5k reject, unless pump.fun or moonshot)
            liq = token_data.get('liquidity_usd', 0)
            dex_id = token_data.get('dex_id', 'unknown')
            
            # Identify Platform
            is_pump = dex_id == 'pumpfun' or address.endswith('pump')
            is_bonk = dex_id == 'moonshot' or address.endswith('bonk') 
            
            # For Pump.fun/Moonshot, use FDV as backup since liquidity might report 0 initially
            min_liq = 12500
            if is_pump or is_bonk:
                fdv = token_data.get('fdv', 0)
                platform_name = "Moonshot" if is_bonk else "Pump.fun"
                if liq < 500 and fdv > 5000:
                    print(f"⚠️ {platform_name} token with low liq (${liq}), accepting based on FDV (${fdv:.0f})")
                    liq = fdv # Bypass check
            
            if liq <= min_liq and not is_boost:
                print(f"⛔ SKIP {ticker}: Liquidity too thin (${liq:.0f} < ${min_liq})")
                self.pending_buys.discard(address)
                self.signal_registry.pop(address, None)
                return

            # 3. MC CAP FILTER - Skip if entry is too late (>300k MC)
            fdv = token_data.get('fdv', 0)
            MC_CAP = 300000  # $300k max entry
            if fdv > MC_CAP and not is_boost:
                print(f"⛔ SKIP {ticker}: MC too high (${fdv/1000:.0f}k > ${MC_CAP/1000:.0f}k) - Late entry!")
                self.pending_buys.discard(address)
                self.signal_registry.pop(address, None)
                return

            # 3. Age/Momentum Check ("Pairs more than a few hours old...")
            created_at_ts = token_data.get('created_at', 0)
            if created_at_ts > 0:
                import time as time_module
                age_hours = (time_module.time()*1000 - created_at_ts) / (1000 * 3600)
                if age_hours > 4:
                    if vol_24h < 50000:
                        print(f"⛔ SKIP {ticker}: Too old ({age_hours:.1f}h) & low vol")
                        self.pending_buys.discard(address)
                        self.signal_registry.pop(address, None)
                        return

        print(f"💰 [{'REAL' if self.real_mode else 'PAPER'}] Attempting to BUY {ticker} with {buy_amount:.4f} SOL ({(buy_amount/current_balance)*100:.1f}% of balance)")
        
        raw_price = token_data['price']
        fetched_symbol = token_data['symbol']
        
        # Update Ticker
        if "UNKNOWN" in ticker:
            ticker = f"${fetched_symbol}"
        
        entry_price = raw_price
        tokens_received = 0  # Will be populated in real mode
        
        if self.real_mode:
            # REAL EXECUTION - Try Jupiter first, fallback to PumpPortal
            tx_sig = await self.engine.execute_swap(
                input_mint="So11111111111111111111111111111111111111112", 
                output_mint=address, 
                amount_token=buy_amount, 
                is_buy=True
            )
            
            # Fallback to PumpPortal if Jupiter fails (pump.fun OR bonk.fun tokens)
            # Use dex_id and address suffix to identify platform
            dex_id = token_data.get('dex_id', 'unknown')
            is_pump = dex_id == 'pumpfun' or address.endswith('pump')
            is_bonk = dex_id == 'moonshot' or address.endswith('bonk')
            
            if not tx_sig and (is_pump or is_bonk):
                ecosystem = "Moonshot" if is_bonk else "Pump.fun"
                print(f"⚠️ Jupiter failed. Trying PumpPortal for {ecosystem} token...")
                tx_sig = await self.engine.pumpportal_swap(address, buy_amount, is_buy=True)
            
            if not tx_sig:
                print(f"❌ Real Buy Failed for {ticker}")
                self.pending_buys.discard(address)
                return
                
            print(f"✅ REAL BUY EXECUTED. Sig: {tx_sig}")
            
            # Wait for confirmation
            await asyncio.sleep(3)
            
            # CALCULATE ACTUAL ENTRY PRICE from tokens received
            # Entry Price = (SOL Spent * SOL Price in USD) / Tokens Received
            # Retry token balance fetch multiple times since RPC can lag
            tokens_received = 0
            for balance_attempt in range(5):
                tokens_received = await self.engine.get_token_balance(address)
                if tokens_received > 0:
                    break
                print(f"⏳ Waiting for token balance... attempt {balance_attempt+1}/5")
                await asyncio.sleep(2)
            
            sol_price_usd = 150.0  # Will be refined below
            
            # Get current SOL price from token data
            if token_data.get('price_native') and token_data.get('price') and token_data['price_native'] > 0:
                sol_price_usd = token_data['price'] / token_data['price_native']
            
            if tokens_received > 0:
                # Actual USD spent
                usd_spent = buy_amount * sol_price_usd
                # Actual price per token
                entry_price = usd_spent / tokens_received
                print(f"📊 ACTUAL Entry: ${entry_price:.8f} ({tokens_received:.2f} tokens for {buy_amount} SOL)")
            else:
                # Fallback: Fetch FRESH price AFTER swap execution instead of using stale pre-buy price
                # This is critical - using pre-buy price causes wrong PnL calculations
                print(f"⚠️ Could not get token balance, fetching FRESH post-execution price...")
                # Try Jupiter Real-Time Price first (Lower Latency)
                fresh_price = await self.get_realtime_price(address)
                if fresh_price > 0:
                    entry_price = fresh_price
                    print(f"📊 Using fresh real-time price (Jupiter): ${entry_price:.8f}")
                else:
                    fresh_price_data = await self.get_token_data(address)
                    if fresh_price_data and fresh_price_data.get('price', 0) > 0:
                        entry_price = fresh_price_data['price']
                        print(f"📊 Using fresh post-buy price (DexScreener): ${entry_price:.8f}")
                    else:
                        # Last resort: use raw_price but this is risky for PnL
                        entry_price = raw_price
                        print(f"❌ WARNING: Using stale pre-buy price: ${entry_price:.8f} - PnL may be inaccurate!")
        else:
            # PAPER EXECUTION
            # Simulate Slippage
            entry_price = raw_price * (1 + SIMULATED_SLIPPAGE)
            # Deduct Balance
            self.balance -= (buy_amount + PRIORITY_FEE)
            print(f"✅ [PAPER] BOUGHT {ticker} at ${entry_price:.6f} (incl. slip). Paid {PRIORITY_FEE} SOL fee.")
        
        # For boosts, update existing trade with additional amount. For new, create trade.
        if is_boost:
            # Update existing trade's meta to mark as boosted and add boost amount
            existing = self.db.get_trade(address)
            meta = json.loads(existing.get('meta', '{}')) if existing.get('meta') else {}
            meta['boosted'] = True
            meta['boost_source'] = source
            meta['boost_amount'] = buy_amount
            meta['total_amount'] = existing['amount_sol'] + buy_amount
            self.db.update_trade(address, existing['status'], existing['pnl_percent'], meta)
            print(f"📈 Boost recorded: {ticker} +{buy_amount:.4f} SOL from {source}")
        else:
            # === FIX: Fetch FRESH token data AFTER swap executes ===
            # The pre-buy token_data is stale - prices move fast during execution
            print(f"📡 Fetching fresh post-execution data for accurate entry MC...")
            fresh_token_data = await self.get_token_data(address)
            
            if fresh_token_data:
                fresh_fdv = fresh_token_data.get('fdv', 0)
                fresh_price = fresh_token_data.get('price', 0)
                print(f"📊 Fresh data: FDV=${fresh_fdv/1000:.1f}k, Price=${fresh_price:.10f}")
            else:
                # Fallback to cached if fresh fetch fails
                fresh_fdv = token_data.get('fdv', 0)
                fresh_price = token_data.get('price', 0)
                print(f"⚠️ Fresh fetch failed, using pre-buy cache")
            
            # Calculate entry MC from actual execution
            # Method: Use fresh FDV directly (it reflects current MC at time of fill)
            # Then scale by ratio of our actual entry price vs fresh price
            if entry_price > 0 and fresh_price > 0 and fresh_fdv > 0:
                # Our actual fill price vs current price tells us where we actually got in
                entry_mc = fresh_fdv * (entry_price / fresh_price)
                print(f"📊 Entry MC calculated: ${entry_mc/1000:.1f}k (from fresh post-fill data)")
            else:
                # Last resort fallback
                entry_mc = fresh_fdv if fresh_fdv > 0 else token_data.get('fdv', 0)
                print(f"⚠️ Using direct FDV as entry MC: ${entry_mc/1000:.1f}k")
                
            # Store entry_tokens for manual sell detection
            meta = {'entry_mc': entry_mc, 'max_mc_hit': entry_mc, 'events': [], 'entry_tokens': tokens_received}
            
            # Calculate token age
            token_age_mins = None
            created_at_ts = token_data.get('created_at', 0)
            if created_at_ts and created_at_ts > 0:
                token_age_mins = (datetime.now().timestamp() * 1000 - created_at_ts) / 60000
            
            # Enhanced data collection - capture everything at entry
            self.db.add_trade(
                ticker=ticker,
                address=address,
                entry_price=entry_price,
                amount_sol=buy_amount,
                source=source,
                source_channel=None,  # Will be enhanced when we parse channel names
                entry_mc=entry_mc,
                entry_volume=token_data.get('volume_h24'),
                entry_liquidity=token_data.get('liquidity_usd'),
                dex_id=token_data.get('dex_id'),
                token_age_mins=token_age_mins
            )
            
            # Update trade with initial meta (for backward compat)
            self.db.update_trade(address, 'OPEN', 0.0, meta)
        
        # Clean up pending and signal registry
        self.pending_buys.discard(address)
        if not is_boost:
            self.signal_registry.pop(address, None)
        
        # Send to main webhook
        boost_label = " [BOOST]" if is_boost else ""
        await self.send_webhook(
            f"✅ BOUGHT {ticker}{boost_label}",
            f"{'🔴 REAL' if self.real_mode else '📄 PAPER'} | Amount: {buy_amount:.4f} SOL | Source: {source or 'unknown'}",
            65280,
            address=address,
            entry_price=entry_price,
            fee=PRIORITY_FEE
        )
        
        # Send to Caller Webhook (Dynamic Routing: Zeus, Gems, Rhysky)
        if not is_boost:
            try:
                # Identify Target Webhook
                target_webhook = None
                s_lower = (source or 'unknown').lower()
                
                if 'zeus' in s_lower:
                    target_webhook = ZEUS_CALLS_WEBHOOK
                elif 'gem' in s_lower:
                    target_webhook = GEMS_CALLS_WEBHOOK
                elif 'rhysky' in s_lower:
                    target_webhook = RHYSKY_CALLS_WEBHOOK
                elif '4am' in s_lower:
                    target_webhook = FOURAM_CALLS_WEBHOOK
                elif 'axe' in s_lower:
                    target_webhook = AXE_CALLS_WEBHOOK
                elif 'legion' in s_lower:
                    target_webhook = LEGION_CALLS_WEBHOOK
                elif 'spider' in s_lower:
                    target_webhook = SPIDER_CALLS_WEBHOOK
                elif 'pfultimate' in s_lower:
                    target_webhook = PFULTIMATE_CALLS_WEBHOOK
                elif 'discord' in s_lower:
                    target_webhook = ZEUS_CALLS_WEBHOOK
                elif 'telegram' in s_lower:
                    # Fallback: Default generic Telegram to Gems (original behavior)
                    target_webhook = GEMS_CALLS_WEBHOOK
                
                # Only proceed if we have a valid target webhook
                if target_webhook:
                    entry_mc = token_data.get('fdv', 0)
                    mc_display = f"${entry_mc/1000:.1f}K" if entry_mc < 1_000_000 else f"${entry_mc/1_000_000:.2f}M"
                    source_emoji = "🎮" if source == "discord" else "✈️" if source == "telegram" else "📡"
                    
                    embed = {
                        "title": f"{source_emoji} NEW CALL: {ticker}",
                        "description": f"Signal from **{source.upper() if source else 'UNKNOWN'}**",
                        "color": 0x5865F2 if source == "discord" else 0x0088cc,
                        "fields": [
                            {"name": "Entry MC", "value": mc_display, "inline": True},
                            {"name": "Buy Amount", "value": f"{buy_amount:.4f} SOL", "inline": True},
                            {"name": "Address", "value": f"`{address[:8]}...{address[-6:]}`", "inline": False}
                        ],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        resp = await session.post(target_webhook, json={"embeds": [embed]})
                        if resp.status in [200, 204]:
                            print(f"✅ Caller webhook sent to {source} ({resp.status})")
                        else:
                            print(f"⚠️ Caller webhook failed: {resp.status} - {await resp.text()}")
                else:
                    if source and source != 'unknown':
                        print(f"⚠️ No webhook configured for source '{source}'. Skipping caller notification.")

            except Exception as e:
                import traceback
                print(f"⚠️ Caller webhook error: {e}")
                traceback.print_exc()
        
        # Broadcast call to Telegram channel (with random delay, runs in background)
        # SKIP Zeus/Discord sources - still execute but don't relay publicly
        if not is_boost:
            s_lower = (source or '').lower()
            if 'zeus' in s_lower or 'discord' in s_lower:
                print(f"🔇 Skipping broadcast for {ticker} (source: {source})")
            else:
                entry_mc = fresh_token_data.get('fdv', 0) if fresh_token_data else token_data.get('fdv', 0)
                asyncio.create_task(broadcast_call(ticker, address, entry_mc))
        
        # Start monitoring (only for new trades, boosts share existing monitor)
        if not is_boost:
            self.start_monitor(address, ticker, entry_price)

    async def resume_monitoring(self):
        """Resumes monitoring for all OPEN trades in the database."""
        open_trades = self.db.get_active_trades()
        count = 0
        for trade in open_trades:
            address = trade['address']
            ticker = trade['ticker']
            entry_price = trade['entry_price']
            
            if address not in self.active_monitors:
                self.start_monitor(address, ticker, entry_price)
                count += 1
        
        if count > 0:
            print(f"🔄 Resumed monitoring for {count} active trades.")

    def start_monitor(self, address: str, ticker: str, entry_price: float):
        if address not in self.active_monitors:
            self.active_monitors.add(address)
            asyncio.create_task(self.monitor_position(address, ticker, entry_price))

    async def sell(self, address: str, current_price: float, percentage: float, reason: str):
        """
        Executes a sell (Real or Paper).
        """
        # === SELL COOLDOWN: Prevent rapid successive sells (wastes fees) ===
        SELL_COOLDOWN_SECONDS = 20
        now = datetime.now()
        last_sell_time = self.sell_cooldowns.get(address)
        if last_sell_time:
            elapsed = (now - last_sell_time).total_seconds()
            if elapsed < SELL_COOLDOWN_SECONDS:
                print(f"⏳ Sell cooldown active for {address[:8]}... ({SELL_COOLDOWN_SECONDS - elapsed:.0f}s remaining)")
                return
        
        # === SELL LOCK: Prevent duplicate sells for the same address ===
        if address in self.pending_sells:
            print(f"⏳ Sell already in progress for {address[:8]}... Skipping duplicate.")
            return
        self.pending_sells.add(address)
        self.sell_cooldowns[address] = now  # Record sell timestamp
        
        try:
            trade = self.db.get_trade(address)
            if not trade:
                return

            # Check if this specific trade is paper (for manually injected positions)
            meta = json.loads(trade['meta']) if trade['meta'] else {}
            is_paper_trade = meta.get('is_paper', False)
            
            # Use paper mode if: global paper mode OR this specific trade is marked as paper
            use_paper_mode = not self.real_mode or is_paper_trade

            print(f"📉 [{'PAPER' if use_paper_mode else 'REAL'}] SELLING {percentage*100}% of ({address}) - {reason}")
            
            pnl_percent = 0
            tx_sig = "PAPER_TX"
            
            if not use_paper_mode:
                # REAL EXECUTION
                # 1. Fetch Actual Token Balance (with retry for RPC lag)
                token_balance = 0
                for attempt in range(3):
                    token_balance = await self.engine.get_token_balance(address)
                    if token_balance > 0:
                        break
                    print(f"⏳ Waiting for token balance... attempt {attempt+1}/3")
                    await asyncio.sleep(3)
                
                if token_balance <= 0:
                    print("❌ Real Sell Failed: No Token Balance found after 3 attempts.")
                    return
                
                print(f"✅ Found {token_balance:.2f} tokens to sell")

                # AGGRESSIVE RETRY LOOP - keep trying until sell succeeds with ESCALATING PRIORITY
                max_sell_attempts = 5
                base_priority_fee = 0.0003  # Start lower
                sell_success = False
                
                # Track SOL balance BEFORE sell for accurate PnL
                sol_before = await self.engine.get_sol_balance()
                sol_received = 0
                
                for sell_attempt in range(max_sell_attempts):
                    # Escalate priority fee each attempt (gentle increase)
                    priority_fee = base_priority_fee + (sell_attempt * 0.0001)
                    print(f"🔄 Sell attempt {sell_attempt + 1}/{max_sell_attempts} (priority: {priority_fee:.4f} SOL)...")
                    
                    # Calculate Amount to Sell
                    current_balance = await self.engine.get_token_balance(address)
                    if current_balance <= 0:
                        print("✅ Tokens already sold!")
                        sell_success = True
                        break
                        
                    amount_to_sell = current_balance * percentage
                    
                    # Try PumpPortal first for pump/bonk tokens (more reliable)
                    tx_sig = None
                    if address.endswith("pump") or address.endswith("bonk"):
                        tx_sig = await self.engine.pumpportal_swap(address, amount_to_sell, is_buy=False, priority_fee=priority_fee)
                    
                    # Fallback to Jupiter
                    if not tx_sig:
                        tx_sig = await self.engine.execute_swap(
                            input_mint=address,
                            output_mint="So11111111111111111111111111111111111111112",
                            amount_token=amount_to_sell,
                            is_buy=False
                        )
                    
                    if tx_sig:
                        print(f"✅ Sell TX sent: {tx_sig}")
                        
                        # IMPORTANT: Once we have a TX signature, DO NOT retry.
                        # The TX is on-chain and will either confirm or fail.
                        # Retrying causes duplicate sells!
                        
                        # Wait longer for confirmation (RPC can be slow)
                        await asyncio.sleep(8)  # Increased from 3s to prevent duplicate triggers
                        new_balance = await self.engine.get_token_balance(address)
                        
                        if percentage >= 1.0 and new_balance <= 0:
                            print(f"✅ SELL VERIFIED! Balance: 0")
                            sell_success = True
                            break
                        elif percentage < 1.0 and new_balance < current_balance:
                            print(f"✅ PARTIAL SELL VERIFIED! {current_balance:.2f} -> {new_balance:.2f}")
                            sell_success = True
                            break
                        else:
                            # TX was sent but balance not updated yet - DON'T RETRY, TX is pending
                            print(f"⚠️ TX sent but balance unchanged ({new_balance:.2f}). Assuming TX is pending...")
                            sell_success = True  # Assume success since TX was sent
                            break  # EXIT - do not resubmit!
                    else:
                        print(f"❌ No TX signature, retrying...")
                    
                    await asyncio.sleep(3)
                
                if not sell_success:
                    print(f"🚨 CRITICAL: Could not sell after {max_sell_attempts} attempts!")
                    await self.send_webhook(
                        f"🚨 SELL FAILED: {trade['ticker']}",
                        f"Could not sell after {max_sell_attempts} attempts. Manual intervention needed!",
                        16711680  # Red
                    )
                    return
                
                # Calculate REAL PnL from actual SOL received
                sol_after = await self.engine.get_sol_balance()
                sol_received = sol_after - sol_before + priority_fee  # Account for fee we paid
                
                # Calculate PnL based on ACTUAL SOL movement
                entry_sol = trade['amount_sol'] * percentage  # SOL we spent on this portion
                if entry_sol > 0:
                    pnl_percent = (sol_received / entry_sol) - 1
                    print(f"💰 REAL PnL: Spent {entry_sol:.4f} SOL -> Got {sol_received:.4f} SOL = {pnl_percent*100:+.1f}%")
                else:
                    pnl_percent = (current_price - trade['entry_price']) / trade['entry_price']


            else:
                # PAPER MODE
                # Simulate Retry Logic
                max_retries = 3
                executed = False
                for attempt in range(max_retries):
                    executed = True
                    break
                
                if not executed:
                    print("❌ PAPER SELL FAILED.")
                    return

                # Simulate Slippage
                exit_price = current_price * (1 - SIMULATED_SLIPPAGE)
                amount_to_sell_sol = trade['amount_sol'] * percentage
                
                pnl_percent = (exit_price - trade['entry_price']) / trade['entry_price']
                revenue_sol = amount_to_sell_sol * (1 + pnl_percent)
                net_return_sol = revenue_sol - PRIORITY_FEE
                self.balance += net_return_sol
                
                # Log sell for paper mode
                self.db.log_sell(
                    address=address,
                    sell_price=exit_price,
                    sell_mc=0,  # Paper mode doesn't track MC
                    amount_sol_received=net_return_sol,
                    percentage_sold=percentage,
                    reason=reason
                )

            # LOG SELL TRANSACTION (for real mode - use ACTUAL on-chain data from Helius)
            if not use_paper_mode and tx_sig:
                # Parse the actual swap transaction to get REAL SOL amounts
                swap_data = await self.parse_swap_transaction(tx_sig)
                
                if swap_data['success'] and swap_data['sol_out'] > 0:
                    # Use ACTUAL on-chain SOL received
                    sol_received_actual = swap_data['sol_out']
                    entry_amount = trade['amount_sol'] * percentage
                    pnl_percent = (sol_received_actual - entry_amount) / entry_amount if entry_amount > 0 else 0
                    print(f"✅ REAL P&L from Helius: Spent {entry_amount:.4f} SOL -> Got {sol_received_actual:.4f} SOL = {pnl_percent*100:+.1f}%")
                else:
                    # Fallback to estimate if Helius fails
                    entry_amount = trade['amount_sol']
                    sold_portion = entry_amount * percentage
                    sol_received_actual = sold_portion * (1 + pnl_percent)
                    print(f"⚠️ Using estimated P&L (Helius unavailable): {pnl_percent*100:+.1f}%")
                
                # Get current MC for logging
                try:
                    token_data = await self.get_token_data(address)
                    sell_mc = token_data.get('fdv', 0) if token_data else 0
                except:
                    sell_mc = 0
                
                self.db.log_sell(
                    address=address,
                    sell_price=current_price,
                    sell_mc=sell_mc,
                    amount_sol_received=sol_received_actual,
                    percentage_sold=percentage,
                    reason=reason
                )
                print(f"📝 Sell logged: {sol_received_actual:.4f} SOL received")

            meta = json.loads(trade['meta']) if trade['meta'] else {}
            
            if percentage < 1.0:
                # Partial Sell
                new_status = 'PARTIAL'
                meta['partial_exit_price'] = current_price
                meta['partial_exit_time'] = str(datetime.now())
                color = 16776960 # Yellow
            else:
                # Full Sell
                new_status = 'CLOSED'
                meta['full_exit_price'] = current_price
                meta['full_exit_time'] = str(datetime.now())
                if address in self.active_monitors:
                    self.active_monitors.remove(address)
                
                # Auto-close empty token account to reclaim rent
                if self.real_mode:
                    await asyncio.sleep(3)  # Wait for sell to settle
                    await self.engine.close_token_account(address)
                
                color = 65280 if pnl_percent > 0 else 16711680 # Green or Red
            
            self.db.update_trade(address, new_status, pnl_percent, meta)
            print(f"ℹ️ Trade Updated: {new_status} | PnL: {pnl_percent*100:.2f}%")
            
            await self.send_webhook(
                f"📉 SOLD {trade['ticker']} ({new_status})",
                f"{'🔴 REAL' if self.real_mode else '📄 PAPER'} | {reason}",
                color,
                address=address,
                entry_price=trade['entry_price'],
                current_price=current_price
            )
            
            # Send to Zeus Results webhook on full close (for caller success tracking)
            # Send to Result Webhook (Dynamic Routing)
            if new_status == 'CLOSED':
                try:
                    source = trade.get('source', 'unknown')
                    s_lower = (source or 'unknown').lower()
                    target_webhook = None  # Initialize before if/elif chain
                    if 'zeus' in s_lower:
                        target_webhook = ZEUS_RESULTS_WEBHOOK
                    elif 'gem' in s_lower:
                        target_webhook = GEMS_RESULTS_WEBHOOK
                    elif 'rhysky' in s_lower:
                        target_webhook = RHYSKY_RESULTS_WEBHOOK
                    elif '4am' in s_lower:
                        target_webhook = FOURAM_RESULTS_WEBHOOK
                    elif 'axe' in s_lower:
                        target_webhook = AXE_RESULTS_WEBHOOK
                    elif 'legion' in s_lower:
                        target_webhook = LEGION_RESULTS_WEBHOOK
                    elif 'spider' in s_lower:
                        target_webhook = SPIDER_RESULTS_WEBHOOK
                    elif 'pfultimate' in s_lower:
                        target_webhook = PFULTIMATE_RESULTS_WEBHOOK
                    elif 'discord' in s_lower:
                        target_webhook = ZEUS_RESULTS_WEBHOOK
                    elif 'telegram' in s_lower:
                         # Fallback for generic 'telegram'
                        target_webhook = GEMS_RESULTS_WEBHOOK
                    
                    if target_webhook:
                        entry_mc = meta.get('entry_mc', 0)
                        max_mc = meta.get('max_mc_hit', 0)
                        
                        # Calculate exit MC from current price ratio
                        if entry_mc > 0 and trade['entry_price'] > 0:
                            exit_mc = entry_mc * (current_price / trade['entry_price'])
                        else:
                            exit_mc = 0
                        
                        # Format MC values
                        def fmt_mc(val):
                            if val >= 1_000_000: return f"${val/1_000_000:.2f}M"
                            elif val >= 1_000: return f"${val/1_000:.1f}K"
                            else: return f"${val:.0f}"
                        
                        # Update caller stats
                        if source in self.caller_stats:
                            if pnl_percent > 0:
                                self.caller_stats[source]['wins'] += 1
                            else:
                                self.caller_stats[source]['losses'] += 1
                            self.caller_stats[source]['total_pnl'] += pnl_percent * 100
                        
                        # Calculate success rate
                        stats = self.caller_stats.get(source, {'wins': 0, 'losses': 0, 'total_pnl': 0})
                        total = stats['wins'] + stats['losses']
                        win_rate = (stats['wins'] / total * 100) if total > 0 else 0
                        
                        # Color based on result
                        result_emoji = "✅" if pnl_percent > 0 else "❌"
                        result_color = 0x4ade80 if pnl_percent > 0 else 0xf87171
                        source_emoji = "🎮" if source == "discord" else "✈️" if source == "telegram" else "📡"
                        
                        embed = {
                            "title": f"{result_emoji} RESULT: {trade['ticker']}",
                            "description": f"{source_emoji} **{source.upper() if source else 'UNKNOWN'}** | PnL: **{pnl_percent*100:+.1f}%**",
                            "color": result_color,
                            "fields": [
                                {"name": "Entry MC", "value": fmt_mc(entry_mc), "inline": True},
                                {"name": "Max MC Hit", "value": fmt_mc(max_mc), "inline": True},
                                {"name": "Exit MC", "value": fmt_mc(exit_mc), "inline": True},
                                {"name": f"{source.title()} Win Rate", "value": f"{win_rate:.0f}% ({stats['wins']}W/{stats['losses']}L)", "inline": True},
                                {"name": f"{source.title()} Total PnL", "value": f"{stats['total_pnl']:+.1f}%", "inline": True}
                            ],
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        async with aiohttp.ClientSession() as session:
                            await session.post(target_webhook, json={"embeds": [embed]})
                            
                except Exception as e:
                    print(f"⚠️ Results webhook error: {e}")
        
        finally:
            # Always release the sell lock
            self.pending_sells.discard(address)

