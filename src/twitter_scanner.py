"""
Twitter/X Narrative Scanner for QuickTrade

Monitors key Twitter accounts for tweets that could spawn memecoins.
Uses twikit library for authentication (no API key required).
"""

import asyncio
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
import aiohttp

try:
    from twikit import Client
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False
    print("⚠️ twikit not installed. Run: pip install twikit")

from src.config import (
    TWITTER_USERNAME,
    TWITTER_EMAIL, 
    TWITTER_PASSWORD,
    WEBHOOK_URL
)


# === Accounts to Monitor (configurable) ===
MONITORED_ACCOUNTS = [
    "elonmusk",        # Elon Musk - DOGE daddy, major catalyst
    "sama",            # Sam Altman - AI/GPT narratives
    "VitalikButerin",  # Vitalik - Ethereum/crypto narratives
    "caboreal",        # Brian Armstrong - Coinbase CEO
    "jack",            # Jack Dorsey - Bitcoin maxi, tech
    "MarioNawfal",     # Crypto news aggregator
    "MustStopMurad",   # Memecoin trader
    "blaboratories",   # Popular CT account
]

# === Narrative Detection Keywords ===
MEMECOIN_KEYWORDS = [
    # Direct memecoin mentions
    "memecoin", "meme coin", "shitcoin", "token", "crypto", "degen",
    
    # Famous meme coins
    "doge", "dogecoin", "shiba", "pepe", "bonk", "wif", 
    
    # AI/tech that spawn meme coins
    "gpt", "chatgpt", "ai agent", "artificial intelligence", "openai",
    
    # Viral/meme potential
    "moon", "pump", "rug", "diamond hands", "wagmi", "gm", 
    
    # Pop culture
    "south park", "simpsons", "snl", "saturday night live",
]

# Numbers/versions that often become tickers
TICKER_NUMBERS = ["67", "69", "420", "1000", "100", "42", "13"]

# Keywords that suggest NOT memecoin material
IGNORE_KEYWORDS = [
    "sponsored", "advertisement", "buy now", "sale", "discount",
    "subscribe", "newsletter", "dm me", "click here"
]


class NarrativeDetector:
    """Analyzes tweets for memecoin-worthy narratives."""
    
    def __init__(self):
        self.keyword_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in MEMECOIN_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.number_pattern = re.compile(
            r'\b(' + '|'.join(TICKER_NUMBERS) + r')\b'
        )
        self.ticker_pattern = re.compile(r'\$([A-Za-z][A-Za-z0-9]{1,10})\b')
        self.ignore_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in IGNORE_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
    
    def analyze(self, tweet_text: str, username: str) -> Dict:
        """
        Analyze a tweet for memecoin potential.
        Returns dict with score and extracted info.
        """
        result = {
            'is_catalyst': False,
            'score': 0,
            'reasons': [],
            'potential_tickers': [],
            'keywords_found': [],
            'numbers_found': [],
        }
        
        # Skip if contains ignore keywords
        if self.ignore_pattern.search(tweet_text):
            return result
        
        text_lower = tweet_text.lower()
        
        # Check for direct memecoin keywords
        keywords = self.keyword_pattern.findall(tweet_text)
        if keywords:
            result['score'] += len(keywords) * 10
            result['keywords_found'] = list(set(k.lower() for k in keywords))
            result['reasons'].append(f"Contains keywords: {', '.join(result['keywords_found'])}")
        
        # Check for version/numbers that become tickers
        numbers = self.number_pattern.findall(tweet_text)
        if numbers:
            result['score'] += len(numbers) * 15
            result['numbers_found'] = numbers
            result['potential_tickers'].extend(numbers)
            result['reasons'].append(f"Contains numbers: {', '.join(numbers)}")
        
        # Check for explicit ticker mentions
        tickers = self.ticker_pattern.findall(tweet_text)
        if tickers:
            result['score'] += len(tickers) * 20
            result['potential_tickers'].extend(tickers)
            result['reasons'].append(f"Contains tickers: ${', $'.join(tickers)}")
        
        # Boost score for high-profile accounts
        if username.lower() in ['elonmusk', 'sama']:
            result['score'] += 25
            result['reasons'].append(f"High-profile account: @{username}")
        
        # Check for announcement patterns
        announcement_patterns = [
            r"announcing", r"launching", r"introducing", r"just released",
            r"big news", r"breaking", r"just in", r"happening now"
        ]
        for pattern in announcement_patterns:
            if re.search(pattern, text_lower):
                result['score'] += 15
                result['reasons'].append(f"Announcement pattern: {pattern}")
                break
        
        # Check for media content (images/videos often go viral)
        if any(x in tweet_text for x in ['pic.twitter', 'video', 't.co/']):
            result['score'] += 5
            result['reasons'].append("Contains media")
        
        # Determine if this is a catalyst (score threshold)
        result['is_catalyst'] = result['score'] >= 25
        
        return result


