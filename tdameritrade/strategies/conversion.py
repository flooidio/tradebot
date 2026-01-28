"""
Strategy conversion: Convert strangle to butterfly/broken-wing fly.
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging
import pandas as pd
from account import Group, Option
from strategies.butterflies import ButterflyBuilder

logger = logging.getLogger(__name__)


class StrategyConverter:
    """
    Converts strangles to butterflies or broken-wing flies to book profit or reduce loss.
    """
    
    def __init__(self):
        self.butterfly_builder = ButterflyBuilder()
    
    def convert_strangle_to_butterfly(self, strangle: Group, chain: pd.DataFrame,
                                     underlying_price: float, direction: str,
                                     threatened_side: Optional[str] = None) -> Optional[Group]:
        """
        Convert a strangle to a butterfly.
        
        Conversion logic:
        - If call side threatened: convert to call butterfly (protect call, profit from put)
        - If put side threatened: convert to put butterfly (protect put, profit from call)
        - If both sides OK: convert based on direction for profit booking
        
        Args:
            strangle: Existing strangle group
            chain: Options chain DataFrame
            underlying_price: Current underlying price
            direction: 'BULLISH' or 'BEARISH' (for profit booking)
            threatened_side: 'CALL' or 'PUT' if one side is threatened
        
        Returns:
            New butterfly group, or None if conversion not possible
        """
        if not strangle.is_open:
            logger.warning("Cannot convert closed strangle")
            return None
        
        if len(strangle.options) != 2:
            logger.warning("Strangle must have exactly 2 legs")
            return None
        
        # Identify call and put legs
        call_leg = None
        put_leg = None
        
        for opt in strangle.options:
            if opt.quote is None:
                continue
            
            put_call = opt.quote.get('putCall', '')
            if put_call == 'CALL':
                call_leg = opt
            elif put_call == 'PUT':
                put_leg = opt
        
        if call_leg is None or put_leg is None:
            logger.warning("Could not identify call and put legs")
            return None
        
        # Determine conversion direction
        if threatened_side == 'CALL':
            # Protect call side: convert to call butterfly
            conversion_direction = 'BEARISH'  # Bearish = put butterfly (protects downside)
            use_leg = call_leg
        elif threatened_side == 'PUT':
            # Protect put side: convert to put butterfly
            conversion_direction = 'BULLISH'  # Bullish = call butterfly (protects upside)
            use_leg = put_leg
        else:
            # Profit booking: use direction parameter
            conversion_direction = direction
            use_leg = call_leg if direction == 'BULLISH' else put_leg
        
        # Get expiration from existing leg
        exp_date = use_leg.exp_date
        days_to_exp = (exp_date - datetime.now().date()).days if exp_date else 0
        
        # Build butterfly using threatened/profit leg as base
        butterfly = self.butterfly_builder.build_directional_otm_fly(
            chain=chain,
            underlying_price=underlying_price,
            direction=conversion_direction,
            target_delta=0.15,
            days_to_exp=days_to_exp
        )
        
        if butterfly is None:
            logger.warning("Could not build butterfly for conversion")
            return None
        
        butterfly.name = f"CONVERTED_{strangle.name}_{conversion_direction}"
        
        return butterfly
    
    def convert_strangle_to_broken_wing(self, strangle: Group, chain: pd.DataFrame,
                                       underlying_price: float, direction: str) -> Optional[Group]:
        """
        Convert strangle to broken-wing fly for better risk/reward.
        
        Similar to butterfly conversion but with asymmetric wings.
        
        Args:
            strangle: Existing strangle group
            chain: Options chain DataFrame
            underlying_price: Current underlying price
            direction: 'BULLISH' or 'BEARISH'
        
        Returns:
            New broken-wing fly group
        """
        if not strangle.is_open:
            return None
        
        # Get expiration
        exp_date = strangle.options[0].exp_date if strangle.options else None
        days_to_exp = (exp_date - datetime.now().date()).days if exp_date else 0
        
        # Build broken-wing fly
        broken_wing = self.butterfly_builder.build_broken_wing_fly(
            chain=chain,
            underlying_price=underlying_price,
            direction=direction,
            risk_reward_ratio=2.0,
            days_to_exp=days_to_exp
        )
        
        if broken_wing is None:
            return None
        
        broken_wing.name = f"CONVERTED_BROKEN_WING_{strangle.name}"
        
        return broken_wing
    
    def should_convert_for_profit(self, strangle: Group, profit_target_pct: float = 0.5) -> bool:
        """
        Check if strangle should be converted to butterfly to book profit.
        
        Args:
            strangle: Strangle group
            profit_target_pct: Profit target as percentage of credit (default 50%)
        
        Returns:
            True if should convert
        """
        if not strangle.is_open:
            return False
        
        current_price = strangle.get_group_price()
        profit = strangle.openPrice - current_price  # For credit spreads, openPrice is positive
        profit_pct = profit / abs(strangle.openPrice)
        
        return profit_pct >= profit_target_pct
    
    def should_convert_for_loss_reduction(self, strangle: Group, loss_threshold_pct: float = 0.5) -> bool:
        """
        Check if strangle should be converted to reduce loss.
        
        Args:
            strangle: Strangle group
            loss_threshold_pct: Loss threshold as percentage of credit (default 50%)
        
        Returns:
            True if should convert
        """
        if not strangle.is_open:
            return False
        
        current_price = strangle.get_group_price()
        loss = current_price - strangle.openPrice
        loss_pct = loss / abs(strangle.openPrice)
        
        # Convert if loss is approaching stop but not yet hit
        return 0.3 <= loss_pct <= loss_threshold_pct
