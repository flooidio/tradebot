"""
Core model layer for trading bot.
Stabilized with instance attributes, standardized pricing conventions, and lifecycle invariants.
"""
import pandas as pd
from datetime import datetime as dt
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class Account:
    """
    Represents a trading account.
    Tracks balance, open option positions, and grouped strategies.
    """

    def __init__(self, balance: float, name: str = "default"):
        """
        Initialize account with starting balance.
        
        Pricing Convention:
        - openPrice/closePrice represent NET cash flow per contract
        - SHORT positions: positive = credit received
        - LONG positions: negative = debit paid
        - Group prices = sum of all leg prices (already signed)
        """
        self.name: str = name
        self.balance: float = balance
        self.options: List["Option"] = []
        self.groups: List["Group"] = []

        # Optional: position log for backtesting / journaling
        self.pos_df = pd.DataFrame(
            columns=[
                "timestamp",
                "qty",
                "open_price",
                "close_price",
                "current_price",
                "exit_type",
                "exit_value",
                "is_open",
            ]
        )

    def __str__(self):
        return f"Account(name={self.name}, balance={self.balance}, groups={len(self.groups)}, options={len(self.options)})"

    # --- Individual option handling ---

    def open_trade(self, option: "Option"):
        """Record cash impact of opening a single-leg option trade."""
        # openPrice already contains sign based on LONG/SHORT logic in Option.open()
        self.balance += option.openPrice * 100
        self.options.append(option)

    def close_trade(self, option: "Option"):
        """Record cash impact of closing a single-leg option trade."""
        self.balance -= option.closePrice * 100

    # --- Group handling (spreads, flies, strangles, etc.) ---

    def open_group_trade(self, group: "Group"):
        """
        Record cash impact of opening a multi-leg group trade.
        
        Lifecycle Invariant: group must be opened before adding to account.
        """
        if not group.is_open:
            raise ValueError(f"Cannot add unopened group {group.name} to account")
        if group.opendt is None:
            raise ValueError(f"Group {group.name} missing opendt")
        
        # openPrice is already net (sum of all legs with signs)
        self.balance += group.openPrice * 100 * group.qty
        self.groups.append(group)
        logger.info(f"Opened group {group.name}: {group.openPrice:.2f} * {group.qty} = ${group.openPrice * 100 * group.qty:.2f}")

    def close_group_trade(self, group: "Group"):
        """
        Record cash impact of closing a multi-leg group trade.
        
        Lifecycle Invariant: group must be closed before removing from account.
        """
        if group.is_open:
            raise ValueError(f"Cannot close open group {group.name} - call group.close() first")
        if group.closedt is None:
            raise ValueError(f"Group {group.name} missing closedt")
        
        # closePrice is net cost to close (sum of all legs with signs)
        self.balance -= group.closePrice * 100 * group.qty
        logger.info(f"Closed group {group.name}: {group.closePrice:.2f} * {group.qty} = ${group.closePrice * 100 * group.qty:.2f}")

    # Optional: legacy helper, keep if you use it elsewhere
    def open(self, qty, price, exit_type, exit_value):
        """Legacy position logger."""
        order = [dt.now(), qty, price, 0, price, exit_type, exit_value, True]
        self.pos_df = self.pos_df.append(
            pd.Series(order, index=self.pos_df.columns),
            ignore_index=True,
        )


