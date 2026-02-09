"""
Telegram Call Broadcaster for QuickTrade
Sends beautifully formatted calls to your Telegram channel via a BOT.
"""
import asyncio
import random
import aiohttp
from src.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BROADCAST_CHANNEL,
    AXIOM_REFERRAL_CODE,
    GARDEN_CALLS_DISCORD_WEBHOOK
)


class TelegramBroadcaster:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.channel = TELEGRAM_BROADCAST_CHANNEL
        self.referral = AXIOM_REFERRAL_CODE
        self.discord_webhook = GARDEN_CALLS_DISCORD_WEBHOOK
        
    async def broadcast_call(
        self, 
        ticker: str, 
        address: str, 
        entry_mc: float = 0,
        extra_delay: bool = True
    ):
        """
        Broadcast a call to the Telegram channel via Bot API.
        """
        if not self.bot_token:
            print("⚠️ No Telegram bot token configured")
            return False
            
        if not self.channel:
            print("⚠️ No broadcast channel configured")
            return False
            
        # Random delay to look natural
        if extra_delay:
            delay = random.uniform(8, 12)
            print(f"📡 Broadcasting call in {delay:.1f}s...")
            await asyncio.sleep(delay)
        
        try:
            # Format market cap
            if entry_mc >= 1_000_000:
                mc_display = f"${entry_mc/1_000_000:.2f}M"
            elif entry_mc >= 1_000:
                mc_display = f"${entry_mc/1_000:.0f}K"
            else:
                mc_display = f"${entry_mc:.0f}" if entry_mc > 0 else "Fresh"
            
            # Links
            axiom_link = f"https://axiom.trade/t/{address}/@{self.referral}?chain=sol"
            ares_link = f"https://ares.pro/invite/{self.referral}"
            
            # Ensure ticker has $ prefix
            display_ticker = ticker if ticker.startswith('$') else f"${ticker}"
            
            # Build premium call message
            # Clean, minimal, focused on the ticker and the buy button
            message = f"""🌿 <b>GARDEN CALLS</b> 🌿

🚀 <b>{display_ticker}</b>

💎 <b>MC:</b> {mc_display}

<code>{address}</code>"""

            # Inline Keyboard (Buttons)
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 Trade on Axiom", "url": axiom_link}
                    ],
                    [
                        {"text": "🌱 Join Ares", "url": ares_link}
                    ]
                ]
            }

            # Send via Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.channel,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": keyboard
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        print(f"✅ TG Call broadcasted for {ticker}")
                    else:
                        error = await resp.text()
                        print(f"❌ Telegram API error: {error}")
            
            # Also send to Discord
            await self._send_discord_call(display_ticker, address, mc_display, axiom_link, ares_link)
            return True
                        
        except Exception as e:
            print(f"❌ Broadcast failed: {e}")
            return False

    async def _send_discord_call(self, ticker: str, address: str, mc_display: str, axiom_link: str, ares_link: str):
        """Send call to Discord webhook with embed."""
        if not self.discord_webhook:
            return
            
        try:
            embed = {
                "title": f"🌿 GARDEN CALLS 🌿",
                "description": f"🚀 **{ticker}**\n\n💎 **MC:** {mc_display}",
                "color": 0x2ECC71,  # Green
                "fields": [
                    {"name": "📋 Contract", "value": f"`{address}`", "inline": False},
                    {"name": "🔗 Trade", "value": f"[Trade on Axiom]({axiom_link})", "inline": True},
                    {"name": "🌱 Join", "value": f"[Join Ares]({ares_link})", "inline": True}
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(self.discord_webhook, json={"embeds": [embed]})
                print(f"✅ Discord Call broadcasted for {ticker}")
        except Exception as e:
            print(f"⚠️ Discord broadcast failed: {e}")

    async def broadcast_profit(
        self, 
        ticker: str, 
        address: str, 
        multiple: float, 
        time_held_mins: float,
        current_mc: float = 0
    ):
        """
        Broadcast a profit milestone (e.g. 2x, 3x, 10x).
        """
        if not self.bot_token or not self.channel:
            return False
            
        try:
            # Format MC
            if current_mc >= 1_000_000:
                mc_display = f"${current_mc/1_000_000:.2f}M"
            elif current_mc >= 1_000:
                mc_display = f"${current_mc/1_000:.0f}K"
            else:
                mc_display = f"${current_mc:.0f}"
            
            # Format Time
            if time_held_mins < 60:
                time_str = f"{time_held_mins:.0f} mins"
            else:
                hours = time_held_mins / 60
                time_str = f"{hours:.1f} hours"

            # Links
            axiom_link = f"https://axiom.trade/t/{address}/@{self.referral}?chain=sol"
            ares_link = f"https://ares.pro/invite/{self.referral}"
            
            # Calculate Profit %
            profit_pct = (multiple - 1) * 100
            
            # Select Header & Emoji based on multiple
            header = "🏆 <b>GARDEN SUCCESS</b> 🏆"
            if multiple >= 10:
                header = "👑 <b>GARDEN LEGEND</b> 👑"
            
            emoji = "🚀"
            if multiple >= 5: emoji = "🔥"
            if multiple >= 10: emoji = "🎆"
            if multiple >= 50: emoji = "🦄"
            
            multiplier_str = f"{multiple:.0f}x" if multiple.is_integer() else f"{multiple:.1f}x"
            
            # Ensure ticker has $ prefix
            display_ticker = ticker if ticker.startswith('$') else f"${ticker}"
            
            message = f"""{header}

{emoji} <b>{display_ticker} SMASHED {multiplier_str}!</b>

💰 <b>Profit:</b> +{profit_pct:.0f}%
⏱️ <b>Held:</b> {time_str}
💎 <b>MC:</b> {mc_display}

<code>{address}</code>"""

            # Inline Keyboard
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🚀 Trade on Axiom", "url": axiom_link}
                    ],
                    [
                        {"text": "🌱 Join Ares", "url": ares_link}
                    ]
                ]
            }

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.channel,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": keyboard
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        print(f"✅ TG Profit broadcasted: {ticker} {multiplier_str}")
                    else:
                        print(f"❌ Telegram API error: {await resp.text()}")
            
            # Also send to Discord
            await self._send_discord_profit(display_ticker, multiplier_str, profit_pct, time_str, mc_display, address, axiom_link, ares_link, header)
            return True
                        
        except Exception as e:
            print(f"❌ Broadcast failed: {e}")
            return False
    
    async def _send_discord_profit(self, ticker: str, multiplier_str: str, profit_pct: float, 
                                   time_str: str, mc_display: str, address: str, 
                                   axiom_link: str, ares_link: str, header: str):
        """Send profit alert to Discord webhook."""
        if not self.discord_webhook:
            return
            
        try:
            # Extract multiple value from string
            mult_value = float(multiplier_str.replace('x', ''))
            
            # Special mentions for milestones
            mention = ""
            extra_content = ""
            if mult_value >= 20:
                mention = "@everyone"
                extra_content = "\n\n🚨 **We're just getting started...** 🚨"
            elif mult_value >= 5:
                mention = "@here"
                extra_content = "\n\n💀 **Yall mf's gonna be sorry once this is for Insiders only** 💀"
            
            # Color based on multiplier
            if mult_value >= 20:
                color = 0xFF0000  # Red for 20x+
            elif mult_value >= 10:
                color = 0xFFD700  # Gold
            elif mult_value >= 5:
                color = 0xFF6600  # Orange
            else:
                color = 0x2ECC71  # Green
            
            embed = {
                "title": header.replace("<b>", "**").replace("</b>", "**"),
                "description": f"🚀 **{ticker} SMASHED {multiplier_str}!**{extra_content}",
                "color": color,
                "fields": [
                    {"name": "💰 Profit", "value": f"+{profit_pct:.0f}%", "inline": True},
                    {"name": "⏱️ Held", "value": time_str, "inline": True},
                    {"name": "💎 MC", "value": mc_display, "inline": True},
                    {"name": "📋 Contract", "value": f"`{address}`", "inline": False},
                    {"name": "🔗 Trade", "value": f"[Trade on Axiom]({axiom_link})", "inline": True},
                    {"name": "🌱 Join", "value": f"[Join Ares]({ares_link})", "inline": True}
                ]
            }
            
            payload = {"embeds": [embed]}
            if mention:
                payload["content"] = mention
            
            async with aiohttp.ClientSession() as session:
                await session.post(self.discord_webhook, json=payload)
                print(f"✅ Discord Profit broadcasted: {ticker} {multiplier_str}")
        except Exception as e:
            print(f"⚠️ Discord profit broadcast failed: {e}")

    async def broadcast_daily_summary(self, daily: dict, weekly: dict, monthly: dict):
        """
        Broadcast a daily summary of performance.
        """
        if not self.bot_token or not self.channel:
            return False
            
        try:
            message = f"""🌞 <b>DAILY MARKET UPDATE</b> 🌞

📅 <b>Today:</b> +{daily['x_gain']:.1f}x (+{daily['pct_gain']:.0f}%)
🔥 <b>This Week:</b> +{weekly['x_gain']:.0f}x (+{weekly['pct_gain']:.0f}%)
🗓️ <b>This Month:</b> +{monthly['x_gain']:.0f}x (+{monthly['pct_gain']:.0f}%)

<i>"Success is the sum of small efforts repeated day in and day out."</i>

🌿 <b>Garden Calls</b> 🌿"""

            # Optional: Add buttons if standard links are desired
            # For now, just a clean text summary as requested "make it look nice"

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.channel,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        print(f"✅ TG Daily Summary broadcasted")
                    else:
                        print(f"❌ Telegram API error: {await resp.text()}")
            
            # Also send to Discord
            await self._send_discord_summary(daily, weekly, monthly)
            return True
                        
        except Exception as e:
            print(f"❌ Broadcast summary failed: {e}")
            return False
    
    async def _send_discord_summary(self, daily: dict, weekly: dict, monthly: dict):
        """Send daily summary to Discord."""
        if not self.discord_webhook:
            return
            
        try:
            embed = {
                "title": "🌞 DAILY MARKET UPDATE 🌞",
                "color": 0xFFD700,
                "fields": [
                    {"name": "📅 Today", "value": f"+{daily['x_gain']:.1f}x (+{daily['pct_gain']:.0f}%)", "inline": True},
                    {"name": "🔥 This Week", "value": f"+{weekly['x_gain']:.0f}x (+{weekly['pct_gain']:.0f}%)", "inline": True},
                    {"name": "🗓️ This Month", "value": f"+{monthly['x_gain']:.0f}x (+{monthly['pct_gain']:.0f}%)", "inline": True}
                ],
                "footer": {"text": "\"Success is the sum of small efforts repeated day in and day out.\" | 🌿 Garden Calls"}
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(self.discord_webhook, json={"embeds": [embed]})
                print(f"✅ Discord Daily Summary broadcasted")
        except Exception as e:
            print(f"⚠️ Discord summary broadcast failed: {e}")

# Global instance
_broadcaster = None

async def get_broadcaster() -> TelegramBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = TelegramBroadcaster()
    return _broadcaster


async def broadcast_call(ticker: str, address: str, entry_mc: float = 0):
    """Convenience function to broadcast a call."""
    broadcaster = await get_broadcaster()
    await broadcaster.broadcast_call(ticker, address, entry_mc)

async def broadcast_profit(ticker: str, address: str, multiple: float, time_held_mins: float, current_mc: float = 0):
    """Convenience function to broadcast a profit milestone."""
    broadcaster = await get_broadcaster()
    await broadcaster.broadcast_profit(ticker, address, multiple, time_held_mins, current_mc)
