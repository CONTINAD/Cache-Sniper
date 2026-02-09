import sqlite3
import pandas as pd
from src.database import Database

class StrategyLab:
    def __init__(self, db: Database):
        self.db = db
        
    def get_strategy_performance(self):
        """
        Analyze trade history and return stats per 'source'.
        Returns a DataFrame with [source, wins, losses, win_rate, total_pnl, score]
        """
        conn = self.db.get_connection()
        # Calculate profit using pnl_percent * amount_sol / 100 (approximate)
        query = """
            SELECT 
                source,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_percent > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_percent <= 0 THEN 1 ELSE 0 END) as losses,
                AVG(pnl_percent) as avg_roi,
                SUM(amount_sol * pnl_percent / 100.0) as total_profit_sol
            FROM trades 
            WHERE status = 'CLOSED' AND source IS NOT NULL
            GROUP BY source
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
            
        # Calculate Win Rate
        df['win_rate'] = (df['wins'] / df['total_trades']) * 100
        
        # Calculate Confidence Score (0-100)
        # Simple Logic: Win Rate * 0.7 + (ROI normalized) * 0.3
        # Baseline: 50% WR = 50 Score. 
        df['score'] = df.apply(self._calculate_score, axis=1)
        
        return df
    
    def _calculate_score(self, row):
        # Weighted Score
        # Win Rate is mostly what matters for sniping
        wr_score = row['win_rate']
        
        # Penalty for low sample size
        if row['total_trades'] < 3:
            wr_score = wr_score * 0.5 
            
        # Bonus for high ROI
        roi_bonus = min(row['avg_roi'], 50) # Cap bonus at 50% ROI
        
        final_score = (wr_score * 0.8) + (roi_bonus * 0.2)
        return min(100, max(0, final_score))

    def evaluate_signal(self, source: str, default_size: float = 0.2) -> float:
        """
        Decides buy size based on strategy performance.
        Returns 0.0 if strategy should be killed.
        """
        stats = self.get_strategy_performance()
        if stats.empty:
            return default_size 
            
        row = stats[stats['source'] == source]
        if row.empty:
            return default_size # No data, stick to default
            
        score = row.iloc[0]['score']
        losses = row.iloc[0]['losses']
        total = row.iloc[0]['total_trades']
        
        # 1. AUTO-KILL SWITCH
        # If last 3 trades were losses? (Simple approximation: if WR < 20% and > 5 trades)
        if total >= 5 and score < 20:
            print(f"💀 KILL SWITCH: Strategy '{source}' has score {score:.1f}. BLOCKING BUY.")
            return 0.0
            
        # 2. SMART SIZING
        if score > 80:
            print(f"🧠 SMART SIZE: High Confidence ({score:.1f}) -> Boosting Size!")
            return 0.5 # Boost to 0.5 SOL
        elif score < 40:
             print(f"🧠 SMART SIZE: Low Confidence ({score:.1f}) -> Reducing Size.")
             return 0.1 # Reduce to 0.1 SOL
             
        return default_size
