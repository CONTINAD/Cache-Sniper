import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.axiom_client import AxiomClient
from src.config import AXIOM_EMAIL, AXIOM_PASSWORD, AXIOM_ACCESS_TOKEN, AXIOM_REFRESH_TOKEN

async def main():
    print(f"🧪 Testing Axiom Integration...")
    print(f"📧 Configured Email: '{AXIOM_EMAIL}'")
    print(f"🔑 Password Length: {len(AXIOM_PASSWORD) if AXIOM_PASSWORD else 0}")
    print(f"🎟️ Manual Access Token Set: {'YES' if AXIOM_ACCESS_TOKEN else 'NO'}")
    print(f"🎟️ Manual Refresh Token Set: {'YES' if AXIOM_REFRESH_TOKEN else 'NO'}")
    
    client = AxiomClient()
    
    if not client.client:
        print("❌ Client initialization failed")
        return

    # Check auth and try to login interactively if needed
    if not client.client.is_authenticated():
        print("🔄 Authentication required. Calling authenticate()...")
        try:
            # Access the internal auth_manager to trigger login
            # Note: This will prompt for OTP on stdin
            success = client.client.auth_manager.authenticate()
            if success:
                print("✅ Authentication Successful!")
            else:
                print("❌ Authentication Failed.")
                return
        except Exception as e:
            print(f"❌ Auth Error: {e}")
            return
    else:
        print("✅ Already Authenticated")


    print("\n📈 Fetching 1h Trending Tokens...")
    trending = await client.get_trending('1h')
    
    if trending:
        print(f"✅ Success! Found {len(trending)} tokens.")
        print("Top 5 Results:")
        for t in trending[:5]:
            print(f" - {t}")
    else:
        print("⚠️ No trending tokens returned (or API error).")

    # Rug check currently disabled until library update
    # print("\n🔍 Testing Token Info (Rug Check)...")
    # is_safe = await client.check_rug_status("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    # print(f"Run Check Result for USDC: {'SAFE' if is_safe else 'RISKY'}")

if __name__ == "__main__":
    asyncio.run(main())
