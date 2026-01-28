# Testing Authentication and API

This guide shows how to test your Charles Schwab API authentication and basic API calls, even when the market is closed.

## Quick Test Script

Use the dedicated test script to validate authentication:

```bash
python test_auth.py
```

This will:
1. ✅ Test authentication (get OAuth token)
2. ✅ Test getting a quote (e.g., SPY)
3. ✅ Test getting account info
4. ✅ Test getting options chain

### Options

```bash
# Test with specific symbol
python test_auth.py --symbol SPX

# Test with paper trading (no real API calls)
python test_auth.py --paper

# Use different config file
python test_auth.py --config config/config_fidelity.yaml
```

## Using Main Bot in Test Mode

You can also run the main bot in test mode to skip market hours check:

```bash
python main.py --test
```

This will:
- Skip market hours validation
- Run one iteration of the main loop
- Test data fetching and API calls
- Exit after completion

## What to Expect

### When Market is Closed

- ✅ Authentication should work
- ✅ Getting quotes may work (depends on broker)
- ⚠️ Options chain may be empty or limited
- ⚠️ Some market data may be stale

### When Market is Open

- ✅ All tests should pass
- ✅ Real-time quotes available
- ✅ Full options chain data

## Troubleshooting

### Authentication Fails

1. **Check environment variables:**
   ```bash
   # Windows PowerShell
   echo $env:SCHWAB_API_KEY
   echo $env:SCHWAB_API_SECRET
   
   # Linux/Mac
   echo $SCHWAB_API_KEY
   echo $SCHWAB_API_SECRET
   ```

2. **Verify credentials are correct:**
   - API key and secret from Charles Schwab developer portal
   - No extra spaces or quotes

3. **Check token endpoint:**
   - Default: `https://api.schwab.com/v1/oauth/token`
   - May need to adjust based on your account type

### Quote Returns Empty

- This is normal when market is closed
- Try a different symbol (SPY, AAPL, etc.)
- Some symbols may have limited data after hours

### Options Chain Empty

- Normal when market is closed
- Chain data is typically only available during market hours
- Authentication is still working if you got this far

## Example Output

```
============================================================
Charles Schwab API Authentication Test
============================================================

============================================================
Testing Authentication
============================================================
✅ Authentication successful!
   Access token: eyJhbGciOiJSUzI1NiIs...
   Token expires at: 2024-01-26 15:30:00

============================================================
Testing Get Quote: SPY
============================================================
✅ Quote retrieved successfully!
   Symbol: SPY
   Last Price: $485.23
   Bid: $485.20
   Ask: $485.25
   Volume: 45234567
```

## Next Steps

Once authentication is validated:

1. ✅ Run full bot in paper mode: `python main.py --paper`
2. ✅ Monitor logs for any API errors
3. ✅ Test during market hours for full functionality
4. ✅ Switch to live trading when ready
