"""
Position manager: Monitors open positions and executes exit/adjustment logic.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import pandas as pd
from account import Account, Group, Option
from strategies.butterflies import ButterflyManagement
from strategies.strangles import StrangleRiskTriggers
from strategies.conversion import StrategyConverter
from engine.execution import ExecutionEngine

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Autonomous trade management system.
    Monitors each open Group and executes exit/adjustment actions.
    """
    
    def __init__(self, execution_engine: ExecutionEngine):
        """
        Initialize position manager.
        
        Args:
            execution_engine: Execution engine for placing orders
        """
        self.execution_engine = execution_engine
        self.butterfly_mgmt = ButterflyManagement()
        self.strangle_risk = StrangleRiskTriggers()
        self.converter = StrategyConverter()
    
    def manage_positions(self, account: Account, underlying_price: float,
                        price_data: Optional[pd.DataFrame] = None,
                        chain: Optional[pd.DataFrame] = None) -> List[Dict]:
        """
        Manage all open positions in account.
        
        Args:
            account: Account with open positions
            underlying_price: Current underlying price
            price_data: Optional price history for indicators
            chain: Optional options chain for adjustments
        
        Returns:
            List of actions taken
        """
        actions = []
        
        for group in account.groups:
            if not group.is_open:
                continue
            
            # Update quotes first (should be done by caller)
            # Then evaluate exit conditions
            action = self.evaluate_group(group, underlying_price, price_data, chain)
            
            if action:
                actions.append(action)
                self.execute_action(account, group, action)
        
        return actions
    
    def evaluate_group(self, group: Group, underlying_price: float,
                      price_data: Optional[pd.DataFrame] = None,
                      chain: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        """
        Evaluate exit conditions for a group.
        
        Returns:
            Action dict with type and parameters, or None
        """
        # Check expiration
        days_to_exp = self._get_days_to_exp(group)
        if days_to_exp <= 0:
            return {
                "type": "CLOSE",
                "reason": "Expired",
                "group": group.name
            }
        
        # Check if 0DTE and should close
        if days_to_exp == 0:
            return {
                "type": "CLOSE",
                "reason": "0DTE - forced close",
                "group": group.name
            }
        
        # Strategy-specific evaluation
        if "BUTTERFLY" in group.name or "FLY" in group.name:
            return self._evaluate_butterfly(group, underlying_price, days_to_exp)
        elif "STRANGLE" in group.name:
            return self._evaluate_strangle(group, underlying_price, days_to_exp, chain)
        else:
            # Generic evaluation
            return self._evaluate_generic(group, underlying_price)
    
    def _evaluate_butterfly(self, group: Group, underlying_price: float,
                           days_to_exp: int) -> Optional[Dict]:
        """Evaluate butterfly-specific exit conditions."""
        # Check profit target
        if self.butterfly_mgmt.check_profit_target(group, target_pct=0.5):
            return {
                "type": "CLOSE",
                "reason": "Profit target reached",
                "group": group.name
            }
        
        # Check stop loss
        if self.butterfly_mgmt.check_stop_loss(group, stop_pct=2.0):
            return {
                "type": "CLOSE",
                "reason": "Stop loss hit",
                "group": group.name
            }
        
        # Check if should roll
        if self.butterfly_mgmt.should_roll(group, days_to_exp, min_dte=3):
            return {
                "type": "ROLL",
                "reason": f"Low DTE: {days_to_exp}",
                "group": group.name
            }
        
        # Check salvage logic
        salvage_action = self.butterfly_mgmt.salvage_logic(group, underlying_price)
        if salvage_action:
            return {
                "type": salvage_action,
                "reason": "Salvage logic triggered",
                "group": group.name
            }
        
        return None
    
    def _evaluate_strangle(self, group: Group, underlying_price: float,
                          days_to_exp: int, chain: Optional[pd.DataFrame]) -> Optional[Dict]:
        """Evaluate strangle-specific exit conditions."""
        # Check profit target (convert to butterfly)
        if self.converter.should_convert_for_profit(group, profit_target_pct=0.5):
            if chain is not None:
                # Determine direction based on current price vs entry
                # Simplified: use current price movement
                direction = "BULLISH" if underlying_price > group.openPrice else "BEARISH"
                return {
                    "type": "CONVERT",
                    "reason": "Profit target - convert to butterfly",
                    "group": group.name,
                    "direction": direction
                }
        
        # Check threatened side
        threatened_side = self.strangle_risk.check_threatened_side(group, underlying_price)
        if threatened_side:
            should_defend = self.strangle_risk.should_defend(group, underlying_price, threatened_side)
            
            if should_defend:
                # Convert to butterfly to protect threatened side
                if chain is not None:
                    return {
                        "type": "CONVERT",
                        "reason": f"{threatened_side} side threatened",
                        "group": group.name,
                        "threatened_side": threatened_side
                    }
            else:
                # Close if defense not worth it
                return {
                    "type": "CLOSE",
                    "reason": f"{threatened_side} side threatened, not defending",
                    "group": group.name
                }
        
        # Check loss reduction conversion
        if self.converter.should_convert_for_loss_reduction(group, loss_threshold_pct=0.5):
            if chain is not None:
                return {
                    "type": "CONVERT",
                    "reason": "Loss reduction conversion",
                    "group": group.name
                }
        
        # Generic stop check
        if group.should_exit():
            return {
                "type": "CLOSE",
                "reason": "Stop loss hit",
                "group": group.name
            }
        
        return None
    
    def _evaluate_generic(self, group: Group, underlying_price: float) -> Optional[Dict]:
        """Generic evaluation for unknown strategy types."""
        if group.should_exit():
            return {
                "type": "CLOSE",
                "reason": "Exit condition met",
                "group": group.name
            }
        return None
    
    def _get_days_to_exp(self, group: Group) -> int:
        """Get days to expiration for a group."""
        if not group.options:
            return 0
        
        exp_date = group.options[0].exp_date
        if exp_date is None:
            return 0
        
        if isinstance(exp_date, datetime):
            exp_date = exp_date.date()
        
        today = datetime.now().date()
        days = (exp_date - today).days
        return max(0, days)
    
    def execute_action(self, account: Account, group: Group, action: Dict):
        """
        Execute an action on a group.
        
        Actions:
        - CLOSE: Close the position
        - ROLL: Roll to next expiration
        - CONVERT: Convert to different strategy
        - ADJUST: Adjust strikes
        """
        action_type = action.get("type")
        reason = action.get("reason", "")
        
        if action_type == "CLOSE":
            logger.info(f"Closing {group.name}: {reason}")
            # Update quotes before closing
            # (should be done by caller, but ensure here)
            group.close()
            account.close_group_trade(group)
            
            # Place closing order
            try:
                self.execution_engine.execute_group(group, account_id=None)
            except Exception as e:
                logger.error(f"Error executing close order for {group.name}: {e}")
        
        elif action_type == "CONVERT":
            logger.info(f"Converting {group.name}: {reason}")
            # Conversion logic would go here
            # For now, close and let selector open new position
            group.close()
            account.close_group_trade(group)
        
        elif action_type == "ROLL":
            logger.info(f"Rolling {group.name}: {reason}")
            # Roll logic would go here
            # Close current, open new with next expiration
        
        elif action_type == "ADJUST":
            logger.info(f"Adjusting {group.name}: {reason}")
            # Adjustment logic would go here
        
        else:
            logger.warning(f"Unknown action type: {action_type}")
