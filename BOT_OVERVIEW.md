# Poly-Maker Bot - Complete Overview

## Table of Contents
1. [What is Market Making?](#what-is-market-making)
2. [System Architecture](#system-architecture)
3. [How the Bot Works](#how-the-bot-works)
4. [Main Components](#main-components)
5. [Trading Logic](#trading-logic)
6. [Configuration](#configuration)
7. [Risk Management](#risk-management)
8. [Common Workflows](#common-workflows)

---

## What is Market Making?

**Market making** is a trading strategy where you provide liquidity to a market by:
- Placing **buy orders** (bids) below the current price
- Placing **sell orders** (asks) above the current price
- Profiting from the **spread** (difference between buy and sell prices)

**Example:**
- Market price: $0.75
- You place a buy order at $0.74
- You place a sell order at $0.76
- When both fill, you profit $0.02 per share

**This bot automates this process** on Polymarket prediction markets.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     POLY-MAKER BOT                          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐         ┌──────▼──────┐      ┌──────▼──────┐
   │ main.py │         │  trading.py │      │ websockets  │
   └────┬────┘         └──────┬──────┘      └──────┬──────┘
        │                     │                     │
        │              ┌──────▼──────┐              │
        │              │ data utils  │◄─────────────┘
        │              └──────┬──────┘
        │                     │
        └─────────────┬───────┴───────┬─────────────┘
                      │               │
           ┌──────────▼──────┐  ┌─────▼─────────┐
           │     SQLite      │  │  Polymarket   │
           │ (polymarket.db) │  │   (Trading)   │
           └─────────────────┘  └───────────────┘
```

### Three-Layer Architecture:

1. **Data Layer** (`poly_data/`)
   - Manages market data, positions, orders
   - Maintains WebSocket connections
   - Stores global state

2. **Logic Layer** (`trading.py`)
   - Trading decisions
   - Price calculations
   - Order placement/cancellation

3. **Control Layer** (`main.py`)
   - Initialization
   - Periodic updates
   - Error handling

---

## How the Bot Works

### 1. Startup Sequence

```
main.py starts
    │
    ├─► Initialize PolymarketClient (connect to API)
    │
    ├─► Load markets from SQLite
    │       - `target_markets` table (what to trade)
    │       - `all_markets` table (market metadata)
    │       - `hyperparameters` table (trading parameters)
    │
    ├─► Fetch current positions from Polymarket API
    │
    ├─► Fetch current orders from Polymarket API
    │
    └─► Start WebSocket connections
            - Market WebSocket (order book updates)
            - User WebSocket (trade fills, order updates)
```

### 2. Main Loop

The bot runs two parallel processes:

**A. Periodic Updates (every 10 seconds)**
```python
while True:
    await asyncio.sleep(10)

    # 1. Clean up stale pending trades
    remove_from_pending()

    # 2. Update positions (only avg price if trades pending)
    update_positions(avgOnly=True)

    # 3. Update orders
    update_orders()

    # 4. Every 60 seconds: refresh market data
    if i % 6 == 0:
        update_markets()
```

**B. WebSocket Event Loop**
```
Market WebSocket receives order book update
    │
    ├─► Update local order book state
    │
    └─► Trigger trading logic (trading.py)
            │
            ├─► Calculate optimal prices
            ├─► Determine buy/sell amounts
            ├─► Place/cancel/update orders
            └─► Manage positions
```

---

## Main Components

### 1. **main.py** - Entry Point

**Purpose:** Orchestrates the entire bot

**Key Functions:**
- `main()` - Initialize everything and start loops
- `update_once()` - Initial data fetch
- `update_periodically()` - Keep data fresh
- Maintains WebSocket connections with reconnection logic

**Flow:**
```
Start → Initialize Client → Load Data → Start WebSockets → Run Forever
```

---

### 2. **trading.py** - Core Trading Logic

**Purpose:** Makes all trading decisions

**Key Functions:**

**`process_data(condition_id)`**
- Called when order book updates via WebSocket
- Main decision-making function
- Checks if we should trade this market
- Calculates prices and sizes
- Places/cancels orders

**`get_order_prices(row, token_id)`**
- Calculates optimal bid/ask prices
- Considers:
  - Current best bid/ask
  - Order book depth
  - Tick size (minimum price increment)
  - Low-price multipliers

**`get_buy_sell_amount(row, token_id, position, max_size)`**
- Determines how much to buy/sell based on rewards and limits.
- Logic:
  - **Dynamic Sizing:** Uses `dynamic_max_size` to scale exposure [0.5x, 2.0x] based on volatility.
  - **Inventory Skew:** Applies a price offset when inventory exceeds 40% of `max_size` to hasten exits.
  - **Ramp-Up:** New markets are throttled to 25% size until proven stable in the database.

**Market Locks:**
```python
market_locks = {}  # Prevents concurrent trading on same market

async with market_locks[condition_id]:
    # Only one trade at a time per market
    process_orders()
```

---

### 3. **poly_data/** - Data Management

#### **polymarket_client.py**
- Wrapper around `py-clob-client`
- Methods:
  - `create_order()` - Place orders
  - `get_all_positions()` - Fetch positions
  - `get_all_orders()` - Fetch orders
  - `get_usdc_balance()` - Check balance
  - `merge_positions()` - Merge YES/NO positions

#### **websocket_handlers.py**
- Maintains two WebSocket connections:

**Market WebSocket** (`connect_market_websocket`)
- Subscribes to order book updates for all markets
- Receives messages like:
  ```json
  {
    "event_type": "book",
    "asset_id": "token123...",
    "price": "0.75",
    "size": "100"
  }
  ```
- Triggers `process_book_message()` → updates order book

**User WebSocket** (`connect_user_websocket`)
- Receives your own trade updates:
  ```json
  {
    "event_type": "fill",
    "trade_id": "xyz",
    "size": "20",
    "price": "0.75"
  }
  ```
- Updates positions in real-time

#### **data_processing.py**
- Processes WebSocket messages
- Updates order book state (SortedDict for efficient lookups)
- Calls trading logic when data changes

#### **data_utils.py**
- `update_markets()` - Load from SQLite
- `update_positions()` - Fetch from Polymarket API
- `update_orders()` - Fetch current orders

#### **global_state.py**
- Central data store accessible everywhere:
  ```python
  global_state.positions = {
      'token_id': {'size': 100, 'avgPrice': 0.75}
  }
  global_state.orders = {
      'token_id': {
          'buy': {'price': 0.74, 'size': 20, 'id': 'order_id'},
          'sell': {'price': 0.76, 'size': 20, 'id': 'order_id'}
      }
  }
  global_state.orderbook = {
      'token_id': {
          'bids': SortedDict({0.74: 100, 0.73: 50}),
          'asks': SortedDict({0.76: 100, 0.77: 50})
      }
  }
  ```

---

### 4. **poly_merger/** - Position Merger (Node.js)

**Purpose:** Merge opposing YES/NO positions to free capital

**When it runs:**
- Automatically when you have both YES and NO positions
- And min(yes_size, no_size) > 20

**What it does:**
```javascript
// If you have:
// 100 YES shares + 80 NO shares

// Merge 80 of each → get back 80 USDC
// Result: 20 YES shares + 80 USDC
```

**Called from Python:**
```python
client.merge_positions(
    amount_to_merge=80000000,  # in microshares
    condition_id='0xabc...',
    is_neg_risk_market=False
)
```

---

### 5. **data_updater/** - Market Data Collection

**Purpose:** Separate module to update market database

**Scripts:**
- `data_updater.py` - Fetch all Polymarket markets
- `find_markets.py` - Calculate rewards and volatility
- Updates `all_markets` SQLite table hourly

**Should run separately** (ideally different IP) to avoid rate limits

---

## Trading Logic

### Price Calculation

```python
def get_order_prices(row, token_id):
    # 1. Get current best bid/ask
    best_bid, best_ask = get_best_bid_ask_deets(...)

    # 2. Calculate mid price
    mid_price = (best_bid + best_ask) / 2

    # 3. Adjust for tick size
    tick_size = row['tick_size']  # e.g., 0.01

    # 4. Set our prices
    buy_price = round_to_tick(best_bid, tick_size)
    sell_price = round_to_tick(best_ask, tick_size)

    # 5. Apply low-price multiplier if needed
    if buy_price < 0.1:
        buy_price *= LOW_PRICE_MULTIPLIER

    return buy_price, sell_price
```

### Order Sizing

```python
def get_buy_sell_amount(row, token_id, position):
    trade_size = row['trade_size']  # e.g., $20
    max_size = row['max_size']      # e.g., $60

    # BUYING LOGIC
    if position < max_size:
        # Still building position
        remaining = max_size - position
        buy_amount = min(trade_size, remaining)
    else:
        # At max, stop buying (or small amount)
        buy_amount = 0

    # SELLING LOGIC
    if position >= trade_size:
        # Have enough to sell
        sell_amount = min(position, trade_size)
    else:
        sell_amount = 0

    return buy_amount, sell_amount
```

### Order Management

**When to place orders:**
```python
# BUY order conditions:
if (position < max_size AND
    position < 250 AND
    buy_amount >= min_size AND
    no_existing_buy_order):
    place_buy_order()

# SELL order conditions:
if (position >= trade_size AND
    no_existing_sell_order):
    place_sell_order()
```

**When to cancel/update:**
```python
# Only update if significant change
price_diff = abs(new_price - old_price)
size_diff = abs(new_size - old_size) / old_size

if price_diff > 0.005 OR size_diff > 0.10:
    cancel_old_order()
    place_new_order()
```

---

## Configuration

### SQLite Database Structure

**1. target_markets table**
```
┌────────────────────────┬──────────┬────────────┬──────────────┬──────────┐
│ question               │ max_size │ trade_size │ param_type   │ comments │
├────────────────────────┼──────────┼────────────┼──────────────┼──────────┤
│ Trump wins election?   │    100   │     50     │ aggressive   │ ...      │
│ Fed rate cut by June?  │     60   │     20     │ conservative │ ...      │
└────────────────────────┴──────────┴────────────┴──────────────┴──────────┘
```

**2. all_markets table** (auto-updated by data_updater)
```
┌────────────┬────────┬────────┬──────────┬─────────┬──────┬────────┐
│ question   │ token1 │ token2 │ best_bid │ best_ask│ ...  │ rewards│
├────────────┼────────┼────────┼──────────┼─────────┼──────┼────────┤
│ ...        │ 123... │ 456... │  0.74    │  0.76   │ ...  │  5.2   │
└────────────┴────────┴────────┴──────────┴─────────┴──────┴────────┘
```

**3. hyperparameters table**
```
┌──────────────────────┬─────────────────────┬───────┐
│ type                 │ param               │ value │
├──────────────────────┼─────────────────────┼───────┤
│ aggressive           │ stop_loss_threshold │  -15  │
│ aggressive           │ take_profit_threshold│  10  │
│ aggressive           │ volatility_threshold│  20   │
│ conservative         │ stop_loss_threshold │  -5   │
└──────────────────────┴─────────────────────┴───────┘
```

### Environment Variables (.env)

```bash
# Your wallet's private key
PK=0xabc123...

# Your wallet address (matches the private key!)
BROWSER_ADDRESS=0x1234...

# Polygon RPC (optional)

# Polygon RPC (optional)
POLYGON_RPC_URL=https://polygon-rpc.com
```

---

## Risk Management

### 1. Stop Loss

**Triggers when loss thresholds or volatility limits are hit:**

- **Tiered Stop-Loss (Spread-Anchored):**
  - **Tier 1 (0.5x Spread loss):** Underwater by half a spread. Reduces sell size by 50% to minimize exposure.
  - **Tier 2 (1.0x Spread loss):** Underwater by full spread. Exits full position and triggers a sleep cooldown.
  - **Tier 3 (2.0x Spread loss):** Emergency exit. Uses limit orders with a 5% slippage guard to prevent dumping into thin liquidity.

- **Adaptive Volatility Filter:**
  - High-reward markets are granted higher volatility thresholds (`base_vol + reward_bonus`).
  - Trading halts globally if portfolio-wide drawdown exceeds 5% in 24 hours.

**What happens:**
1. Sell entire position at best bid
2. Write to `positions/{condition_id}.json`:
   ```json
   {
     "sleep_till": 1234567890,
     "reason": "stop_loss"
   }
   ```
3. Don't trade this market until `sleep_till` expires

### 2. Take Profit

**Automatic sell orders:**
```python
take_profit_price = avg_price * (1 + take_profit_threshold/100)
sell_price = max(best_ask, take_profit_price)
```

Example:
- Bought at $0.70
- Take profit threshold: 10%
- Sell order placed at: $0.77 (or higher if market is above)

### 3. Volatility Filter

**Skips trading if:**
```python
if market['3_hour_volatility'] > volatility_threshold:
    # Too volatile, skip
    return
```

### 4. Position Limits

```python
# Per-market limit
if position >= max_size:
    # Stop buying, only sell

# Global limit
if position >= 250:
    # Hard cap
```

### 5. Reverse Position Check

**Prevents hedging against yourself:**
```python
# Check opposite token
reverse_token = REVERSE_TOKENS[token_id]
reverse_position = positions.get(reverse_token, {}).get('size', 0)

if reverse_position > min_size:
    # Don't buy if we have significant opposite position
    return
```

---

## Common Workflows

### Starting the Bot

```bash
# 1. Configure environment
vim .env  # Set PK, BROWSER_ADDRESS

# 2. Select markets via CLI
# Auto-select or manually add to local SQLite DB

# 3. Start bot
python main.py

# 4. Monitor
tail -f main.log
```

### Checking Status

```bash
# View positions, orders, balance
python check_positions.py

# View logs
tail -f main.log
tail -f data_processing.log
tail -f websocket_handlers.log
```

### Updating Market Selection

```bash
# 1. Refresh target markets using update_selected_markets.py
# 2. Bot will auto-reload every 60 seconds
# 3. Or restart: Ctrl+C → python main.py
```

### Emergency Stop

```bash
# Stop the bot
Ctrl+C

# Or kill all Python processes
pkill -f "python main.py"

# Check for remaining orders
python check_positions.py
```

### Adjusting Parameters

**Change trade sizes:**
1. Edit "Selected Markets" → `trade_size`, `max_size` columns
2. Bot reloads automatically

**Change risk parameters:**
1. Use `python manage_markets.py hyper [type] [param] [value]`
2. Bot reloads automatically

---

## Data Flow Example

**Complete flow of a trade:**

```
1. WebSocket receives: "Price changed on market X"
   │
   ▼
2. websocket_handlers.py processes message
   │
   ▼
3. data_processing.py updates global_state.orderbook
   │
   ▼
4. data_processing.py calls trading.process_data(condition_id)
   │
   ▼
5. trading.py checks:
   - Is this a selected market? ✓
   - Are we in risk-off period? ✗
   - Do we need to trade? ✓
   │
   ▼
6. trading.py calculates:
   - Current position: 20 shares @ $0.70
   - Best bid/ask: $0.74 / $0.76
   - Should buy: $20 more at $0.74
   │
   ▼
7. trading.py places order via PolymarketClient
   │
   ▼
8. Order sent to Polymarket API
   │
   ▼
9. User WebSocket receives: "Order placed"
   │
   ▼
10. global_state.orders updated
    │
    ▼
11. Later... User WebSocket: "Order filled!"
    │
    ▼
12. global_state.positions updated
    │
    ▼
13. If profitable, place sell order at take_profit_price
```

---

## Troubleshooting

### Bot not placing orders?

**Check:**
1. Logs: `tail -f main.log`
2. Is market in "Selected Markets"?
3. Balance sufficient? `python check_positions.py`
4. In risk-off period? `cat positions/*.json`
5. WebSocket connected? Look for "WebSocket connected" in logs

### Orders not filling?

**Reasons:**
- Prices not competitive (too far from best bid/ask)
- Low liquidity market
- Order size too large
- **This is normal for market making!** Orders sit and wait

### High losses?

**Actions:**
1. Check `stop_loss_threshold` in Hyperparameters
2. Reduce `trade_size` and `max_size`
3. Select less volatile markets
4. Increase `volatility_threshold` to skip volatile markets

### WebSocket disconnections?

**Normal behavior:**
- Auto-reconnects with exponential backoff
- Max backoff: 60 seconds
- Check network connection if frequent

---

## Key Files Reference

```
poly-maker-prod/
├── main.py                    # Entry point
├── trading.py                 # Core trading logic
├── check_positions.py         # Position checker
├── approve_and_trade.py       # USDC approval + test order
│
├── poly_data/
│   ├── polymarket_client.py   # API wrapper
│   ├── websocket_handlers.py  # WebSocket connections
│   ├── data_processing.py     # Order book processing
│   ├── data_utils.py          # Data fetching
│   ├── trading_utils.py       # Helper functions
│   ├── global_state.py        # Shared state
│   └── CONSTANTS.py           # Configuration
│
├── poly_merger/
│   └── merge.js               # Position merger (Node.js)
│
├── data_updater/
│   ├── data_updater.py        # Market data collector
│   └── google_utils.py        # Legacy helper (deprecated)
│
├── positions/                 # Risk-off state files
│   └── {condition_id}.json    # Per-market sleep state
│
├── .env                       # Environment variables
├── requirements.txt           # Python dependencies
└── BOT_OVERVIEW.md           # This document
```

---

## Advanced Concepts

### Order Book State Management

The bot maintains a local copy of the order book:

```python
global_state.orderbook = {
    'token_id': {
        'bids': SortedDict({
            0.74: 100,  # price: size
            0.73: 50,
            0.72: 200
        }),
        'asks': SortedDict({
            0.76: 100,
            0.77: 150,
            0.78: 80
        })
    }
}
```

**Updates:** Incremental via WebSocket
- `book` event: Full snapshot
- `price_change` event: Update single price level

### Pending Trade Tracking

Prevents race conditions:

```python
global_state.performing = {
    'token_id': {'trade_id_1', 'trade_id_2'}
}

# When trade is pending:
if token_id in global_state.performing:
    update_positions(avgOnly=True)  # Only update avg price, not size
```

### Token Mapping

YES/NO tokens are paired:

```python
global_state.REVERSE_TOKENS = {
    'token1_id': 'token2_id',  # YES → NO
    'token2_id': 'token1_id'   # NO → YES
}
```

Used to detect opposing positions.

---

## Performance Tips

1. **Reduce API calls:** Bot caches data locally
2. **WebSocket efficiency:** Only subscribes to selected markets
3. **Order updates:** Only when price/size changes significantly
4. **Position merging:** Frees capital automatically
5. **Parallel processing:** Handles multiple markets simultaneously

---

## Safety Checklist

Before running with real money:

- [ ] Test with small amounts first
- [ ] Verify SQLite database configuration
- [ ] Check USDC approval is set
- [ ] Monitor for 24 hours with small positions
- [ ] Understand stop-loss behavior
- [ ] Have sufficient MATIC for gas
- [ ] Keep credentials secure (never commit .env)
- [ ] Run data_updater on separate IP

---

## Getting Help

- **Logs:** Check `*.log` files
- **Positions:** Run `python check_positions.py`
- **Orders:** Check Polymarket.com UI
- **Issues:** Review this document

---

**Remember:** Market making requires patience. Profits come from many small trades over time, not immediate gains!
