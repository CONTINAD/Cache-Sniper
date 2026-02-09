"""
Telegram Channel Listener for QuickTrade
Uses Telethon to listen to configured Telegram channels for buy signals.
"""
import asyncio
from telethon import TelegramClient, events
from src.parser import SignalParser
from src.config import (
    TELEGRAM_API_ID, 
    TELEGRAM_API_HASH, 
    TELEGRAM_CHANNELS
)

class TelegramListener:
    def __init__(self, trader):
        self.trader = trader
        self.parser = SignalParser()
        self.bought_tokens = set()
        
        # Initialize Telethon client
        self.client = TelegramClient(
            'quicktrade_session', 
            TELEGRAM_API_ID, 
            TELEGRAM_API_HASH
        )
        
    async def start(self):
        """Start listening to Telegram channels."""
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            print("⚠️ Telegram credentials not configured. Skipping Telegram listener.")
            return
            
        if not TELEGRAM_CHANNELS:
            print("⚠️ No Telegram channels configured. Skipping Telegram listener.")
            return
            
        await self.client.start()
        print(f"📱 Telegram Listener started!")
        print(f"   Monitoring {len(TELEGRAM_CHANNELS)} channels: {TELEGRAM_CHANNELS}")
        
        # Register message handler (Listen to ALL messages for debug, filtering in handler)
        @self.client.on(events.NewMessage())
        async def handler(event):
            await self.handle_message(event)
        
        # Keep running
        await self.client.run_until_disconnected()
    
    async def handle_message(self, event):
        """Process incoming Telegram message for signals."""
        message_text = event.message.text
        if not message_text:
            return
            
        # Identify Source Channel
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '') or getattr(chat, 'username', '') or 'Unknown'
        chat_username = getattr(chat, 'username', '')
        
        # DEBUG: Log every message to see if we're connected
        print(f"📩 [TG DEBUG] [{chat_title} (@{chat_username})] {message_text[:50]}...")
        
        normalized_source = "telegram"
        title_lower = chat_title.lower()
        username_lower = f"@{chat_username}".lower() if chat_username else ""
        
        # Check if this is a monitored channel
        is_monitored = False
        for channel in TELEGRAM_CHANNELS:
            chan_clean = channel.lower().strip()
            if chan_clean in title_lower or (username_lower and chan_clean == username_lower):
                is_monitored = True
                break
        
        if not is_monitored:
            # Check keywords just in case
            if not any(k in title_lower for k in ["pfultimate", "pumpfun ultimate", "zeus", "gem", "rhysky", "4am", "axe", "spider", "legion"]):
                return  # Skip unmonitored chats
        
        if "pfultimate" in title_lower or "pf_ultimate" in title_lower or "pumpfun ultimate" in title_lower or "pfultimate" in username_lower:
            normalized_source = "pfultimate"
        elif "zeus" in title_lower:
            normalized_source = "zeus"
        elif "gem" in title_lower:
            normalized_source = "gems"
        elif "rhysky" in title_lower:
            normalized_source = "rhysky"
        elif "4am" in title_lower or "signalsolana" in title_lower:
            normalized_source = "4am"
        elif "axe" in title_lower:
            normalized_source = "axe"
        elif "spider" in title_lower:
            normalized_source = "spider"
        elif "legion" in title_lower:
            normalized_source = "legion"
            
        print(f"🔔 [TG MATCH] [{chat_title}] Processing signal...")
            
        # Parse for buy signal
        signal = self.parser.parse_message(message_text)
        
        if signal:
            address = signal['address']
            ticker = signal['ticker']
            
            # Skip if already bought
            if address in self.bought_tokens:
                print(f"[TG] Skipping {ticker} - already bought")
                return
            
            print(f"🚨 [TELEGRAM] BUY SIGNAL: {ticker}")
            print(f"   Source: {normalized_source.upper()}")
            print(f"   Address: {address}")
            
            self.bought_tokens.add(address)
            
            # Execute trade (all sources use same size now)
            await self.trader.buy(address, ticker, source=normalized_source)


# Standalone runner for testing
if __name__ == "__main__":
    from src.trader import PaperTrader
    
    async def main():
        trader = PaperTrader()
        listener = TelegramListener(trader)
        await listener.start()
    
    asyncio.run(main())
