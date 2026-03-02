# Script Usage Guide

## ✅ **ACTIVELY USED - Core Production Scripts**

These scripts are part of the main bot execution flow:

### Primary Entry Points
- **`main.py`** ⭐ - Main bot entry point, orchestrates WebSocket connections and periodic updates
- **`trading.py`** ⭐ - Core trading logic (`perform_trade` function), order placement, position management
- **`update_markets.py`** - Updates market data from SQLite (called periodically by main.py)
- **`data_updater/data_updater.py`** - Fetches all Polymarket markets, calculates metrics, updates SQLite
- **`update_selected_markets.py`** - Auto-selects profitable markets from SQLite and updates the target markets.
  - `--min-reward`: Filter by minimum daily reward (e.g. 100).
  - `--max-markets`: Maximum number of markets to track.
  - `--replace`: Clear existing target markets before adding new ones.

### Supporting Modules (Used by Core Scripts)
- **`poly_data/polymarket_client.py`** - Polymarket API client
- **`poly_data/data_utils.py`** - Market/position/order data utilities
- **`poly_data/data_processing.py`** - WebSocket data processing, calls `perform_trade`
- **`poly_data/websocket_handlers.py`** - WebSocket connection management
- **`poly_data/trading_utils.py`** - Trading utility functions (price calculation, order sizing)
- **`poly_data/global_state.py`** - Global state management
- **`poly_data/CONSTANTS.py`** - Constants and configuration
- **`poly_data/trade_logger.py`** - Logs trades locally / to database
- **`poly_data/reward_tracker.py`** - Tracks maker rewards
- **`poly_data/position_snapshot.py`** - Logs position snapshots
- **`poly_data/utils.py`** - General utilities
- **`data_updater/google_utils.py`** - Legacy utilities (deprecated)
- **`data_updater/trading_utils.py`** - Trading utilities for data updater
- **`data_updater/find_markets.py`** - Market discovery functions
- **`poly_merger/merge.js`** - Node.js script for position merging (called by Python)

---

## 🔧 **UTILITY SCRIPTS - Run Manually As Needed**

These scripts are useful for administration and monitoring but not part of the main flow:

- **`cancel_all_orders.py`** - Cancel all open orders (manual intervention)
- **`check_positions.py`** - Check current positions across all markets
- **`approve_and_trade.py`** - Approve token spending and place a trade
- **`export_trades_to_sheets.py`** - Export trade history (legacy script)
- **`update_hyperparameters.py`** - Update trading parameters in SQLite
- **`validate_polymarket_bot.py`** - Validate bot configuration and connectivity

---

## 🧪 **TEST SCRIPTS - Not Used in Production**

These are for testing and development only:

- **`test_aggressive_trading.py`** - Test aggressive trading mode
- **`test_immediate_order.py`** - Test immediate order placement
- **`test_trade_logger.py`** - Test trade logging functionality
- **`force_trade_test.py`** - Force a trade on a specific market (bypasses WebSocket)
- **`quick_order_test.py`** - Quick order placement test
- **`direct_order_test.py`** - Direct order placement test

---

## 📊 **ANALYSIS SCRIPTS - Not Used in Production**

These are for analysis and research:

- **`analyze_performance.py`** - Analyze trading performance
- **`analyze_profitable_markets.py`** - Analyze which markets are most profitable

---

## ❓ **UNCLEAR / POTENTIALLY DEPRECATED**

These scripts may be outdated or have unclear usage:

- **`select_markets.py`** - Alternative market selection (may be replaced by `update_selected_markets.py`)
- **`select_best_markets.py`** - Another market selection variant
- **`fix_trade_sizes.py`** - One-time fix script (likely no longer needed)
- **`check_market_config.py`** - Check market configuration
- **`update_stats.py`** - Update statistics (unclear if actively used)
- **`dashboard_old.py`** - Old dashboard version (likely deprecated)
- **`poly_data/gspread.py`** - Legacy utility (deprecated)

---

## 📋 **Execution Flow Summary**

### Normal Bot Operation:
```
main.py
  ├─→ Initializes PolymarketClient
  ├─→ Calls update_markets() from data_utils.py
  ├─→ Connects WebSocket (websocket_handlers.py)
  │     └─→ Receives market data → data_processing.py
  │           └─→ Calls perform_trade() from trading.py
  │                 ├─→ Uses trading_utils.py for calculations
  │                 ├─→ Uses polymarket_client.py for API calls
  │                 └─→ Uses trade_logger.py to log trades
  └─→ Periodic updates (every 10s positions/orders, 60s markets)
```

### Data Update Flow:
```
data_updater/data_updater.py (run separately)
  ├─→ Fetches all markets from Polymarket API
  ├─→ Calculates metrics (rewards, volatility, etc.)
  └─→ Updates local SQLite DB

update_selected_markets.py (run manually)
  ├─→ Reads from SQLite 'all_markets' table
  ├─→ Calculates rewards, volatility, and profitability
  ├─→ Applies correlation limits and ramp-up logic
  └─→ Updates SQLite 'target_markets' table
```

### Position Merging Flow:
```
trading.py (perform_trade)
  └─→ Detects opposing YES/NO positions
      └─→ Calls poly_merger/merge.js (Node.js)
          └─→ Executes blockchain merge transaction
```

---

## 🎯 **Quick Reference**

**To run the bot:**
```bash
python main.py
```

**To update market data:**
```bash
python data_updater/data_updater.py
```

**To update selected markets:**
```bash
python update_selected_markets.py
# or with high reward filter:
python update_selected_markets.py --min-reward 100
```

**To cancel all orders:**
```bash
python cancel_all_orders.py
```

**To check positions:**
```bash
python check_positions.py
```

---

## 📝 **Notes**

- Scripts marked with ⭐ are critical for bot operation
- Test scripts should never be run in production
- Utility scripts are safe to run but don't affect the main bot flow
- The bot reads from SQLite (`target_markets` table) for which markets to trade
- The bot writes to local logs/database for trade logging

