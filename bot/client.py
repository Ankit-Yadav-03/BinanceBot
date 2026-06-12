"""
Binance Futures Testnet — low-level REST client.

Uses only `requests` (no python-binance) so the HTTP layer is
transparent and every request/response is fully logged.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import get_logger

logger = get_logger("trading_bot.client")

# -- Base URL ------------------------------------------------------------------
BASE_URL = "https://testnet.binancefuture.com"

# -- Timeouts ------------------------------------------------------------------
CONNECT_TIMEOUT = 5   # seconds
READ_TIMEOUT    = 10  # seconds


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx response or an error JSON body."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API error [{code}]: {message}")


class BinanceFuturesClient:
    """
    Thread-safe, minimal Binance USDT-M Futures REST client.

    Parameters
    ----------
    api_key    : Testnet API key
    api_secret : Testnet API secret
    base_url   : Override if needed (default: testnet)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError(
                "API key and secret are required. "
                "Set BINANCE_API_KEY / BINANCE_API_SECRET env vars."
            )
        self._api_key    = api_key
        self._api_secret = api_secret.encode()
        self._base_url   = base_url.rstrip("/")
        self._session    = self._build_session()

        logger.info("BinanceFuturesClient initialised | base_url=%s", self._base_url)

    # -- Session ---------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        return s

    # -- Signing ---------------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        """Append a HMAC-SHA256 signature and current timestamp to params."""
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
            self._api_secret,
            query.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        params["signature"] = sig
        return params

    # -- Low-level request -----------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        signed: bool = False,
    ) -> Any:
        url = f"{self._base_url}{path}"
        p   = dict(params or {})

        if signed:
            p = self._sign(p)

        # Log the outgoing request (mask the secret from log)
        safe_params = {k: v for k, v in p.items() if k != "signature"}
        logger.info(">>> %s %s | params=%s", method.upper(), path, safe_params)

        try:
            resp = self._session.request(
                method,
                url,
                params=p if method.upper() == "GET" else None,
                data=p  if method.upper() != "GET" else None,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.ConnectionError as exc:
            logger.error("Network connection failed: %s", exc)
            raise ConnectionError(f"Cannot reach Binance testnet: {exc}") from exc
        except requests.Timeout as exc:
            logger.error("Request timed out: %s", exc)
            raise TimeoutError(f"Request timed out after {READ_TIMEOUT}s: {exc}") from exc

        # Log raw response
        logger.info(
            "<<< %s %s | status=%d | body=%s",
            method.upper(),
            path,
            resp.status_code,
            resp.text[:500],   # cap at 500 chars so logs stay readable
        )

        # Parse JSON
        try:
            data = resp.json()
        except ValueError:
            logger.error("Non-JSON response: %s", resp.text)
            raise BinanceAPIError(-1, f"Non-JSON response: {resp.text}")

        # Binance error body has {"code": <negative int>, "msg": "..."}
        if isinstance(data, dict) and data.get("code", 0) < 0:
            code = data["code"]
            msg  = data.get("msg", "Unknown error")
            logger.error("Binance API error | code=%d | msg=%s", code, msg)
            raise BinanceAPIError(code, msg)

        if not resp.ok:
            logger.error("HTTP %d: %s", resp.status_code, resp.text)
            raise BinanceAPIError(resp.status_code, resp.text)

        return data

    # -- Public API endpoints --------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in ms (also validates connectivity)."""
        data = self._request("GET", "/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self) -> dict:
        """Return full exchange info (symbols, filters, limits)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_account(self) -> dict:
        """Return account info (balances, positions)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Return all open orders, optionally filtered by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)

    # -- Order placement -------------------------------------------------------

    def place_order(self, order_params: Dict[str, Any]) -> dict:
        """
        Place a new order on USDT-M Futures.

        Parameters
        ----------
        order_params : dict returned by validators.validate_order_params()

        Returns
        -------
        Raw Binance order response dict.
        """
        logger.info("Placing order | %s", order_params)
        response = self._request(
            "POST",
            "/fapi/v1/order",
            params=order_params,
            signed=True,
        )
        logger.info("Order placed successfully | orderId=%s", response.get("orderId"))
        return response

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an existing open order."""
        params = {"symbol": symbol.upper(), "orderId": order_id}
        logger.info("Cancelling order | symbol=%s | orderId=%d", symbol, order_id)
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)


# -- Factory helper ------------------------------------------------------------

def client_from_env() -> BinanceFuturesClient:
    """
    Build a client using environment variables.

    Required env vars:
      BINANCE_API_KEY
      BINANCE_API_SECRET
    """
    api_key    = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        raise EnvironmentError(
            "BINANCE_API_KEY and BINANCE_API_SECRET must be set.\n"
            "Export them or create a .env file and use `python-dotenv`."
        )
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
