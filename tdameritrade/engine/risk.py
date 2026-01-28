"""
Risk governor: Account limits, behavior lockouts, position sizing.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from account import Account, Group

logger = logging.getLogger(__name__)


class RiskGovernor:
    """
    Risk management system that enforces account limits and behavior constraints.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize risk governor with configuration.
        
        Config structure:
        {
            "daily_max_loss": float,  # Maximum loss per day
            "weekly_max_loss": float,  # Maximum loss per week
            "max_open_risk": float,  # Maximum open risk (BP usage)
            "max_trades_per_day": int,  # Maximum number of trades per day
            "cooldown_minutes": int,  # Minutes between trades
            "loss_cooldown_minutes": int,  # Minutes to pause after 2 losses
            "daily_loss_pause": bool,  # Pause trading if daily max loss hit
            "position_sizing": {
                "method": "fixed_dollar" | "volatility_adjusted",
                "fixed_dollar_risk": float,  # Risk per trade in dollars
                "atr_multiplier": float,  # For volatility-adjusted sizing
                "vix_scaling": bool  # Scale with VIX
            }
        }
        """
        self.config = config
        self.daily_loss = 0.0
        self.weekly_loss = 0.0
        self.trade_count_today = 0
        self.last_trade_time: Optional[datetime] = None
        self.loss_count = 0
        self.loss_pause_until: Optional[datetime] = None
        self.daily_stop_triggered = False
        self.session_start = datetime.now().date()
    
    def reset_daily(self):
        """Reset daily counters (call at start of trading session)."""
        today = datetime.now().date()
        if today != self.session_start:
            self.daily_loss = 0.0
            self.trade_count_today = 0
            self.daily_stop_triggered = False
            self.session_start = today
            logger.info("Daily risk counters reset")
    
    def check_daily_loss(self, account: Account) -> Tuple[bool, str]:
        """
        Check if daily loss limit is reached.
        
        Returns:
            Tuple of (can_trade, reason)
        """
        self.reset_daily()
        
        # Calculate today's P/L
        today_pnl = 0.0
        for group in account.groups:
            if not group.is_open and group.opendt and group.opendt.date() == self.session_start:
                today_pnl += group.profit * 100 * group.qty
        
        self.daily_loss = abs(min(0, today_pnl))  # Only count losses
        
        daily_max = self.config.get("daily_max_loss", float('inf'))
        if self.daily_loss >= daily_max:
            self.daily_stop_triggered = True
            return False, f"Daily max loss reached: ${self.daily_loss:.2f} >= ${daily_max:.2f}"
        
        return True, "OK"
    
    def check_weekly_loss(self, account: Account) -> Tuple[bool, str]:
        """Check if weekly loss limit is reached."""
        # Calculate week's P/L
        week_start = datetime.now() - timedelta(days=7)
        week_pnl = 0.0
        
        for group in account.groups:
            if not group.is_open and group.opendt and group.opendt >= week_start:
                week_pnl += group.profit * 100 * group.qty
        
        self.weekly_loss = abs(min(0, week_pnl))
        weekly_max = self.config.get("weekly_max_loss", float('inf'))
        
        if self.weekly_loss >= weekly_max:
            return False, f"Weekly max loss reached: ${self.weekly_loss:.2f} >= ${weekly_max:.2f}"
        
        return True, "OK"
    
    def check_max_open_risk(self, account: Account, new_risk: float) -> Tuple[bool, str]:
        """
        Check if adding new position would exceed max open risk.
        
        Args:
            account: Account object
            new_risk: Risk (buying power) of new position
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # Calculate current open risk
        current_risk = 0.0
        for group in account.groups:
            if group.is_open:
                # Estimate risk as max loss potential
                # For credit spreads: risk = width - credit received
                # Simplified: use openPrice as proxy
                current_risk += abs(group.openPrice) * 100 * group.qty
        
        total_risk = current_risk + new_risk
        max_risk = self.config.get("max_open_risk", float('inf'))
        
        if total_risk > max_risk:
            return False, f"Max open risk exceeded: ${total_risk:.2f} > ${max_risk:.2f}"
        
        return True, "OK"
    
    def check_trade_cooldown(self) -> Tuple[bool, str]:
        """Check if cooldown period has passed since last trade."""
        if self.last_trade_time is None:
            return True, "OK"
        
        cooldown_minutes = self.config.get("cooldown_minutes", 0)
        if cooldown_minutes == 0:
            return True, "OK"
        
        elapsed = (datetime.now() - self.last_trade_time).total_seconds() / 60
        if elapsed < cooldown_minutes:
            remaining = cooldown_minutes - elapsed
            return False, f"Cooldown active: {remaining:.1f} minutes remaining"
        
        return True, "OK"
    
    def check_loss_cooldown(self) -> Tuple[bool, str]:
        """Check if loss-triggered cooldown is active."""
        if self.loss_pause_until is None:
            return True, "OK"
        
        if datetime.now() < self.loss_pause_until:
            remaining = (self.loss_pause_until - datetime.now()).total_seconds() / 60
            return False, f"Loss cooldown active: {remaining:.1f} minutes remaining"
        
        # Cooldown expired
        self.loss_pause_until = None
        return True, "OK"
    
    def record_trade(self, group: Group, is_loss: bool = False):
        """Record a trade for risk tracking."""
        self.trade_count_today += 1
        self.last_trade_time = datetime.now()
        
        if is_loss:
            self.loss_count += 1
            
            # Check for 2-loss pause
            if self.loss_count >= 2:
                pause_minutes = self.config.get("loss_cooldown_minutes", 60)
                self.loss_pause_until = datetime.now() + timedelta(minutes=pause_minutes)
                self.loss_count = 0  # Reset after pause
                logger.warning(f"2 losses recorded, pausing for {pause_minutes} minutes")
        else:
            # Reset loss count on win
            self.loss_count = 0
    
    def check_max_trades(self) -> Tuple[bool, str]:
        """Check if max trades per day limit is reached."""
        max_trades = self.config.get("max_trades_per_day", float('inf'))
        if self.trade_count_today >= max_trades:
            return False, f"Max trades per day reached: {self.trade_count_today} >= {max_trades}"
        return True, "OK"
    
    def can_trade(self, account: Account, new_risk: float = 0.0) -> Tuple[bool, str]:
        """
        Comprehensive check if trading is allowed.
        
        Args:
            account: Account object
            new_risk: Risk of proposed new position
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check daily stop
        if self.daily_stop_triggered and self.config.get("daily_loss_pause", True):
            return False, "Daily max loss stop triggered"
        
        # Check daily loss
        can_trade, reason = self.check_daily_loss(account)
        if not can_trade:
            return False, reason
        
        # Check weekly loss
        can_trade, reason = self.check_weekly_loss(account)
        if not can_trade:
            return False, reason
        
        # Check max open risk
        can_trade, reason = self.check_max_open_risk(account, new_risk)
        if not can_trade:
            return False, reason
        
        # Check trade cooldown
        can_trade, reason = self.check_trade_cooldown()
        if not can_trade:
            return False, reason
        
        # Check loss cooldown
        can_trade, reason = self.check_loss_cooldown()
        if not can_trade:
            return False, reason
        
        # Check max trades
        can_trade, reason = self.check_max_trades()
        if not can_trade:
            return False, reason
        
        return True, "OK"
    
    def calculate_position_size(self, group: Group, account: Account,
                               atr: Optional[float] = None, vix: Optional[float] = None) -> int:
        """
        Calculate position size based on risk parameters.
        
        Args:
            group: Group to size
            account: Account object
            atr: Current ATR value (for volatility-adjusted sizing)
            vix: Current VIX value (for VIX scaling)
        
        Returns:
            Number of contracts
        """
        sizing_config = self.config.get("position_sizing", {})
        method = sizing_config.get("method", "fixed_dollar")
        
        if method == "fixed_dollar":
            fixed_risk = sizing_config.get("fixed_dollar_risk", 100.0)
            # Estimate risk per contract
            risk_per_contract = abs(group.openPrice) * 100  # Simplified
            if risk_per_contract > 0:
                qty = int(fixed_risk / risk_per_contract)
            else:
                qty = 1
            return max(1, min(qty, 10))  # Cap at 10 contracts
        
        elif method == "volatility_adjusted":
            base_risk = sizing_config.get("fixed_dollar_risk", 100.0)
            atr_mult = sizing_config.get("atr_multiplier", 1.0)
            
            # Adjust for ATR
            if atr is not None:
                # Higher ATR = smaller size
                atr_factor = 1.0 / (1.0 + atr * atr_mult)
            else:
                atr_factor = 1.0
            
            # Adjust for VIX
            if vix is not None and sizing_config.get("vix_scaling", False):
                # Higher VIX = smaller size
                vix_factor = 1.0 / (1.0 + (vix - 15) / 10)  # Normalize around VIX 15
            else:
                vix_factor = 1.0
            
            adjusted_risk = base_risk * atr_factor * vix_factor
            risk_per_contract = abs(group.openPrice) * 100
            if risk_per_contract > 0:
                qty = int(adjusted_risk / risk_per_contract)
            else:
                qty = 1
            return max(1, min(qty, 10))
        
        else:
            # Default: 1 contract
            return 1
