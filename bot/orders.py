"""
Order placement logic.

Sits between cli.py (user input) and client.py (raw HTTP).
Formats responses into a clean, printable structure.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceAPIError
from .validators import validate_order_params, ValidationError
from .logging_config import get_logger

logger = get_logger("trading_bot.orders")


# -- Response formatter --------------------------------------------------------

def format_order_response(resp: dict) -> Dict[str, Any]:
    """
    Extract the fields we care about from a raw Binance order response.
    Returns a clean dict suitable for display.
    """
    return {
        "orderId":     resp.get("orderId"),
        "symbol":      resp.get("symbol"),
        "side":        resp.get("side"),
        "type":        resp.get("type"),
        "origQty":     resp.get("origQty"),
        "executedQty": resp.get("executedQty"),
        "avgPrice":    resp.get("avgPrice"),
        "price":       resp.get("price"),
        "stopPrice":   resp.get("stopPrice"),
        "status":      resp.get("status"),
        "timeInForce": resp.get("timeInForce"),
        "updateTime":  resp.get("updateTime"),
    }


def print_order_summary(params: dict) -> None:
    """Print a summary of what we're about to send."""
    print("\n" + "═" * 52)
    print("  ORDER REQUEST SUMMARY")
    print("═" * 52)
    print(f"  Symbol     : {params.get('symbol')}")
    print(f"  Side       : {params.get('side')}")
    print(f"  Type       : {params.get('type')}")
    print(f"  Quantity   : {params.get('quantity')}")
    if params.get("price"):
        print(f"  Price      : {params.get('price')}")
    if params.get("stopPrice"):
        print(f"  Stop Price : {params.get('stopPrice')}")
    if params.get("timeInForce"):
        print(f"  TIF        : {params.get('timeInForce')}")
    print("═" * 52 + "\n")


def print_order_result(fmt: Dict[str, Any], success: bool) -> None:
    """Print a formatted order result."""
    print("\n" + "═" * 52)
    print("  ORDER RESPONSE")
    print("═" * 52)
    if success:
        print(f"  ✓ Status      : {fmt.get('status')}")
        print(f"  Order ID      : {fmt.get('orderId')}")
        print(f"  Symbol        : {fmt.get('symbol')}")
        print(f"  Side          : {fmt.get('side')}")
        print(f"  Type          : {fmt.get('type')}")
        print(f"  Orig Qty      : {fmt.get('origQty')}")
        print(f"  Executed Qty  : {fmt.get('executedQty')}")
        if fmt.get("avgPrice") not in (None, "0", "0.00000000"):
            print(f"  Avg Price     : {fmt.get('avgPrice')}")
        if fmt.get("price") not in (None, "0", "0.00000000"):
            print(f"  Limit Price   : {fmt.get('price')}")
        if fmt.get("stopPrice") not in (None, "0", "0.00000000"):
            print(f"  Stop Price    : {fmt.get('stopPrice')}")
        if fmt.get("timeInForce"):
            print(f"  Time-in-Force : {fmt.get('timeInForce')}")
        print("\n  ✓ Order placed successfully.")
    else:
        print("  ✗ Order FAILED — see error above.")
    print("═" * 52 + "\n")


# -- Main order function -------------------------------------------------------

def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Validate → summarise → place → format → display.

    Returns the formatted response dict on success, None on failure.
    """
    # 1. Validate
    try:
        params = validate_order_params(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValidationError as exc:
        logger.error("Validation failed: %s", exc)
        print(f"\n  ✗ Validation Error: {exc}\n")
        return None

    # 2. Print what we're sending
    print_order_summary(params)

    # 3. Place the order
    try:
        raw = client.place_order(params)
    except BinanceAPIError as exc:
        logger.error("Order placement failed | code=%d | msg=%s", exc.code, exc.message)
        print(f"\n  ✗ Binance API Error [{exc.code}]: {exc.message}\n")
        print_order_result({}, success=False)
        return None
    except (ConnectionError, TimeoutError) as exc:
        logger.error("Network error during order placement: %s", exc)
        print(f"\n  ✗ Network Error: {exc}\n")
        print_order_result({}, success=False)
        return None

    # 4. Format and display
    fmt = format_order_response(raw)
    print_order_result(fmt, success=True)
    logger.info("Order result | %s", fmt)
    return fmt
