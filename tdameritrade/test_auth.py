"""
Test script to validate Charles Schwab API authentication and basic API calls.
Can be run even when market is closed.
"""
import os
import sys
import yaml
import logging
from engine.broker import CharlesSchwabAdapter, PaperBrokerAdapter
from dotenv import load_dotenv

# Load .env file and log the result
env_file_path = os.path.join(os.path.dirname(__file__), '.env')
env_file_exists = os.path.exists(env_file_path)
if env_file_exists:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Loaded .env file from: {env_file_path}")
else:
    load_dotenv()  # Still try to load (might be in parent directory)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info(f"⚠️  .env file not found at: {env_file_path} (using system environment variables)")


def load_config(config_path: str = "config/config_tos.yaml"):
    """Load config with environment variable substitution."""
    import re
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    def replace_env_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
    return yaml.safe_load(content)


def test_authentication(broker):
    """Test authentication and token retrieval."""
    logger.info("=" * 60)
    logger.info("Testing Authentication")
    logger.info("=" * 60)
    
    try:
        # Check if we have an access token
        if hasattr(broker, 'access_token') and broker.access_token:
            logger.info(f"✅ Authentication successful!")
            logger.info(f"   Access token: {broker.access_token[:20]}...")
            if hasattr(broker, 'token_expires_at') and broker.token_expires_at:
                from datetime import datetime
                expires_at = datetime.fromtimestamp(broker.token_expires_at)
                logger.info(f"   Token expires at: {expires_at}")
            return True
        else:
            logger.error("❌ No access token received")
            return False
    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_quote(broker, symbol: str = "SPY"):
    """Test getting a quote for a symbol."""
    logger.info("=" * 60)
    logger.info(f"Testing Get Quote: {symbol}")
    logger.info("=" * 60)
    
    try:
        quote = broker.get_quote(symbol)
        
        if quote:
            logger.info(f"✅ Quote retrieved successfully!")
            logger.info(f"   Symbol: {symbol}")
            
            # Display relevant quote data
            if isinstance(quote, dict):
                if 'lastPrice' in quote:
                    logger.info(f"   Last Price: ${quote['lastPrice']}")
                if 'bidPrice' in quote:
                    logger.info(f"   Bid: ${quote['bidPrice']}")
                if 'askPrice' in quote:
                    logger.info(f"   Ask: ${quote['askPrice']}")
                if 'totalVolume' in quote:
                    logger.info(f"   Volume: {quote['totalVolume']}")
                
                # Print full quote for debugging
                logger.info(f"\n   Full quote data:")
                for key, value in quote.items():
                    logger.info(f"      {key}: {value}")
            else:
                logger.info(f"   Quote data: {quote}")
            
            return True
        else:
            logger.warning(f"⚠️  Quote returned empty/None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to get quote: {e}")
        # Show more details about the error
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"   API Error Details: {error_data}")
            except:
                logger.error(f"   API Response: {e.response.text}")
        import traceback
        traceback.print_exc()
        return False


def test_get_account_info(broker):
    """Test getting account information."""
    logger.info("=" * 60)
    logger.info("Testing Get Account Info")
    logger.info("=" * 60)
    
    try:
        # First test: Get account numbers list
        logger.info("Step 1: Getting account numbers...")
        endpoint = "accounts/accountNumbers"
        accounts = broker._request("GET", endpoint, use_marketdata_base=False)
        
        logger.info(f"✅ Account numbers retrieved successfully!")
        logger.info(f"   Response type: {type(accounts)}")
        logger.info(f"   Response: {accounts}")
        
        # Parse account numbers
        account_list = []
        if isinstance(accounts, list):
            account_list = accounts
        elif isinstance(accounts, dict):
            account_list = accounts.get("accounts", accounts.get("accountNumbers", []))
        
        if account_list:
            logger.info(f"   Found {len(account_list)} account(s)")
            for i, acc in enumerate(account_list):
                logger.info(f"   Account {i+1}: {acc}")
        
        # Now test getting full account info
        account_info = broker.get_account_info()
        
        if account_info:
            logger.info(f"✅ Account info retrieved successfully!")
            
            if isinstance(account_info, dict):
                # Display relevant account data
                if 'accountNumber' in account_info:
                    logger.info(f"   Account Number: {account_info['accountNumber']}")
                if 'accountType' in account_info:
                    logger.info(f"   Account Type: {account_info['accountType']}")
                if 'currentBalances' in account_info:
                    balances = account_info['currentBalances']
                    if 'cashBalance' in balances:
                        logger.info(f"   Cash Balance: ${balances['cashBalance']}")
                    if 'buyingPower' in balances:
                        logger.info(f"   Buying Power: ${balances['buyingPower']}")
                
                logger.info(f"\n   Full account data:")
                for key, value in account_info.items():
                    logger.info(f"      {key}: {value}")
            
            return True
        else:
            logger.warning(f"⚠️  Account info returned empty/None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to get account info: {e}")
        # Show more details about the error
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"   API Error Details: {error_data}")
            except:
                logger.error(f"   API Response: {e.response.text}")
        import traceback
        traceback.print_exc()
        return False


