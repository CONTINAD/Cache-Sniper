"""
X (Twitter) Sentiment Analysis Module for Anti-Gravity

Analyzes real-time X sentiment for Pump.fun meme coin launches.
Filters out bot spam and manufactured promotion to identify organic hype.

Key Features:
- Search tweets by contract address or ticker
- Score account quality (age, followers, engagement)
- Detect bot/shill patterns
- Calculate aggregate sentiment pass/fail

Uses twikit library for authentication (no API key required).
"""

import asyncio
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Tuple
from dataclasses import dataclass
import aiohttp

try:
    from twikit import Client
    TWIKIT_AVAILABLE = True
except ImportError:
    TWIKIT_AVAILABLE = False
    print("⚠️ twikit not installed. X Sentiment disabled. Run: pip install twikit")

from src.config import (
    TWITTER_USERNAME,
    TWITTER_EMAIL,
    TWITTER_PASSWORD,
    WEBHOOK_URL
)

# === SENTIMENT CONFIGURATION ===
# These can be overridden via environment variables in config.py

# Minimum unique accounts mentioning token to pass
X_SENTIMENT_MIN_MENTIONS = 5

# Time window to search for recent mentions (minutes)
X_SENTIMENT_TIME_WINDOW_MINS = 15

# Minimum average account quality score (0-1)
X_SENTIMENT_MIN_ACCOUNT_QUALITY = 0.4

# Maximum bot ratio before failing (0-1)
X_SENTIMENT_MAX_BOT_RATIO = 0.30

# Skip sentiment check for tokens above this MC (already validated by market)
X_SENTIMENT_BYPASS_HIGH_MC = 100000

# Cache TTL for sentiment results (seconds)
X_SENTIMENT_CACHE_TTL = 300

# Timeout for sentiment check (seconds)
X_SENTIMENT_TIMEOUT = 8


@dataclass
class SentimentResult:
    """Result of a sentiment analysis check."""
    passed: bool
    reason: str
    unique_mentions: int
    avg_quality: float
    bot_ratio: float
    total_tweets: int
    top_accounts: List[str]
    score: float
    

