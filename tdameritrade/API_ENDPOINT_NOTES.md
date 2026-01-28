# Charles Schwab API Endpoint Notes

## Current Status

✅ **Authentication is working!** The OAuth token is being retrieved successfully.

❌ **API endpoints are returning 400 errors** with "Internal Server Error" messages.

## What This Means

The authentication flow is correct, but the market data endpoints may need adjustment. The errors suggest:

1. **Endpoint URLs might be incorrect** - The base URL or endpoint paths may need to match your specific API access level
2. **Request format might be wrong** - Parameters, headers, or request structure may need adjustment
3. **API version differences** - Your API access might use a different version or endpoint structure

## Next Steps

### Option 1: Check Your API Documentation

1. Log into https://developer.schwab.com/
2. Go to your app's API documentation
3. Check the exact endpoint URLs and formats for:
   - Market data quotes
   - Options chains
   - Account information

### Option 2: Use schwab-py Library (Recommended)

Consider using the official `schwab-py` library which handles endpoint formats correctly:

```bash
pip install schwab-py
```

Then you can use it as a reference or integrate it:

```python
from schwab.auth import easy_client

client = easy_client(
    api_key='YOUR_API_KEY',
    app_secret='YOUR_API_SECRET',
    callback_url='https://127.0.0.1',
    token_path='./token.json'
)

# Get quotes
response = client.get_quotes(['SPY'])
data = response.json()
```

### Option 3: Manual Endpoint Testing

You can test endpoints manually using curl or Postman to find the correct format:

```bash
curl -X GET "https://api.schwabapi.com/trader/v1/marketdata/quotes?symbols=SPY" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

## Common Endpoint Formats to Try

Based on the errors, here are some variations to check:

### Quotes Endpoint
- `GET /marketdata/quotes?symbols=SPY`
- `GET /marketdata/quotes?symbol=SPY`
- `GET /marketdata/v1/quotes?symbols=SPY`
- `GET /quotes?symbols=SPY`

### Account Endpoint
- `GET /accounts/accountNumbers`
- `GET /accounts`
- `GET /trader/accounts`
- `GET /v1/accounts`

### Options Chain
- `GET /marketdata/chains?symbol=SPY&strikeCount=5`
- `GET /marketdata/v1/chains?symbol=SPY&strikeCount=5`
- `GET /chains?symbol=SPY&strikeCount=5`

## Current Implementation

The code in `engine/broker.py` tries multiple endpoint formats automatically, but if none work, you'll need to:

1. Check your Charles Schwab API documentation
2. Update the base URLs and endpoint paths in `engine/broker.py`
3. Or use the `schwab-py` library which handles this correctly

## Getting Help

If you have access to the Charles Schwab API documentation:
1. Share the correct endpoint formats
2. I can update the code to match
3. Or we can integrate the `schwab-py` library

The authentication is working correctly, so once we fix the endpoint formats, everything should work!
