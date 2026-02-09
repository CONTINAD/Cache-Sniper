import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict

DB_PATH = "trades.db"

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize the trades table with enhanced data collection columns."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Main trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                address TEXT NOT NULL UNIQUE,
                entry_price REAL,
                amount_sol REAL,
                status TEXT,
                pnl_percent REAL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                meta TEXT,
                source TEXT,
                source_channel TEXT,
                caller_name TEXT,
                entry_mc REAL,
                exit_mc REAL,
                peak_mc REAL,
                entry_volume_1h REAL,
                entry_liquidity REAL,
                entry_holders INTEGER,
                dex_id TEXT,
                token_age_mins REAL
            )
        ''')
        
        # Price snapshots table for time-series analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_address TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                price REAL,
                mc REAL,
                volume_5m INTEGER,
                buys_5m INTEGER,
                sells_5m INTEGER,
                pnl_percent REAL
            )
        ''')
        
        # Sell transactions table for accurate realized PnL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sell_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_address TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                sell_price REAL,
                sell_mc REAL,
                amount_sol_received REAL,
                percentage_sold REAL,
                reason TEXT
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_address ON price_snapshots(trade_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_time ON price_snapshots(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sells_address ON sell_transactions(trade_address)')
        
        # Add new columns if they don't exist (for existing databases)
        new_columns = [
            ('source', 'TEXT'),
            ('source_channel', 'TEXT'),
            ('caller_name', 'TEXT'),
            ('entry_mc', 'REAL'),
            ('exit_mc', 'REAL'),
            ('peak_mc', 'REAL'),
            ('entry_volume_1h', 'REAL'),
            ('entry_liquidity', 'REAL'),
            ('entry_holders', 'INTEGER'),
            ('dex_id', 'TEXT'),
            ('token_age_mins', 'REAL')
        ]
        
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}")
            except:
                pass  # Column already exists
            
        # Buy Queue (Manual Snipes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buy_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                amount_sol REAL NOT NULL,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                tx_signature TEXT,
                error_message TEXT
            )
        ''')
        
        # Phase 3: New Pairs (Fresh Mints)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_pairs (
                address TEXT PRIMARY KEY,
                ticker TEXT,
                name TEXT,
                liquidity_usd REAL,
                created_at TIMESTAMP,
                processed_status TEXT DEFAULT 'NEW' -- NEW, SNIPED, IGNORED
            )
        ''')
        
        # Phase 3: Bot Settings (Toggles)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            )
        ''')
        
        # Initialize default settings if not exist
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('auto_snipe_trending', 'false')")
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('auto_snipe_new', 'false')")
            
        conn.commit()
        conn.close()
    
    def add_manual_buy(self, token_address: str, amount_sol: float):
        """Queue a manual buy request."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
            INSERT INTO buy_queue (token_address, amount_sol, status, created_at)
            VALUES (?, ?, 'PENDING', ?)
        ''', (token_address, amount_sol, now))
        
        conn.commit()
        conn.close()
        print(f"📥 Manual buy queued: {token_address} ({amount_sol} SOL)")

    def get_pending_buys(self) -> List[Dict]:
        """Get all pending buy requests."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM buy_queue WHERE status = 'PENDING' ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_buy_processed(self, buy_id: int, status: str, tx_signature: str = None, error_message: str = None):
        """Update status of a manual buy request."""
        conn = self.get_connection()
        c = conn.cursor()
        now = datetime.now()
        c.execute('''
            UPDATE buy_queue 
            SET status = ?, processed_at = ?, tx_signature = ?, error_message = ?
            WHERE id = ?
        ''', (status, now, tx_signature, error_message, buy_id))
        conn.commit()
        conn.close()

    # --- Phase 3: Settings & New Pairs ---
    
    def get_setting(self, key: str) -> bool:
        """Get a boolean setting value."""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0].lower() == 'true'
        return False

    def set_setting(self, key: str, value: bool):
        """Set a boolean setting value."""
        conn = self.get_connection()
        c = conn.cursor()
        val_str = 'true' if value else 'false'
        c.execute("INSERT OR REPLACE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)", (key, val_str))
        conn.commit()
        conn.close()

    def add_new_pair(self, address: str, ticker: str, name: str, liquidity: float):
        """Log a new pair/mint."""
        conn = self.get_connection()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT OR IGNORE INTO new_pairs (address, ticker, name, liquidity_usd, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (address, ticker, name, liquidity, datetime.now()))
            conn.commit()
        except Exception as e:
            print(f"DB Error add_new_pair: {e}")
        finally:
            conn.close()

    def get_recent_new_pairs(self, limit: int = 50):
        """Get recent new pairs for dashboard."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM new_pairs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]


    def add_trade(self, ticker: str, address: str, entry_price: float, amount_sol: float, 
                  source: str = None, source_channel: str = None, caller_name: str = None,
                  entry_mc: float = None, entry_volume: float = None, entry_liquidity: float = None,
                  entry_holders: int = None, dex_id: str = None, token_age_mins: float = None):
        """Add a trade with comprehensive data collection."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        # Initialize meta with events array for lifecycle tracking
        meta = {"events": []}
        
        cursor.execute('''
            INSERT INTO trades (
                ticker, address, entry_price, amount_sol, status, pnl_percent, 
                created_at, updated_at, meta, source, source_channel, caller_name,
                entry_mc, peak_mc, entry_volume_1h, entry_liquidity, entry_holders, 
                dex_id, token_age_mins
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticker, address, entry_price, amount_sol, 'OPEN', 0.0, now, now,
            json.dumps(meta), source, source_channel, caller_name,
            entry_mc, entry_mc,  # peak_mc starts as entry_mc
            entry_volume, entry_liquidity, entry_holders, dex_id, token_age_mins
        ))
        conn.commit()
        conn.close()
        
        channel_label = f" [{source_channel}]" if source_channel else (f" [{source.upper()}]" if source else "")
        mc_label = f" MC:{entry_mc/1000:.1f}K" if entry_mc else ""
        print(f"💾 Trade saved: {ticker}{channel_label}{mc_label}")

    def update_trade(self, address: str, status: str, pnl_percent: float, meta: Dict = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        # Build update query
        query = "UPDATE trades SET status = ?, pnl_percent = ?, updated_at = ?"
        params = [status, pnl_percent, now]
        
        if meta:
            query += ", meta = ?"
            params.append(json.dumps(meta))
            
        query += " WHERE address = ?"
        params.append(address)
        
        cursor.execute(query, tuple(params))
        conn.commit()
        conn.close()

    def log_sell(self, address: str, sell_price: float, sell_mc: float, 
                 amount_sol_received: float, percentage_sold: float, reason: str):
        """Log a sell transaction for accurate realized PnL calculation."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute('''
            INSERT INTO sell_transactions 
            (trade_address, timestamp, sell_price, sell_mc, amount_sol_received, percentage_sold, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (address, now, sell_price, sell_mc, amount_sol_received, percentage_sold, reason))
        
        conn.commit()
        conn.close()
    
    def get_realized_pnl(self, address: str, entry_amount_sol: float) -> dict:
        """Calculate realized PnL from actual sell transactions."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM sell_transactions WHERE trade_address = ? ORDER BY timestamp
        ''', (address,))
        
        sells = cursor.fetchall()
        conn.close()
        
        if not sells:
            return {'realized_sol': 0, 'realized_pnl_pct': 0, 'sell_count': 0}
        
        total_received = sum(s['amount_sol_received'] for s in sells)
        realized_pnl_pct = ((total_received - entry_amount_sol) / entry_amount_sol) * 100 if entry_amount_sol > 0 else 0
        
        return {
            'realized_sol': total_received,
            'realized_pnl_pct': realized_pnl_pct,
            'sell_count': len(sells)
        }

    def get_active_trades(self) -> List[Dict]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status NOT LIKE 'CLOSED%'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_trades(self) -> List[Dict]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_trade(self, address: str) -> Optional[Dict]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE address = ?", (address,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_trade_status(self, address: str, status: str):
        """Used by Dashboard for manual interventions (e.g. Panic Sell)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute("UPDATE trades SET status = ?, updated_at = ? WHERE address = ?", (status, now, address))
        conn.commit()
        conn.close()
    
    # === ENHANCED DATA COLLECTION METHODS ===
    
    def add_snapshot(self, address: str, price: float, mc: float, 
                     buys_5m: int = 0, sells_5m: int = 0, pnl_percent: float = 0):
        """Capture a price snapshot for time-series analysis."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO price_snapshots (trade_address, timestamp, price, mc, volume_5m, buys_5m, sells_5m, pnl_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (address, datetime.now(), price, mc, buys_5m + sells_5m, buys_5m, sells_5m, pnl_percent))
        conn.commit()
        conn.close()
    
    def add_trade_event(self, address: str, event_type: str, data: Dict = None):
        """Log an event in the trade's lifecycle (TP hit, SL move, clip, etc.)."""
        trade = self.get_trade(address)
        if not trade:
            return
        
        meta = json.loads(trade['meta']) if trade['meta'] else {}
        if 'events' not in meta:
            meta['events'] = []
        
        event = {
            'time': datetime.now().isoformat(),
            'type': event_type,
            **(data or {})
        }
        meta['events'].append(event)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET meta = ? WHERE address = ?", (json.dumps(meta), address))
        conn.commit()
        conn.close()
    
    def update_peak_mc(self, address: str, new_mc: float):
        """Update peak MC if new value is higher."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trades SET peak_mc = ? 
            WHERE address = ? AND (peak_mc IS NULL OR peak_mc < ?)
        """, (new_mc, address, new_mc))
        conn.commit()
        conn.close()
    
    def set_exit_mc(self, address: str, exit_mc: float):
        """Set the exit MC when trade closes."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET exit_mc = ? WHERE address = ?", (exit_mc, address))
        conn.commit()
        conn.close()
    
    def get_snapshots(self, address: str) -> List[Dict]:
        """Get all price snapshots for a trade."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM price_snapshots WHERE trade_address = ? ORDER BY timestamp", (address,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def calculate_stats(self, days: int) -> Dict:
        """
        Calculate aggregate stats for the last N days.
        Returns: {'x_gain': float, 'pct_gain': float, 'count': int, 'wins': int}
        """
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Parse created_at properly. SQLite uses strings.
        # We filter in Python if needed, or use SQLite date functions if format is consistent.
        # Format in add_trade is `now` (datetime object), which SQLite adapter converts to "YYYY-MM-DD HH:MM:SS.ssssss"
        # So we can use datetime comparison.
        
        start_date = datetime.now() - timedelta(days=days)
        cursor.execute("SELECT * FROM trades")
        rows = cursor.fetchall()
        conn.close()
        
        total_x_potential = 0.0
        total_pct = 0.0
        count = 0
        wins = 0
        
        for row in rows:
            trade = dict(row)
            try:
                created_at_str = trade['created_at']
                # Handle potentially different formats or objects if adapters vary
                if isinstance(created_at_str, str):
                    if 'T' in created_at_str:
                         dt = datetime.fromisoformat(created_at_str)
                    else:
                         dt = datetime.strptime(created_at_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                else:
                    dt = created_at_str # Already datetime?
                
                if dt >= start_date:
                    count += 1
                    
                    # Calculate Max X caught (Potential)
                    entry_mc = trade.get('entry_mc', 0)
                    meta = json.loads(trade['meta']) if trade['meta'] else {}
                    max_mc = meta.get('max_mc_hit', 0)
                    
                    if entry_mc and entry_mc > 0:
                        if not max_mc: max_mc = entry_mc
                             
                        x_mult = max_mc / entry_mc
                        pct_gain = (x_mult - 1) * 100
                        
                        # "Daily X Gain" usually sums up the X's of the winners (Hype mode)
                        # e.g. "We hit a 10x and a 5x!" -> Total 15x
                        if x_mult > 1.0:
                             total_x_potential += x_mult
                             wins += 1
                        
                        # Net % includes losses for internal accuracy, but for 'Hype X' we use total_x_potential
                        total_pct += pct_gain

            except Exception as e:
                # print(f"Error parsing trade stat: {e}")
                continue
                
        return {
            'x_gain': total_x_potential,
            'pct_gain': total_pct, # Keep net pct for reality check if needed, or switch to potential too? 
                                   # User said "daily x gain", likely potential.
                                   # Let's keep pct as Net for now, or maybe sum of gains?
                                   # Let's stick to x_gain being the headline.
            'count': count,
            'wins': wins,
            'win_rate': (wins/count*100) if count > 0 else 0
        }
