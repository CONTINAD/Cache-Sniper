"""
Ears Database - Smart Money Tracker Storage

Tables:
- tracked_wallets: Wallets we're monitoring
- wallet_transactions: Their on-chain activity
- wallet_clusters: Connected wallet groups
- ears_signals: Generated trading signals
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict

EARS_DB_PATH = "ears.db"


class EarsDB:
    def __init__(self, db_path=EARS_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize all Ears tables."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Tracked wallets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_wallets (
                address TEXT PRIMARY KEY,
                alias TEXT,
                discovery_source TEXT,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                avg_roi REAL DEFAULT 0.0,
                total_pnl_sol REAL DEFAULT 0.0,
                reputation_score REAL DEFAULT 50.0,
                is_active BOOLEAN DEFAULT 1,
                last_activity TIMESTAMP,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                meta TEXT
            )
        ''')

        # Wallet transactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                token_address TEXT NOT NULL,
                token_symbol TEXT,
                action TEXT NOT NULL,
                amount_sol REAL,
                token_amount REAL,
                price_usd REAL,
                mc_at_trade REAL,
                tx_signature TEXT UNIQUE,
                outcome_pnl REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wallet_address) REFERENCES tracked_wallets(address)
            )
        ''')

        # Wallet clusters (connected wallets that trade together)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                cluster_strength REAL DEFAULT 0.5,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cluster_id, wallet_address)
            )
        ''')

        # Ears signals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ears_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                token_symbol TEXT,
                signal_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                source_wallets TEXT,
                mc_at_signal REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acted_on BOOLEAN DEFAULT 0,
                outcome_pnl REAL,
                notes TEXT
            )
        ''')

        # Indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_tx_wallet ON wallet_transactions(wallet_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_tx_token ON wallet_transactions(token_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_wallet_tx_time ON wallet_transactions(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_token ON ears_signals(token_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_time ON ears_signals(created_at)')

        conn.commit()
        conn.close()

    # ==================== WALLET MANAGEMENT ====================

    def add_wallet(self, address: str, alias: str = None, source: str = "manual", 
                   initial_score: float = 50.0) -> bool:
        """Add a wallet to track."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO tracked_wallets 
                (address, alias, discovery_source, reputation_score)
                VALUES (?, ?, ?, ?)
            ''', (address, alias, source, initial_score))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_wallet(self, address: str) -> Optional[Dict]:
        """Get a tracked wallet by address."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tracked_wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_active_wallets(self, min_score: float = 0) -> List[Dict]:
        """Get all active tracked wallets above minimum score."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM tracked_wallets 
            WHERE is_active = 1 AND reputation_score >= ?
            ORDER BY reputation_score DESC
        ''', (min_score,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_wallet_stats(self, address: str, is_win: bool, pnl_percent: float, pnl_sol: float):
        """Update wallet statistics after a trade outcome."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get current stats
        cursor.execute('SELECT total_trades, wins, losses, total_pnl_sol FROM tracked_wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
        
        total_trades = row[0] + 1
        wins = row[1] + (1 if is_win else 0)
        losses = row[2] + (0 if is_win else 1)
        total_pnl = row[3] + pnl_sol
        win_rate = wins / total_trades if total_trades > 0 else 0
        avg_roi = total_pnl / total_trades if total_trades > 0 else 0
        
        # Calculate reputation score (weighted formula)
        # Score = (WinRate * 40) + (min(AvgROI, 100) * 0.4) + (min(TotalTrades, 50) * 0.4)
        score = (win_rate * 40) + (min(avg_roi * 100, 40)) + (min(total_trades, 50) * 0.4)
        score = max(0, min(100, score))  # Clamp 0-100
        
        cursor.execute('''
            UPDATE tracked_wallets SET
                total_trades = ?,
                wins = ?,
                losses = ?,
                win_rate = ?,
                avg_roi = ?,
                total_pnl_sol = ?,
                reputation_score = ?,
                last_activity = CURRENT_TIMESTAMP
            WHERE address = ?
        ''', (total_trades, wins, losses, win_rate, avg_roi, total_pnl, score, address))
        
        conn.commit()
        conn.close()

    # ==================== TRANSACTION LOGGING ====================

    def log_transaction(self, wallet_address: str, token_address: str, action: str,
                        amount_sol: float = None, token_amount: float = None,
                        price_usd: float = None, mc: float = None,
                        tx_sig: str = None, symbol: str = None) -> int:
        """Log a wallet transaction."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO wallet_transactions
                (wallet_address, token_address, token_symbol, action, amount_sol, 
                 token_amount, price_usd, mc_at_trade, tx_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (wallet_address, token_address, symbol, action, amount_sol,
                  token_amount, price_usd, mc, tx_sig))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_transaction_outcome(self, tx_id: int, outcome_pnl: float):
        """Update the PnL outcome of a transaction."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE wallet_transactions 
                SET outcome_pnl = ? 
                WHERE id = ?
            ''', (outcome_pnl, tx_id))
            conn.commit()
        finally:
            conn.close()

    def get_wallet_transactions(self, wallet_address: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a wallet."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM wallet_transactions 
            WHERE wallet_address = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (wallet_address, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_pending_transactions(self, hours: int = 24) -> List[Dict]:
        """Get transactions where outcome hasn't been verified yet."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM wallet_transactions 
            WHERE outcome_pnl IS NULL 
            AND timestamp > datetime('now', ? || ' hours')
            AND timestamp < datetime('now', '-15 minutes') -- Give it time to move
            ORDER BY timestamp ASC
            LIMIT 50
        ''', (f'-{hours}',))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_token_buyers(self, token_address: str, before_time: datetime = None) -> List[Dict]:
        """Get all wallets that bought a specific token."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if before_time:
            cursor.execute('''
                SELECT DISTINCT wt.wallet_address, tw.reputation_score, tw.win_rate,
                       wt.amount_sol, wt.mc_at_trade, wt.timestamp
                FROM wallet_transactions wt
                JOIN tracked_wallets tw ON wt.wallet_address = tw.address
                WHERE wt.token_address = ? AND wt.action = 'BUY' AND wt.timestamp < ?
                ORDER BY wt.timestamp ASC
            ''', (token_address, before_time.isoformat()))
        else:
            cursor.execute('''
                SELECT DISTINCT wt.wallet_address, tw.reputation_score, tw.win_rate,
                       wt.amount_sol, wt.mc_at_trade, wt.timestamp
                FROM wallet_transactions wt
                JOIN tracked_wallets tw ON wt.wallet_address = tw.address
                WHERE wt.token_address = ? AND wt.action = 'BUY'
                ORDER BY wt.timestamp ASC
            ''', (token_address,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ==================== SIGNAL MANAGEMENT ====================

    def create_signal(self, token_address: str, signal_type: str, confidence: float,
                      source_wallets: List[str], mc: float = None, symbol: str = None) -> int:
        """Create a new trading signal."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ears_signals
            (token_address, token_symbol, signal_type, confidence, source_wallets, mc_at_signal)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (token_address, symbol, signal_type, confidence, json.dumps(source_wallets), mc))
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id

    def get_recent_signals(self, hours: int = 24, min_confidence: float = 0) -> List[Dict]:
        """Get recent signals above minimum confidence."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM ears_signals
            WHERE created_at > datetime('now', ? || ' hours')
            AND confidence >= ?
            ORDER BY created_at DESC
        ''', (f'-{hours}', min_confidence))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_signal_acted(self, signal_id: int, outcome_pnl: float = None):
        """Mark a signal as acted upon with optional outcome."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE ears_signals SET acted_on = 1, outcome_pnl = ?
            WHERE id = ?
        ''', (outcome_pnl, signal_id))
        conn.commit()
        conn.close()

    def get_signal_for_token(self, token_address: str) -> Optional[Dict]:
        """Check if we have a recent signal for this token."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM ears_signals
            WHERE token_address = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (token_address,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ==================== CLUSTER MANAGEMENT ====================

    def add_to_cluster(self, cluster_id: int, wallet_address: str, strength: float = 0.5):
        """Add a wallet to a cluster."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO wallet_clusters
            (cluster_id, wallet_address, cluster_strength)
            VALUES (?, ?, ?)
        ''', (cluster_id, wallet_address, strength))
        conn.commit()
        conn.close()

    def get_cluster_wallets(self, cluster_id: int) -> List[Dict]:
        """Get all wallets in a cluster."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT wc.*, tw.alias, tw.reputation_score, tw.win_rate
            FROM wallet_clusters wc
            JOIN tracked_wallets tw ON wc.wallet_address = tw.address
            WHERE wc.cluster_id = ?
            ORDER BY tw.reputation_score DESC
        ''', (cluster_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def find_wallet_cluster(self, wallet_address: str) -> Optional[int]:
        """Find which cluster a wallet belongs to."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT cluster_id FROM wallet_clusters WHERE wallet_address = ?', (wallet_address,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    # ==================== ANALYTICS ====================

    def get_top_wallets(self, limit: int = 20) -> List[Dict]:
        """Get top performing tracked wallets."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM tracked_wallets
            WHERE is_active = 1 AND total_trades >= 3
            ORDER BY reputation_score DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_wallet_stats_summary(self) -> Dict:
        """Get summary stats for all tracked wallets."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total_wallets,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_wallets,
                AVG(reputation_score) as avg_score,
                AVG(win_rate) as avg_win_rate,
                SUM(total_pnl_sol) as total_pnl
            FROM tracked_wallets
        ''')
        row = cursor.fetchone()
        conn.close()
        return {
            'total_wallets': row[0] or 0,
            'active_wallets': row[1] or 0,
            'avg_score': row[2] or 0,
            'avg_win_rate': row[3] or 0,
            'total_pnl': row[4] or 0
        }


# Quick test
if __name__ == "__main__":
    db = EarsDB()
    print("✅ Ears database initialized successfully!")
    print(f"📊 Stats: {db.get_wallet_stats_summary()}")
