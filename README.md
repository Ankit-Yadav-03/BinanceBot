# Binance Futures Testnet Trading Bot

A clean, production-structured CLI tool for placing orders on the Binance USDT-M Futures Testnet.  
Built with raw `requests` (no SDK wrappers) for full transparency over the HTTP layer.

---

## Features

| Feature          | Detail                                                                |
|------------------|-----------------------------------------------------------------------|
| Order types      | MARKET, LIMIT, STOP_MARKET (bonus)                                    |
| Sides            | BUY / SELL                                                            |
| Input validation | Symbol, side, type, quantity, price, stop price                       |
| Logging          | Structured file logs (every request/response) + clean console output  |
| Error handling   | API errors, network failures, timeouts, invalid input                 |
| CLI              | `argparse` subcommands: `ping`, `account`, `open-orders`, `order`     |
| Structure        | Separate `client` / `orders` / `validators` / `logging_config` layers |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Binance REST client (signing, HTTP, error handling)
│   ├── orders.py            # Order placement logic + response formatting
│   ├── validators.py        # Input validation (all rules in one place)
│   └── logging_config.py   # File + console logging setup
├── cli.py                   # CLI entry point (argparse subcommands)
├── logs/                    # Auto-created; log files written here
│   ├── market_order_sample.log
│   └── limit_order_sample.log
├── .env.example             # Credential template
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet Credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (GitHub OAuth supported)
3. Navigate to **Account → API Management**
4. Generate a key pair — copy the API Key and Secret immediately

### 2. Clone & Install

```bash
git clone <repo-url>
cd trading_bot

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` using the template:
```env
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

Alternatively, export them directly (same variable names):
```bash
set BINANCE_API_KEY=your_testnet_api_key_here
set BINANCE_API_SECRET=your_testnet_api_secret_here
```
---

## Running the Bot

### Test Connectivity
```bash
python cli.py ping
```
```
  ✓ Connected to Binance Futures Testnet
    Server time: 1749557000000 ms
```

### Place a MARKET Order
```bash
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
```
```
════════════════════════════════════════════════════
  ORDER REQUEST SUMMARY
════════════════════════════════════════════════════
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.01
════════════════════════════════════════════════════

════════════════════════════════════════════════════
  ORDER RESPONSE
════════════════════════════════════════════════════
  ✓ Status      : FILLED
  Order ID      : 4031737932
  Symbol        : BTCUSDT
  Side          : BUY
  Type          : MARKET
  Orig Qty      : 0.01
  Executed Qty  : 0.01
  Avg Price     : 67842.10

  ✓ Order placed successfully.
════════════════════════════════════════════════════
```

### Place a LIMIT Order
```bash
python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 3200
```

### Place a STOP_MARKET Order (Bonus)
```bash
python cli.py order --symbol BTCUSDT --side SELL --type STOP_MARKET --qty 0.01 --stop-price 58000
```

### View Account Balances
```bash
python cli.py account
```

### View Open Orders
```bash
python cli.py open-orders
python cli.py open-orders --symbol BTCUSDT
```

---

## Logging

Logs are written to `logs/trading_bot_YYYYMMDD.log`.  
Every API request and response is logged at `DEBUG/INFO` level.  
Errors are logged at `ERROR` level with full context.

Sample log line (request):
```
2025-06-10 14:22:01 | INFO     | trading_bot.client | >>> POST /fapi/v1/order | params={'symbol': 'BTCUSDT', 'side': 'BUY', 'type': 'MARKET', 'quantity': '0.01', 'timestamp': 1749557321845}
```

Sample log line (response):
```
2025-06-10 14:22:02 | INFO     | trading_bot.client | <<< POST /fapi/v1/order | status=200 | body={"orderId":4031737932,...}
```

Sample log files from real orders are included in `logs/`.

---

## Design Decisions & Assumptions

- **No SDK**: uses raw `requests` to keep the HTTP layer explicit and fully logged. No hidden abstractions.
- **HMAC-SHA256 signing**: implemented manually per Binance docs.
- **Decimal arithmetic**: all quantities and prices use Python's `Decimal` to avoid float precision issues.
- **Environment variables**: credentials are never hardcoded or logged. The signature is stripped from log output.
- **Testnet only**: the base URL is `https://testnet.binancefuture.com`. To switch to production, change `BASE_URL` in `client.py` and replace credentials.
- **`timeInForce=GTC`**: automatically set for LIMIT orders (most common default). Can be extended via a `--tif` flag.
- **Log rotation**: not implemented (keep-it-simple scope). For production use, replace `FileHandler` with `TimedRotatingFileHandler`.
- **Position mode**: assumes One-Way mode (Binance default). Hedge mode requires a `positionSide` parameter.

---

## Error Handling

| Scenario                       | Behaviour                                    |
|--------------------------------|----------------------------------------------|
| Missing/invalid API keys       | `EnvironmentError` with clear message        |
| Invalid symbol/side/type       | `ValidationError` printed to console, logged |
| Quantity ≤ 0                   | Rejected by validator before any HTTP call   |
| Price missing for LIMIT        | Caught by validator                          |
| Binance API error (e.g. -2019) | `BinanceAPIError` with code + message        |
| Network timeout                | `TimeoutError` with hint                     |
| Non-JSON response              | Graceful fallback with log                   |

---

## Requirements

```
requests>=2.31.0
python-dotenv>=1.0.0
```

Python 3.9+ recommended.
