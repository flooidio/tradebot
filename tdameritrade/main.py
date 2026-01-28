"""
Main execution loop for trading bot V2.
"""
import os
import sys
import time
import yaml
import logging
from datetime import datetime, time as dt_time
from typing import Dict, Optional
import pandas as pd

# Import core components
from account import Account
from engine.broker import CharlesSchwabAdapter, PaperBrokerAdapter
from engine.execution import ExecutionEngine
from engine.risk import RiskGovernor
from engine.manager import PositionManager
from engine.selector import StrategySelector
from data.feeds import PriceFeed, VIXFeed, DataAggregator
from strategies.butterflies import ButterflyBuilder
from strategies.strangles import StrangleBuilder
from logs.journal import TradeJournal
from engine.genai import get_genai_analyst

from dotenv import load_dotenv
import os

# Load .env file and log the result
env_file_path = os.path.join(os.path.dirname(__file__), '.env')
env_file_exists = os.path.exists(env_file_path)
if env_file_exists:
    load_dotenv()
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Loaded .env file from: {env_file_path}")
else:
    load_dotenv()  # Still try to load (might be in parent directory)
    logger = logging.getLogger(__name__)
    logger.info(f"⚠️  .env file not found at: {env_file_path} (using system environment variables)")


class TradingBot:
    """
    Main trading bot class that orchestrates all components.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize trading bot from configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        # Load configuration with environment variable substitution
        self.config = self._load_config_with_env_vars(config_path)
        
        # Initialize components
        self.account = Account(
            balance=self.config.get("account", {}).get("starting_balance", 25000.0),
            name=self.config.get("account", {}).get("name", "default")
        )
        
        # Initialize broker
        broker_config = self.config.get("broker", {})
        paper_mode = broker_config.get("paper_mode", True)
        
        if paper_mode:
            self.broker = PaperBrokerAdapter()
        else:
            # Support both API key/secret and OAuth2 methods
            # Check each credential source and log where it comes from
            api_key = broker_config.get("api_key")
            api_secret = broker_config.get("api_secret")
            client_id = broker_config.get("client_id")
            refresh_token = broker_config.get("refresh_token")
            
            # Log credential sources
            logger.info("=" * 60)
            logger.info("🔐 Credential Source Check")
            logger.info("=" * 60)
            
            if api_key:
                logger.info("  API Key: ✅ Found in config file")
            elif os.environ.get("SCHWAB_API_KEY"):
                logger.info("  API Key: ✅ Found in environment variable (from .env or system)")
                api_key = os.environ.get("SCHWAB_API_KEY")
            else:
                logger.warning("  API Key: ❌ Not found in config or environment")
            
            if api_secret:
                logger.info("  API Secret: ✅ Found in config file")
            elif os.environ.get("SCHWAB_API_SECRET"):
                logger.info("  API Secret: ✅ Found in environment variable (from .env or system)")
                api_secret = os.environ.get("SCHWAB_API_SECRET")
            else:
                logger.warning("  API Secret: ❌ Not found in config or environment")
            
            if client_id:
                logger.info("  Client ID: ✅ Found in config file")
            elif os.environ.get("SCHWAB_CLIENT_ID"):
                logger.info("  Client ID: ✅ Found in environment variable (from .env or system)")
                client_id = os.environ.get("SCHWAB_CLIENT_ID")
            else:
                logger.debug("  Client ID: Not provided (using API key/secret method)")
            
            if refresh_token:
                logger.info("  Refresh Token: ✅ Found in config file")
            elif os.environ.get("SCHWAB_REFRESH_TOKEN"):
                logger.info("  Refresh Token: ✅ Found in environment variable (from .env or system)")
                refresh_token = os.environ.get("SCHWAB_REFRESH_TOKEN")
            else:
                logger.debug("  Refresh Token: Not provided (using API key/secret method)")
            
            logger.info("=" * 60)
            logger.info("")
            
            self.broker = CharlesSchwabAdapter(
                api_key=api_key or "",
                api_secret=api_secret or "",
                account_id=broker_config.get("account_id"),
                paper_mode=paper_mode,
                client_id=client_id,
                refresh_token=refresh_token
            )
        
        # Initialize execution engine
        self.execution_engine = ExecutionEngine(self.broker, paper_mode=paper_mode)
        
        # Initialize risk governor
        self.risk_governor = RiskGovernor(self.config.get("risk", {}))
        
        # Initialize position manager
        self.position_manager = PositionManager(self.execution_engine)
        
        # Initialize strategy selector
        self.strategy_selector = StrategySelector(self.config.get("strategy", {}))
        
        # Initialize data feeds
        symbol = self.config.get("trading", {}).get("symbol", "SPX")
        self.price_feed = PriceFeed(symbol, self.broker, interval="1min")
        self.vix_feed = VIXFeed(self.broker) if self.config.get("trading", {}).get("use_vix", True) else None
        self.data_aggregator = DataAggregator(self.price_feed, self.vix_feed)
        
        # Initialize journal
        self.journal = TradeJournal(log_dir=self.config.get("logging", {}).get("log_dir", "logs"))
        
        # Initialize GenAI (optional)
        self.genai = get_genai_analyst(os.environ.get("OPENAI_API_KEY"))
        
        # Trading state
        self.running = False
        self.last_update = None
    
    def _load_config_with_env_vars(self, config_path: str) -> Dict:
        """
        Load YAML config and substitute environment variables.
        
        Supports ${VAR_NAME} syntax in YAML values.
        """
        import re
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Substitute environment variables in format ${VAR_NAME}
        def replace_env_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))  # Return original if not found
        
        content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
        
        return yaml.safe_load(content)
    
    def run(self):
        """Main execution loop."""
        logger.info("Starting trading bot...")
        self.running = True
        
        while self.running:
            try:
                # Check if market is open (skip in test mode)
                if not hasattr(self, 'test_mode') and not self._is_market_open():
                    logger.info("Market closed, waiting...")
                    time.sleep(60)
                    continue
                
                # Main loop: fetch data → compute signals → select strategy → manage positions
                self._main_loop()
                
                # Sleep between iterations
                sleep_interval = self.config.get("trading", {}).get("update_interval", 30)
                time.sleep(sleep_interval)
            
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying
        
        # Generate daily summary
        self._generate_daily_summary()
        logger.info("Trading bot stopped")
    
    def _main_loop(self):
        """Single iteration of main trading loop."""
        # 1. Fetch data
        logger.debug("Fetching market data...")
        self.price_feed.fetch_latest()
        if self.vix_feed:
            self.vix_feed.fetch_latest()
        
        combined_data = self.data_aggregator.get_combined_data()
        price_data = combined_data["price_data"]
        volume_data = combined_data["volume_data"]
        underlying_price = combined_data["underlying_price"]
        vix = combined_data.get("vix")
        
        if len(price_data) == 0:
            logger.warning("No price data available")
            return
        
        # 2. Compute indicators
        indicators = self.data_aggregator.compute_indicators(price_data)
        atr = indicators.get("atr")
        
        # 3. Get options chain
        try:
            chain_data = self.broker.get_chain(
                symbol=self.config.get("trading", {}).get("symbol", "SPX"),
                strike_count=50,
                include_quotes=True
            )
            chain_df = self._parse_chain(chain_data)
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            chain_df = pd.DataFrame()
        
        # 4. Manage existing positions
        if len(self.account.groups) > 0:
            actions = self.position_manager.manage_positions(
                self.account, underlying_price, price_data, chain_df
            )
            for action in actions:
                self.journal.log_decision("POSITION_ACTION", action)
        
        # 5. Check risk limits
        can_trade, reason = self.risk_governor.can_trade(self.account)
        if not can_trade:
            logger.info(f"Trading blocked: {reason}")
            return
        
        # 6. Select strategy
        iv = self._estimate_iv(chain_df) if len(chain_df) > 0 else 0.15
        strategy_mode, reason, params = self.strategy_selector.select_strategy(
            price_data, volume_data, chain_df, underlying_price, iv, vix
        )
        
        # Apply account policy
        strategy_mode, params = self.strategy_selector.apply_account_policy(strategy_mode, params)
        
        # Log strategy selection
        self.journal.log_strategy_selection(strategy_mode, reason, params)
        
        if strategy_mode == "NO_TRADE":
            logger.debug(f"No trade: {reason}")
            return
        
        # 7. Build and execute strategy
        group = self._build_strategy(strategy_mode, chain_df, underlying_price, params)
        
        if group is None:
            logger.warning(f"Could not build {strategy_mode}")
            return
        
        # Check position sizing
        position_size = self.risk_governor.calculate_position_size(
            group, self.account, atr=atr, vix=vix
        )
        group.qty = position_size
        
        # Check risk again with new position
        new_risk = abs(group.openPrice) * 100 * group.qty
        can_trade, reason = self.risk_governor.check_max_open_risk(self.account, new_risk)
        if not can_trade:
            logger.info(f"Risk limit would be exceeded: {reason}")
            return
        
        # Execute
        try:
            response = self.execution_engine.execute_group(group)
            order_id = response.get("orderId")
            
            self.journal.log_order(order_id, "OPEN", group.name, {
                "strategy": strategy_mode,
                "params": params
            })
            
            # Record trade
            self.risk_governor.record_trade(group, is_loss=False)
            
            # Add to account
            self.account.open_group_trade(group)
            
            # GenAI explanation
            if self.genai:
                explanation = self.genai.explain_entry(strategy_mode, {
                    "underlying_price": underlying_price,
                    "iv": iv,
                    "vix": vix
                }, reason)
                logger.info(f"Entry explanation: {explanation}")
        
        except Exception as e:
            logger.error(f"Error executing strategy: {e}")
    
    def _build_strategy(self, strategy_mode: str, chain: pd.DataFrame,
                       underlying_price: float, params: Dict):
        """Build strategy group based on mode."""
        if strategy_mode == "STRANGLE":
            builder = StrangleBuilder()
            return builder.build_strangle(
                chain, underlying_price,
                call_delta=params.get("call_delta", 0.15),
                put_delta=params.get("put_delta", 0.15),
                days_to_exp=params.get("days_to_exp", 0)
            )
        elif "BUTTERFLY" in strategy_mode:
            builder = ButterflyBuilder()
            direction = "BULLISH" if "BULLISH" in strategy_mode else "BEARISH"
            return builder.build_directional_otm_fly(
                chain, underlying_price, direction,
                target_delta=params.get("target_delta", 0.15),
                days_to_exp=params.get("days_to_exp", 0)
            )
        return None
    
    def _parse_chain(self, chain_data: Dict) -> pd.DataFrame:
        """Parse options chain data into DataFrame."""
        # Convert chain data to DataFrame format
        # (simplified - would need full parsing)
        return pd.DataFrame()
    
    def _estimate_iv(self, chain: pd.DataFrame) -> float:
        """Estimate implied volatility from chain."""
        if len(chain) == 0:
            return 0.15
        # Use average IV from chain
        if "volatility" in chain.columns:
            return chain["volatility"].mean()
        return 0.15
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now()
        market_open = dt_time(6, 30)  # 6:30 AM PT
        market_close = dt_time(13, 0)  # 1:00 PM PT
        
        current_time = now.time()
        return market_open <= current_time <= market_close and now.weekday() < 5
    
    def _generate_daily_summary(self):
        """Generate daily trading summary."""
        summary = self.journal.generate_daily_summary(self.account)
        logger.info(f"Daily summary: {summary}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading Bot V2")
    parser.add_argument("--config", "-c", default="config/config_tos.yaml",
                       help="Configuration file path")
    parser.add_argument("--paper", "-p", action="store_true",
                       help="Force paper trading mode")
    parser.add_argument("--test", "-t", action="store_true",
                       help="Test mode: skip market hours check and run one iteration")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )
    
    # Create and run bot
    bot = TradingBot(args.config)
    if args.paper:
        bot.broker = PaperBrokerAdapter()
        bot.execution_engine.broker = bot.broker
    
    # Test mode: run one iteration and exit
    if args.test:
        logger.info("Running in TEST mode (skipping market hours check)")
        bot.test_mode = True
        try:
            bot._main_loop()
            logger.info("Test completed successfully!")
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            sys.exit(1)
    else:
        try:
            bot.run()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
