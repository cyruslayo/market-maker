# Files Safe to Share on GitHub

This document lists all files that are **SAFE** to include in a public GitHub repository. These files do not contain:
- Private keys
- API keys
- Wallet addresses
- Credentials
- Sensitive log data
- Personal information

## ✅ **SAFE TO SHARE - Core Scripts**

### Main Application Files
- `main.py` - Main entry point (reads from .env, no hardcoded secrets)
- `trading.py` - Core trading logic (no secrets)
- `update_markets.py` - Market data updater (reads from .env)
- `update_selected_markets.py` - Market selection script (reads from .env)

### Core Modules (`poly_data/`)
- `poly_data/__init__.py`
- `poly_data/CONSTANTS.py` - Constants only
- `poly_data/data_processing.py` - Data processing logic
- `poly_data/data_utils.py` - Utility functions
- `poly_data/global_state.py` - State management
- `poly_data/position_snapshot.py` - Position logging (reads from .env)
- `poly_data/reward_tracker.py` - Reward tracking
- `poly_data/trade_logger.py` - Trade logging (reads from .env)
- `poly_data/trading_utils.py` - Trading utilities
- `poly_data/utils.py` - General utilities
- `poly_data/websocket_handlers.py` - WebSocket handlers
- `poly_data/abis.py` - Contract ABIs (public data)
- `poly_data/polymarket_client.py` - Client (reads from .env, no hardcoded keys)
- `poly_data/gspread.py` - Legacy integration (deprecated)

### Data Updater Module (`data_updater/`)
- `data_updater/data_updater.py` - Main data updater (reads from .env)
- `data_updater/find_markets.py` - Market discovery
- `data_updater/google_utils.py` - Legacy utilities (deprecated)
- `data_updater/trading_utils.py` - Trading utilities
- `data_updater/erc20ABI.json` - Public contract ABI

### Utility Scripts (Safe - Read from .env)
- `cancel_all_orders.py` - Cancel orders (reads from .env)
- `check_positions.py` - Check positions (reads from .env)
- `approve_and_trade.py` - Approve and trade (reads from .env)
- `export_trades_to_sheets.py` - Export trades (legacy)
- `update_hyperparameters.py` - Update hyperparameters (reads from local DB)
- `validate_polymarket_bot.py` - Validation script (reads from .env, USDC_ADDRESS is public contract address)

### Analysis Scripts
- `analyze_performance.py` - Performance analysis
- `analyze_profitable_markets.py` - Market analysis

### Market Selection Scripts
- `select_markets.py` - Market selection
- `select_best_markets.py` - Best market selection
- `update_selected_markets.py` - Update selected markets

### Test Scripts
- `test_aggressive_trading.py` - Test script
- `test_immediate_order.py` - Test script
- `test_trade_logger.py` - Test script
- `force_trade_test.py` - Test script
- `quick_order_test.py` - Test script
- `direct_order_test.py` - Test script
- `check_market_config.py` - Config checker

### Dashboard
- `dashboard.py` - Web dashboard
- `dashboard_old.py` - Old dashboard version

### Poly Merger (Node.js)
- `poly_merger/merge.js` - Position merger (reads from .env)
- `poly_merger/package.json` - Node.js dependencies
- `poly_merger/package-lock.json` - Lock file
- `poly_merger/README.md` - Documentation
- `poly_merger/safe-helpers.js` - Helper functions
- `poly_merger/safeAbi.js` - Contract ABI

### Other Modules
- `poly_stats/__init__.py`
- `poly_stats/account_stats.py` - Account statistics
- `poly_utils/__init__.py`
- `poly_utils/google_utils.py` - Legacy Google utilities (deprecated)

### Documentation
- `README.md` - Main documentation
- `BOT_OVERVIEW.md` - Bot overview
- `QUICKSTART.md` - Quick start guide
- `CLAUDE.md` - Claude documentation
- `IMPROVEMENTS.md` - Improvements log
- `SCRIPT_USAGE.md` - Script usage guide
- `SAFE_TO_SHARE.md` - This file

