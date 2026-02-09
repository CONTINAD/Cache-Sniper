import discord
import asyncio
import aiohttp
import os
import sys
import atexit
from datetime import datetime, timedelta
from src.config import DISCORD_TOKEN, CHANNEL_ID
from src.parser import SignalParser

from src.trader import PaperTrader

# ============ SINGLETON LOCK ============
# Prevents multiple bot instances from running simultaneously (causes DB locks)
PID_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.bot.pid')

def check_single_instance():
    """Ensure only one bot instance is running."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if that process is still running
            try:
                os.kill(old_pid, 0)  # Signal 0 just checks if process exists
                print(f"❌ FATAL: Another bot instance is already running (PID {old_pid})!")
                print(f"   Kill it first with: kill {old_pid}")
                print(f"   Or delete the lock file: rm {PID_FILE}")
                sys.exit(1)
            except OSError:
                # Process not running, stale PID file - clean it up
                print(f"🧹 Cleaning up stale PID file (old PID {old_pid} not running)")
                os.remove(PID_FILE)
        except (ValueError, FileNotFoundError):
            # Invalid or missing PID file, clean up
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    
    # Write our PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    print(f"🔒 Bot singleton lock acquired (PID {os.getpid()})")

def cleanup_pid_file():
    """Remove PID file on exit."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            print("🔓 Bot singleton lock released")
    except:
        pass

# Register cleanup on normal exit
atexit.register(cleanup_pid_file)

# Check immediately when module loads
check_single_instance()
# AxiomAutomation removed - not in use
from src.strategy_lab import StrategyLab

# Missed signal recovery settings

# Missed signal recovery settings
LATE_ENTRY_WINDOW_MINS = 5  # How long after signal to still consider valid
MAX_PRICE_DRIFT_PERCENT = 0.15  # Max 15% price change to still enter

class QuickTradeBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.parser = SignalParser()
        self.trader = PaperTrader()
        self.strategy_lab = StrategyLab(self.trader.db)
        # AxiomAutomation removed - not in use
        self.bought_tokens = set()
        # Track recent signals for late entry: {address: {'time': datetime, 'price': float, 'ticker': str}}
        self.recent_signals = {}
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex/tokens/"
        self._last_summary_date = None  # Track last sent date to prevent duplicates

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Listening on Channel ID: {CHANNEL_ID}')
        # Resume monitoring for any active trades in database (incl. manual entries)
        await self.trader.resume_monitoring()
        # Start late entry checker
        asyncio.create_task(self.check_missed_signals())
        # Start heartbeat
        asyncio.create_task(self.heartbeat())
        # Start Daily Summary Task
        asyncio.create_task(self.daily_summary_task())
        # Start Manual Buy Monitor
        asyncio.create_task(self.check_manual_buys())
        # AxiomAutomation disabled - not in use
        # Start Twitter Narrative Scanner (if enabled)
        asyncio.create_task(self.start_twitter_scanner())
    
    async def start_twitter_scanner(self):
        """Start the Twitter narrative scanner if enabled."""
        from src.config import TWITTER_SCANNER_ENABLED
        
        if not TWITTER_SCANNER_ENABLED:
            print("🐦 Twitter Scanner disabled (set TWITTER_SCANNER_ENABLED=true to enable)")
            return
        
        try:
            from src.twitter_scanner import TwitterScanner
            scanner = TwitterScanner()
            await scanner.run()
        except Exception as e:
            print(f"⚠️ Twitter Scanner error: {e}")
    
    async def daily_summary_task(self):
        """Check every minute if it's 12:00 PM EST and send summary."""
        from src.telegram_broadcaster import get_broadcaster
        print("🌞 Daily Summary Task started")
        
        while True:
            # Check every minute
            await asyncio.sleep(60)
            
            now = datetime.now()
            # Assuming server timezone matches user expectation (EST based on metadata)
            # If UTC, we'd need to adjust. User metadata says local time is -05:00.
            # So checking local time 12:00 is correct for 12 PM EST.
            
            if now.hour == 12 and now.minute == 0:
                # Check if already sent today
                today = now.date()
                if self._last_summary_date == today:
                    continue  # Already sent today, skip
                    
                print("🌞 It's 12:00 PM! Generating Daily Summary...")
                
                try:
                    # Fetch stats
                    stats_1d = self.trader.db.calculate_stats(1)
                    stats_7d = self.trader.db.calculate_stats(7)
                    stats_30d = self.trader.db.calculate_stats(30)
                    
                    # Broadcast
                    broadcaster = await get_broadcaster()
                    await broadcaster.broadcast_daily_summary(stats_1d, stats_7d, stats_30d)
                    
                    # Mark as sent today
                    self._last_summary_date = today
                    print(f"✅ Daily Summary sent for {today}")
                    
                except Exception as e:
                    print(f"❌ Error sending daily summary: {e}")
                except Exception as e:
                    print(f"❌ Error sending daily summary: {e}")

    async def check_manual_buys(self):
        """Poll database for manual buy requests from Dashboard."""
        print("👀 Manual Buy Monitor started")
        while True:
            await asyncio.sleep(2) # Check frequently
            try:
                pending = self.trader.db.get_pending_buys()
                for req in pending:
                    print(f"📥 Processing Manual Buy: {req['token_address']}")
                    
                    # Execute Buy
                    # We pass "MANUAL" as ticker, buy() will fetch real data
                    # The original instruction's code snippet was a bit garbled,
                    # so I'm interpreting it as wanting to add StrategyLab logic
                    # and then execute the buy.
                    
                    address = req['token_address']
                    amount = req['amount_sol']
                    buy_id = req['id']
                    source = "manual_axiom" # Explicitly set source for manual buys
                    
                    # --- STRATEGY LAB INTELLIGENCE ---
                    # For 'manual' buys, we might skip this or use a 'manual' source score.
                    # For now, let's treat manual buys as overrides (always execute unless explicit kill)
                    
                    # Apply smart sizing if it's an automated source (checked inside AxiomAutomation usually, 
                    # but if we process queued items here that came from automation, we can re-check)
                    # Actually manual buys come from dashboard, so they are user intent. 
                    # We will apply StrategyLab to the automation loop in axiom_automation.py instead.
                    
                    # For manual buys, we assume user intent overrides strategy lab for execution,
                    # but we can still log or use strategy lab for sizing if desired.
                    # For now, we'll just execute the buy as requested by the user.
                    
                    if amount > 0:
                        print(f"🤖 Processing Buy: {address[:8]}... | Amnt: {amount} | Src: {source}")
                        # The original `ticker="MANUAL"` was removed in the snippet,
                        # but `trader.buy` expects a ticker. Re-adding it.
                        await self.trader.buy(address, ticker="MANUAL", amount_sol=amount, source=source)
                        
                        # Update status (completed)
                        self.trader.db.mark_buy_processed(buy_id, "PROCESSED", tx_signature="simulated_tx")
                    else:
                        print(f"⚠️ Manual Buy request for {address} has amount_sol <= 0. Marking as failed.")
                        self.trader.db.mark_buy_processed(buy_id, "FAILED", error_message="Amount requested was 0 or less.")
            except Exception as e:
                print(f"⚠️ Manual Buy Error: {e}")
    
    async def heartbeat(self):
        """Send periodic heartbeat to Discord to confirm bot is alive."""
        from src.config import WEBHOOK_URL
        import aiohttp
        
        heartbeat_interval = 300  # 5 minutes
        
        while True:
            await asyncio.sleep(heartbeat_interval)
            try:
                # Get quick stats
                active_trades = len([t for t in self.trader.db.get_active_trades() if t['status'] not in ['CLOSED']])
                
                embed = {
                    "title": "💓 QuickTrade Heartbeat",
                    "description": f"Bot is alive and monitoring.",
                    "color": 0x00FF00,
                    "fields": [
                        {"name": "Active Positions", "value": str(active_trades), "inline": True},
                        {"name": "Uptime Check", "value": "✅ OK", "inline": True}
                    ]
                }
                
                async with aiohttp.ClientSession() as session:
                    await session.post(WEBHOOK_URL, json={"embeds": [embed]})
                    
                print("💓 Heartbeat sent")
            except Exception as e:
                print(f"⚠️ Heartbeat error: {e}")
        
    async def on_message(self, message):
        if message.author == self.user:
            return

        # Verbose logging for debug
        print(f"📩 [DISCORD RAW] [{message.channel.id}] {message.author}: {message.content[:100]}...")

        if message.channel.id != CHANNEL_ID:
            # print(f"Ignored message from channel {message.channel.id} (Expected {CHANNEL_ID})")
            return

        signal = self.parser.parse_message(message.content)
        
        if signal:
            await self.handle_buy_signal(signal, message)
            return

        if self.parser.is_trim_signal(message.content):
            print(f"TRIM Signal detected in {message.jump_url}")
            pass

    async def get_current_price(self, address: str) -> float:
        """Fetch current price from DexScreener."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.dexscreener_api}{address}") as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            sol_pairs = [p for p in pairs if p['chainId'] == 'solana']
                            if sol_pairs:
                                best = max(sol_pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                                return float(best['priceUsd'])
            except:
                pass
        return 0

    async def handle_buy_signal(self, signal, message):
        address = signal['address']
        ticker = signal['ticker']
        
        # Check if already bought
        if address in self.bought_tokens:
            print(f"Skipping {ticker} ({address}) - Already recognized.")
            return

        print(f"🚨 BUY SIGNAL DETECTED 🚨")
        print(f"Ticker: {ticker}")
        print(f"Address: {address}")
        print(f"Source: {message.jump_url}")
        
        # Get current price for late entry tracking
        current_price = await self.get_current_price(address)
        
        # Store signal for late entry recovery
        self.recent_signals[address] = {
            'time': datetime.now(),
            'price': current_price,
            'ticker': ticker
        }
        
        # Add to bought set
        self.bought_tokens.add(address)
        
        # Execute trade
        await self.trader.buy(address, ticker, source="discord")

    async def check_missed_signals(self):
        """Background task to check for late entry opportunities on missed signals."""
        print("🔍 Late entry checker started")
        
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            now = datetime.now()
            expired = []
            
            for address, data in list(self.recent_signals.items()):
                signal_time = data['time']
                original_price = data['price']
                ticker = data['ticker']
                
                # Skip if already bought
                if address in self.bought_tokens:
                    expired.append(address)
                    continue
                
                # Check if within time window
                age = now - signal_time
                if age > timedelta(minutes=LATE_ENTRY_WINDOW_MINS):
                    expired.append(address)
                    continue
                
                # Check current price
                current_price = await self.get_current_price(address)
                if current_price <= 0 or original_price <= 0:
                    continue
                
                # Calculate price drift
                drift = abs(current_price - original_price) / original_price
                
                if drift <= MAX_PRICE_DRIFT_PERCENT:
                    print(f"🔄 LATE ENTRY: {ticker} still valid!")
                    print(f"   Original: ${original_price:.8f} | Current: ${current_price:.8f} | Drift: {drift*100:.1f}%")
                    
                    # Execute late entry
                    self.bought_tokens.add(address)
                    await self.trader.buy(address, ticker, source="discord")
                    
                    expired.append(address)
                else:
                    print(f"⏭️ {ticker} drifted too much ({drift*100:.1f}%), skipping late entry")
                    expired.append(address)
            
            # Cleanup expired signals
            for addr in expired:
                self.recent_signals.pop(addr, None)

# Create global instance
bot = QuickTradeBot()

if __name__ == "__main__":
    print("🔥 REAL TRADING MODE ENGAGED 🔥")
    bot.run(DISCORD_TOKEN)

