import re
from typing import Optional, Dict

class SignalParser:
    def __init__(self):
        # Regex for Solana address (Base58, 32-44 chars)
        # Pump.fun addresses often end in 'pump' but we should be general enough
        self.address_pattern = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')
        
        # Regex to identify a buy signal
        self.buy_signal_pattern = re.compile(r"Signal Vault Alpha Buy!", re.IGNORECASE)
        
        # Regex for ticker (e.g., $SCRAPPY). avoiding pure numbers to skip "$26.36K"
        # We look for $ followed by letters, or the specific " - $Ticker" pattern
        self.ticker_pattern = re.compile(r'-\s+\$([A-Za-z0-9]+)')

    def parse_message(self, content: str) -> Optional[Dict]:
        """
        Parses a Discord message content to extract signal data.
        Returns None if not a valid buy signal.
        """
        # Strict Mode: Originally required "Signal Vault Alpha Buy!"
        # Relaxed Mode: If we find a CA and it's NOT a trim, we can count it (or manual test)
        # However, to avoid noise, let's keep the header check BUT add a "Raw CA" fallback if it looks like a manual paste (short length?)
        
        is_official_signal = bool(self.buy_signal_pattern.search(content))
        
        # Extract all potential addresses
        addresses = self.address_pattern.findall(content)
        
        valid_ca = None
        
        # 1. Try to find the "Tap to Copy" formatted one first
        if "Contract Address (Tap to Copy)" in content:
            parts = content.split("Contract Address (Tap to Copy)")
            if len(parts) > 1:
                potential = self.address_pattern.search(parts[1])
                if potential:
                    valid_ca = potential.group(0)
        
        # 2. Key Fallback: If no valid_ca yet, look at ANY address found
        if not valid_ca and addresses:
            pump_addresses = [a for a in addresses if a.endswith('pump')]
            if pump_addresses:
                valid_ca = pump_addresses[0]
            else:
                valid_ca = addresses[0]

        if not valid_ca:
            return None

        # Logic: If it has the Header OR if it's a "Trim" we skip (handled by is_trim_signal checks in bot)
        # But wait, bot.py checks is_trim_signal separately.
        # If we want to allow "Manual Paste", we should permit it if valid_ca exists, 
        # even if is_official_signal is False?
        # User said "I just posted a CA". So likely NO header.
        
        # We MUST ensure we don't buy "Trim" messages by accident if we relax the header check.
        # The bot.py calls parse_message logic first. 
        # Let's return a BUY signal if we found a CA and it is NOT a trim.
        
        if self.is_trim_signal(content):
            return None

        # Extract Ticker - Try multiple patterns in order of specificity
        ticker = None
        
        # Pattern 1: Original format "- $TICKER" 
        ticker_match = self.ticker_pattern.search(content)
        if ticker_match:
            ticker = ticker_match.group(1)
        
        # Pattern 2: Any $TICKER format (but not dollar amounts like $123 or $12.5K)
        if not ticker:
            dollar_ticker_pattern = re.compile(r'\$([A-Za-z][A-Za-z0-9]{1,15})\b')
            matches = dollar_ticker_pattern.findall(content)
            for match in matches:
                # Skip if it looks like a dollar amount (ends with K, M, B or is very short)
                if match.upper() not in ('K', 'M', 'B', 'SOL', 'USD', 'USDC', 'USDT'):
                    ticker = match
                    break
        
        # Pattern 3: Extract from pump.fun link format [TICKER](https://pump.fun...)
        if not ticker:
            pump_link_pattern = re.compile(r'\[([A-Za-z][A-Za-z0-9 ]{0,20})\]\(https://pump\.fun')
            pump_match = pump_link_pattern.search(content)
            if pump_match:
                ticker = pump_match.group(1).strip().split()[0]  # Take first word if multiple
        
        # Pattern 4: Look for ticker after emoji flags like 🔔
        if not ticker:
            emoji_ticker_pattern = re.compile(r'[🔔📢⚡️🚀]\s*([A-Za-z][A-Za-z0-9]{1,15})')
            emoji_match = emoji_ticker_pattern.search(content)
            if emoji_match:
                ticker = emoji_match.group(1)
        
        # Pattern 5: Ticker in parentheses - common in pfultimate/MonstaScan format
        # e.g., "cream cheese bagel (bagel)" -> extracts "bagel"
        if not ticker:
            paren_ticker_pattern = re.compile(r'\(([A-Za-z][A-Za-z0-9]{1,15})\)')
            paren_match = paren_ticker_pattern.search(content)
            if paren_match:
                ticker = paren_match.group(1)
        
        # Fallback
        if not ticker:
            ticker = "UNKNOWN"

        return {
            "type": "BUY",
            "address": valid_ca,
            "ticker": f"${ticker}" if not ticker.startswith('$') else ticker,
            "raw_content": content,
            "is_manual": not is_official_signal # Flag for debug
        }

    def is_trim_signal(self, content: str) -> bool:
        return "Signal Vault Trim!" in content