class Group:
    """
    Represents a group of option legs traded as one strategy:
    spreads, butterflies, strangles, etc.
    """

    def __init__(self, options: list["Option"], name: str = ""):
        self.name = name or "group"
        self.options: list[Option] = options

        self.openPrice: float = 0.0
        self.closePrice: float = 0.0
        self.profit: float = 0.0

        self.opendt: dt | None = None
        self.closedt: dt | None = None
        self.groupdt: dt = dt.now()

        self.exit_type: str | None = None  # stop, trailing, limit
        self.exit_value: float | None = None  # absolute group price level
        self.qty: int = 0
        self.is_open: bool = False

    def __str__(self):
        return f"Group(name={self.name}, legs={len(self.options)}, openPrice={self.openPrice}, is_open={self.is_open})"

    def open(self, qty: int, exit_type: str, exit_value: float):
        """
        Open the group with a given quantity and exit rule.
        exit_value is expressed as a multiple of the initial group price.
        """
        self.opendt = dt.now()
        self.qty = qty
        self.exit_type = exit_type  # 'stop', 'trailing', 'limit'

        # Ensure all legs have an openPrice before we sum
        self.openPrice = sum(opt.openPrice for opt in self.options)
        self.profit = 0.0  # realized + unrealized; updated later

        # For a 'stop' rule, exit_value is a multiple of openPrice
        self.exit_value = exit_value * self.openPrice
        self.is_open = True

        print([[opt.symbol, opt.openPrice] for opt in self.options])

    def get_group_price(self, use_mid: bool = False) -> float:
        """
        Compute the current net price of the group based on each leg's quote.
        
        Pricing Convention (source of truth):
        - SHORT legs: use ask (cost to buy back) → positive contribution
        - LONG legs: use bid (value to sell) → negative contribution
        - Net: sum of all legs = current cost to close the entire group
        
        Args:
            use_mid: If True, use (bid+ask)/2 instead of bid/ask
        
        Returns:
            Net price per contract to close the group (positive = costs money, negative = pays money)
        """
        group_price = 0.0
        for opt in self.options:
            if opt.quote is None:
                logger.warning(f"Option {opt.symbol} has no quote for group price calculation")
                continue
            
            # Source of truth: get bid/ask with slippage handling
            bid = opt.quote["bid"].item() if "bid" in opt.quote else 0.0
            ask = opt.quote["ask"].item() if "ask" in opt.quote else 0.0
            
            if use_mid:
                price = (bid + ask) / 2 if (bid > 0 and ask > 0) else opt.quote.get("mark", 0.0)
            else:
                # SHORT: cost to buy back = ask (what we pay)
                # LONG: value to sell = bid (what we receive)
                price = ask if opt.pos == "SHORT" else bid
            
            # Apply sign convention
            group_price += price if opt.pos == "SHORT" else -price
        
        return group_price

    def should_exit(self) -> bool:
        """
        Evaluate exit conditions based on current group price.
        
        Exit Logic:
        - stop: exit when group_price >= exit_value (loss threshold)
        - trailing: exit when price moves against us by trailing amount
        - limit: exit when group_price <= exit_value (profit target)
        
        Returns:
            True if exit conditions are met
        """
        if not self.is_open:
            return False
        if self.exit_type is None or self.exit_value is None:
            return False
        
        # Update quotes first (caller should call update_quote() on all legs)
        group_price = self.get_group_price()
        
        if self.exit_type == "stop":
            # For credit spreads: higher price = loss
            # exit_value is set as multiple of openPrice (e.g., 2.0 = 200% of credit)
            if group_price >= self.exit_value:
                logger.info(f"Stop triggered: group_price {group_price:.2f} >= exit_value {self.exit_value:.2f}")
                return True
        
        elif self.exit_type == "limit":
            # Profit target: lower price = profit (for credit spreads)
            if group_price <= self.exit_value:
                logger.info(f"Limit triggered: group_price {group_price:.2f} <= exit_value {self.exit_value:.2f}")
                return True
        
        elif self.exit_type == "trailing":
            # TODO: implement trailing stop logic
            pass
        
        return False

    def close(self):
        """Close the group and all its legs at current market quotes."""
        self.closedt = dt.now()
        self.closePrice = self.get_group_price()
        # Profit: what we paid (openPrice) minus what it costs to close now.
        self.profit = self.openPrice - self.closePrice
        self.is_open = False

        for opt in self.options:
            opt.close(opt.qty)

    # Helpers for future strategy logic (strangle → butterfly, adjustments, etc.)
    def add_leg(self, option: "Option"):
        self.options.append(option)

    def remove_leg(self, option: "Option"):
        self.options = [opt for opt in self.options if opt is not option]


