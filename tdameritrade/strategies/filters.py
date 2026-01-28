"""
Strategy filters: VP zones, ADD regime, FVG detection, ATR regime, no-trade filters.
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class VPZoneDetector:
    """
    Volume Profile (VP) zone detection.
    Identifies high-volume nodes (hot zones/magnets) and low-volume gaps.
    """
    
    def __init__(self, lookback_periods: int = 20):
        """
        Initialize VP zone detector.
        
        Args:
            lookback_periods: Number of periods to analyze for VP zones
        """
        self.lookback_periods = lookback_periods
        self.zones: List[Dict] = []
    
    def detect_zones(self, price_data: pd.DataFrame, volume_data: pd.Series) -> List[Dict]:
        """
        Detect VP zones from price and volume data.
        
        Args:
            price_data: DataFrame with OHLC data
            volume_data: Series with volume data
        
        Returns:
            List of VP zones with price levels and strength
        """
        # Combine price and volume
        df = price_data.copy()
        df['volume'] = volume_data
        
        # Calculate volume profile
        price_bins = np.linspace(df['low'].min(), df['high'].max(), 50)
        df['price_bin'] = pd.cut(df['close'], bins=price_bins)
        
        # Aggregate volume by price bin
        vp = df.groupby('price_bin')['volume'].sum().sort_values(ascending=False)
        
        # Identify high-volume nodes (POC - Point of Control)
        poc_level = vp.idxmax().mid if hasattr(vp.idxmax(), 'mid') else float(vp.idxmax())
        
        # Identify value area (70% of volume)
        cumulative_volume = vp.cumsum()
        total_volume = vp.sum()
        value_area_threshold = total_volume * 0.7
        
        value_area = vp[cumulative_volume <= value_area_threshold]
        value_area_high = value_area.index.max().mid if hasattr(value_area.index.max(), 'mid') else float(value_area.index.max())
        value_area_low = value_area.index.min().mid if hasattr(value_area.index.min(), 'mid') else float(value_area.index.min())
        
        zones = [
            {
                "type": "POC",
                "level": poc_level,
                "strength": "high",
                "description": "Point of Control - highest volume node"
            },
            {
                "type": "VA_HIGH",
                "level": value_area_high,
                "strength": "medium",
                "description": "Value Area High"
            },
            {
                "type": "VA_LOW",
                "level": value_area_low,
                "strength": "medium",
                "description": "Value Area Low"
            }
        ]
        
        self.zones = zones
        return zones
    
    def is_near_zone(self, price: float, threshold: float = 0.01) -> Optional[Dict]:
        """
        Check if price is near a VP zone.
        
        Args:
            price: Current price
            threshold: Percentage threshold for "near" (default 1%)
        
        Returns:
            VP zone if price is near, None otherwise
        """
        for zone in self.zones:
            zone_level = zone["level"]
            if abs(price - zone_level) / zone_level <= threshold:
                return zone
        return None


class ADDRegimeClassifier:
    """
    ADD (Accumulation/Distribution/Distribution) regime classifier.
    Classifies market regime based on price action and volume.
    """
    
    def __init__(self):
        self.current_regime: str = "UNKNOWN"
        self.regime_history: List[Tuple[datetime, str]] = []
    
    def classify(self, price_data: pd.DataFrame, volume_data: pd.Series) -> str:
        """
        Classify current market regime.
        
        Regimes:
        - ACCUMULATION: Price rising on increasing volume
        - DISTRIBUTION: Price falling on increasing volume
        - BALANCED: Price and volume in equilibrium
        - CHOP: Sideways price action with low volume
        
        Args:
            price_data: DataFrame with OHLC data
            volume_data: Series with volume data
        
        Returns:
            Regime classification string
        """
        if len(price_data) < 20:
            return "UNKNOWN"
        
        # Calculate price change
        price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-20]) / price_data['close'].iloc[-20]
        
        # Calculate volume trend
        volume_ma = volume_data.rolling(20).mean()
        recent_volume = volume_data.iloc[-5:].mean()
        avg_volume = volume_ma.iloc[-1]
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Calculate volatility (ATR-like)
        high_low = (price_data['high'] - price_data['low']).rolling(20).mean()
        volatility = high_low.iloc[-1] / price_data['close'].iloc[-1] if price_data['close'].iloc[-1] > 0 else 0
        
        # Classify regime
        if abs(price_change) < 0.01 and volatility < 0.02:
            regime = "CHOP"
        elif price_change > 0.02 and volume_ratio > 1.2:
            regime = "ACCUMULATION"
        elif price_change < -0.02 and volume_ratio > 1.2:
            regime = "DISTRIBUTION"
        elif abs(price_change) < 0.02:
            regime = "BALANCED"
        else:
            regime = "BALANCED"
        
        self.current_regime = regime
        self.regime_history.append((datetime.now(), regime))
        
        return regime
    
    def is_safe_for_strangle(self) -> bool:
        """Check if regime is safe for neutral strangle strategies."""
        return self.current_regime in ["BALANCED", "CHOP"]
    
    def is_safe_for_directional(self) -> bool:
        """Check if regime is safe for directional butterfly strategies."""
        return self.current_regime in ["ACCUMULATION", "DISTRIBUTION"]


class FVGDetector:
    """
    Fair Value Gap (FVG) detector.
    Identifies price gaps that represent potential support/resistance levels.
    """
    
    def __init__(self):
        self.fvgs: List[Dict] = []
    
    def detect_fvgs(self, price_data: pd.DataFrame) -> List[Dict]:
        """
        Detect Fair Value Gaps from candlestick data.
        
        FVG: Three candles where middle candle's range doesn't overlap
        with previous and next candles, creating a gap.
        
        Args:
            price_data: DataFrame with OHLC data
        
        Returns:
            List of FVG zones
        """
        fvgs = []
        
        if len(price_data) < 3:
            return fvgs
        
        for i in range(1, len(price_data) - 1):
            prev_candle = price_data.iloc[i-1]
            curr_candle = price_data.iloc[i]
            next_candle = price_data.iloc[i+1]
            
            # Bullish FVG: gap between prev high and next low
            if prev_candle['high'] < next_candle['low']:
                fvg = {
                    "type": "BULLISH",
                    "low": prev_candle['high'],
                    "high": next_candle['low'],
                    "timestamp": price_data.index[i],
                    "filled": False
                }
                fvgs.append(fvg)
            
            # Bearish FVG: gap between prev low and next high
            elif prev_candle['low'] > next_candle['high']:
                fvg = {
                    "type": "BEARISH",
                    "low": next_candle['high'],
                    "high": prev_candle['low'],
                    "timestamp": price_data.index[i],
                    "filled": False
                }
                fvgs.append(fvg)
        
        # Check if FVGs have been filled
        current_price = price_data['close'].iloc[-1]
        for fvg in fvgs:
            if fvg['low'] <= current_price <= fvg['high']:
                fvg['filled'] = True
        
        self.fvgs = fvgs
        return fvgs
    
    def get_unfilled_fvgs(self) -> List[Dict]:
        """Get list of unfilled FVGs (potential support/resistance)."""
        return [fvg for fvg in self.fvgs if not fvg['filled']]
    
    def is_near_fvg(self, price: float, threshold: float = 0.01) -> Optional[Dict]:
        """Check if price is near an unfilled FVG."""
        for fvg in self.get_unfilled_fvgs():
            if fvg['low'] * (1 - threshold) <= price <= fvg['high'] * (1 + threshold):
                return fvg
        return None


class ATRRegimeClassifier:
    """
    ATR-based regime classifier.
    Classifies volatility regime based on Average True Range.
    """
    
    def __init__(self, period: int = 14):
        self.period = period
        self.current_regime: str = "UNKNOWN"
    
    def calculate_atr(self, price_data: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range."""
        high_low = price_data['high'] - price_data['low']
        high_close = abs(price_data['high'] - price_data['close'].shift())
        low_close = abs(price_data['low'] - price_data['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(self.period).mean()
        
        return atr
    
    def classify_regime(self, price_data: pd.DataFrame) -> str:
        """
        Classify volatility regime based on ATR.
        
        Regimes:
        - LOW_VOL: ATR < 20th percentile
        - NORMAL_VOL: ATR between 20th and 80th percentile
        - HIGH_VOL: ATR > 80th percentile
        """
        atr = self.calculate_atr(price_data)
        current_atr = atr.iloc[-1]
        
        # Calculate percentiles
        atr_percentiles = atr.quantile([0.2, 0.8])
        low_threshold = atr_percentiles[0.2]
        high_threshold = atr_percentiles[0.8]
        
        if current_atr < low_threshold:
            regime = "LOW_VOL"
        elif current_atr > high_threshold:
            regime = "HIGH_VOL"
        else:
            regime = "NORMAL_VOL"
        
        self.current_regime = regime
        return regime


class NoTradeFilter:
    """
    Filters that prevent trading in unsafe conditions.
    """
    
    def __init__(self):
        self.news_windows: List[Tuple[time, time]] = [
            (time(8, 30), time(9, 30)),  # Pre-market news
            (time(12, 0), time(13, 0)),  # Mid-day news
        ]
    
    def check_news_window(self, current_time: Optional[datetime] = None) -> bool:
        """Check if current time is in a news window."""
        if current_time is None:
            current_time = datetime.now()
        
        current_time_only = current_time.time()
        
        for start, end in self.news_windows:
            if start <= current_time_only <= end:
                return True
        return False
    
    def check_chop(self, price_data: pd.DataFrame, threshold: float = 0.02) -> bool:
        """
        Detect choppy market conditions.
        
        Args:
            price_data: OHLC data
            threshold: Maximum price movement to consider "chop"
        
        Returns:
            True if market is choppy
        """
        if len(price_data) < 20:
            return False
        
        price_range = (price_data['high'].iloc[-20:].max() - price_data['low'].iloc[-20:].min()) / price_data['close'].iloc[-20]
        return price_range < threshold
    
    def check_volatility_spike(self, price_data: pd.DataFrame, multiplier: float = 2.0) -> bool:
        """
        Detect volatility spikes that may indicate unsafe conditions.
        
        Args:
            price_data: OHLC data
            multiplier: ATR multiplier threshold
        
        Returns:
            True if volatility spike detected
        """
        atr_calc = ATRRegimeClassifier()
        atr = atr_calc.calculate_atr(price_data)
        
        if len(atr) < 20:
            return False
        
        current_atr = atr.iloc[-1]
        avg_atr = atr.iloc[-20:].mean()
        
        return current_atr > avg_atr * multiplier
    
    def should_trade(self, price_data: pd.DataFrame, current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Comprehensive check if trading should be allowed.
        
        Returns:
            Tuple of (should_trade, reason)
        """
        if self.check_news_window(current_time):
            return False, "News window"
        
        if self.check_chop(price_data):
            return False, "Choppy market"
        
        if self.check_volatility_spike(price_data):
            return False, "Volatility spike"
        
        return True, "OK"