def test_get_chain(broker, symbol: str = "SPY"):
    """Test getting options chain (may be empty when market closed)."""
    logger.info("=" * 60)
    logger.info(f"Testing Get Options Chain: {symbol}")
    logger.info("=" * 60)
    
    try:
        chain = broker.get_chain(
            symbol=symbol,
            strike_count=5,  # Just a few strikes for testing
            include_quotes=True
        )
        
        if chain:
            logger.info(f"✅ Options chain retrieved successfully!")
            
            if isinstance(chain, dict):
                # Check what's in the chain
                logger.info(f"   Chain keys: {list(chain.keys())}")
                
                if 'callExpDateMap' in chain:
                    calls = chain['callExpDateMap']
                    logger.info(f"   Call expirations: {len(calls)}")
                
                if 'putExpDateMap' in chain:
                    puts = chain['putExpDateMap']
                    logger.info(f"   Put expirations: {len(puts)}")
                
                if 'underlying' in chain:
                    underlying = chain['underlying']
                    logger.info(f"   Underlying: {underlying}")
            
            return True
        else:
            logger.warning(f"⚠️  Options chain returned empty/None")
            logger.info("   (This is normal when market is closed)")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to get options chain: {e}")
        # Show more details about the error
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                logger.error(f"   API Error Details: {error_data}")
            except:
                logger.error(f"   API Response: {e.response.text}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Charles Schwab API Authentication")
    parser.add_argument("--config", "-c", default="config/config_tos.yaml",
                       help="Configuration file path")
    parser.add_argument("--symbol", "-s", default="SPY",
                       help="Symbol to test quotes (default: SPY)")
    parser.add_argument("--paper", "-p", action="store_true",
                       help="Use paper trading adapter (no real API calls)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging (shows all auth steps, requests, responses)")
    parser.add_argument("--api", "-a", choices=["trader", "marketdata", "both"], default="both",
                       help="Which API to test: 'trader' (accounts/orders), 'marketdata' (quotes/chains), or 'both' (default)")
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('engine.broker').setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Charles Schwab API Authentication Test")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Testing: {args.api.upper()} API(s)")
    if args.api == "trader":
        logger.info("  - Trader API: accounts, orders, positions")
    elif args.api == "marketdata":
        logger.info("  - Marketdata API: quotes, options chains")
    else:
        logger.info("  - Trader API: accounts, orders, positions")
        logger.info("  - Marketdata API: quotes, options chains")
    logger.info("")
    logger.info("NOTE: If API calls fail with 400 errors, check API_ENDPOINT_NOTES.md")
    logger.info("      The endpoint formats may need adjustment based on your API access.")
    logger.info("")
    
    # Load config
    try:
        config = load_config(args.config)
        broker_config = config.get("broker", {})
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return 1
    
    # Initialize broker
    if args.paper:
        logger.info("Using Paper Trading Adapter (simulated)")
        broker = PaperBrokerAdapter()
    else:
        logger.info("Using Charles Schwab API")
        
        # Get credentials and log their source
        api_key = broker_config.get("api_key")
        api_secret = broker_config.get("api_secret")
        client_id = broker_config.get("client_id")
        refresh_token = broker_config.get("refresh_token")
        
        # Log credential sources
        logger.info("")
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
        
        if not api_key or not api_secret:
            if not client_id or not refresh_token:
                logger.error("❌ Missing credentials!")
                logger.error("   Set SCHWAB_API_KEY and SCHWAB_API_SECRET environment variables")
                logger.error("   OR set SCHWAB_CLIENT_ID and SCHWAB_REFRESH_TOKEN")
                return 1
        
        try:
            broker = CharlesSchwabAdapter(
                api_key=api_key or "",
                api_secret=api_secret or "",
                account_id=broker_config.get("account_id"),
                paper_mode=False,
                client_id=client_id,
                refresh_token=refresh_token,
                verbose=args.verbose
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize broker: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    # Run tests
    results = {}
    
    # Test 1: Authentication
    results['auth'] = test_authentication(broker)
    logger.info("")
    
    if not results['auth']:
        logger.error("Authentication failed. Cannot proceed with other tests.")
        return 1
    
    # Test 2: Get Quote (marketdata API)
    if args.api in ["marketdata", "both"]:
        results['quote'] = test_get_quote(broker, args.symbol)
        logger.info("")
    else:
        logger.info("Skipping marketdata API tests (quotes, chains)")
        results['quote'] = None
        logger.info("")
    
    # Test 3: Get Account Info (trader API)
    if args.api in ["trader", "both"]:
        if not args.paper:
            try:
                results['account'] = test_get_account_info(broker)
            except ValueError as e:
                logger.warning(f"Account test skipped: {e}")
                results['account'] = False
            logger.info("")
        else:
            logger.info("Skipping trader API tests (paper mode)")
            results['account'] = None
            logger.info("")
    else:
        logger.info("Skipping trader API tests (accounts)")
        results['account'] = None
        logger.info("")
    
    # Test 4: Get Options Chain (marketdata API)
    if args.api in ["marketdata", "both"]:
        results['chain'] = test_get_chain(broker, args.symbol)
        logger.info("")
    else:
        logger.info("Skipping marketdata API tests (options chain)")
        results['chain'] = None
        logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        if passed is None:
            status = "⏭️  SKIP"
        elif passed:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        logger.info(f"   {test_name.upper()}: {status}")
    
    # Only check passed tests (skip None values)
    passed_tests = [v for v in results.values() if v is not None]
    all_passed = all(passed_tests) if passed_tests else False
    
    if all_passed:
        logger.info("")
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.info("")
        logger.warning("⚠️  Some tests failed (this may be normal when market is closed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