class TwitterScanner:
    """
    Monitors Twitter/X for memecoin narrative catalysts.
    Uses twikit for authentication and polling.
    """
    
    def __init__(self, webhook_url: str = None):
        self.client = None
        self.detector = NarrativeDetector()
        self.webhook_url = webhook_url or WEBHOOK_URL
        self.seen_tweets: Set[str] = set()  # Track seen tweet IDs
        self.last_check: Dict[str, datetime] = {}  # Last check time per account
        self.is_authenticated = False
        self.poll_interval = 45  # seconds between checks
        
    async def authenticate(self) -> bool:
        """Authenticate with Twitter using credentials from config."""
        if not TWIKIT_AVAILABLE:
            print("❌ twikit library not available")
            return False
            
        if not all([TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD]):
            print("❌ Twitter credentials not configured in .env")
            print("   Add: TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD")
            return False
        
        try:
            self.client = Client('en-US')
            
            # Try to load existing cookies first
            try:
                self.client.load_cookies('twitter_cookies.json')
                print("✅ Loaded Twitter session from cookies")
                self.is_authenticated = True
                return True
            except:
                pass
            
            # Login fresh
            print("🔐 Authenticating with Twitter...")
            await self.client.login(
                auth_info_1=TWITTER_USERNAME,
                auth_info_2=TWITTER_EMAIL,
                password=TWITTER_PASSWORD
            )
            
            # Save cookies for next time
            self.client.save_cookies('twitter_cookies.json')
            print("✅ Twitter authentication successful!")
            self.is_authenticated = True
            return True
            
        except Exception as e:
            print(f"❌ Twitter authentication failed: {e}")
            return False
    
    async def get_user_tweets(self, username: str, count: int = 5) -> List[Dict]:
        """Fetch recent tweets from a user."""
        if not self.is_authenticated:
            return []
        
        try:
            user = await self.client.get_user_by_screen_name(username)
            if not user:
                return []
            
            tweets = await user.get_tweets('Tweets', count=count)
            
            results = []
            for tweet in tweets:
                results.append({
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'username': username,
                    'url': f"https://x.com/{username}/status/{tweet.id}",
                    'likes': getattr(tweet, 'favorite_count', 0),
                    'retweets': getattr(tweet, 'retweet_count', 0),
                })
            
            return results
            
        except Exception as e:
            print(f"⚠️ Error fetching tweets from @{username}: {e}")
            return []
    
    async def check_for_catalysts(self) -> List[Dict]:
        """Check all monitored accounts for new catalyst tweets."""
        catalysts = []
        
        for username in MONITORED_ACCOUNTS:
            tweets = await self.get_user_tweets(username, count=3)
            
            for tweet in tweets:
                # Skip if already seen
                if tweet['id'] in self.seen_tweets:
                    continue
                
                self.seen_tweets.add(tweet['id'])
                
                # Analyze for narrative potential
                analysis = self.detector.analyze(tweet['text'], username)
                
                if analysis['is_catalyst']:
                    catalyst = {
                        **tweet,
                        'analysis': analysis
                    }
                    catalysts.append(catalyst)
                    print(f"🚨 NARRATIVE DETECTED from @{username}!")
                    print(f"   Score: {analysis['score']}")
                    print(f"   Reasons: {', '.join(analysis['reasons'])}")
                    print(f"   Tweet: {tweet['text'][:100]}...")
            
            # Small delay between accounts to avoid rate limits
            await asyncio.sleep(1)
        
        return catalysts
    
    async def send_alert(self, catalyst: Dict):
        """Send Discord webhook alert for a detected catalyst."""
        if not self.webhook_url:
            return
        
        analysis = catalyst['analysis']
        
        # Format potential tickers
        tickers_str = ""
        if analysis['potential_tickers']:
            tickers_str = f"\n🎯 **Potential Tickers:** ${', $'.join(analysis['potential_tickers'])}"
        
        embed = {
            "title": f"🚨 NARRATIVE ALERT: @{catalyst['username']}",
            "description": f"{catalyst['text'][:500]}",
            "color": 0xFF6B35,  # Orange for alerts
            "fields": [
                {"name": "Score", "value": str(analysis['score']), "inline": True},
                {"name": "Reasons", "value": "\n".join(analysis['reasons'][:3]), "inline": False},
            ],
            "footer": {"text": f"QuickTrade Narrative Scanner"},
            "timestamp": datetime.now().isoformat(),
            "url": catalyst['url']
        }
        
        if analysis['potential_tickers']:
            embed["fields"].append({
                "name": "🎯 Potential Tickers",
                "value": ", ".join([f"${t}" for t in analysis['potential_tickers']]),
                "inline": True
            })
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(self.webhook_url, json={"embeds": [embed]})
                print(f"✅ Sent narrative alert for @{catalyst['username']}")
        except Exception as e:
            print(f"⚠️ Failed to send alert: {e}")
    
    async def search_pumpfun(self, query: str) -> List[Dict]:
        """Search pump.fun for tokens matching a narrative."""
        try:
            # Use DexScreener to search for tokens
            url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        # Filter for Solana pump.fun tokens
                        solana_pumps = [
                            p for p in pairs 
                            if p.get('chainId') == 'solana' 
                            and 'pump' in p.get('pairAddress', '').lower()
                        ]
                        
                        return solana_pumps[:5]  # Top 5 matches
        except Exception as e:
            print(f"⚠️ Pump.fun search error: {e}")
        
        return []
    
    async def run(self):
        """Main scanning loop."""
        print("🐦 Twitter Narrative Scanner Starting...")
        
        if not await self.authenticate():
            print("❌ Failed to authenticate. Scanner disabled.")
            return
        
        print(f"👀 Monitoring {len(MONITORED_ACCOUNTS)} accounts:")
        for acc in MONITORED_ACCOUNTS:
            print(f"   • @{acc}")
        
        while True:
            try:
                catalysts = await self.check_for_catalysts()
                
                for catalyst in catalysts:
                    await self.send_alert(catalyst)
                    
                    # Optionally search for related tokens
                    for ticker in catalyst['analysis']['potential_tickers'][:2]:
                        tokens = await self.search_pumpfun(ticker)
                        if tokens:
                            print(f"🔍 Found {len(tokens)} tokens for ${ticker}")
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"⚠️ Scanner error: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def test_auth(self):
        """Test authentication."""
        success = await self.authenticate()
        if success:
            print("✅ Twitter auth successful!")
        else:
            print("❌ Twitter auth failed")
        return success
    
    async def test_fetch(self, username: str = "elonmusk"):
        """Test fetching tweets from an account."""
        await self.authenticate()
        
        username = username.lstrip('@')
        print(f"📥 Fetching tweets from @{username}...")
        
        tweets = await self.get_user_tweets(username, count=5)
        
        for i, tweet in enumerate(tweets, 1):
            print(f"\n--- Tweet {i} ---")
            print(f"Text: {tweet['text'][:200]}...")
            print(f"URL: {tweet['url']}")
            
            # Analyze
            analysis = self.detector.analyze(tweet['text'], username)
            if analysis['is_catalyst']:
                print(f"🚨 CATALYST! Score: {analysis['score']}")
                print(f"   Reasons: {', '.join(analysis['reasons'])}")
        
        return tweets


# Standalone test
if __name__ == "__main__":
    async def main():
        scanner = TwitterScanner()
        await scanner.test_auth()
        await scanner.test_fetch("elonmusk")
    
    asyncio.run(main())
