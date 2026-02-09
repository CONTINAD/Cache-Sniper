"""
Strategy Lab - 15 Trading Strategies with Advanced Logic
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


@dataclass
class TakeProfit:
    multiplier: float
    percentage: float


@dataclass
class StrategyResult:
    should_buy: bool
    reason: str = ""


class BaseStrategy(ABC):
    name: str = "Base"
    emoji: str = "📊"
    risk_level: str = "Medium"
    reward_level: str = "Medium"
    description: str = ""
    
    @abstractmethod
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        pass
    
    @abstractmethod
    def get_tp_levels(self) -> List[TakeProfit]:
        pass
    
    @abstractmethod
    def get_stop_loss(self) -> float:
        pass
    
    def get_trailing_stop(self) -> Optional[float]:
        return None
    
    def get_strategy_info(self) -> Dict:
        """Return detailed strategy info for UI."""
        tps = self.get_tp_levels()
        tp_str = ", ".join([f"{int(tp.percentage*100)}%@{tp.multiplier}x" for tp in tps])
        return {
            'name': self.name,
            'emoji': self.emoji,
            'risk': self.risk_level,
            'reward': self.reward_level,
            'description': self.description,
            'tp_levels': tp_str,
            'stop_loss': f"{self.get_stop_loss()*100:.0f}%",
            'trailing': f"{self.get_trailing_stop()*100:.0f}%" if self.get_trailing_stop() else "None"
        }


# ============================================================
# STRATEGY 1: SCALPER - Quick In/Out
# ============================================================
class ScalperStrategy(BaseStrategy):
    name = "SCALPER"
    emoji = "⚡"
    risk_level = "Low"
    reward_level = "Low"
    description = "Quick 20% gains, tight stop"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        # Scalper needs volume to exit
        vol = signal_data.get('volume_5m_usd', 0)
        # User requested min $2k volume
        if vol < 2000:
             return StrategyResult(should_buy=False, reason="Low Vol (<$2k)")
        return StrategyResult(should_buy=True, reason="Vol OK")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(multiplier=1.2, percentage=1.0)]
    
    def get_stop_loss(self) -> float:
        return -0.10


# ... (strategies 2-9 omitted if unchanged) ... 

# ============================================================
# STRATEGY 10: DEGEN
# ============================================================
class DegenStrategy(BaseStrategy):
    name = "DEGEN"
    emoji = "🎰"
    risk_level = "Maximum"
    reward_level = "Maximum"
    description = "YOLO (Vol > $2k)"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        vol = signal_data.get('volume_5m_usd', 0)
        if vol < 2000:
            return StrategyResult(should_buy=False, reason="Dead coin (Vol<$2k)")
        return StrategyResult(should_buy=True, reason="YOLO 🎰")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.2), TakeProfit(5.0, 0.2), TakeProfit(100.0, 0.6)]
    
    def get_stop_loss(self) -> float:
        return -0.60


# ============================================================
# STRATEGY 11: SNIPER (NEW)
# ============================================================
class SniperStrategy(BaseStrategy):
    name = "SNIPER"
    emoji = "🎯"
    risk_level = "Medium"
    reward_level = "High"
    description = "MC < $25K, Liq > $8K, Vol > $2K"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        liq = signal_data.get('liquidity_usd', 0)
        vol = signal_data.get('volume_5m_usd', 0)
        
        if vol < 2000:
            return StrategyResult(should_buy=False, reason="Vol < $2k")
            
        # Early entry sniper
        if mc < 25000 and liq > 8000:
            return StrategyResult(should_buy=True, reason=f"${mc/1000:.0f}K MC, ${liq/1000:.0f}K liq ✓")
        return StrategyResult(should_buy=False, reason="MC/Liq fail")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.4), TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.3)]
    
    def get_stop_loss(self) -> float:
        return -0.25


# ... ( Strategies 12-13 omitted ) ...


# ============================================================
# STRATEGY 14: MICRO CAP (NEW)
# ============================================================
class MicroCapStrategy(BaseStrategy):
    name = "MICRO"
    emoji = "🔬"
    risk_level = "Very High"
    reward_level = "Very High"
    description = "MC < $15K, Vol > $2k"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        vol = signal_data.get('volume_5m_usd', 0)
        
        if vol < 2000:
            return StrategyResult(should_buy=False, reason="Vol < $2k")
            
        if mc < 15000 and mc > 1000:
            return StrategyResult(should_buy=True, reason=f"${mc/1000:.1f}K micro ✓")
        return StrategyResult(should_buy=False, reason=f"${mc/1000:.1f}K not micro")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.3), TakeProfit(10.0, 0.4)]
    
    def get_stop_loss(self) -> float:
        return -0.50


# ============================================================
# STRATEGY 2: MOMENTUM - Ride the Wave
# ============================================================
class MomentumStrategy(BaseStrategy):
    name = "MOMENTUM"
    emoji = "🌊"
    risk_level = "Medium"
    reward_level = "Medium"
    description = "Wait for +3% confirmation"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        price_change = signal_data.get('price_change_5m', 0)
        if price_change >= 0.03:
            return StrategyResult(should_buy=True, reason=f"+{price_change*100:.1f}% ✓")
        return StrategyResult(should_buy=False, reason=f"+{price_change*100:.1f}% < 3%")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.5, 0.5), TakeProfit(2.5, 0.5)]
    
    def get_stop_loss(self) -> float:
        return -0.25


# ============================================================
# STRATEGY 3: DIAMOND HANDS
# ============================================================
class DiamondHandsStrategy(BaseStrategy):
    name = "DIAMOND"
    emoji = "💎"
    risk_level = "High"
    reward_level = "High"
    description = "Hold for 3x-10x or bust"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        # Diamond hands needs liquidity to survive dumps
        liq = signal_data.get('liquidity_usd', 0)
        if liq < 10000:
             return StrategyResult(should_buy=False, reason="Liq < $10k")
        return StrategyResult(should_buy=True, reason="Diamond Ready")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.3), TakeProfit(10.0, 0.4)]
    
    def get_stop_loss(self) -> float:
        return -0.50


# ============================================================
# STRATEGY 4: VOLUME SURGE
# ============================================================
class VolumeSurgeStrategy(BaseStrategy):
    name = "VOLUME"
    emoji = "📈"
    risk_level = "Medium"
    reward_level = "High"
    description = "Only if 5m vol > $5K"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        vol = signal_data.get('volume_5m_usd', 0)
        if vol >= 5000:
            return StrategyResult(should_buy=True, reason=f"${vol/1000:.1f}K vol ✓")
        return StrategyResult(should_buy=False, reason=f"${vol/1000:.1f}K < $5K")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.6), TakeProfit(4.0, 0.4)]
    
    def get_stop_loss(self) -> float:
        return -0.30


# ============================================================
# STRATEGY 5: MC SWEET SPOT
# ============================================================
class MCSweetSpotStrategy(BaseStrategy):
    name = "MC SWEET"
    emoji = "🎯"
    risk_level = "Medium"
    reward_level = "High"
    description = "MC $20K-$50K only"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        if 20000 <= mc <= 50000:
            return StrategyResult(should_buy=True, reason=f"${mc/1000:.0f}K MC ✓")
        return StrategyResult(should_buy=False, reason=f"${mc/1000:.0f}K outside range")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.5), TakeProfit(5.0, 0.5)]
    
    def get_stop_loss(self) -> float:
        return -0.30


# ============================================================
# STRATEGY 6: LIQUIDITY SAFE
# ============================================================
class LiquiditySafeStrategy(BaseStrategy):
    name = "LIQ SAFE"
    emoji = "🛡️"
    risk_level = "Low"
    reward_level = "Medium"
    description = "Liq > $12K (Pump.fun Meta)"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        liq = signal_data.get('liquidity_usd', 0)
        # Lowered to $12k based on Dec 2025 Avg Graduation Liq
        if liq >= 12000:
            return StrategyResult(should_buy=True, reason=f"${liq/1000:.0f}K liq ✓")
        return StrategyResult(should_buy=False, reason=f"${liq/1000:.0f}K < $12K")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.5, 0.7), TakeProfit(3.0, 0.3)]
    
    def get_stop_loss(self) -> float:
        return -0.20


# ... (Skipping unaffected strategies) ...

# ============================================================
# STRATEGY 7: FOMO CATCHER
# ============================================================
class FOMOCatcherStrategy(BaseStrategy):
    name = "FOMO"
    emoji = "🚀"
    risk_level = "High"
    reward_level = "Low"
    description = "Chase +50% pumps"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        change = signal_data.get('price_change_1h', 0)
        if change >= 0.50:
            return StrategyResult(should_buy=True, reason=f"+{change*100:.0f}% pump")
        return StrategyResult(should_buy=False, reason=f"+{change*100:.0f}% < 50%")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.2, 1.0)]
    
    def get_stop_loss(self) -> float:
        return -0.10


# ============================================================
# STRATEGY 8: TRAILING PRO
# ============================================================
class TrailingProStrategy(BaseStrategy):
    name = "TRAILING"
    emoji = "📏"
    risk_level = "Medium"
    reward_level = "Variable"
    description = "Lock profits with trail"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
         # Need base liquidity to trail properly without slippage death
        liq = signal_data.get('liquidity_usd', 0)
        if liq < 5000:
             return StrategyResult(should_buy=False, reason="Liq < $5k")
        return StrategyResult(should_buy=True, reason="Liq OK")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.5, 0.5)]
    
    def get_stop_loss(self) -> float:
        return -0.25
    
    def get_trailing_stop(self) -> Optional[float]:
        return -0.20


# ============================================================
# STRATEGY 9: CONSERVATIVE
# ============================================================
class ConservativeStrategy(BaseStrategy):
    name = "CONSERV"
    emoji = "🏦"
    risk_level = "Very Low"
    reward_level = "Low"
    description = "Liq>$15K & MC<$30K"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        liq = signal_data.get('liquidity_usd', 0)
        mc = signal_data.get('market_cap', 0)
        # Stricter Liquidity but adjusted for Pump.fun reality
        if liq >= 15000 and mc < 30000:
            return StrategyResult(should_buy=True, reason="Liq+MC Safe ✓")
        return StrategyResult(should_buy=False, reason="Use Safer Entry")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.3, 0.8), TakeProfit(2.0, 0.2)]
    
    def get_stop_loss(self) -> float:
        return -0.15


# ============================================================
# STRATEGY 10: DEGEN
# ============================================================
class DegenStrategy(BaseStrategy):
    name = "DEGEN"
    emoji = "🎰"
    risk_level = "Maximum"
    reward_level = "Maximum"
    description = "YOLO (Vol > $1k)"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        vol = signal_data.get('volume_5m_usd', 0)
        if vol < 1000:
            return StrategyResult(should_buy=False, reason="Dead coin (Vol<$1k)")
        return StrategyResult(should_buy=True, reason="YOLO 🎰")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.2), TakeProfit(5.0, 0.2), TakeProfit(100.0, 0.6)]
    
    def get_stop_loss(self) -> float:
        return -0.60


# ============================================================
# STRATEGY 11: SNIPER (NEW)
# ============================================================
class SniperStrategy(BaseStrategy):
    name = "SNIPER"
    emoji = "🎯"
    risk_level = "Medium"
    reward_level = "High"
    description = "MC < $25K, Liq > $8K"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        liq = signal_data.get('liquidity_usd', 0)
        # Early entry sniper
        if mc < 25000 and liq > 8000:
            return StrategyResult(should_buy=True, reason=f"${mc/1000:.0f}K MC, ${liq/1000:.0f}K liq ✓")
        return StrategyResult(should_buy=False, reason="MC/Liq fail")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(2.0, 0.4), TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.3)]
    
    def get_stop_loss(self) -> float:
        return -0.25

# ... (Rest of file) ...


# ============================================================
# STRATEGY 12: REVERSAL (NEW)
# ============================================================
class ReversalStrategy(BaseStrategy):
    name = "REVERSAL"
    emoji = "🔄"
    risk_level = "High"
    reward_level = "High"
    description = "Buy dips (-20% 1hr)"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        change = signal_data.get('price_change_1h', 0)
        if change <= -0.20:
            return StrategyResult(should_buy=True, reason=f"{change*100:.0f}% dip ✓")
        return StrategyResult(should_buy=False, reason=f"{change*100:.0f}% not dipping")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.5, 0.5), TakeProfit(2.0, 0.5)]
    
    def get_stop_loss(self) -> float:
        return -0.30


# ============================================================
# STRATEGY 13: WHALE WATCHER (NEW)
# ============================================================
class WhaleWatcherStrategy(BaseStrategy):
    name = "WHALE"
    emoji = "🐋"
    risk_level = "Medium"
    reward_level = "High"
    description = "High vol + liq combo"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        vol = signal_data.get('volume_5m_usd', 0)
        liq = signal_data.get('liquidity_usd', 0)
        if vol > 3000 and liq > 20000:
            return StrategyResult(should_buy=True, reason=f"Vol ${vol/1000:.1f}K, Liq ${liq/1000:.0f}K ✓")
        return StrategyResult(should_buy=False, reason="Vol/Liq low")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.8, 0.5), TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.2)]
    
    def get_stop_loss(self) -> float:
        return -0.25


# ============================================================
# STRATEGY 14: MICRO CAP (NEW)
# ============================================================
class MicroCapStrategy(BaseStrategy):
    name = "MICRO"
    emoji = "🔬"
    risk_level = "Very High"
    reward_level = "Very High"
    description = "MC < $15K moonshots"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        if mc < 15000 and mc > 1000:
            return StrategyResult(should_buy=True, reason=f"${mc/1000:.1f}K micro ✓")
        return StrategyResult(should_buy=False, reason=f"${mc/1000:.1f}K not micro")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(3.0, 0.3), TakeProfit(5.0, 0.3), TakeProfit(10.0, 0.4)]
    
    def get_stop_loss(self) -> float:
        return -0.50


# ============================================================
# STRATEGY 15: BALANCED (NEW)
# ============================================================
class BalancedStrategy(BaseStrategy):
    name = "BALANCED"
    emoji = "⚖️"
    risk_level = "Medium"
    reward_level = "Medium"
    description = "50/50 risk/reward"
    
    def should_buy(self, signal_data: Dict) -> StrategyResult:
        mc = signal_data.get('market_cap', 0)
        liq = signal_data.get('liquidity_usd', 0)
        vol = signal_data.get('volume_5m_usd', 0)
        
        if vol < 2000:
             return StrategyResult(should_buy=False, reason="Vol < $2k")
             
        # Buy if MC/Liq ratio is healthy (not too low liquidity relative to MC)
        if liq > 0 and mc > 0:
            ratio = liq / mc
            if ratio >= 0.3:  # At least 30% liquidity to MC
                return StrategyResult(should_buy=True, reason=f"{ratio*100:.0f}% liq ratio ✓")
        return StrategyResult(should_buy=False, reason="Bad liq ratio")
    
    def get_tp_levels(self) -> List[TakeProfit]:
        return [TakeProfit(1.5, 0.4), TakeProfit(2.0, 0.3), TakeProfit(3.0, 0.3)]
    
    def get_stop_loss(self) -> float:
        return -0.20


# ============================================================
# ALL STRATEGIES REGISTRY (Call-Based Trading - 5 Active)
# ============================================================
# Removed: MOMENTUM, VOLUME_SURGE, MC_SWEET_SPOT, LIQ_SAFE, FOMO, 
#          TRAILING, CONSERVATIVE, REVERSAL, WHALE, BALANCED
# Reason: Call-based trading doesn't need indicator-based entry filters.
#         The core filters (Global Fees, Liquidity, Age) are in trader.py.

ALL_STRATEGIES = [
    ScalperStrategy(),      # Quick 20% flips
    DiamondHandsStrategy(), # Hold for 3x-10x
    DegenStrategy(),        # YOLO moon or bust
    SniperStrategy(),       # Early MC < $25k
    MicroCapStrategy(),     # Ultra early < $15k
]

def get_strategy_by_name(name: str) -> Optional[BaseStrategy]:
    for s in ALL_STRATEGIES:
        if s.name == name:
            return s
    return None
