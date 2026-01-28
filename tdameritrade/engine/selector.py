"""
Strategy selector: Chooses strategy mode based on market regime.
"""
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd
from strategies.filters import VPZoneDetector, FVGDetector, ADDRegimeClassifier, ATRRegimeClassifier, NoTradeFilter
from strategies.butterflies import ButterflyBuilder, ButterflyEntryRules
from strategies.strangles import StrangleBuilder, StrangleEntryRules

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Selects appropriate strategy based on market regime and conditions.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize strategy selector.
        
        Config structure:
        {
            "account_policy": "TOS" | "FIDELITY",  # Aggressive vs conservative
            "strategies": {
                "butterfly": {...},
                "strangle": {...}
            }
        }
        """
        self.config = config
        self.account_policy = config.get("account_policy", "TOS")
        
        # Initialize detectors
        self.vp_detector = VPZoneDetector()
        self.fvg_detector = FVGDetector()
        self.add_classifier = ADDRegimeClassifier()
        self.atr_classifier = ATRRegimeClassifier()
        self.no_trade_filter = NoTradeFilter()
        
        # Initialize strategy builders
        self.butterfly_builder = ButterflyBuilder()
        self.butterfly_entry = ButterflyEntryRules()
        self.strangle_builder = StrangleBuilder()
        self.strangle_entry = StrangleEntryRules()
    
    def select_strategy(self, price_data: pd.DataFrame, volume_data: pd.Series,
                       chain: pd.DataFrame, underlying_price: float,
                       iv: float, vix: Optional[float] = None) -> Tuple[Optional[str], str, Dict]:
        """
        Select strategy mode based on current market conditions.
        
        Strategy modes:
        - "STRANGLE": Neutral IV decay strategy
        - "BUTTERFLY_BULLISH": Directional bullish butterfly
        - "BUTTERFLY_BEARISH": Directional bearish butterfly
        - "NO_TRADE": Unsafe conditions
        
        Args:
            price_data: OHLC price data
            volume_data: Volume data
            chain: Options chain
            underlying_price: Current underlying price
            iv: Implied volatility
            vix: Optional VIX value
        
        Returns:
            Tuple of (strategy_mode, reason, strategy_params)
        """
        # First check: no-trade filters
        should_trade, reason = self.no_trade_filter.should_trade(price_data)
        if not should_trade:
            return "NO_TRADE", reason, {}
        
        # Classify regimes
        add_regime = self.add_classifier.classify(price_data, volume_data)
        atr_regime = self.atr_classifier.classify_regime(price_data)
        
        # Detect zones and gaps
        vp_zones = self.vp_detector.detect_zones(price_data, volume_data)
        fvgs = self.fvg_detector.detect_fvgs(price_data)
        
        # Strategy selection logic
        strategy_mode, reason, params = self._select_based_on_regime(
            add_regime, atr_regime, vp_zones, fvgs, underlying_price,
            price_data, volume_data, chain, iv, vix
        )
        
        return strategy_mode, reason, params
    
    def _select_based_on_regime(self, add_regime: str, atr_regime: str,
                               vp_zones: List[Dict], fvgs: List[Dict],
                               underlying_price: float, price_data: pd.DataFrame,
                               volume_data: pd.Series, chain: pd.DataFrame,
                               iv: float, vix: Optional[float]) -> Tuple[str, str, Dict]:
        """
        Select strategy based on regime classification.
        """
        # Check for strangle conditions (neutral regime)
        if add_regime in ["BALANCED", "CHOP"]:
            # Check strangle entry conditions
            can_enter, reason = self.strangle_entry.check_entry_conditions(
                price_data, volume_data, iv
            )
            
            if can_enter:
                # Determine if power hour
                is_ph = self.strangle_entry.is_power_hour()
                
                # Select delta/width
                call_delta, put_delta = self.strangle_builder.select_delta_width(
                    underlying_price, iv, days_to_exp=0, regime=add_regime
                )
                
                params = {
                    "call_delta": call_delta,
                    "put_delta": put_delta,
                    "days_to_exp": 0 if is_ph else 5,
                    "power_hour": is_ph
                }
                
                return "STRANGLE", reason, params
        
        # Check for directional butterfly conditions
        if add_regime == "ACCUMULATION":
            # Bullish butterfly
            can_enter, reason = self.butterfly_entry.check_entry_conditions(
                price_data, volume_data, underlying_price, "BULLISH"
            )
            
            if can_enter:
                confirmations = self.butterfly_entry.get_confirmation_signals(price_data)
                params = {
                    "direction": "BULLISH",
                    "target_delta": 0.15,
                    "days_to_exp": 0,
                    "confirmations": confirmations
                }
                return "BUTTERFLY_BULLISH", reason, params
        
        elif add_regime == "DISTRIBUTION":
            # Bearish butterfly
            can_enter, reason = self.butterfly_entry.check_entry_conditions(
                price_data, volume_data, underlying_price, "BEARISH"
            )
            
            if can_enter:
                confirmations = self.butterfly_entry.get_confirmation_signals(price_data)
                params = {
                    "direction": "BEARISH",
                    "target_delta": 0.15,
                    "days_to_exp": 0,
                    "confirmations": confirmations
                }
                return "BUTTERFLY_BEARISH", reason, params
        
        # Default: no trade
        return "NO_TRADE", f"Regime {add_regime} + {atr_regime} ATR - no suitable strategy", {}
    
    def apply_account_policy(self, strategy_mode: str, params: Dict) -> Tuple[str, Dict]:
        """
        Apply account-specific policy adjustments.
        
        TOS (aggressive): Tighter stops, more risk
        FIDELITY (conservative): Wider stops, less risk, prefer strangles
        """
        adjusted_params = params.copy()
        
        if self.account_policy == "FIDELITY":
            # Conservative: prefer strangles, wider stops
            if strategy_mode == "STRANGLE":
                # Wider strangle
                adjusted_params["call_delta"] = params.get("call_delta", 0.15) * 0.9
                adjusted_params["put_delta"] = params.get("put_delta", 0.15) * 0.9
                adjusted_params["exit_value"] = 2.5  # Wider stop (250% vs 200%)
            elif "BUTTERFLY" in strategy_mode:
                # Tighter butterfly, wider stops
                adjusted_params["target_delta"] = params.get("target_delta", 0.15) * 0.8
                adjusted_params["exit_value"] = 2.5
        
        elif self.account_policy == "TOS":
            # Aggressive: tighter stops, more directional
            if strategy_mode == "STRANGLE":
                adjusted_params["exit_value"] = 1.8  # Tighter stop (180%)
            elif "BUTTERFLY" in strategy_mode:
                adjusted_params["exit_value"] = 1.8
        
        return strategy_mode, adjusted_params
