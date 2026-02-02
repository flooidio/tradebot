"""
Trade journaling and structured logging.
"""
from typing import Dict, List, Optional
from datetime import datetime
import json
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class TradeJournal:
    """
    Structured trade journal for logging all trading decisions and outcomes.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize trade journal.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Journal file
        self.journal_file = self.log_dir / f"journal_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        # Setup structured logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup structured JSON logging."""
        log_file = self.log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
        
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        ))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    
    def log_decision(self, decision_type: str, data: Dict):
        """
        Log a trading decision.
        
        Decision types:
        - SIGNAL: Market signal detected
        - STRATEGY_SELECTED: Strategy chosen
        - ORDER_PLACED: Order placed
        - ORDER_FILLED: Order filled
        - POSITION_OPENED: Position opened
        - POSITION_CLOSED: Position closed
        - EXIT_TRIGGERED: Exit condition met
        - CONVERSION: Strategy converted
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": decision_type,
            "data": data
        }
        
        # Write to journal file
        with open(self.journal_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Also log to standard logger
        logger.info(f"{decision_type}: {json.dumps(data)}")
    
    def log_signal(self, signal_type: str, signal_data: Dict, reason: str):
        """Log a market signal."""
        self.log_decision("SIGNAL", {
            "signal_type": signal_type,
            "signal_data": signal_data,
            "reason": reason
        })
    
    def log_strategy_selection(self, strategy_mode: str, reason: str, params: Dict):
        """Log strategy selection."""
        self.log_decision("STRATEGY_SELECTED", {
            "strategy_mode": strategy_mode,
            "reason": reason,
            "params": params
        })
    
    def log_order(self, order_id: str, order_type: str, group_name: str, details: Dict):
        """Log order placement."""
        self.log_decision("ORDER_PLACED", {
            "order_id": order_id,
            "order_type": order_type,
            "group_name": group_name,
            "details": details
        })
    
    def log_position(self, action: str, group_name: str, pnl: float, details: Dict):
        """Log position action (open/close)."""
        self.log_decision(f"POSITION_{action}", {
            "group_name": group_name,
            "pnl": pnl,
            "details": details
        })
    
    def generate_daily_summary(self, account) -> Dict:
        """
        Generate daily trading summary.
        
        Returns:
            Summary dictionary with statistics
        """
        # Load today's journal entries
        entries = []
        if self.journal_file.exists():
            with open(self.journal_file, "r") as f:
                for line in f:
                    entries.append(json.loads(line))
        
        # Calculate statistics
        trades_today = [e for e in entries if e["type"] in ["POSITION_OPENED", "POSITION_CLOSED"]]
        orders_today = [e for e in entries if e["type"] == "ORDER_PLACED"]
        
        # Calculate P/L
        closed_groups = [g for g in account.groups if not g.is_open]
        total_pnl = sum(g.profit * 100 * g.qty for g in closed_groups)
        
        summary = {
            "date": datetime.now().date().isoformat(),
            "trades": len(trades_today),
            "orders": len(orders_today),
            "total_pnl": total_pnl,
            "win_rate": self._calculate_win_rate(closed_groups),
            "violations": self._find_violations(entries),
            "missed_setups": self._find_missed_setups(entries)
        }
        
        # Write summary
        summary_file = self.log_dir / f"summary_{datetime.now().strftime('%Y%m%d')}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary
    
    def _calculate_win_rate(self, closed_groups: List) -> float:
        """Calculate win rate from closed groups."""
        if len(closed_groups) == 0:
            return 0.0
        
        wins = sum(1 for g in closed_groups if g.profit > 0)
        return wins / len(closed_groups)
    
    def _find_violations(self, entries: List[Dict]) -> List[Dict]:
        """Find risk rule violations."""
        violations = []
        # Check for violations in entries
        # (would need to cross-reference with risk rules)
        return violations
    
    def _find_missed_setups(self, entries: List[Dict]) -> List[Dict]:
        """Find missed trading setups."""
        missed = []
        # Analyze signals that didn't result in trades
        signals = [e for e in entries if e["type"] == "SIGNAL"]
        trades = [e for e in entries if e["type"] == "STRATEGY_SELECTED"]
        
        # Find signals without corresponding trades
        for signal in signals:
            # Check if trade followed
            signal_time = datetime.fromisoformat(signal["timestamp"])
            following_trades = [t for t in trades 
                               if datetime.fromisoformat(t["timestamp"]) > signal_time]
            if len(following_trades) == 0:
                missed.append(signal)
        
        return missed


class ReplayHarness:
    """
    Replay harness for testing changes against recorded data.
    """
    
    def __init__(self, journal: TradeJournal):
        self.journal = journal
    
    def replay_day(self, date: str, account, strategy_selector, execution_engine):
        """
        Replay a trading day from journal data.
        
        Args:
            date: Date to replay (YYYYMMDD)
            account: Account object
            strategy_selector: Strategy selector instance
            execution_engine: Execution engine instance
        """
        journal_file = self.journal.log_dir / f"journal_{date}.jsonl"
        
        if not journal_file.exists():
            logger.error(f"Journal file not found: {journal_file}")
            return
        
        # Load entries
        entries = []
        with open(journal_file, "r") as f:
            for line in f:
                entries.append(json.loads(line))
        
        # Replay in order
        for entry in entries:
            # Replay decision logic
            # (simplified - would need full context)
            logger.info(f"Replaying: {entry['type']} at {entry['timestamp']}")
