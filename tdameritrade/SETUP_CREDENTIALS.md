# Setting Up Credentials

This guide shows you how to securely configure your trading bot credentials without checking them into version control.

## Option 1: Environment Variables (Recommended)

### Windows (PowerShell)

```powershell
# Set environment variables for current session (API Key/Secret method)
$env:SCHWAB_API_KEY = "your_api_key_here"
$env:SCHWAB_API_SECRET = "your_api_secret_here"

# OR if using OAuth2 method:
# $env:SCHWAB_CLIENT_ID = "your_client_id_here"
# $env:SCHWAB_REFRESH_TOKEN = "your_refresh_token_here"

# To make them persistent (for current user)
[System.Environment]::SetEnvironmentVariable("SCHWAB_API_KEY", "your_api_key_here", "User")
[System.Environment]::SetEnvironmentVariable("SCHWAB_API_SECRET", "your_api_secret_here", "User")
```

### Windows (Command Prompt)

```cmd
set SCHWAB_API_KEY=your_api_key_here
set SCHWAB_API_SECRET=your_api_secret_here
```

### Linux/Mac (Bash)

```bash
# Set for current session (API Key/Secret method)
export SCHWAB_API_KEY="your_api_key_here"
export SCHWAB_API_SECRET="your_api_secret_here"

# Make persistent by adding to ~/.bashrc or ~/.zshrc
echo 'export SCHWAB_API_KEY="your_api_key_here"' >> ~/.bashrc
echo 'export SCHWAB_API_SECRET="your_api_secret_here"' >> ~/.bashrc
source ~/.bashrc
```

## Option 2: Using a .env File (Alternative)

1. Create a `.env` file in the project root:
```bash
# API Key/Secret method (recommended)
SCHWAB_API_KEY=your_api_key_here
SCHWAB_API_SECRET=your_api_secret_here

# OR OAuth2 method (alternative)
# SCHWAB_CLIENT_ID=your_client_id_here
# SCHWAB_REFRESH_TOKEN=your_refresh_token_here

OPENAI_API_KEY=your_openai_key_here  # Optional, for GenAI features
```

2. Install python-dotenv:
```bash
pip install python-dotenv
```

3. Update `main.py` to load .env file (add at the top):
```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file
```

**Important**: The `.env` file is already in `.gitignore` and will NOT be checked into git.

## Option 3: Direct in Config File (Not Recommended)

You can set credentials directly in the config YAML files, but this is **NOT recommended** as it risks checking credentials into version control.

If you must do this:
1. Copy `config/config_tos.yaml.example` to `config/config_tos.yaml`
2. Replace `${SCHWAB_API_KEY}` with your actual API key
3. Replace `${SCHWAB_API_SECRET}` with your actual API secret
4. **DO NOT commit** the actual config files to git

## Verifying Your Setup

After setting environment variables, verify they're loaded:

### Windows (PowerShell)
```powershell
echo $env:SCHWAB_CLIENT_ID
echo $env:SCHWAB_REFRESH_TOKEN
```

### Linux/Mac
```bash
echo $SCHWAB_CLIENT_ID
echo $SCHWAB_REFRESH_TOKEN
```

## Getting Charles Schwab API Credentials

### Method 1: API Key/Secret (Recommended)
**How it works:** Your API key and secret are used to obtain an OAuth access token, which is then used for API calls. The token is automatically refreshed when it expires.

1. Go to https://developer.schwab.com/
2. Create a developer account
3. Create a new app
4. Get your `api_key` and `api_secret` from the app dashboard
5. The bot will automatically use these to get and refresh OAuth tokens

### Method 2: OAuth2 Refresh Token (Alternative)
**How it works:** If you already have a refresh token from a previous OAuth authorization flow, you can use it directly.

1. Go to https://developer.schwab.com/
2. Create a developer account
3. Create a new app
4. Complete the OAuth2 authorization flow to get a `refresh_token`
5. Use `client_id` and `refresh_token` in your config

## Security Best Practices

1. ✅ **DO** use environment variables
2. ✅ **DO** keep `.env` files in `.gitignore`
3. ✅ **DO** use example/template config files
4. ❌ **DON'T** commit actual credentials to git
5. ❌ **DON'T** share credentials in chat/email
6. ❌ **DON'T** hardcode credentials in source code

## Troubleshooting

If you get authentication errors:

1. Verify environment variables are set:
   ```bash
   # Linux/Mac
   env | grep SCHWAB
   
   # Windows PowerShell
   Get-ChildItem Env: | Where-Object {$_.Name -like "*SCHWAB*"}
   ```

2. Restart your terminal/IDE after setting environment variables

3. Check that the config file uses `${VARIABLE_NAME}` syntax

4. Verify credentials are correct:
   - For API Key method: `SCHWAB_API_KEY` and `SCHWAB_API_SECRET`
   - For OAuth2 method: `SCHWAB_CLIENT_ID` and `SCHWAB_REFRESH_TOKEN`
