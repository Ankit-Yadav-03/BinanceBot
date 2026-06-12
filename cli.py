#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Binance Futures Testnet trading bot.

Usage examples:
  python cli.py order --symbol BTCUSDT --side BUY  --type MARKET --qty 0.01
  python cli.py order --symbol ETHUSDT --side SELL --type LIMIT  --qty 0.1 --price 3200
  python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 58000
  python cli.py account
  python cli.py open-orders --symbol BTCUSDT
  python cli.py ping
"""

from __future__ import annotations

import argparse
import sys
import os

# Allow running from the project root
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()  # loads .env file if present

from bot.client import client_from_env, BinanceAPIError
from bot.orders import place_order
from bot.logging_config import get_logger

logger = get_logger("trading_bot.cli")


# ── Subcommand: ping ──────────────────────────────────────────────────────────

def cmd_ping(args: argparse.Namespace) -> None:
    """Check connectivity to Binance Futures Testnet."""
    client = client_from_env()
    try:
        ts = client.get_server_time()
        print(f"\n  ✓ Connected to Binance Futures Testnet")
        print(f"    Server time: {ts} ms\n")
        logger.info("Ping successful | serverTime=%d", ts)
    except Exception as exc:
        print(f"\n  ✗ Ping failed: {exc}\n")
        logger.error("Ping failed: %s", exc)
        sys.exit(1)


# ── Subcommand: account ───────────────────────────────────────────────────────

def cmd_account(args: argparse.Namespace) -> None:
    """Show account balances (non-zero assets only)."""
    client = client_from_env()
    try:
        data = client.get_account()
        assets = [a for a in data.get("assets", []) if float(a.get("walletBalance", 0)) != 0]
        print("\n  ACCOUNT BALANCES")
        print("  " + "─" * 40)
        if not assets:
            print("  No non-zero balances found.")
        for a in assets:
            print(f"  {a['asset']:<10} wallet={a['walletBalance']:<18} unrealizedPnl={a.get('unrealizedProfit', '0')}")
        print()
    except BinanceAPIError as exc:
        print(f"\n  ✗ API Error [{exc.code}]: {exc.message}\n")
        sys.exit(1)


# ── Subcommand: open-orders ───────────────────────────────────────────────────

def cmd_open_orders(args: argparse.Namespace) -> None:
    """List open orders, optionally filtered by symbol."""
    client = client_from_env()
    try:
        orders = client.get_open_orders(symbol=args.symbol)
        print(f"\n  OPEN ORDERS{' for ' + args.symbol if args.symbol else ''}")
        print("  " + "─" * 50)
        if not orders:
            print("  No open orders.\n")
            return
        for o in orders:
            print(
                f"  [{o['orderId']}] {o['symbol']} {o['side']} {o['type']}"
                f"  qty={o['origQty']}  price={o['price']}  status={o['status']}"
            )
        print()
    except BinanceAPIError as exc:
        print(f"\n  ✗ API Error [{exc.code}]: {exc.message}\n")
        sys.exit(1)


# ── Subcommand: order ─────────────────────────────────────────────────────────

def cmd_order(args: argparse.Namespace) -> None:
    """Place a new order (MARKET / LIMIT / STOP_MARKET)."""
    client = client_from_env()
    logger.info(
        "CLI order request | symbol=%s side=%s type=%s qty=%s price=%s stop=%s",
        args.symbol, args.side, args.type, args.qty, args.price, args.stop_price,
    )
    result = place_order(
        client=client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.type,
        quantity=args.qty,
        price=args.price,
        stop_price=args.stop_price,
    )
    if result is None:
        sys.exit(1)


# ── Parser setup ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet — CLI trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py ping
  python cli.py account
  python cli.py open-orders --symbol BTCUSDT
  python cli.py order --symbol BTCUSDT --side BUY  --type MARKET     --qty 0.01
  python cli.py order --symbol ETHUSDT --side SELL --type LIMIT      --qty 0.1 --price 3200
  python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 58000
        """,
    )

    subs = parser.add_subparsers(dest="command", help="Available commands")
    subs.required = True

    # ping
    subs.add_parser("ping", help="Test connectivity to Binance Testnet")

    # account
    subs.add_parser("account", help="Show account balances")

    # open-orders
    p_open = subs.add_parser("open-orders", help="List open orders")
    p_open.add_argument("--symbol", metavar="SYMBOL", help="Filter by symbol (e.g. BTCUSDT)")

    # order
    p_order = subs.add_parser("order", help="Place a new order")
    p_order.add_argument(
        "--symbol", required=True, metavar="SYMBOL",
        help="Trading pair, e.g. BTCUSDT",
    )
    p_order.add_argument(
        "--side", required=True, choices=["BUY", "SELL"],
        help="Order side",
    )
    p_order.add_argument(
        "--type", required=True, choices=["MARKET", "LIMIT", "STOP_MARKET"],
        dest="type", help="Order type",
    )
    p_order.add_argument(
        "--qty", required=True, metavar="QUANTITY",
        help="Order quantity (e.g. 0.01)",
    )
    p_order.add_argument(
        "--price", default=None, metavar="PRICE",
        help="Limit price (required for LIMIT orders)",
    )
    p_order.add_argument(
        "--stop-price", default=None, metavar="STOP_PRICE", dest="stop_price",
        help="Stop price (required for STOP_MARKET orders)",
    )

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

COMMAND_MAP = {
    "ping":        cmd_ping,
    "account":     cmd_account,
    "open-orders": cmd_open_orders,
    "order":       cmd_order,
}


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    logger.info("CLI invoked | command=%s | args=%s", args.command, vars(args))

    handler = COMMAND_MAP.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
