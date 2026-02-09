import asyncio
from src.axiom_client import AxiomClient
from src.trader import PaperTrader
# from src.strategy_lab import StrategyLab # Type hinting

class AxiomAutomation:
    def __init__(self, trader: PaperTrader, strategy_lab):
        self.trader = trader
        self.strategy_lab = strategy_lab
        self.axiom = AxiomClient()
        self.running = False
        
    async def start(self):
        """Start all automation tasks."""
        self.running = True
        print("🤖 Axiom Automation Services Starting...")
        
        # 1. Start Fresh Mints Monitor (WebSocket)
        asyncio.create_task(self._monitor_fresh_mints())
        
        # 2. Start Trending Monitor (Polling)
        asyncio.create_task(self._monitor_trending())
        
    async def _monitor_fresh_mints(self):
        """Subscribe to WebSocket for new pairs."""
        print("🔌 Connecting to Fresh Mints Feed...")
        
        retry_delay = 5
        while self.running:
            try:
                # Initialize WS if needed
                if not hasattr(self.axiom.client, 'ws') or not self.axiom.client.ws:
                    from axiomtradeapi.websocket._client import AxiomTradeWebSocketClient
                    if self.axiom.client.auth_manager:
                         self.axiom.client.ws = AxiomTradeWebSocketClient(self.axiom.client.auth_manager)
                
                # Callback handler
                async def on_new_token(data):
                    try:
                        content = data.get('content', {})
                        address = content.get('tokenAddress')
                        ticker = content.get('tokenTicker')
                        name = content.get('tokenName')
                        liquidity = content.get('liquidity', {}).get('usd', 0)
                        
                        if not address: return
                        
                        # 1. Save to DB
                        self.trader.db.add_new_pair(address, ticker, name, liquidity)
                        print(f"🆕 FRESH MINT: {ticker} ({address}) | Liq: ${liquidity:.0f}")
                        
                        # 2. Check Auto-Snipe
                        if self.trader.db.get_setting('auto_snipe_new'):
                            source = "auto_fresh_mint"
                            # INTELLIGENCE CHECK
                            size = self.strategy_lab.evaluate_signal(source, default_size=0.1) # Default smaller for fresh
                            
                            if size > 0:
                                print(f"🔫 AUTO-SNIPING New Pair: {ticker} | Size: {size} SOL")
                                await self.trader.buy(address, ticker, amount_sol=size, source=source)
                            else:
                                print(f"🛑 BLOCKED Fresh Snipe on {ticker} (Strategy Kill Switch Active)")
                            
                    except Exception as e:
                        print(f"⚠️ Error processing new token: {e}")

                # Subscribe
                success = await self.axiom.client.subscribe_new_tokens(on_new_token)
                if success:
                    print("✅ Subscribed to Fresh Mints!")
                    # Keep alive loop (WebSocket client runs in background but we need to keep task alive)
                    while self.running and self.axiom.client.ws and self.axiom.client.ws.ws:
                        await asyncio.sleep(1)
                else:
                    print("❌ Failed to subscribe to Fresh Mints. Retrying...")
            
            except Exception as e:
                print(f"⚠️ Fresh Mints WebSocket Error: {e}")
            
            await asyncio.sleep(retry_delay)

    async def _monitor_trending(self):
        """Poll trending tokens and auto-snipe top 3."""
        print("📈 Trending Monitor Started")
        
        while self.running:
            try:
                if self.trader.db.get_setting('auto_snipe_trending'):
                    trending = await self.axiom.get_trending('1h')
                    if trending:
                        # Top 3 only
                        top_3 = trending[:3]
                        for token in top_3:
                            address = token.get('tokenAddress')
                            ticker = token.get('tokenTicker')
                            
                            # Check if valid candidate
                            if address not in self.trader.active_monitors and \
                               address not in self.trader.bought_tokens and \
                               address not in self.trader.pending_buys:
                                
                                source = "auto_trending"
                                # INTELLIGENCE CHECK
                                size = self.strategy_lab.evaluate_signal(source, default_size=0.3)
                                
                                if size > 0:
                                    print(f"🔫 AUTO-SNIPING Trending Top 3: {ticker} | Size: {size} SOL")
                                    await self.trader.buy(address, ticker, amount_sol=size, source=source)
                                    # Add delay between buys to avoid spamming
                                    await asyncio.sleep(2)
                                else:
                                     print(f"🛑 BLOCKED Trending Snipe on {ticker} (Strategy Kill Switch Active)")
                                
            except Exception as e:
                print(f"⚠️ Trending Monitor Error: {e}")
                
            await asyncio.sleep(10) # Check every 10 seconds
