import logging
import axiomtradeapi
from axiomtradeapi import AxiomTradeClient
from src.config import (
    AXIOM_EMAIL, AXIOM_PASSWORD, 
    AXIOM_ACCESS_TOKEN, AXIOM_REFRESH_TOKEN
)

AXIOM_API_AVAILABLE = True

class AxiomClient:
    """
    Wrapper for Axiom Trade API integration.
    """
    def __init__(self):
        self.client = None
        self.access_token = None
        
        if not AXIOM_API_AVAILABLE:
            print("⚠️ Axiom SDK not installed.")
            return

        # Initialize client
        try:
            # 1. Try Manual Tokens (Most Reliable)
            if AXIOM_ACCESS_TOKEN and AXIOM_REFRESH_TOKEN:
                # Pass tokens directly to constructor to avoid ValueError
                self.client = AxiomTradeClient(
                    auth_token=AXIOM_ACCESS_TOKEN,
                    refresh_token=AXIOM_REFRESH_TOKEN
                )
                print("✅ Axiom Client Initialized with Manual Tokens")
            
            # 2. Try Credentials (if no manual tokens)
            elif AXIOM_EMAIL and AXIOM_PASSWORD:
                self.client = AxiomTradeClient(username=AXIOM_EMAIL, password=AXIOM_PASSWORD)
            
            else:
               print("⚠️ Axiom credentials/tokens missing.")
               return

            # Check Auth status
            if self.client and self.client.is_authenticated():
                 print("✅ Axiom Trade API Authenticated!")
            else:
                 print("⚠️ Axiom Not Authenticated. Run `python3 src/verify_axiom.py` to login or add tokens to .env.")
                 
        except Exception as e:
            print(f"⚠️ Axiom Init Error: {e}")
    
    async def get_trending(self, time_period='1h'):
        """Fetch trending tokens from Axiom."""
        if not self.client or not self.client.is_authenticated():
            return []
        
        try:
            # Get current access token
            tokens = self.client.get_tokens()
            access_token = tokens.get('access_token')
            
            if not access_token:
                print("⚠️ Axiom: No access token available for request")
                return []

            # Inspection showed get_trending_tokens(access_token, time_period='1h')
            # Fix: Pass access_token as first arg
            res = self.client.get_trending_tokens(access_token, time_period)
            # Parse result to return list of Dicts
            return res if res else []
        except Exception as e:
            print(f"⚠️ Axiom Trending Error: {e}")
            return []

    async def check_rug_status(self, token_address: str) -> bool:
        """
        Check if token is potentially a rug using Axiom data.
        Returns True if SAFE, False if RISKY/RUG.
        """
        # TODO: Implement actual rug check when library supports it
        # Currently get_token_info is not available in AxiomTradeClient
        return True
