"""
Execution engine: converts trading decisions into broker orders.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from account import Group, Option
from engine.broker import BrokerAdapter, PaperBrokerAdapter

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Execution engine that converts strategy decisions into broker orders.
    Handles multi-leg orders, OCO orders, and fallback logic.
    """
    
    def __init__(self, broker: BrokerAdapter, paper_mode: bool = False):
        """
        Initialize execution engine.
        
        Args:
            broker: Broker adapter instance
            paper_mode: If True, use paper trading (overrides broker setting)
        """
        if paper_mode:
            self.broker = PaperBrokerAdapter()
        else:
            self.broker = broker
        self.paper_mode = paper_mode
        self.order_history: List[Dict] = []
    
    def execute_group(self, group: Group, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a multi-leg group order.
        
        Args:
            group: Group object with option legs
            account_id: Optional account ID override
        
        Returns:
            Order response from broker
        """
        if not group.is_open:
            raise ValueError("Cannot execute closed group")
        
        if len(group.options) == 0:
            raise ValueError("Group has no option legs")
        
        # Build order leg collection
        order_legs = []
        for opt in group.options:
            if not opt.is_open:
                raise ValueError(f"Option {opt.symbol} is not open")
            
            instruction = self._get_instruction(opt.pos, opt.is_open)
            
            order_legs.append({
                "instruction": instruction,
                "quantity": opt.qty,
                "instrument": {
                    "symbol": opt.symbol,
                    "assetType": "OPTION"
                }
            })
        
        # Determine order type and price
        # For multi-leg orders, we need net price
        net_price = group.get_group_price()
        
        # Build order
        order = {
            "orderType": "LIMIT",  # Use LIMIT for better execution
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": abs(net_price),  # Price is always positive
            "orderLegCollection": order_legs
        }
        
        # Try to place order
        try:
            response = self.broker.place_order(order)
            order_id = response.get("orderId")
            
            logger.info(f"Placed order {order_id} for group {group.name}: {len(order_legs)} legs")
            
            # Store in history
            self.order_history.append({
                "order_id": order_id,
                "group_name": group.name,
                "timestamp": datetime.now(),
                "order": order,
                "response": response
            })
            
            return response
        
        except Exception as e:
            logger.error(f"Failed to place order for group {group.name}: {e}")
            # Fallback: try individual legs if broker doesn't support multi-leg
            if len(order_legs) > 1:
                logger.warning("Attempting fallback to individual leg orders")
                return self._execute_legs_individually(group, order_legs)
            raise
    
    def _execute_legs_individually(self, group: Group, order_legs: List[Dict]) -> Dict[str, Any]:
        """
        Fallback: execute legs individually if broker doesn't support multi-leg.
        """
        results = []
        for i, leg in enumerate(order_legs):
            opt = group.options[i]
            net_price = abs(opt.openPrice)
            
            single_order = {
                "orderType": "LIMIT",
                "session": "NORMAL",
                "duration": "DAY",
                "orderStrategyType": "SINGLE",
                "price": net_price,
                "orderLegCollection": [leg]
            }
            
            try:
                response = self.broker.place_order(single_order)
                results.append(response)
                logger.info(f"Placed individual leg order for {opt.symbol}")
            except Exception as e:
                logger.error(f"Failed to place leg order for {opt.symbol}: {e}")
                # Cancel previous legs if one fails
                for prev_result in results:
                    if "orderId" in prev_result:
                        self.broker.cancel_order(prev_result["orderId"])
                raise
        
        return {
            "orderId": f"MULTI_{datetime.now().timestamp()}",
            "status": "PARTIAL",
            "legs": results
        }
    
    def _get_instruction(self, position: str, is_opening: bool) -> str:
        """
        Convert position type to broker instruction.
        
        Args:
            position: 'LONG' or 'SHORT'
            is_opening: True if opening new position
        
        Returns:
            Broker instruction string
        """
        if position == "LONG":
            return "BUY_TO_OPEN" if is_opening else "BUY_TO_CLOSE"
        elif position == "SHORT":
            return "SELL_TO_OPEN" if is_opening else "SELL_TO_CLOSE"
        else:
            raise ValueError(f"Invalid position: {position}")
    
    def cancel_group_order(self, order_id: str) -> bool:
        """Cancel an order by ID."""
        return self.broker.cancel_order(order_id)
    
    def replace_group_order(self, order_id: str, group: Group) -> Dict[str, Any]:
        """Replace an existing order with updated group parameters."""
        # Build new order (same as execute_group)
        order_legs = []
        for opt in group.options:
            instruction = self._get_instruction(opt.pos, opt.is_open)
            order_legs.append({
                "instruction": instruction,
                "quantity": opt.qty,
                "instrument": {
                    "symbol": opt.symbol,
                    "assetType": "OPTION"
                }
            })
        
        net_price = group.get_group_price()
        order = {
            "orderType": "LIMIT",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "price": abs(net_price),
            "orderLegCollection": order_legs
        }
        
        return self.broker.replace_order(order_id, order)
    
    def check_fills(self, order_id: str) -> List[Dict[str, Any]]:
        """Check if order has been filled."""
        return self.broker.get_fills(order_id)
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders from broker."""
        # Note: This would need broker-specific implementation
        # For now, return from history
        return [o for o in self.order_history if o.get("response", {}).get("status") != "FILLED"]
