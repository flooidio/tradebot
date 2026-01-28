"""
Strangle strategy: IV decay / power hour neutral strategies.
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, time
import logging
from account import Group, Option
from strategies.filters import ADDRegimeClassifier, ATRRegimeClassifier, NoTradeFilter

logger = logging.getLogger(__name__)


class StrangleBuilder:
    """
    Builds strangle strategies from options chain.
    """
    
    def __init__(self):
        self.add_classifier = ADDRegimeClassifier()
        self.atr_classifier = ATRRegimeClassifier()
    
    def build_strangle(self, chain: pd.DataFrame, underlying_price: float,
                      call_delta: float = 0.15, put_delta: float = 0.15,
                      days_to_exp: int = 0, width_pct: float = 0.05) -> Optional[Group]:
        """
        Build a strangle (short call + short put).
        
        Args:
            chain: Options chain DataFrame
            underlying_price: Current underlying price
            call_delta: Target delta for call leg
            put_delta: Target delta for put leg
            days_to_exp: Target days to expiration
            width_pct: Minimum width as percentage of underlying (default 5%)
        
        Returns:
            Group object with strangle legs, or None if can't build
        """
        # Filter for target expiration
        if days_to_exp > 0:
            exp_filter = (chain['daysToExpiration'] == days_to_exp)
            chain = chain[exp_filter]
        
        if len(chain) == 0:
            logger.warning(f"No options found for {days_to_exp} DTE")
            return None
        
        # Separate calls and puts
        calls = chain[chain['putCall'] == 'CALL'].copy()
        puts = chain[chain['putCall'] == 'PUT'].copy()
        
        if len(calls) == 0 or len(puts) == 0:
            logger.warning("Missing calls or puts in chain")
            return None
        
        # Find call near target delta
        calls['delta_abs'] = calls['delta'].abs()
        call_candidates = calls[(calls['delta_abs'] >= call_delta * 0.8) & 
                                (calls['delta_abs'] <= call_delta * 1.2)]
        
        if len(call_candidates) == 0:
            # Fallback: closest to target delta
            call_leg = calls.iloc[(calls['delta_abs'] - call_delta).abs().argsort()[:1]]
        else:
            call_leg = call_candidates.iloc[0]
        
        # Find put near target delta
        puts['delta_abs'] = puts['delta'].abs()
        put_candidates = puts[(puts['delta_abs'] >= put_delta * 0.8) & 
                              (puts['delta_abs'] <= put_delta * 1.2)]
        
        if len(put_candidates) == 0:
            # Fallback: closest to target delta
            put_leg = puts.iloc[(puts['delta_abs'] - put_delta).abs().argsort()[:1]]
        else:
            put_leg = put_candidates.iloc[0]
        
        # Check width
        call_strike = call_leg['strikePrice']
        put_strike = put_leg['strikePrice']
        width = (call_strike - put_strike) / underlying_price
        
        if width < width_pct:
            logger.warning(f"Strangle width {width*100:.2f}% is too narrow (min {width_pct*100:.2f}%)")
            return None
        
        # Build legs
        legs = []
        
        # Short call
        call_opt = Option(call_leg['symbol'])
        call_opt.open(call_leg, qty=1, pos='SHORT', exit_type='stop', exit_value=2.0)
        legs.append(call_opt)
        
        # Short put
        put_opt = Option(put_leg['symbol'])
        put_opt.open(put_leg, qty=1, pos='SHORT', exit_type='stop', exit_value=2.0)
        legs.append(put_opt)
        
        # Create group
        group = Group(legs, name=f"STRANGLE_{days_to_exp}DTE")
        group.open(qty=1, exit_type='stop', exit_value=2.0)
        
        return group
    
    def select_delta_width(self, underlying_price: float, iv: float, 
                          days_to_exp: int, regime: str) -> Tuple[float, float]:
        """
        Select optimal delta and width based on market conditions.
        
        Args:
            underlying_price: Current underlying price
            iv: Implied volatility
            days_to_exp: Days to expiration
            regime: Market regime (BALANCED, CHOP, etc.)
        
        Returns:
            Tuple of (call_delta, put_delta)
        """
        # Base deltas
        base_delta = 0.15
        
        # Adjust for regime
        if regime == "CHOP":
            # Tighter strangle in choppy markets
            base_delta = 0.12
        elif regime == "BALANCED":
            base_delta = 0.15
        else:
            # Wider in trending markets
            base_delta = 0.20
        
        # Adjust for IV
        if iv > 0.3:  # High IV
            base_delta = base_delta * 0.9  # Tighter
        elif iv < 0.15:  # Low IV
            base_delta = base_delta * 1.1  # Wider
        
        # Adjust for DTE
        if days_to_exp <= 1:  # 0DTE
            base_delta = 0.10  # Very tight
        elif days_to_exp <= 3:
            base_delta = base_delta * 0.9
        
        return base_delta, base_delta


class StrangleEntryRules:
    """
    Entry rules for strangle strategies.
    """
    
    def __init__(self):
        self.add_classifier = ADDRegimeClassifier()
        self.atr_classifier = ATRRegimeClassifier()
        self.no_trade_filter = NoTradeFilter()
    
    def check_entry_conditions(self, price_data: pd.DataFrame, volume_data: pd.Series,
                             iv: float) -> Tuple[bool, str]:
        """
        Check if entry conditions are met for strangle.
        
        Entry conditions:
        1. ADD regime is BALANCED or CHOP (neutral)
        2. IV is reasonable (not too low)
        3. Not in news window
        4. Not choppy (contradicts #1 but double-check)
        5. ATR regime is NORMAL or LOW_VOL
        
        Returns:
            Tuple of (should_enter, reason)
        """
        # Check no-trade filters
        should_trade, reason = self.no_trade_filter.should_trade(price_data)
        if not should_trade:
            return False, reason
        
        # Check ADD regime
        regime = self.add_classifier.classify(price_data, volume_data)
        if regime not in ["BALANCED", "CHOP"]:
            return False, f"ADD regime {regime} not suitable for neutral strangle"
        
        # Check IV
        if iv < 0.10:  # Very low IV
            return False, f"IV too low: {iv:.2%}"
        if iv > 0.50:  # Very high IV (may want to wait)
            return False, f"IV very high: {iv:.2%} (consider waiting)"
        
        # Check ATR regime
        atr_regime = self.atr_classifier.classify_regime(price_data)
        if atr_regime == "HIGH_VOL":
            return False, f"ATR regime {atr_regime} indicates high volatility"
        
        # Check for power hour (last hour of trading)
        current_time = datetime.now()
        if current_time.hour >= 15:  # 3 PM = power hour
            # Power hour strangles can be tighter
            return True, f"Power hour + {regime} regime + IV {iv:.2%}"
        
        return True, f"{regime} regime + IV {iv:.2%} + {atr_regime} ATR"
    
    def is_power_hour(self, current_time: Optional[datetime] = None) -> bool:
        """Check if current time is power hour (last hour of trading)."""
        if current_time is None:
            current_time = datetime.now()
        
        # Power hour: 3:00 PM - 4:00 PM ET
        return current_time.hour >= 15


class StrangleRiskTriggers:
    """
    Risk triggers for strangle positions (threatened side detection).
    """
    
    def __init__(self):
        pass
    
    def check_threatened_side(self, group: Group, underlying_price: float,
                             threshold_pct: float = 0.7) -> Optional[str]:
        """
        Check if call or put side is threatened.
        
        A side is "threatened" if underlying price moves toward that strike
        and the option is approaching ITM.
        
        Args:
            group: Strangle group
            underlying_price: Current underlying price
            threshold_pct: Delta threshold (default 70% of strike distance)
        
        Returns:
            'CALL', 'PUT', or None
        """
        if not group.is_open or len(group.options) != 2:
            return None
        
        # Find call and put legs
        call_leg = None
        put_leg = None
        
        for opt in group.options:
            if opt.quote is None:
                continue
            
            put_call = opt.quote.get('putCall', '')
            if put_call == 'CALL':
                call_leg = opt
            elif put_call == 'PUT':
                put_leg = opt
        
        if call_leg is None or put_leg is None:
            return None
        
        # Get strikes
        call_strike = call_leg.quote.get('strikePrice', 0)
        put_strike = put_leg.quote.get('strikePrice', 0)
        
        # Check call side
        call_distance = (call_strike - underlying_price) / underlying_price
        if call_distance < threshold_pct:
            # Check delta
            call_delta = call_leg.quote.get('delta', 0)
            if abs(call_delta) > 0.3:  # Approaching ITM
                return 'CALL'
        
        # Check put side
        put_distance = (underlying_price - put_strike) / underlying_price
        if put_distance < threshold_pct:
            # Check delta
            put_delta = put_leg.quote.get('delta', 0)
            if abs(put_delta) > 0.3:  # Approaching ITM
                return 'PUT'
        
        return None
    
    def should_defend(self, group: Group, underlying_price: float,
                     threatened_side: str) -> bool:
        """
        Determine if threatened side should be defended.
        
        Defense options:
        - Roll the threatened leg
        - Close the threatened leg
        - Convert to butterfly (see conversion.py)
        
        Returns:
            True if should take defensive action
        """
        if threatened_side is None:
            return False
        
        # Get current P/L
        current_price = group.get_group_price()
        profit = group.openPrice - current_price
        
        # If still profitable, consider defending
        if profit > 0:
            return True
        
        # If loss is small, defend
        loss_pct = (current_price - group.openPrice) / abs(group.openPrice)
        if loss_pct < 0.5:  # Less than 50% loss
            return True
        
        # If loss is large, may be better to close
        return False