class XSentimentAnalyzer:
    """
    Analyzes X (Twitter) sentiment for meme coin tokens.
    
    Scoring Philosophy:
    - Focus on QUALITY over QUANTITY of mentions
    - Penalize bot patterns and shill behavior
    - Reward diverse, organic engagement
    """
    
    def __init__(self):
        self.client = None
        self.is_authenticated = False
        self._cache: Dict[str, Tuple[SentimentResult, datetime]] = {}
        self._auth_lock = asyncio.Lock()
        
        # Bot detection patterns
        self.bot_username_pattern = re.compile(r'^[a-zA-Z]+\d{6,}$')  # user8372649
        self.shill_patterns = [
            r'100x', r'1000x', r'easy\s*\d+x', r'guaranteed', r'moon\s*soon',
            r'next\s*(doge|shib|pepe)', r'gem\s*alert', r'ape\s*in\s*now',
            r'dont\s*miss', r'last\s*chance', r'buy\s*now', r'nfa\s*dyor'
        ]
        self.shill_pattern = re.compile('|'.join(self.shill_patterns), re.IGNORECASE)
        
    async def authenticate(self) -> bool:
        """
        Authenticate with X using auth token cookie (preferred) or credentials.
        
        Priority:
        1. TWITTER_AUTH_TOKEN from .env (bypasses Cloudflare)
        2. Existing cookie file
        3. Username/password login (may hit Cloudflare)
        """
        if not TWIKIT_AVAILABLE:
            print("❌ twikit library not available")
            return False
            
        async with self._auth_lock:
            if self.is_authenticated:
                return True
            
            try:
                self.client = Client('en-US')
                
                # Method 1: Try auth token from .env (BEST - bypasses Cloudflare)
                import os
                auth_token = os.getenv('TWITTER_AUTH_TOKEN', '')
                ct0_token = os.getenv('TWITTER_CT0', '')
                
                if auth_token:
                    print("🔐 Using auth_token cookie for X authentication...")
                    # Set cookies directly - twikit uses these internally
                    cookies = {
                        'auth_token': auth_token,
                    }
                    if ct0_token:
                        cookies['ct0'] = ct0_token
                    
                    self.client.set_cookies(cookies)
                    self.is_authenticated = True
                    print("✅ X authenticated via auth_token cookie!")
                    return True
                
                # Method 2: Try to load existing cookies file
                try:
                    self.client.load_cookies('x_sentiment_cookies.json')
                    print("✅ Loaded X session from cookies (sentiment)")
                    self.is_authenticated = True
                    return True
                except:
                    pass
                
                # Method 3: Username/password login (fallback - may hit Cloudflare)
                if not all([TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD]):
                    print("❌ X credentials not configured in .env")
                    print("   Add TWITTER_AUTH_TOKEN (preferred) or TWITTER_USERNAME/EMAIL/PASSWORD")
                    return False
                
                print("🔐 Authenticating with X via username/password...")
                await self.client.login(
                    auth_info_1=TWITTER_USERNAME,
                    auth_info_2=TWITTER_EMAIL,
                    password=TWITTER_PASSWORD
                )
                
                # Save cookies for next time
                self.client.save_cookies('x_sentiment_cookies.json')
                print("✅ X sentiment authentication successful!")
                self.is_authenticated = True
                return True
                
            except Exception as e:
                print(f"❌ X sentiment authentication failed: {e}")
                return False
    
    async def search_token_mentions(self, address: str, ticker: str, limit: int = 50) -> List[Dict]:
        """
        Search X for tweets mentioning the token.
        
        Searches for:
        - Contract address (full and truncated)
        - Ticker with $ prefix
        - Ticker without prefix (if unique enough)
        """
        if not self.is_authenticated:
            if not await self.authenticate():
                return []
        
        tweets = []
        
        try:
            # Build search queries - PRIORITIZE CONTRACT ADDRESS over ticker
            # Tickers like "Associate" are too generic and won't find crypto mentions
            addr_short = address[:8]  # First 8 chars of CA (most people tweet this)
            
            # Ticker clean (but deprioritize - too generic often)
            ticker_clean = ticker.replace('$', '').upper()
            
            queries = [
                addr_short,  # Short CA prefix (most common on crypto twitter)
                address,  # Full contract address
                f"pump.fun {addr_short}",  # Pump.fun link format
            ]
            
            for query in queries:
                try:
                    # Search for tweets
                    results = await self.client.search_tweet(query, 'Latest', count=min(limit, 20))
                    
                    for tweet in results:
                        # Extract tweet data
                        tweet_data = {
                            'id': tweet.id,
                            'text': tweet.text,
                            'created_at': tweet.created_at,
                            'user': {
                                'id': tweet.user.id if tweet.user else None,
                                'username': tweet.user.screen_name if tweet.user else 'unknown',
                                'name': tweet.user.name if tweet.user else 'Unknown',
                                'followers': getattr(tweet.user, 'followers_count', 0) if tweet.user else 0,
                                'following': getattr(tweet.user, 'following_count', 0) if tweet.user else 0,
                                'created_at': getattr(tweet.user, 'created_at', None) if tweet.user else None,
                                'default_profile': getattr(tweet.user, 'default_profile_image', True) if tweet.user else True,
                                'verified': getattr(tweet.user, 'verified', False) if tweet.user else False,
                            },
                            'likes': getattr(tweet, 'favorite_count', 0),
                            'retweets': getattr(tweet, 'retweet_count', 0),
                            'replies': getattr(tweet, 'reply_count', 0),
                        }
                        tweets.append(tweet_data)
                    
                    # Rate limit protection
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"⚠️ Search error for '{query}': {e}")
                    continue
            
            # Deduplicate by tweet ID
            seen_ids = set()
            unique_tweets = []
            for t in tweets:
                if t['id'] not in seen_ids:
                    seen_ids.add(t['id'])
                    unique_tweets.append(t)
            
            return unique_tweets
            
        except Exception as e:
            print(f"⚠️ Token search failed: {e}")
            return []
    
    def score_account_quality(self, user: Dict) -> float:
        """
        Score an X account's quality/authenticity (0-1).
        
        Factors:
        - Account age (30%)
        - Follower count (20%)
        - Following ratio (15%)
        - Profile completeness (20%)
        - Engagement potential (15%)
        """
        score = 0.0
        
        # 1. Account Age (30%)
        created_at = user.get('created_at')
        if created_at:
            try:
                if isinstance(created_at, str):
                    # Parse Twitter date format
                    created_dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                else:
                    created_dt = created_at
                
                age_days = (datetime.now(created_dt.tzinfo) - created_dt).days
                
                if age_days > 365 * 2:  # 2+ years
                    score += 0.30
                elif age_days > 365:  # 1+ year
                    score += 0.25
                elif age_days > 180:  # 6+ months
                    score += 0.20
                elif age_days > 90:  # 3+ months
                    score += 0.10
                elif age_days > 30:  # 1+ month
                    score += 0.05
                # < 30 days = 0 (likely bot/burner)
            except:
                score += 0.10  # Unknown age, give partial credit
        
        # 2. Follower Count (20%) - log scale
        followers = user.get('followers', 0)
        if followers >= 10000:
            score += 0.20
        elif followers >= 1000:
            score += 0.15
        elif followers >= 100:
            score += 0.10
        elif followers >= 10:
            score += 0.05
        
        # 3. Following Ratio (15%)
        following = user.get('following', 0)
        if followers > 0 and following > 0:
            ratio = followers / following
            if ratio > 2:  # More followers than following
                score += 0.15
            elif ratio > 0.5:
                score += 0.10
            elif ratio > 0.1:
                score += 0.05
            # < 0.1 ratio = likely follow-spammer
        
        # 4. Profile Completeness (20%)
        if not user.get('default_profile', True):
            score += 0.10  # Has custom profile picture
        if user.get('name', '') != user.get('username', ''):
            score += 0.05  # Has display name different from username
        if user.get('verified', False):
            score += 0.05  # Verified account
        
        # 5. Username Quality (15%)
        username = user.get('username', '')
        if not self.bot_username_pattern.match(username):
            score += 0.10  # Not bot-like username
        if len(username) < 15:
            score += 0.05  # Reasonable length username
        
        return min(score, 1.0)
    
    def detect_bot_patterns(self, tweet: Dict) -> Tuple[bool, List[str]]:
        """
        Detect if a tweet appears to be from a bot or shill.
        
        Returns: (is_bot, [reasons])
        """
        reasons = []
        text = tweet.get('text', '')
        user = tweet.get('user', {})
        
        # 1. Shill content patterns
        if self.shill_pattern.search(text):
            reasons.append("Shill language detected")
        
        # 2. Excessive $ mentions
        dollar_count = text.count('$')
        if dollar_count > 3:
            reasons.append(f"Excessive $ tags ({dollar_count})")
        
        # 3. Excessive hashtags
        hashtag_count = text.count('#')
        if hashtag_count > 5:
            reasons.append(f"Hashtag spam ({hashtag_count})")
        
        # 4. Bot-like username
        username = user.get('username', '')
        if self.bot_username_pattern.match(username):
            reasons.append("Bot-like username")
        
        # 5. New account with low followers
        followers = user.get('followers', 0)
        if followers < 10:
            reasons.append("Very low followers (<10)")
        
        # 6. Default profile
        if user.get('default_profile', True) and followers < 50:
            reasons.append("Default profile + low followers")
        
        # 7. Extreme following ratio (follow bots)
        following = user.get('following', 0)
        if following > 1000 and followers < 50:
            reasons.append("Follow bot pattern")
        
        is_bot = len(reasons) >= 2  # 2+ red flags = bot
        return is_bot, reasons
    
    def filter_by_time_window(self, tweets: List[Dict], window_mins: int) -> List[Dict]:
        """Filter tweets to only those within the time window."""
        cutoff = datetime.now() - timedelta(minutes=window_mins)
        filtered = []
        
        for tweet in tweets:
            created_at = tweet.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        tweet_dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                        tweet_dt = tweet_dt.replace(tzinfo=None)  # Make naive for comparison
                    else:
                        tweet_dt = created_at
                        if hasattr(tweet_dt, 'tzinfo') and tweet_dt.tzinfo:
                            tweet_dt = tweet_dt.replace(tzinfo=None)
                    
                    if tweet_dt > cutoff:
                        tweet['parsed_time'] = tweet_dt
                        filtered.append(tweet)
                except Exception as e:
                    # Include if we can't parse (give benefit of doubt)
                    filtered.append(tweet)
            else:
                filtered.append(tweet)
        
        return filtered
    
    async def check_sentiment(self, address: str, ticker: str) -> Dict:
        """
        Main entry point: Check X sentiment for a token.
        
        Returns dict with:
        - passed: bool
        - reason: str
        - unique_mentions: int
        - avg_quality: float
        - bot_ratio: float
        - total_tweets: int
        - score: float
        """
        # Check cache first
        cache_key = f"{address}:{ticker}"
        if cache_key in self._cache:
            result, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < timedelta(seconds=X_SENTIMENT_CACHE_TTL):
                print(f"🐦 Using cached sentiment for {ticker}")
                return result.__dict__
        
        # Default fail result
        default_fail = SentimentResult(
            passed=False,
            reason="Sentiment check failed",
            unique_mentions=0,
            avg_quality=0.0,
            bot_ratio=1.0,
            total_tweets=0,
            top_accounts=[],
            score=0.0
        )
        
        try:
            # Authenticate if needed
            if not self.is_authenticated:
                if not await self.authenticate():
                    # Auth failed - graceful degradation, let buy proceed
                    return SentimentResult(
                        passed=True,
                        reason="Auth failed - bypassing check",
                        unique_mentions=0,
                        avg_quality=0.0,
                        bot_ratio=0.0,
                        total_tweets=0,
                        top_accounts=[],
                        score=0.0
                    ).__dict__
            
            # Search for mentions
            print(f"🐦 Searching X for {ticker} mentions...")
            tweets = await asyncio.wait_for(
                self.search_token_mentions(address, ticker),
                timeout=X_SENTIMENT_TIMEOUT
            )
            
            if not tweets:
                result = SentimentResult(
                    passed=False,
                    reason=f"No X mentions found for {ticker}",
                    unique_mentions=0,
                    avg_quality=0.0,
                    bot_ratio=0.0,
                    total_tweets=0,
                    top_accounts=[],
                    score=0.0
                )
                self._cache[cache_key] = (result, datetime.now())
                return result.__dict__
            
            # Filter by time window
            recent_tweets = self.filter_by_time_window(tweets, X_SENTIMENT_TIME_WINDOW_MINS)
            
            # Analyze each tweet
            unique_users = {}  # user_id -> best tweet
            bot_count = 0
            quality_scores = []
            
            for tweet in recent_tweets:
                user = tweet.get('user', {})
                user_id = user.get('id') or user.get('username', 'unknown')
                
                # Skip if we already have this user (keep highest engagement tweet)
                if user_id in unique_users:
                    existing = unique_users[user_id]
                    existing_engagement = existing.get('likes', 0) + existing.get('retweets', 0)
                    new_engagement = tweet.get('likes', 0) + tweet.get('retweets', 0)
                    if new_engagement <= existing_engagement:
                        continue
                
                # Check for bot patterns
                is_bot, bot_reasons = self.detect_bot_patterns(tweet)
                if is_bot:
                    bot_count += 1
                    continue  # Don't count bots toward unique mentions
                
                # Score account quality
                quality = self.score_account_quality(user)
                quality_scores.append(quality)
                
                # Only count if quality meets minimum
                if quality >= X_SENTIMENT_MIN_ACCOUNT_QUALITY * 0.5:  # Slightly lower for counting
                    unique_users[user_id] = {
                        **tweet,
                        'quality_score': quality
                    }
            
            # Calculate metrics
            unique_mentions = len(unique_users)
            total_tweets = len(recent_tweets)
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            bot_ratio = bot_count / total_tweets if total_tweets > 0 else 0
            
            # Get top accounts by quality
            sorted_users = sorted(
                unique_users.values(),
                key=lambda x: x.get('quality_score', 0),
                reverse=True
            )
            top_accounts = [u['user']['username'] for u in sorted_users[:5]]
            
            # Calculate composite score
            score = (
                (unique_mentions / X_SENTIMENT_MIN_MENTIONS) * 0.4 +
                (avg_quality / X_SENTIMENT_MIN_ACCOUNT_QUALITY) * 0.3 +
                ((1 - bot_ratio) / (1 - X_SENTIMENT_MAX_BOT_RATIO)) * 0.3
            )
            score = min(score, 2.0)  # Cap at 2x
            
            # Determine pass/fail
            passed = (
                unique_mentions >= X_SENTIMENT_MIN_MENTIONS and
                avg_quality >= X_SENTIMENT_MIN_ACCOUNT_QUALITY and
                bot_ratio <= X_SENTIMENT_MAX_BOT_RATIO
            )
            
            # Build reason
            if passed:
                reason = f"✅ {unique_mentions} quality mentions, {avg_quality:.0%} avg quality"
            else:
                fails = []
                if unique_mentions < X_SENTIMENT_MIN_MENTIONS:
                    fails.append(f"Only {unique_mentions}/{X_SENTIMENT_MIN_MENTIONS} unique mentions")
                if avg_quality < X_SENTIMENT_MIN_ACCOUNT_QUALITY:
                    fails.append(f"Low quality ({avg_quality:.0%} < {X_SENTIMENT_MIN_ACCOUNT_QUALITY:.0%})")
                if bot_ratio > X_SENTIMENT_MAX_BOT_RATIO:
                    fails.append(f"High bot ratio ({bot_ratio:.0%})")
                reason = " | ".join(fails)
            
            result = SentimentResult(
                passed=passed,
                reason=reason,
                unique_mentions=unique_mentions,
                avg_quality=avg_quality,
                bot_ratio=bot_ratio,
                total_tweets=total_tweets,
                top_accounts=top_accounts,
                score=score
            )
            
            # Cache result
            self._cache[cache_key] = (result, datetime.now())
            
            print(f"🐦 Sentiment: {unique_mentions} mentions, {avg_quality:.0%} quality, {bot_ratio:.0%} bots -> {'PASS' if passed else 'FAIL'}")
            
            return result.__dict__
            
        except asyncio.TimeoutError:
            print(f"⚠️ Sentiment check timed out for {ticker}")
            # Timeout - let buy proceed (graceful degradation)
            return SentimentResult(
                passed=True,
                reason="Timeout - bypassing check",
                unique_mentions=0,
                avg_quality=0.0,
                bot_ratio=0.0,
                total_tweets=0,
                top_accounts=[],
                score=0.0
            ).__dict__
            
        except Exception as e:
            print(f"⚠️ Sentiment check error: {e}")
            # Error - let buy proceed (graceful degradation)
            return SentimentResult(
                passed=True,
                reason=f"Error: {str(e)[:50]} - bypassing",
                unique_mentions=0,
                avg_quality=0.0,
                bot_ratio=0.0,
                total_tweets=0,
                top_accounts=[],
                score=0.0
            ).__dict__


