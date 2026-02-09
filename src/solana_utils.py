import base58
import base64
import json
import aiohttp
import asyncio
from typing import Optional

from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed

from src.config import SOLANA_PRIVATE_KEY, RPC_URL, PRIORITY_FEE

class SolanaEngine:
    def __init__(self):
        self.rpc_client = AsyncClient(RPC_URL)
        try:
            if SOLANA_PRIVATE_KEY:
                self.payer = Keypair.from_base58_string(SOLANA_PRIVATE_KEY)
                self.pubkey = str(self.payer.pubkey())
                print(f"🔑 Loaded Wallet: {self.pubkey}")
            else:
                raise ValueError("No private key")
        except Exception as e:
            print(f"⚠️ No valid Private Key found ({e}). Running in READ-ONLY / DRY RUN mode.")
            self.payer = None
            self.pubkey = "PaperTradingWallet111111111111111111111111"

    async def get_sol_balance(self) -> float:
        """Fetch SOL balance."""
        try:
            resp = await self.rpc_client.get_balance(self.payer.pubkey())
            if resp and resp.value is not None:
                return resp.value / 1e9
            return 0.0
        except Exception as e:
            print(f"⚠️ Error fetching SOL balance: {e}")
            return 0.0

    async def get_token_balance(self, mint_address: str) -> float:
        """Fetch SPL Token balance using Helius API."""
        try:
            import aiohttp
            
            # Use JSON RPC directly - more reliable
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    str(self.payer.pubkey()),
                    {"programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"},  # Token-2022
                    {"encoding": "jsonParsed"}
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(RPC_URL, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        accounts = data.get('result', {}).get('value', [])
                        
                        for acc in accounts:
                            info = acc['account']['data']['parsed']['info']
                            if info['mint'] == mint_address:
                                amount = float(info['tokenAmount']['uiAmount'] or 0)
                                if amount > 0:
                                    print(f"✅ Found {amount:.2f} tokens for {mint_address[:20]}...")
                                    return amount
                        
                        # Also check regular SPL Token program
                        payload['params'][1] = {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}
                        async with session.post(RPC_URL, json=payload, timeout=10) as resp2:
                            if resp2.status == 200:
                                data2 = await resp2.json()
                                accounts2 = data2.get('result', {}).get('value', [])
                                for acc in accounts2:
                                    info = acc['account']['data']['parsed']['info']
                                    if info['mint'] == mint_address:
                                        amount = float(info['tokenAmount']['uiAmount'] or 0)
                                        if amount > 0:
                                            print(f"✅ Found {amount:.2f} tokens for {mint_address[:20]}...")
                                            return amount
            return 0.0
        except Exception as e:
            print(f"⚠️ Error fetching token balance: {e}")
            return 0.0

    async def get_quote(self, input_mint: str, output_mint: str, amount_lamports: int, slippage_bps: int = 200):
        """Fetch quote from Jupiter V6 with failover."""
        urls = [
            "https://quote-api.jup.ag/v6/quote",
            "https://api.jup.ag/swap/v1/quote"  # Fallback
        ]
        
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount_lamports,
            "slippageBps": slippage_bps
        }
        
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, params=params, timeout=1.5) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            print(f"⚠️ Jup Quote Failed ({url}): {response.status}")
                except Exception as e:
                    print(f"⚠️ Jup Quote Error ({url}): {e}")
                    continue
        
        print("❌ All Jupiter Quote endpoints failed.")
        return None

    async def get_swap_tx(self, quote_response):
        """Fetch serialized swap transaction from Jupiter."""
        url = "https://quote-api.jup.ag/v6/swap"
        payload = {
            "quoteResponse": quote_response,
            "userPublicKey": self.pubkey,
            "wrapAndUnwrapSol": True,
            # Priority Fee Config (Very Important)
            "prioritizationFeeLamports": int(PRIORITY_FEE * 1e9) # e.g. 0.0001 SOL
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("swapTransaction")
                else:
                    print(f"❌ Jupiter Swap Tx Failed: {await response.text()}")
                    return None

    async def execute_swap(self, input_mint: str, output_mint: str, amount_token: float, is_buy: bool):
        """
        Executes a real swap on Solana via Jupiter.
        is_buy=True -> SOL to Token
        is_buy=False -> Token to SOL
        """
        # 0. Adjust Decimals
        # SOL has 9 decimals.
        # Tokens? We need to know decimals if we are selling.
        # For Buying (SOL Input), it's easy: 1e9.
        
        SOL_MINT = "So11111111111111111111111111111111111111112"
        
        if is_buy:
            input_mint = SOL_MINT
            # output_mint is the token
            decimals = 9
        else:
            # We are selling Token -> SOL
            # We need to fetch decimals for the input token to convert amount_token to integer
            # For speed, assume 6 for most memes? No, dangerous.
            # Real way: Fetch mint info.
            # Fast way: User passes raw amount?
            # Let's do a quick fetch of decimals or pass it in. 
            # For now, let's implement a decimal fetch helper or try to use `get_token_balance` response if possible.
            # Actually, `get_token_balance` returns float.
            # Let's get balance details to find decimals.
            pass
        
        # ... Wait, if 'is_buy' is True, amount_token is Amount of SOL to spend.
        # if 'is_buy' is False, amount_token is Amount of Tokens to sell.
        
        amount_int = 0
        if is_buy:
            amount_int = int(amount_token * 1e9)
        else:
            # We need token decimals.
            # Let's modify logic to fetch it.
            # Quick hack: Fetch balance again to get decimals from RPC response
            try:
                from solders.pubkey import Pubkey
                from spl.token.instructions import get_associated_token_address
                mint = Pubkey.from_string(input_mint)
                ata = get_associated_token_address(self.payer.pubkey(), mint)
                resp = await self.rpc_client.get_token_account_balance(ata)
                if resp.value:
                    decimals = resp.value.decimals
                    amount_int = int(amount_token * (10 ** decimals))
                else:
                    print("❌ No token balance found to sell.")
                    return None
            except Exception as e:
                print(f"❌ Error getting decimals: {e}")
                return None

        # 1. Get Quote
        print(f"🔄 Getting Quote for {'BUY' if is_buy else 'SELL'}...")
        quote = await self.get_quote(input_mint, output_mint, amount_int)
        if not quote:
            return None

        # 2. Get Swap Tx
        print("🔄 Fetching Swap Transaction...")
        raw_tx_str = await self.get_swap_tx(quote)
        if not raw_tx_str:
            return None

        # 3. Deserialize & Sign
        try:
            raw_tx_bytes = base64.b64decode(raw_tx_str)
            tx = VersionedTransaction.from_bytes(raw_tx_bytes)
            
            # Sign with keypair
            tx.message = VersionedTransaction(tx.message, [self.payer]).message 
            # Wait, solders signing is specific. 
            # Correct way:
            signed_tx = VersionedTransaction(tx.message, [self.payer])
            
            # 4. Send & Confirm
            print("🚀 Sending Transaction...")
            # signature = await self.rpc_client.send_transaction(signed_tx) # AsyncClient method signature might vary by version
            # Modern solana-py: send_transaction(tx, opts=...)
            
            opts = TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
            resp = await self.rpc_client.send_transaction(signed_tx, opts=opts)
            
            sig = resp.value
            print(f"✅ Transaction Sent! Signature: {sig}")
            
            # 5. Confirm (Optional but good)
            # await self.rpc_client.confirm_transaction(sig)
            
            return str(sig)

        except Exception as e:
            print(f"❌ Transaction Failure: {e}")
            return None

    async def pumpportal_swap(self, mint_address: str, amount: "float | str", is_buy: bool = True, priority_fee: float = 0.0005, slippage: int = 25):
        """
        Execute swap via PumpPortal API for Pump.fun tokens.
        amount: SOL amount if buying, or Token Amount/"100%" if selling.
        priority_fee: SOL amount for priority.
        """
        api_url = "https://pumpportal.fun/api/trade-local"
        
        action = "buy" if is_buy else "sell"
        
        # If selling 100%, payload specific
        denominated_in_sol = "true"
        if not is_buy:
            denominated_in_sol = "false"
        
        payload = {
            "publicKey": self.pubkey,
            "action": action,
            "mint": mint_address,
            "amount": amount,
            "denominatedInSol": denominated_in_sol,
            "slippage": slippage,
            "priorityFee": priority_fee,
            "pool": "auto"
        }
        
        print(f"🔄 PumpPortal: Getting {action.upper()} transaction (Amt: {amount}, Fee: {priority_fee})...")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(api_url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        tx_data = await response.read()
                        print(f"✅ PumpPortal: Got transaction ({len(tx_data)} bytes)")
                        
                        # Deserialize and sign
                        tx = VersionedTransaction.from_bytes(tx_data)
                        signed_tx = VersionedTransaction(tx.message, [self.payer])
                        
                        # Send
                        print("🚀 Sending PumpPortal transaction...")
                        opts = TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
                        resp = await self.rpc_client.send_transaction(signed_tx, opts=opts)
                        
                        sig = str(resp.value)
                        print(f"✅ PumpPortal TX Sent! Sig: {sig}")
                        return sig
                    else:
                        error_text = await response.text()
                        print(f"❌ PumpPortal Error ({response.status}): {error_text}")
                        return None
                        
            except Exception as e:
                print(f"❌ PumpPortal Exception: {e}")
                return None

    async def close_token_account(self, mint_address: str) -> bool:
        """Close empty token account to reclaim ~0.002 SOL rent."""
        try:
            from solders.pubkey import Pubkey
            from spl.token.instructions import close_account, CloseAccountParams
            from solders.transaction import Transaction
            from solders.message import Message
            
            # Find the token account for this mint
            token_programs = [
                "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"   # Regular SPL
            ]
            
            for program_id in token_programs:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        str(self.payer.pubkey()),
                        {"programId": program_id},
                        {"encoding": "jsonParsed"}
                    ]
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(RPC_URL, json=payload, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            accounts = data.get('result', {}).get('value', [])
                            
                            for acc in accounts:
                                info = acc['account']['data']['parsed']['info']
                                if info['mint'] == mint_address:
                                    balance = float(info['tokenAmount']['uiAmount'] or 0)
                                    
                                    if balance == 0:
                                        # Found empty account - close it
                                        ata_address = acc['pubkey']
                                        print(f"🔥 Closing empty token account: {ata_address[:20]}...")
                                        
                                        # Use Helius close instruction
                                        close_payload = {
                                            "jsonrpc": "2.0",
                                            "id": 1,
                                            "method": "getRecentBlockhash",
                                            "params": []
                                        }
                                        
                                        async with session.post(RPC_URL, json=close_payload, timeout=10) as bh_resp:
                                            if bh_resp.status == 200:
                                                bh_data = await bh_resp.json()
                                                blockhash = bh_data['result']['value']['blockhash']
                                                
                                                # Build close account instruction
                                                from spl.token.constants import TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID
                                                
                                                prog_id = TOKEN_2022_PROGRAM_ID if "Tokenz" in program_id else TOKEN_PROGRAM_ID
                                                
                                                close_ix = close_account(
                                                    CloseAccountParams(
                                                        program_id=prog_id,
                                                        account=Pubkey.from_string(ata_address),
                                                        dest=self.payer.pubkey(),
                                                        owner=self.payer.pubkey(),
                                                    )
                                                )
                                                
                                                from solders.hash import Hash
                                                from solders.message import MessageV0
                                                
                                                msg = MessageV0.try_compile(
                                                    self.payer.pubkey(),
                                                    [close_ix],
                                                    [],
                                                    Hash.from_string(blockhash)
                                                )
                                                tx = VersionedTransaction(msg, [self.payer])
                                                
                                                opts = TxOpts(skip_preflight=True, preflight_commitment=Confirmed)
                                                result = await self.rpc_client.send_transaction(tx, opts=opts)
                                                
                                                print(f"✅ Account closed! Reclaimed ~0.002 SOL. Sig: {str(result.value)[:30]}...")
                                                return True
                                    else:
                                        print(f"⚠️ Token account has {balance} tokens, cannot close")
                                        return False
            
            print("ℹ️ No empty token account found to close")
            return False
            
        except Exception as e:
            print(f"⚠️ Error closing token account: {e}")
            return False