### Configuration Files
- `requirements.txt` - Python dependencies
- `.gitignore` - Git ignore rules
- `.claudeignore` - Claude ignore rules (if exists)

### Data Files (Optional - Large files)
- `recommended_hyperparameters.csv` - Sample hyperparameters (if no sensitive data)

---

## ❌ **DO NOT SHARE - Contains Sensitive Information**

### Environment & Credentials
- `.env` - **NEVER SHARE** - Contains private keys, API keys, wallet addresses
- `.env.*` - Any environment files
- `credentials.json` - **NEVER SHARE** - Legacy Google Service Account credentials (if exists)

### Log Files
- `*.log` - **DO NOT SHARE** - May contain sensitive data, errors, addresses
  - `main.log`
  - `aggressive_bot.log`
  - `aggressive_test.log`
  - `bot_output.log`
  - `data_processing.log`
  - `data_update_output.log`
  - `data_updater.log`
  - `polymarket_validation.log`
  - `websocket_handlers.log`

### Data Directories
- `data/` - **DO NOT SHARE** - May contain sensitive market data
- `data_updater/data/` - **DO NOT SHARE** - Market data
- `data_updater/data_20251010/` - **DO NOT SHARE** - Historical data
- `data_updater/data_20251016/` - **DO NOT SHARE** - Historical data
- `data_updater/data_20251018/` - **DO NOT SHARE** - Historical data
- `positions/` - **DO NOT SHARE** - Position data

### IDE & System Files
- `.idea/` - IDE configuration
- `.DS_Store` - macOS system file
- `__pycache__/` - Python cache
- `*.pyc` - Compiled Python files
- `node_modules/` - Node.js dependencies (too large, use package.json)

### One-Time Fix Scripts
- `fix_trade_sizes.py` - One-time fix (may contain specific data)

---

## 📋 **Recommended .gitignore Additions**

Make sure your `.gitignore` includes:
```
# Sensitive files
.env
.env.*
credentials.json
*.log

# Data directories
data/
data_updater/data/
data_updater/data_*/
positions/

# IDE
.idea/
.DS_Store

# Python
__pycache__/
*.pyc

# Node
node_modules/
```

---

## ✅ **Verification Checklist**

Before pushing to GitHub, verify:

- [ ] No `.env` file is included
- [ ] No `credentials.json` is included (if exists)
- [ ] No `*.log` files are included
- [ ] No hardcoded private keys in any `.py` files
- [ ] No hardcoded wallet addresses (except public contract addresses like USDC)
- [ ] All sensitive data is read from environment variables
- [ ] `.gitignore` is properly configured
- [ ] No data directories with personal trading data

---

## 🔍 **How to Verify a File is Safe**

1. **Check for hardcoded secrets:**
   ```bash
   grep -r "0x[a-fA-F0-9]\{64\}" .  # Private keys (64 hex chars)
   grep -r "PK=" .  # Private key assignments
   grep -r "api_key" .  # API keys
   ```

2. **Check for environment variable usage:**
   ```bash
   grep -r "os.getenv\|os.environ\|load_dotenv" .  # Should use env vars
   ```

3. **Check log files:**
   - Review log files for any sensitive information before sharing
   - Better to exclude all `*.log` files

---

## 📝 **Notes**

- All Python scripts use `os.getenv()` or `load_dotenv()` to read secrets from `.env`
- Contract addresses (like USDC) are public and safe to share
- The code is designed to be secure when `.env` is excluded

---

## 🚀 **Quick Start for New Repository**

1. Copy all files from the "SAFE TO SHARE" list
2. Create a `.env.example` file with placeholder values:
   ```
   PK=your_private_key_here
   BROWSER_ADDRESS=your_wallet_address_here
   POLYGON_RPC_URL=https://polygon-rpc.com
   ```
3. Ensure `.gitignore` excludes sensitive files
4. Initialize git and push

