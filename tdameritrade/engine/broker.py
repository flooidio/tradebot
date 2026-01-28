"""
Broker adapter interface for trading execution.
Supports Charles Schwab API (replacing TD Ameritrade).
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BrokerAdapter(ABC):
    """
    Abstract interface for broker APIs.
    All broker implementations must provide these methods.
    """
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get current quote for a symbol."""
        pass
    
    @abstractmethod
    def get_chain(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Get options chain for underlying symbol."""
        pass
    
    @abstractmethod
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Place a single or multi-leg order."""
        pass
    
    @abstractmethod
    def replace_order(self, order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
        """Replace an existing order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        pass
    
    @abstractmethod
    def get_fills(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get fill information for orders."""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information and balances."""
        pass


class CharlesSchwabAdapter(BrokerAdapter):
    """
    Charles Schwab API adapter.
    
    Note: Charles Schwab uses OAuth2 similar to TD Ameritrade.
    API documentation: https://developer.schwab.com/
    """
    
    def __init__(self, api_key: str, api_secret: str, 
                 account_id: Optional[str] = None, paper_mode: bool = False,
                 client_id: Optional[str] = None, refresh_token: Optional[str] = None,
                 verbose: bool = False):
        """
        Initialize Charles Schwab API client.
        
        Note: api_key IS the client_id, and api_secret IS the client_secret.
        These are OAuth2 client credentials used in Basic auth header.
        
        Args:
            api_key: API key (this IS the client_id for OAuth2)
            api_secret: API secret (this IS the client_secret for OAuth2)
            account_id: Account number (optional, can be retrieved)
            paper_mode: If True, use paper trading endpoints
            client_id: Optional alternative client_id (if different from api_key)
            refresh_token: OAuth2 refresh token (optional, for refresh_token grant)
            verbose: If True, log detailed request/response information
        """
        self.verbose = verbose
        # API Key/Secret are the OAuth2 client credentials
        # api_key = client_id, api_secret = client_secret
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Use api_key as client_id if client_id not provided
        self.client_id = client_id or api_key
        self.refresh_token = refresh_token
        
        self.account_id = account_id
        self.paper_mode = paper_mode
        
        # Base URLs
        # Charles Schwab API uses different base URLs for different endpoints
        if paper_mode:
            self.base_url = "https://api.schwabapi.com/trader/v1/paper"
            self.marketdata_base_url = "https://api.schwabapi.com/marketdata/v1"
        else:
            self.base_url = "https://api.schwabapi.com/trader/v1"
            self.marketdata_base_url = "https://api.schwabapi.com/marketdata/v1"
        
        # Token URL per Charles Schwab documentation
        self.token_url = "https://api.schwabapi.com/v1/oauth/token"
        
        # Separate tokens for marketdata and trader APIs
        self.marketdata_token: Optional[str] = None
        self.marketdata_token_expires_at: Optional[float] = None
        self.trader_token: Optional[str] = None
        self.trader_token_expires_at: Optional[float] = None
        
        # Legacy support - keep access_token for backward compatibility
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        
        # Determine auth method and initialize
        # Note: api_key = client_id, api_secret = client_secret
        # Support multiple authentication methods:
        # 1. client_id/client_secret with refresh_token -> use refresh_token grant (per documentation Step 4)
        # 2. client_id/client_secret only -> use client_credentials grant (may work for some API access levels)
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Must provide api_key (client_id) and api_secret (client_secret).\n"
                "These are your OAuth2 client credentials from Charles Schwab developer portal."
            )
        
        if refresh_token:
            # Use refresh_token grant (per documentation Step 4)
            self.auth_method = "refresh_token"
            # Get initial token using refresh_token grant
            self._authenticate_oauth2()  # Uses refresh_token grant
            self.marketdata_token = self.access_token
            self.marketdata_token_expires_at = self.token_expires_at
            logger.info("Initial token obtained using refresh_token grant (per documentation)")
        else:
            # No refresh token - try client_credentials grant
            self.auth_method = "client_credentials"
            # Get initial token using client_credentials grant
            self._authenticate_api_key()  # Uses client_credentials grant
            self.marketdata_token = self.access_token
            self.marketdata_token_expires_at = self.token_expires_at
            logger.info("Initial token obtained using client_credentials grant")
            # If response includes refresh_token, store it for future use
            if self.refresh_token:
                logger.info("Refresh token received - will use refresh_token grant for future authentications")
                self.auth_method = "refresh_token"
    
    def _authenticate_api_key(self, scope: str = None):
        """
        Authenticate using client_credentials grant.
        
        Note: api_key IS client_id, api_secret IS client_secret.
        
        Uses OAuth2 client credentials grant flow:
        1. Send client_id (api_key) and client_secret (api_secret) to token endpoint
        2. Receive access token (and optionally refresh_token)
        3. Use access token for API calls
        4. Refresh token when it expires (using refresh_token if available, otherwise client_credentials again)
        
        Args:
            scope: Optional scope parameter (e.g., "api" for trader, "market_data" for marketdata)
                   If None, will request tokens for both APIs
        """
        import requests
        import base64
        
        # api_key = client_id, api_secret = client_secret
        # Per documentation, Basic auth uses BASE64_ENCODED_Client_ID:Client_Secret
        client_id = self.client_id  # This is api_key
        client_secret = self.api_secret  # This is the client_secret
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Use client_credentials grant
        payload = {
            "grant_type": "client_credentials"
        }
        
        # Add scope if specified (some APIs require different scopes)
        if scope:
            payload["scope"] = scope
        
        if self.verbose:
            logger.info("=" * 60)
            logger.info("🔐 AUTHENTICATION REQUEST (Client Credentials Grant)")
            logger.info("   Using api_key as client_id, api_secret as client_secret")
            logger.info("=" * 60)
            logger.info(f"URL: {self.token_url}")
            logger.info(f"Method: POST")
            logger.info(f"Headers:")
            for k, v in headers.items():
                if k == "Authorization":
                    # Don't log full credentials, just show it's Basic auth
                    logger.info(f"  {k}: Basic <REDACTED>")
                else:
                    logger.info(f"  {k}: {v}")
            logger.info(f"Payload: {payload}")
            logger.info(f"Scope: {scope or 'None (shared token)'}")
            
            # Generate curl command for easy testing (PowerShell-compatible)
            logger.info("")
            logger.info("📋 CURL COMMAND (PowerShell-compatible):")
            logger.info("-" * 60)
            
            # Build curl command as single line (works in both PowerShell and bash)
            curl_parts = [f"curl -X 'POST'", f"'{self.token_url}'"]
            
            # Add headers (with actual credentials for curl)
            for k, v in headers.items():
                curl_parts.append(f"-H '{k}: {v}'")
            
            # Add form data
            import urllib.parse
            form_data = urllib.parse.urlencode(payload)
            curl_parts.append(f"-d '{form_data}'")
            
            # Single line format (works in PowerShell and bash)
            curl_cmd = " ".join(curl_parts)
            
            logger.info(curl_cmd)
            logger.info("")
            logger.info("(For multi-line in PowerShell, use backticks ` instead of \\ )")
            logger.info("-" * 60)
            logger.info("")
        
        try:
            response = requests.post(self.token_url, headers=headers, data=payload)
            
            if self.verbose:
                logger.info("")
                logger.info("📥 AUTHENTICATION RESPONSE")
                logger.info("=" * 60)
                logger.info(f"Status Code: {response.status_code}")
                logger.info(f"Response Headers:")
                for k, v in response.headers.items():
                    logger.info(f"  {k}: {v}")
            
            response.raise_for_status()
            
            token_data = response.json()
            
            if self.verbose:
                logger.info(f"Response Body (keys only): {list(token_data.keys())}")
                if "access_token" in token_data:
                    token_preview = token_data["access_token"][:30] + "..." if len(token_data["access_token"]) > 30 else token_data["access_token"]
                    logger.info(f"Access Token (preview): {token_preview}")
                if "expires_in" in token_data:
                    logger.info(f"Expires In: {token_data['expires_in']} seconds")
                logger.info("=" * 60)
                logger.info("")
            
            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 1800)  # Default 30 min (per docs: 1800 = 30 minutes)
            
            # Per documentation: Access tokens are valid for 30 minutes (1800 seconds)
            # Refresh tokens are valid for 7 days
            
            # Store refresh_token if provided in response (for future refreshes)
            if "refresh_token" in token_data:
                self.refresh_token = token_data["refresh_token"]
                if self.verbose:
                    logger.info(f"Refresh Token received (valid for 7 days)")
            
            # Ensure expires_in is a number (sometimes API returns string)
            try:
                expires_in = float(expires_in) if expires_in else 1800.0
            except (ValueError, TypeError):
                expires_in = 1800.0  # Default 30 minutes per documentation
            
            expires_at = datetime.now().timestamp() + expires_in
            
            # Store token based on scope or use for both if no scope specified
            if scope:
                if "market" in scope.lower() or "data" in scope.lower():
                    self.marketdata_token = access_token
                    self.marketdata_token_expires_at = expires_at
                    logger.debug(f"Marketdata OAuth token obtained, expires in {expires_in} seconds")
                else:
                    self.trader_token = access_token
                    self.trader_token_expires_at = expires_at
                    logger.debug(f"Trader OAuth token obtained, expires in {expires_in} seconds")
            else:
                # If no scope specified, use same token for both (backward compatibility)
                # But also try to get separate tokens if API supports it
                self.access_token = access_token
                self.token_expires_at = expires_at
                self.marketdata_token = access_token
                self.marketdata_token_expires_at = expires_at
                self.trader_token = access_token
                self.trader_token_expires_at = expires_at
                logger.debug(f"OAuth token obtained (shared), expires in {expires_in} seconds")
            
        except Exception as e:
            logger.error(f"Failed to get OAuth token with API key/secret: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def _authenticate_oauth2(self, scope: str = None):
        """
        Authenticate using OAuth2 refresh token.
        
        Per Charles Schwab documentation:
        POST https://api.schwabapi.com/v1/oauth/token
        -H 'Authorization: Basic {BASE64_ENCODED_Client_ID:Client_Secret}'
        -H 'Content-Type: application/x-www-form-urlencoded'
        -d 'grant_type=refresh_token&refresh_token={REFRESH_TOKEN}'
        
        Args:
            scope: Optional scope parameter (e.g., "api" for trader, "market_data" for marketdata)
                   If None, will request tokens for both APIs
        """
        import requests
        import base64
        
        # api_key = client_id, api_secret = client_secret
        # Per documentation: Use Client_ID:Client_Secret in Basic auth header
        client_id = self.client_id  # This is api_key (or explicitly provided client_id)
        client_secret = self.api_secret  # This is the client_secret
        credentials = f"{client_id}:{client_secret}"
        
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        auth_header = f"Basic {encoded_credentials}"
        
        # OAuth2 with refresh token - per documentation
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        # Add scope if specified
        if scope:
            payload["scope"] = scope
        
        if self.verbose:
            logger.info("=" * 60)
            logger.info("🔐 AUTHENTICATION REQUEST (OAuth2 Refresh Token)")
            logger.info("=" * 60)
            logger.info(f"URL: {self.token_url}")
            logger.info(f"Method: POST")
            logger.info(f"Headers:")
            for k, v in headers.items():
                if k == "Authorization":
                    logger.info(f"  {k}: Basic <REDACTED>")
                else:
                    logger.info(f"  {k}: {v}")
            logger.info(f"Payload: {payload}")
            logger.info(f"Scope: {scope or 'None (shared token)'}")
            
            # Generate curl command for easy testing (PowerShell-compatible)
            logger.info("")
            logger.info("📋 CURL COMMAND (PowerShell-compatible):")
            logger.info("-" * 60)
            
            # Build curl command as single line (works in both PowerShell and bash)
            curl_parts = [f"curl -X 'POST'", f"'{self.token_url}'"]
            
            # Add headers
            for k, v in headers.items():
                curl_parts.append(f"-H '{k}: {v}'")
            
            # Add form data
            import urllib.parse
            form_data = urllib.parse.urlencode(payload)
            curl_parts.append(f"-d '{form_data}'")
            
            # Single line format (works in PowerShell and bash)
            curl_cmd = " ".join(curl_parts)
            
            logger.info(curl_cmd)
            logger.info("")
            logger.info("(For multi-line in PowerShell, use backticks ` instead of \\ )")
            logger.info("-" * 60)
            logger.info("")
        
        response = requests.post(self.token_url, headers=headers, data=payload)
        
        if self.verbose:
            logger.info("")
            logger.info("📥 AUTHENTICATION RESPONSE")
            logger.info("=" * 60)
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response Headers:")
            for k, v in response.headers.items():
                logger.info(f"  {k}: {v}")
        
        response.raise_for_status()
        
        token_data = response.json()
        
        if self.verbose:
            logger.info(f"Response Body (keys only): {list(token_data.keys())}")
            if "access_token" in token_data:
                token_preview = token_data["access_token"][:30] + "..." if len(token_data["access_token"]) > 30 else token_data["access_token"]
                logger.info(f"Access Token (preview): {token_preview}")
            if "expires_in" in token_data:
                logger.info(f"Expires In: {token_data['expires_in']} seconds")
            logger.info("=" * 60)
            logger.info("")
        
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 1800)  # Default 30 min (per docs: 1800 = 30 minutes)
        
        # Per documentation: Access tokens are valid for 30 minutes (1800 seconds)
        # Refresh tokens are valid for 7 days
        # If a new refresh_token is provided, update it
        if "refresh_token" in token_data:
            self.refresh_token = token_data["refresh_token"]
            if self.verbose:
                logger.info(f"New Refresh Token received (valid for 7 days)")
        
        # Ensure expires_in is a number (sometimes API returns string)
        try:
            expires_in = float(expires_in) if expires_in else 1800.0
        except (ValueError, TypeError):
            expires_in = 1800.0  # Default 30 minutes per documentation
        
        expires_at = datetime.now().timestamp() + expires_in
        
        # Store token based on scope or use for both if no scope specified
        if scope:
            if "market" in scope.lower() or "data" in scope.lower():
                self.marketdata_token = access_token
                self.marketdata_token_expires_at = expires_at
                logger.debug(f"Marketdata OAuth token refreshed, expires in {expires_in} seconds")
            else:
                self.trader_token = access_token
                self.trader_token_expires_at = expires_at
                logger.debug(f"Trader OAuth token refreshed, expires in {expires_in} seconds")
        else:
            # If no scope specified, use same token for both (backward compatibility)
            self.access_token = access_token
            self.token_expires_at = expires_at
            self.marketdata_token = access_token
            self.marketdata_token_expires_at = expires_at
            self.trader_token = access_token
            self.trader_token_expires_at = expires_at
            logger.debug(f"OAuth token refreshed (shared), expires in {expires_in} seconds")
    
    def _ensure_authenticated(self, use_marketdata_base: bool = False):
        """
        Refresh OAuth token if expired.
        
        Args:
            use_marketdata_base: If True, ensure marketdata token is valid.
                                 If False, ensure trader token is valid.
        """
        now = datetime.now().timestamp()
        api_type = "marketdata" if use_marketdata_base else "trader"
        
        if self.verbose:
            logger.info(f"🔍 Checking authentication for {api_type} API...")
            if use_marketdata_base:
                logger.info(f"  Marketdata token: {'Present' if self.marketdata_token else 'Missing'}")
                if self.marketdata_token_expires_at:
                    expires_dt = datetime.fromtimestamp(self.marketdata_token_expires_at)
                    logger.info(f"  Expires at: {expires_dt}")
            else:
                logger.info(f"  Trader token: {'Present' if self.trader_token else 'Missing'}")
                if self.trader_token_expires_at:
                    expires_dt = datetime.fromtimestamp(self.trader_token_expires_at)
                    logger.info(f"  Expires at: {expires_dt}")
            logger.info(f"  Access token: {'Present' if self.access_token else 'Missing'}")
            if self.token_expires_at:
                expires_dt = datetime.fromtimestamp(self.token_expires_at)
                logger.info(f"  Expires at: {expires_dt}")
        
        if use_marketdata_base:
            # Marketdata API: can reuse token and refresh it
            if not self.marketdata_token or (self.marketdata_token_expires_at and now >= self.marketdata_token_expires_at):
                if self.verbose:
                    logger.info("  ⚠️  Marketdata token expired or missing, refreshing...")
                if self.auth_method == "refresh_token" or self.auth_method == "oauth2_refresh":
                    # Use refresh_token grant if available
                    self._authenticate_oauth2()
                    self.marketdata_token = self.access_token
                    self.marketdata_token_expires_at = self.token_expires_at
                elif self.auth_method == "client_credentials":
                    # Use client_credentials grant
                    self._authenticate_api_key()
                    self.marketdata_token = self.access_token
                    self.marketdata_token_expires_at = self.token_expires_at
                    # If we got a refresh_token, switch to refresh_token method for next time
                    if self.refresh_token:
                        self.auth_method = "refresh_token"
                        logger.debug("Switched to refresh_token grant method (refresh_token received)")
                else:
                    raise ValueError(f"Unknown auth method: {self.auth_method}")
            # Use existing marketdata token if still valid
            if not self.marketdata_token:
                self.marketdata_token = self.access_token
                self.marketdata_token_expires_at = self.token_expires_at
        else:
            # Trader/Accounts API: use API key/secret (client_credentials or refresh_token if available)
            if self.verbose:
                logger.info("  🔄 Checking trader token (using API key/secret)...")
            
            # Trader API requires API key/secret
            if not self.api_key or not self.api_secret:
                raise ValueError(
                    "Trader API requires API key/secret authentication. "
                    "Please provide api_key and api_secret."
                )
            
            # Check if trader token exists and is still valid
            if not self.trader_token or (self.trader_token_expires_at and now >= self.trader_token_expires_at):
                # Get fresh token using available method
                if self.verbose:
                    logger.info("  🔄 Getting new bearer token for trader API...")
                if self.refresh_token:
                    # Prefer refresh_token grant if available
                    self._authenticate_oauth2()
                else:
                    # Use client_credentials grant
                    self._authenticate_api_key()
                # Store as trader token
                self.trader_token = self.access_token
                self.trader_token_expires_at = self.token_expires_at
                # If we got a refresh_token, use it for next time
                if self.refresh_token and self.auth_method == "client_credentials":
                    self.auth_method = "refresh_token"
                    logger.debug("Switched to refresh_token grant method (refresh_token received)")
            # Trader token is separate from marketdata token
        
        if self.verbose:
            if use_marketdata_base:
                token_preview = (self.marketdata_token[:30] + "...") if self.marketdata_token and len(self.marketdata_token) > 30 else self.marketdata_token
                logger.info(f"  ✅ Using marketdata token: {token_preview}")
            else:
                token_preview = (self.trader_token[:30] + "...") if self.trader_token and len(self.trader_token) > 30 else self.trader_token
                logger.info(f"  ✅ Using trader token: {token_preview}")
    
    def _request(self, method: str, endpoint: str, use_marketdata_base: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            use_marketdata_base: If True, use marketdata base URL and marketdata token
            **kwargs: Additional arguments for requests (params, json, etc.)
        """
        import requests
        import time
        
        # Ensure appropriate token is valid
        self._ensure_authenticated(use_marketdata_base=use_marketdata_base)
        
        # Use marketdata base URL for market data endpoints
        base = self.marketdata_base_url if use_marketdata_base else self.base_url
        url = f"{base}/{endpoint.lstrip('/')}"
        
        # Select appropriate token
        if use_marketdata_base:
            token = self.marketdata_token or self.access_token
        else:
            token = self.trader_token or self.access_token
        
        if not token:
            raise ValueError(f"No valid token available for {'marketdata' if use_marketdata_base else 'trader'} API")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        # Only add Content-Type for non-GET requests with body
        if method.upper() != "GET" and ("json" in kwargs or "data" in kwargs):
            headers["Content-Type"] = "application/json"
        
        if self.verbose:
            logger.info("=" * 60)
            logger.info(f"🌐 API REQUEST ({'Marketdata' if use_marketdata_base else 'Trader'} API)")
            logger.info("=" * 60)
            logger.info(f"URL: {url}")
            logger.info(f"Method: {method}")
            logger.info(f"Headers:")
            for k, v in headers.items():
                if k == "Authorization":
                    token_preview = token[:30] + "..." if len(token) > 30 else token
                    logger.info(f"  {k}: Bearer {token_preview}")
                else:
                    logger.info(f"  {k}: {v}")
            if "params" in kwargs:
                logger.info(f"Params: {kwargs['params']}")
            if "json" in kwargs:
                logger.info(f"JSON Body: {kwargs['json']}")
            
            # Generate curl command for easy testing (PowerShell-compatible)
            logger.info("")
            logger.info("📋 CURL COMMAND (PowerShell-compatible):")
            logger.info("=" * 60)
            
            # Build URL with params
            curl_url = url
            if "params" in kwargs and kwargs["params"]:
                import urllib.parse
                param_pairs = [f"{k}={urllib.parse.quote(str(v))}" for k, v in kwargs["params"].items()]
                if param_pairs:
                    curl_url = f"{url}?{'&'.join(param_pairs)}"
            
            # Build curl command as single line (works in both PowerShell and bash)
            curl_parts = [f"curl -X '{method.upper()}'", f"'{curl_url}'"]
            
            # Add headers
            for k, v in headers.items():
                curl_parts.append(f"-H '{k}: {v}'")
            
            # Add JSON body if present
            if "json" in kwargs:
                import json
                json_str = json.dumps(kwargs["json"]).replace("'", "\\'")
                curl_parts.append(f"-d '{json_str}'")
            elif "data" in kwargs:
                data_str = str(kwargs["data"]).replace("'", "\\'")
                curl_parts.append(f"-d '{data_str}'")
            
            # Single line format (works in PowerShell and bash)
            curl_cmd = " ".join(curl_parts)
            
            logger.info(curl_cmd)
            logger.info("=" * 60)
            logger.info("")
        
        # Rate limiting: Charles Schwab allows 120 requests per minute
        time.sleep(0.5)  # 0.5 second minimum between requests
        
        response = requests.request(method, url, headers=headers, **kwargs)
        
        if self.verbose:
            logger.info("📥 API RESPONSE")
            logger.info("=" * 60)
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response Headers:")
            for k, v in response.headers.items():
                logger.info(f"  {k}: {v}")
            try:
                response_data = response.json()
                logger.info(f"Response Body (keys only): {list(response_data.keys()) if isinstance(response_data, dict) else type(response_data)}")
            except:
                logger.info(f"Response Body (text): {response.text[:200]}...")
            logger.info("=" * 60)
            logger.info("")
        
        if response.status_code == 401:
            # Token expired or invalid for this API, get a fresh token
            if self.verbose:
                logger.warning(f"⚠️  Got 401 error, refreshing token for {'marketdata' if use_marketdata_base else 'trader'} API...")
            
            # Force a fresh token request (don't rely on expiration check)
            if use_marketdata_base:
                # Marketdata API: refresh using available method
                if self.auth_method == "refresh_token" or self.auth_method == "oauth2_refresh":
                    self._authenticate_oauth2()  # Get fresh token using refresh_token grant
                elif self.auth_method == "client_credentials":
                    self._authenticate_api_key()  # Get fresh token using client_credentials grant
                self.marketdata_token = self.access_token
                self.marketdata_token_expires_at = self.token_expires_at
                # Use the fresh token
                token = self.marketdata_token or self.access_token
            else:
                # Trader API: use API key/secret (refresh_token if available, otherwise client_credentials)
                if not self.api_key or not self.api_secret:
                    raise ValueError(
                        "Trader API requires API key/secret authentication. "
                        "Cannot refresh token for trader API without api_key and api_secret."
                    )
                # Prefer refresh_token grant if available, otherwise use client_credentials
                if self.refresh_token:
                    self._authenticate_oauth2()  # Get fresh token using refresh_token grant
                else:
                    self._authenticate_api_key()  # Get fresh token using client_credentials grant
                # Store as trader token
                self.trader_token = self.access_token
                self.trader_token_expires_at = self.token_expires_at
                # Use the fresh token
                token = self.trader_token or self.access_token
            
            if not token:
                raise ValueError(f"Failed to get valid token for {'marketdata' if use_marketdata_base else 'trader'} API after 401")
            
            headers["Authorization"] = f"Bearer {token}"
            if self.verbose:
                token_preview = token[:30] + "..." if len(token) > 30 else token
                logger.info(f"  🔄 Retrying request with fresh token: {token_preview}")
            response = requests.request(method, url, headers=headers, **kwargs)
        
        # Better error handling - show actual API error message
        if not response.ok:
            error_msg = f"API Error {response.status_code}: {response.text}"
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = f"API Error {response.status_code}: {error_data.get('message', error_data.get('error', error_data.get('error_description', response.text)))}"
                    # Log full error for debugging
                    logger.error(f"Full error response: {error_data}")
            except:
                logger.error(f"Raw response: {response.text[:500]}")  # First 500 chars
            logger.error(f"Request failed: {method} {url}")
            logger.error(f"Request params: {kwargs.get('params', {})}")
            logger.error(f"Error: {error_msg}")
            response.raise_for_status()
        
        return response.json()
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get current quote for a symbol.
        
        Uses correct Charles Schwab API endpoint format:
        GET /marketdata/v1/quotes?symbols=SYMBOL&indicative=false
        """
        endpoint = "quotes"
        params = {
            "symbols": symbol,
            "indicative": "false"
        }
        
        try:
            data = self._request("GET", endpoint, use_marketdata_base=True, params=params)
            
            # Handle response format - quotes are typically in a dict keyed by symbol
            if isinstance(data, dict):
                # Try symbol as key
                if symbol in data:
                    return data[symbol]
                # Try uppercase symbol
                if symbol.upper() in data:
                    return data[symbol.upper()]
                # Check if it's a list of quotes
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                # Return full data if it looks like quote data
                if any(k in data for k in ['lastPrice', 'bidPrice', 'askPrice', 'last', 'bid', 'ask', 'quoteTime']):
                    return data
            return data
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            raise
    
    def get_chain(self, symbol: str, strike_count: int = 50, 
                  include_quotes: bool = True, strategy: str = "SINGLE",
                  interval: int = 0, range_type: str = "ALL",
                  from_date: Optional[str] = None, to_date: Optional[str] = None,
                  exp_month: str = "ALL") -> Dict[str, Any]:
        """
        Get options chain for underlying symbol.
        
        Uses marketdata base URL for options chain endpoint.
        
        Args:
            symbol: Underlying symbol (e.g., "SPX")
            strike_count: Number of strikes above/below ATM
            include_quotes: Include bid/ask quotes
            strategy: Option strategy type
            interval: Strike interval
            range_type: Strike range (ITM, OTM, ALL, etc.)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            exp_month: Expiration month filter
        """
        endpoint = "chains"
        
        # Build params - Charles Schwab format
        params = {
            "symbol": symbol,
            "strikeCount": strike_count,
            "includeQuotes": str(include_quotes).lower(),
            "strategy": strategy,
            "interval": interval,
            "range": range_type,
        }
        
        if exp_month and exp_month != "ALL":
            params["expMonth"] = exp_month
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        try:
            return self._request("GET", endpoint, use_marketdata_base=True, params=params)
        except Exception as e:
            logger.error(f"Failed to get options chain for {symbol}: {e}")
            raise
    
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place a single or multi-leg order.
        
        Order format:
        {
            "orderType": "LIMIT" | "MARKET",
            "session": "NORMAL",
            "duration": "DAY" | "GOOD_TILL_CANCEL",
            "orderStrategyType": "SINGLE" | "OCO" | "TRIGGER",
            "price": float,  # For LIMIT orders
            "orderLegCollection": [
                {
                    "instruction": "BUY" | "SELL" | "BUY_TO_OPEN" | "SELL_TO_OPEN" | "BUY_TO_CLOSE" | "SELL_TO_CLOSE",
                    "quantity": int,
                    "instrument": {
                        "symbol": str,
                        "assetType": "OPTION"
                    }
                }
            ]
        }
        """
        if not self.account_id:
            # Try to get account ID from account info
            account_info = self.get_account_info()
            self.account_id = account_info.get("accountNumber")
        
        endpoint = f"accounts/{self.account_id}/orders"
        return self._request("POST", endpoint, json=order)
    
    def replace_order(self, order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
        """Replace an existing order."""
        if not self.account_id:
            account_info = self.get_account_info()
            self.account_id = account_info.get("accountNumber")
        
        endpoint = f"accounts/{self.account_id}/orders/{order_id}"
        return self._request("PUT", endpoint, json=order)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.account_id:
            account_info = self.get_account_info()
            self.account_id = account_info.get("accountNumber")
        
        endpoint = f"accounts/{self.account_id}/orders/{order_id}"
        try:
            self._request("DELETE", endpoint)
            return True
        except Exception as e:
            print(f"Error canceling order {order_id}: {e}")
            return False
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self.account_id:
            account_info = self.get_account_info()
            self.account_id = account_info.get("accountNumber")
        
        endpoint = f"accounts/{self.account_id}/positions"
        data = self._request("GET", endpoint)
        return data.get("positions", [])
    
    def get_fills(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get fill information for orders."""
        if not self.account_id:
            account_info = self.get_account_info()
            self.account_id = account_info.get("accountNumber")
        
        endpoint = f"accounts/{self.account_id}/orders"
        params = {"maxResults": 1000}
        if order_id:
            endpoint = f"{endpoint}/{order_id}"
        
        data = self._request("GET", endpoint, params=params)
        
        if order_id:
            return [data] if data else []
        else:
            # Filter for filled orders
            orders = data.get("orders", [])
            return [o for o in orders if o.get("status") == "FILLED"]
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information and balances.
        
        Uses trader API base URL: GET /trader/v1/accounts/accountNumbers
        """
        # If account_id not set, get account list first
        if not self.account_id:
            endpoint = "accounts/accountNumbers"
            if self.verbose:
                logger.info("=" * 60)
                logger.info("🔍 Getting Account Numbers")
                logger.info("=" * 60)
                logger.info(f"Endpoint: {endpoint}")
                logger.info(f"API: Trader API (accounts)")
                logger.info("")
            try:
                # Accounts endpoints use trader base URL (not marketdata)
                accounts = self._request("GET", endpoint, use_marketdata_base=False)
                
                # Handle response format - could be list or dict
                account_list = []
                if isinstance(accounts, list):
                    account_list = accounts
                elif isinstance(accounts, dict):
                    # Try different possible keys
                    account_list = accounts.get("accounts", accounts.get("accountNumbers", []))
                    if not account_list and len(accounts) > 0:
                        # If it's a dict with account data directly
                        account_list = [accounts]
                
                if account_list and len(account_list) > 0:
                    # Get first account number
                    first_account = account_list[0]
                    self.account_id = first_account.get("accountNumber") or first_account.get("accountId") or first_account.get("account")
                    logger.info(f"Retrieved account ID: {self.account_id}")
                else:
                    logger.warning(f"Account list response format unexpected: {accounts}")
            except Exception as e:
                logger.error(f"Failed to get account numbers: {e}")
                # Don't raise - allow manual account_id setting
        
        if not self.account_id:
            logger.warning("Could not retrieve account ID automatically. Please set account_id in config.")
            # Return empty dict instead of raising error for testing
            return {}
        
        # Get account details - use trader base URL
        endpoint = f"accounts/{self.account_id}"
        try:
            return self._request("GET", endpoint, use_marketdata_base=False)
        except Exception as e:
            logger.error(f"Failed to get account info for {self.account_id}: {e}")
            raise


class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper trading adapter that simulates broker without real orders.
    Useful for testing and development.
    """
    
    def __init__(self):
        self.orders: Dict[str, Dict] = {}
        self.positions: List[Dict] = []
        self.fills: List[Dict] = []
        self.account_balance = 100000.0  # Starting paper balance
        self.order_counter = 0
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Simulated quote - would need real market data feed."""
        return {
            "bid": 0.0,
            "ask": 0.0,
            "last": 0.0,
            "mark": 0.0
        }
    
    def get_chain(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """Simulated chain - would need real market data feed."""
        return {"callExpDateMap": {}, "putExpDateMap": {}, "underlying": {}}
    
    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate order placement."""
        self.order_counter += 1
        order_id = f"PAPER_{self.order_counter}"
        
        order["orderId"] = order_id
        order["status"] = "FILLED"  # Auto-fill in paper mode
        self.orders[order_id] = order
        
        # Simulate fill
        fill = {
            "orderId": order_id,
            "timestamp": datetime.now().isoformat(),
            "fills": []
        }
        
        for leg in order.get("orderLegCollection", []):
            fill["fills"].append({
                "price": order.get("price", 0.0),
                "quantity": leg.get("quantity", 0)
            })
        
        self.fills.append(fill)
        return {"orderId": order_id, "status": "FILLED"}
    
    def replace_order(self, order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate order replacement."""
        if order_id in self.orders:
            self.orders[order_id].update(order)
            return {"orderId": order_id, "status": "REPLACED"}
        raise ValueError(f"Order {order_id} not found")
    
    def cancel_order(self, order_id: str) -> bool:
        """Simulate order cancellation."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "CANCELED"
            return True
        return False
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get simulated positions."""
        return self.positions.copy()
    
    def get_fills(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get simulated fills."""
        if order_id:
            return [f for f in self.fills if f.get("orderId") == order_id]
        return self.fills.copy()
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get simulated account info."""
        return {
            "accountNumber": "PAPER_ACCOUNT",
            "accountType": "PAPER",
            "currentBalances": {
                "cashBalance": self.account_balance,
                "buyingPower": self.account_balance * 2
            }
        }