class Option:
    """
    Represents a single option leg in a strategy.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

        self.quote: pd.Series | None = None
        self.pos: str | None = None  # 'LONG' or 'SHORT'
        self.opendt: dt | None = None
        self.closedt: dt | None = None

        self.qty: int = 0
        self.openPrice: float = 0.0
        self.closePrice: float = 0.0
        self.profit: float = 0.0

        self.exit_type: str | None = None  # stop, trailing, limit
        self.exit_value: float | None = None

        self.exp_date = None
        self.expired: bool = False
        self.is_open: bool = False

    def __str__(self):
        return f"Option(symbol={self.symbol}, pos={self.pos}, openPrice={self.openPrice}, is_open={self.is_open})"

    def open(self, quote: pd.Series, qty: int, pos: str, exit_type: str, exit_value: float):
        """
        Open the option leg based on current quote.
        
        Lifecycle Invariant: Must have valid quote, qty > 0, valid position type.
        
        Pricing Convention (source of truth):
        - SHORT: we sell at bid, but cost to close = ask → openPrice = ask (positive)
        - LONG: we buy at ask, but value to close = bid → openPrice = -bid (negative)
        
        Args:
            quote: pandas Series with bid, ask, mark, and option metadata
            qty: number of contracts
            pos: 'LONG' or 'SHORT'
            exit_type: 'stop', 'limit', or 'trailing'
            exit_value: multiple of openPrice for stop/limit logic
        """
        # Validation
        if qty <= 0:
            raise ValueError(f"Quantity must be positive, got {qty}")
        if pos not in ["LONG", "SHORT"]:
            raise ValueError(f"Position must be LONG or SHORT, got {pos}")
        if "bid" not in quote or "ask" not in quote:
            raise ValueError(f"Quote missing bid/ask for {self.symbol}")
        
        self.quote = quote
        self.pos = pos
        self.opendt = dt.now()
        self.qty = qty
        self.exit_type = exit_type

        # Source of truth: get pricing with validation
        ask = float(quote["ask"].item()) if hasattr(quote["ask"], "item") else float(quote["ask"])
        bid = float(quote["bid"].item()) if hasattr(quote["bid"], "item") else float(quote["bid"])
        
        if ask <= 0 or bid <= 0:
            logger.warning(f"Invalid bid/ask for {self.symbol}: bid={bid}, ask={ask}")

        # Pricing convention: SHORT = positive (credit), LONG = negative (debit)
        # SHORT: cost to close = ask (what we pay to buy back)
        # LONG: value to close = bid (what we receive to sell)
        price = ask if pos == "SHORT" else -bid
        self.openPrice = price
        self.profit = 0.0

        # Exit value: multiple of entry price
        # For SHORT: exit_value=2.0 means exit if price >= 2x entry (200% loss)
        # For LONG: exit_value=0.5 means exit if price <= 0.5x entry (50% profit)
        self.exit_value = exit_value * abs(price) if exit_type == "stop" else exit_value * abs(price)

        # Extract expiration date
        if "expDate" in quote:
            exp = quote["expDate"]
            if hasattr(exp, "dt"):
                self.exp_date = exp.dt.date
            elif hasattr(exp, "item"):
                self.exp_date = exp.item()
            else:
                self.exp_date = exp
        elif "expirationDate" in quote:
            # Handle timestamp format
            exp_ts = quote["expirationDate"]
            if hasattr(exp_ts, "item"):
                exp_ts = exp_ts.item()
            self.exp_date = dt.fromtimestamp(exp_ts / 1000).date() if exp_ts else None

        self.expired = False
        self.is_open = True
        
        logger.debug(f"Opened {pos} {qty}x {self.symbol} at {price:.2f}, exit_value={self.exit_value:.2f}")
    
    def update_quote(self, quote: pd.Series):
        """
        Update the quote for this option leg.
        Call this before evaluating exit conditions or getting current price.
        """
        if not self.is_open:
            logger.warning(f"Cannot update quote for closed option {self.symbol}")
            return
        self.quote = quote

    def close(self, qty: int):
        """
        Close the leg using current stored quote.
        You should update self.quote before calling close() in live trading.
        """
        if self.quote is None:
            # In a real system, you'd raise or log here.
            return

        self.closedt = dt.now()
        self.qty = qty

        ask = self.quote["ask"].item()
        bid = self.quote["bid"].item()

        if self.expired:
            # TODO: handle intrinsic value at expiration using underlying and strike
            price = 0.0 if self.pos == "LONG" else ask
        else:
            price = ask if self.pos == "SHORT" else -bid

        self.closePrice = price
        self.profit = self.openPrice - self.closePrice
        self.is_open = False

    def should_exit(self, price: float) -> bool:
        """
        Simple price-based exit rule.
        You can later replace this with VP/FVG/ATR-aware logic.
        """
        if self.exit_type == "stop" and self.exit_value is not None:
            if price >= self.exit_value:
                return True
        return False
