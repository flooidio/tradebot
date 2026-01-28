"""
Butterfly strategy implementations: directional OTM fly, broken-wing fly.
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from account import Group, Option
from strategies.filters import VPZoneDetector, FVGDetector, ADDRegimeClassifier

logger = logging.getLogger(__name__)


class ButterflyBuilder:
    """
    Builds butterfly and broken-wing fly strategies from options chain.
    """
    
    def __init__(self):
        self.vp_detector = VPZoneDetector()
        self.fvg_detector = FVGDetector()
        self.add_classifier = ADDRegimeClassifier()
    
    def build_directional_otm_fly(self, chain: pd.DataFrame, underlying_price: float,
                                 direction: str, target_delta: float = 0.15,
                                 days_to_exp: int = 0) -> Optional[Group]:
        """
        Build a directional OTM butterfly.
        
        Directional butterfly structure:
        - Long 1x lower strike (OTM)
        - Short 2x middle strike (ATM/OTM)
        - Long 1x higher strike (OTM)
        
        Args:
            chain: Options chain DataFrame
            underlying_price: Current underlying price
            direction: 'BULLISH' or 'BEARISH'
            target_delta: Target delta for wings
            days_to_exp: Target days to expiration
        
        Returns:
            Group object with butterfly legs, or None if can't build
        """
        # Filter chain for target expiration
        if days_to_exp > 0:
            exp_filter = (chain['daysToExpiration'] == days_to_exp)
            chain = chain[exp_filter]
        
        if len(chain) == 0:
            logger.warning(f"No options found for {days_to_exp} DTE")
            return None
        
        # Select option type based on direction
        option_type = 'CALL' if direction == 'BULLISH' else 'PUT'
        type_filter = chain['putCall'] == option_type
        chain = chain[type_filter]
        
        if len(chain) == 0:
            logger.warning(f"No {option_type} options found")
            return None
        
        # Find strikes near target delta
        chain['delta_abs'] = chain['delta'].abs()
        chain_sorted = chain.sort_values('delta_abs')
        
        # Find lower wing (target delta)
        lower_wing = chain_sorted[chain_sorted['delta_abs'] <= target_delta].iloc[0] if len(chain_sorted[chain_sorted['delta_abs'] <= target_delta]) > 0 else None
        
        if lower_wing is None:
            logger.warning(f"Could not find lower wing with delta ~{target_delta}")
            return None
        
        # Find middle strike (ATM, delta ~0.5 for calls, ~-0.5 for puts)
        target_mid_delta = 0.5 if direction == 'BULLISH' else -0.5
        mid_candidates = chain_sorted[(chain_sorted['delta'] >= target_mid_delta * 0.8) & 
                                      (chain_sorted['delta'] <= target_mid_delta * 1.2)]
        
        if len(mid_candidates) == 0:
            # Fallback: use strike closest to underlying
            mid_strike = chain_sorted.iloc[(chain_sorted['strikePrice'] - underlying_price).abs().argsort()[:1]]
        else:
            mid_strike = mid_candidates.iloc[0]
        
        # Find upper wing (symmetric to lower wing)
        lower_strike = lower_wing['strikePrice']
        mid_strike_price = mid_strike['strikePrice']
        upper_strike = mid_strike_price + (mid_strike_price - lower_strike)
        
        # Find option closest to upper strike
        upper_wing = chain_sorted.iloc[(chain_sorted['strikePrice'] - upper_strike).abs().argsort()[:1]]
        
        # Build legs
        legs = []
        
        # Long lower wing
        lower_opt = Option(lower_wing['symbol'])
        lower_opt.open(lower_wing, qty=1, pos='LONG', exit_type='stop', exit_value=0.5)
        legs.append(lower_opt)
        
        # Short middle (x2)
        mid_opt1 = Option(mid_strike['symbol'])
        mid_opt1.open(mid_strike, qty=1, pos='SHORT', exit_type='stop', exit_value=2.0)
        legs.append(mid_opt1)
        
        mid_opt2 = Option(mid_strike['symbol'])
        mid_opt2.open(mid_strike, qty=1, pos='SHORT', exit_type='stop', exit_value=2.0)
        legs.append(mid_opt2)
        
        # Long upper wing
        upper_opt = Option(upper_wing['symbol'])
        upper_opt.open(upper_wing, qty=1, pos='LONG', exit_type='stop', exit_value=0.5)
        legs.append(upper_opt)
        
        # Create group
        group = Group(legs, name=f"{direction}_BUTTERFLY_{days_to_exp}DTE")
        group.open(qty=1, exit_type='stop', exit_value=2.0)
        
        return group
    
    def build_broken_wing_fly(self, chain: pd.DataFrame, underlying_price: float,
                             direction: str, risk_reward_ratio: float = 2.0,
                             days_to_exp: int = 0) -> Optional[Group]:
        """
        Build a broken-wing butterfly (asymmetric risk/reward).
        
        Broken-wing fly structure:
        - Long 1x lower strike
        - Short 2x middle strike
        - Long 1x higher strike (further OTM for better risk/reward)
        
        Args:
            chain: Options chain DataFrame
            underlying_price: Current underlying price
            direction: 'BULLISH' or 'BEARISH'
            risk_reward_ratio: Desired risk/reward ratio
            days_to_exp: Target days to expiration
        
        Returns:
            Group object with broken-wing fly legs
        """
        # Similar to directional fly but with asymmetric upper wing
        # Start with regular fly
        base_fly = self.build_directional_otm_fly(chain, underlying_price, direction, 
                                                   target_delta=0.15, days_to_exp=days_to_exp)
        
        if base_fly is None:
            return None
        
        # Adjust upper wing to improve risk/reward
        # Move upper wing further OTM
        upper_leg = base_fly.options[-1]
        
        # Find more OTM option
        option_type = 'CALL' if direction == 'BULLISH' else 'PUT'
        type_filter = chain['putCall'] == option_type
        chain_filtered = chain[type_filter]
        
        if len(chain_filtered) == 0:
            return base_fly
        
        # Get current upper strike
        current_upper_strike = upper_leg.quote['strikePrice'].item() if hasattr(upper_leg.quote['strikePrice'], 'item') else upper_leg.quote['strikePrice']
        
        # Find next strike further OTM
        if direction == 'BULLISH':
            otm_options = chain_filtered[chain_filtered['strikePrice'] > current_upper_strike]
        else:
            otm_options = chain_filtered[chain_filtered['strikePrice'] < current_upper_strike]
        
        if len(otm_options) > 0:
            new_upper = otm_options.iloc[0]
            upper_leg.symbol = new_upper['symbol']
            upper_leg.quote = new_upper
            # Recalculate open price
            ask = new_upper['ask'].item() if hasattr(new_upper['ask'], 'item') else new_upper['ask']
            upper_leg.openPrice = -ask  # LONG position
        
        base_fly.name = f"{direction}_BROKEN_WING_{days_to_exp}DTE"
        return base_fly


class ButterflyEntryRules:
    """
    Entry rules for butterfly strategies based on VP, FVG, and ADD alignment.
    """
    
    def __init__(self):
        self.vp_detector = VPZoneDetector()
        self.fvg_detector = FVGDetector()
        self.add_classifier = ADDRegimeClassifier()
    
    def check_entry_conditions(self, price_data: pd.DataFrame, volume_data: pd.Series,
                              underlying_price: float, direction: str) -> Tuple[bool, str]:
        """
        Check if entry conditions are met for butterfly.
        
        Entry conditions:
        1. VP zone alignment (price near VP zone)
        2. Unfilled FVG in direction
        3. ADD regime supports direction
        4. No conflicting signals
        
        Returns:
            Tuple of (should_enter, reason)
        """
        # Check ADD regime
        regime = self.add_classifier.classify(price_data, volume_data)
        if direction == 'BULLISH' and regime != 'ACCUMULATION':
            return False, f"ADD regime {regime} does not support {direction}"
        if direction == 'BEARISH' and regime != 'DISTRIBUTION':
            return False, f"ADD regime {regime} does not support {direction}"
        
        # Check VP zones
        vp_zones = self.vp_detector.detect_zones(price_data, volume_data)
        near_zone = self.vp_detector.is_near_zone(underlying_price)
        if not near_zone:
            return False, "Price not near VP zone"
        
        # Check FVG
        fvgs = self.fvg_detector.detect_fvgs(price_data)
        unfilled_fvgs = self.fvg_detector.get_unfilled_fvgs()
        
        # Check for FVG in direction
        directional_fvg = None
        for fvg in unfilled_fvgs:
            if direction == 'BULLISH' and fvg['type'] == 'BULLISH':
                if fvg['low'] <= underlying_price <= fvg['high']:
                    directional_fvg = fvg
                    break
            elif direction == 'BEARISH' and fvg['type'] == 'BEARISH':
                if fvg['low'] <= underlying_price <= fvg['high']:
                    directional_fvg = fvg
                    break
        
        if not directional_fvg:
            return False, f"No unfilled {direction} FVG found"
        
        # All conditions met
        return True, f"VP zone + {direction} FVG + {regime} regime aligned"
    
    def get_confirmation_signals(self, price_data: pd.DataFrame) -> List[str]:
        """
        Get additional confirmation signals.
        
        Returns:
            List of confirmation signal descriptions
        """
        confirmations = []
        
        # Check for momentum
        if len(price_data) >= 5:
            recent_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-5]) / price_data['close'].iloc[-5]
            if abs(recent_change) > 0.01:
                confirmations.append(f"Momentum: {recent_change*100:.2f}%")
        
        # Check volume
        if 'volume' in price_data.columns:
            recent_volume = price_data['volume'].iloc[-5:].mean()
            avg_volume = price_data['volume'].iloc[-20:].mean() if len(price_data) >= 20 else recent_volume
            if recent_volume > avg_volume * 1.2:
                confirmations.append("Volume confirmation")
        
        return confirmations


class ButterflyManagement:
    """
    Management rules for butterfly positions: targets, stops, salvage logic.
    """
    
    def __init__(self):
        pass
    
    def check_profit_target(self, group: Group, target_pct: float = 0.5) -> bool:
        """
        Check if profit target is reached.
        
        Args:
            group: Butterfly group
            target_pct: Target profit as percentage of max profit (default 50%)
        
        Returns:
            True if target reached
        """
        if not group.is_open:
            return False
        
        current_price = group.get_group_price()
        max_profit = abs(group.openPrice) * target_pct  # Simplified
        
        # For debit butterflies, profit = openPrice - current_price
        profit = group.openPrice - current_price
        
        return profit >= max_profit
    
    def check_stop_loss(self, group: Group, stop_pct: float = 2.0) -> bool:
        """
        Check if stop loss is hit.
        
        Args:
            group: Butterfly group
            stop_pct: Stop loss as multiple of debit (default 200%)
        
        Returns:
            True if stop hit
        """
        return group.should_exit()
    
    def should_roll(self, group: Group, days_to_exp: int, min_dte: int = 3) -> bool:
        """
        Check if position should be rolled to next expiration.
        
        Args:
            group: Butterfly group
            days_to_exp: Current days to expiration
            min_dte: Minimum DTE before rolling
        
        Returns:
            True if should roll
        """
        if days_to_exp <= min_dte and group.is_open:
            return True
        return False
    
    def salvage_logic(self, group: Group, underlying_price: float) -> Optional[str]:
        """
        Determine salvage action for threatened position.
        
        Options:
        - "CLOSE": Close entire position
        - "ADJUST": Adjust strikes
        - "ROLL": Roll to next expiration
        - None: No action needed
        
        Returns:
            Salvage action string or None
        """
        if not group.is_open:
            return None
        
        current_price = group.get_group_price()
        loss_pct = (current_price - group.openPrice) / abs(group.openPrice)
        
        # If loss > 150%, close
        if loss_pct > 1.5:
            return "CLOSE"
        
        # If loss > 100% and near expiration, consider adjusting
        if loss_pct > 1.0:
            # Check if any leg is ITM
            for opt in group.options:
                strike = opt.quote.get('strikePrice', 0)
                if opt.pos == 'LONG' and opt.quote.get('putCall') == 'CALL':
                    if underlying_price > strike:
                        return "ADJUST"  # Call is ITM
                elif opt.pos == 'LONG' and opt.quote.get('putCall') == 'PUT':
                    if underlying_price < strike:
                        return "ADJUST"  # Put is ITM
        
        return None