# Global instance for reuse
_sentiment_analyzer: Optional[XSentimentAnalyzer] = None

def get_sentiment_analyzer() -> XSentimentAnalyzer:
    """Get or create the global sentiment analyzer instance."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = XSentimentAnalyzer()
    return _sentiment_analyzer


# Module availability check
X_SENTIMENT_AVAILABLE = TWIKIT_AVAILABLE


# === TEST FUNCTION ===
async def test_sentiment(address: str = None, ticker: str = "$TEST"):
    """Test sentiment analysis on a token."""
    if not address:
        # Use a known active pump.fun token for testing
        print("Usage: test_sentiment('TOKEN_ADDRESS', '$TICKER')")
        return
    
    analyzer = get_sentiment_analyzer()
    result = await analyzer.check_sentiment(address, ticker)
    
    print("\n" + "="*50)
    print(f"SENTIMENT RESULT for {ticker}")
    print("="*50)
    print(f"Passed: {result['passed']}")
    print(f"Reason: {result['reason']}")
    print(f"Unique Mentions: {result['unique_mentions']}")
    print(f"Avg Quality: {result['avg_quality']:.1%}")
    print(f"Bot Ratio: {result['bot_ratio']:.1%}")
    print(f"Total Tweets: {result['total_tweets']}")
    print(f"Top Accounts: {', '.join(result['top_accounts'][:5])}")
    print(f"Score: {result['score']:.2f}")
    print("="*50)
    
    return result


if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            address = sys.argv[1]
            ticker = sys.argv[2] if len(sys.argv) > 2 else "$TOKEN"
            await test_sentiment(address, ticker)
        else:
            print("X Sentiment Analyzer")
            print("Usage: python x_sentiment.py <token_address> [ticker]")
    
    asyncio.run(main())
