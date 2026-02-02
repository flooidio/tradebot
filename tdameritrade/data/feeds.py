"""
Live market data feeds: price, ADD, VIX, economic calendar.
"""
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
import time
from engine.broker import BrokerAdapter

logger = logging.getLogger(__name__)


class MarketDataFeed:
    """
    Base class for market data feeds.
    """
    
    def __init__(self, symbol: str, broker: Optional[BrokerAdapter] = None):
        self.symbol = symbol
        self.broker = broker
        self.data: pd.DataFrame = pd.DataFrame()
        self.subscribers: List[Callable] = []
    
    def subscribe(self, callback: Callable):
        """Subscribe to data updates."""
        self.subscribers.append(callback)
    
    def notify_subscribers(self, data: pd.DataFrame):
        """Notify all subscribers of new data."""
        for callback in self.subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    def get_latest(self) -> Optional[pd.Series]:
        """Get latest data point."""
        if len(self.data) == 0:
            return None
        return self.data.iloc[-1]


class PriceFeed(MarketDataFeed):
    """
    Real-time price feed with candle aggregation.
    """
    
    def __init__(self, symbol: str, broker: BrokerAdapter, interval: str = "1min"):
        """
        Initialize price feed.
        
        Args:
            symbol: Underlying symbol
            broker: Broker adapter for API calls
            interval: Candle interval ("1min", "5min", etc.)
        """
        super().__init__(symbol, broker)
        self.interval = interval
        self.last_update: Optional[datetime] = None
    
    def fetch_latest(self) -> pd.DataFrame:
        """Fetch latest price data from broker."""
        if self.broker is None:
            logger.error("No broker configured for price feed")
            return pd.DataFrame()
        
        try:
            quote = self.broker.get_quote(self.symbol)
            
            # Convert to DataFrame row
            row = pd.DataFrame([{
                "timestamp": datetime.now(),
                "open": quote.get("lastPrice", 0),
                "high": quote.get("lastPrice", 0),
                "low": quote.get("lastPrice", 0),
                "close": quote.get("lastPrice", 0),
                "volume": quote.get("totalVolume", 0)
            }])
            
            # Append to data
            if len(self.data) == 0:
                self.data = row
            else:
                self.data = pd.concat([self.data, row], ignore_index=True)
            
            # Aggregate into candles if needed
            if self.interval != "1min":
                self.data = self._aggregate_candles(self.interval)
            
            self.last_update = datetime.now()
            self.notify_subscribers(self.data)
            
            return self.data
        
        except Exception as e:
            logger.error(f"Error fetching price data: {e}")
            return pd.DataFrame()
    
    def _aggregate_candles(self, interval: str) -> pd.DataFrame:
        """Aggregate 1-minute candles into specified interval."""
        if len(self.data) == 0:
            return self.data
        
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        self.data = self.data.set_index('timestamp')
        
        # Resample to interval
        resampled = self.data.resample(interval).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        return resampled.reset_index()
    
    def get_candles(self, lookback: int = 100) -> pd.DataFrame:
        """Get last N candles."""
        if len(self.data) == 0:
            return pd.DataFrame()
        return self.data.tail(lookback)


class VIXFeed(MarketDataFeed):
    """
    VIX (volatility index) feed.
    """
    
    def __init__(self, broker: BrokerAdapter):
        super().__init__("VIX", broker)
    
    def fetch_latest(self) -> float:
        """Fetch latest VIX value."""
        if self.broker is None:
            return 0.0
        
        try:
            quote = self.broker.get_quote("VIX")
            vix_value = quote.get("lastPrice", 0.0)
            
            # Store in data
            row = pd.DataFrame([{
                "timestamp": datetime.now(),
                "vix": vix_value
            }])
            
            if len(self.data) == 0:
                self.data = row
            else:
                self.data = pd.concat([self.data, row], ignore_index=True)
            
            return vix_value
        
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return 0.0
    
    def get_current(self) -> float:
        """Get current VIX value."""
        latest = self.get_latest()
        if latest is None:
            return 0.0
        return latest.get("vix", 0.0)


class EconomicCalendarFeed:
    """
    Economic calendar feed (can start manual, later automate).
    """
    
    def __init__(self):
        self.events: List[Dict] = []
        # Manual events for now
        self._load_manual_events()
    
    def _load_manual_events(self):
        """Load manual economic events."""
        # Example structure
        self.events = [
            {
                "date": datetime.now().date(),
                "time": "08:30",
                "event": "CPI Release",
                "impact": "HIGH"
            },
            # Add more events as needed
        ]
    
    def get_upcoming_events(self, hours_ahead: int = 24) -> List[Dict]:
        """Get upcoming economic events."""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)
        
        upcoming = []
        for event in self.events:
            event_datetime = datetime.combine(event["date"], 
                                             datetime.strptime(event["time"], "%H:%M").time())
            if now <= event_datetime <= cutoff:
                upcoming.append(event)
        
        return upcoming
    
    def is_news_window(self, current_time: Optional[datetime] = None) -> bool:
        """Check if current time is near a high-impact event."""
        if current_time is None:
            current_time = datetime.now()
        
        upcoming = self.get_upcoming_events(hours_ahead=2)
        high_impact = [e for e in upcoming if e.get("impact") == "HIGH"]
        
        return len(high_impact) > 0


class DataAggregator:
    """
    Aggregates multiple data feeds and computes indicators.
    """
    
    def __init__(self, price_feed: PriceFeed, vix_feed: Optional[VIXFeed] = None):
        self.price_feed = price_feed
        self.vix_feed = vix_feed
        self.calendar_feed = EconomicCalendarFeed()
    
    def get_combined_data(self) -> Dict:
        """Get combined data from all feeds."""
        price_data = self.price_feed.get_candles(lookback=100)
        vix = self.vix_feed.get_current() if self.vix_feed else None
        upcoming_events = self.calendar_feed.get_upcoming_events()
        
        return {
            "price_data": price_data,
            "volume_data": price_data["volume"] if "volume" in price_data.columns else pd.Series(),
            "underlying_price": price_data["close"].iloc[-1] if len(price_data) > 0 else 0.0,
            "vix": vix,
            "upcoming_events": upcoming_events,
            "is_news_window": self.calendar_feed.is_news_window()
        }
    
    def compute_indicators(self, price_data: pd.DataFrame) -> Dict:
        """Compute technical indicators from price data."""
        if len(price_data) == 0:
            return {}
        
        indicators = {}
        
        # ATR
        high_low = price_data['high'] - price_data['low']
        high_close = abs(price_data['high'] - price_data['close'].shift())
        low_close = abs(price_data['low'] - price_data['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        indicators['atr'] = true_range.rolling(14).mean().iloc[-1] if len(true_range) >= 14 else 0.0
        
        # Volume profile (simplified)
        if 'volume' in price_data.columns:
            indicators['volume_ma'] = price_data['volume'].rolling(20).mean().iloc[-1] if len(price_data) >= 20 else 0.0
        
        return indicators
