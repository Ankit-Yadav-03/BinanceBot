"""
Input validation for order parameters.
All validation logic lives here — keeps client.py and cli.py clean.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional


# -- Constants -----------------------------------------------------------------

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}
VALID_TIME_IN_FORCE = {"GTC", "IOC", "FOK"}

MIN_QTY = Decimal("0.001")
MAX_QTY = Decimal("1000000")


# -- Exceptions ----------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when any order parameter fails validation."""


# -- Validators ----------------------------------------------------------------

def validate_symbol(symbol: str) -> str:
    """Normalize and validate trading symbol."""
    if not symbol or not isinstance(symbol, str):
        raise ValidationError("Symbol must be a non-empty string.")
    s = symbol.strip().upper()
    if len(s) < 4 or len(s) > 20:
        raise ValidationError(f"Symbol '{s}' looks invalid (length {len(s)}).")
    if not s.isalnum():
        raise ValidationError(f"Symbol '{s}' must be alphanumeric only.")
    return s


def validate_side(side: str) -> str:
    """Validate order side."""
    if not side:
        raise ValidationError("Side is required.")
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{s}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return s


def validate_order_type(order_type: str) -> str:
    """Validate order type."""
    if not order_type:
        raise ValidationError("Order type is required.")
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{t}'. Supported: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return t


def validate_quantity(qty: str | float) -> str:
    """Validate and return quantity as a string (Binance expects strings)."""
    try:
        q = Decimal(str(qty))
    except InvalidOperation:
        raise ValidationError(f"Quantity '{qty}' is not a valid number.")
    if q <= 0:
        raise ValidationError("Quantity must be greater than 0.")
    if q < MIN_QTY:
        raise ValidationError(f"Quantity {q} is below the minimum allowed ({MIN_QTY}).")
    if q > MAX_QTY:
        raise ValidationError(f"Quantity {q} exceeds the maximum allowed ({MAX_QTY}).")
    return str(q)


def validate_price(price: str | float | None, order_type: str) -> Optional[str]:
    """
    Validate price field.
    - MARKET     : price is irrelevant — ignored, returns None.
    - LIMIT      : price is required and must be > 0.
    - STOP_MARKET: price is NOT sent to Binance — only stopPrice is used.
    """
    order_type = order_type.upper()

    if order_type in ("MARKET", "STOP_MARKET"):
        # Binance does not accept a 'price' field for these types
        return None

    # LIMIT requires a price
    if price is None:
        raise ValidationError(f"--price is required for {order_type} orders.")
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValidationError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValidationError("Price must be greater than 0.")
    return str(p)


def validate_stop_price(stop_price: str | float | None, order_type: str) -> Optional[str]:
    """Validate stop price — required only for STOP_MARKET orders."""
    if order_type.upper() != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValidationError("stopPrice is required for STOP_MARKET orders.")
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValidationError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValidationError("Stop price must be greater than 0.")
    return str(sp)


def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> dict:
    """
    Run all validations and return a clean, normalized parameter dict
    ready to be sent directly to the Binance API.

    Param sets per order type:
      MARKET      : symbol, side, type, quantity
      LIMIT       : symbol, side, type, quantity, price, timeInForce
      STOP_MARKET : symbol, side, type, quantity, stopPrice

    Raises ValidationError on the first failure encountered.
    """
    v_symbol = validate_symbol(symbol)
    v_side   = validate_side(side)
    v_type   = validate_order_type(order_type)
    v_qty    = validate_quantity(quantity)
    v_price  = validate_price(price, v_type)
    v_stop   = validate_stop_price(stop_price, v_type)

    result: dict = {
        "symbol":   v_symbol,
        "side":     v_side,
        "type":     v_type,
        "quantity": v_qty,
    }

    if v_type == "LIMIT":
        result["price"]       = v_price   # guaranteed non-None by validate_price
        result["timeInForce"] = "GTC"     # standard default; override via --tif if needed

    if v_type == "STOP_MARKET":
        result["stopPrice"] = v_stop      # guaranteed non-None by validate_stop_price

    return result
