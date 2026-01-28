# Quick Start: Setting Credentials

## Fastest Method (Environment Variables)

### Windows PowerShell:
```powershell
# API Key/Secret method (recommended)
$env:SCHWAB_API_KEY = "your_api_key"
$env:SCHWAB_API_SECRET = "your_api_secret"
```

### Linux/Mac:
```bash
# API Key/Secret method (recommended)
export SCHWAB_API_KEY="your_api_key"
export SCHWAB_API_SECRET="your_api_secret"
```

Then run:
```bash
python main.py --config config/config_tos.yaml
```

The config files use `${SCHWAB_API_KEY}` and `${SCHWAB_API_SECRET}` syntax which automatically pulls from environment variables.

## Why This is Secure

1. ✅ Environment variables are NOT in your code
2. ✅ Config files can be committed (they reference env vars, not actual values)
3. ✅ Each developer sets their own credentials locally
4. ✅ No risk of accidentally committing secrets

## Full Documentation

See `SETUP_CREDENTIALS.md` for detailed instructions and alternative methods.
