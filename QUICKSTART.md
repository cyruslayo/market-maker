# = Quick Start Guide

## Prerequisites

1.   Python 3.8+ installed
2.   `.env` file configured with:
   - `PK` (Private key)
   - `BROWSER_ADDRESS` (Wallet address)
3.   SQLite Database generated with `manage_markets.py init`
4.   Basic understanding of Polymarket (see CLAUDE.md)

---

## Option 1: Fully Automated Setup (Recommended) >

### Step 1: Initialize SQL Database
The bot uses a local SQLite database (`polymarket.db`) for market configuration.
```bash
python manage_markets.py init
```

### Step 2: Start Market Discovery
Run the data updater to continuously fetch market metrics (rewards, volume, etc.).
```bash
python data_updater/data_updater.py
```

### Step 3: Select Advanced Trading Targets
Use the high-reward auto-selector to pick the best markets.
```bash
# Example: Select top 5 markets with $100+ daily rewards
python update_selected_markets.py --min-reward 100 --max-markets 5 --replace
```

### Step 4: Start Trading Bot
```bash
python main.py
```

---

## Option 2: Manual Step-by-Step =

### Step 1: Update Market Data
```bash
# This fetches all Polymarket markets and calculates rewards
python update_markets.py
```
 Takes ~5-10 minutes to complete

### Step 2: Select Markets
```bash
# Auto-select top 5 markets by composite score
python select_markets.py --top 5 --min-reward 0.75 --max-volatility 20
```

Or use the dashboard:
```bash
streamlit run dashboard.py
# Go to "Market Selection" tab  set parameters  click "Auto-Select Markets"
```

### Step 3: Start Trading
```bash
python main.py
```

Monitor with:
```bash
tail -f main.log
```

---

## Option 3: One-Time Data Update =

If you just want to update market data once without scheduling:

```bash
# Update market data (run once)
python data_updater/data_updater.py

# Then select markets
python update_selected_markets.py
```

---

## Testing: Paper Trading

Run the bot against the live Polymarket order book in a safe, simulated environment to test quoting and risk management strategies without risking real capital.

### Standard Paper Trading
Run the paper trading engine indefinitely, simulating real bot behavior with a local matching engine:
```bash
python paper_main.py
```
*Note: Press `Ctrl+C` to stop and view the final paper trading latency and slippage report.*

### Paper Trading Gauntlet
Run a time-boxed gauntlet session (e.g. 48 hours) to stress-test your configuration across various market scenarios:
```bash
python run_extreme_papertrade.py --hours 48
```

---

## Stopping the Bot

### Stop Main Bot
```bash
# Find process
ps aux | grep "python main.py"

# Kill by PID
kill <PID>

# Or kill all instances
pkill -f "python.*main.py"
```

### Stop Data Updater
```bash
# Graceful shutdown
Ctrl+C (in terminal running data_updater)

# Force kill
pkill -f "python.*data_updater"
```

### Stop Dashboard
```bash
# In terminal running streamlit
Ctrl+C
```

---

## Common Commands

### View Market Statistics
```bash
python select_markets.py --stats
```

### Preview Market Selection (Dry Run)
```bash
python select_markets.py --top 10 --dry-run
```

### Check Bot Status
```bash
ps aux | grep -i "python.*main.py"
```

### View Logs
```bash
# Main bot
tail -f main.log

# Data updater
tail -f data_updater.log

# Data updater
tail -f data_updater.log
```

---

## Typical Workflow

### Morning:
```bash
# Start data updater (run in background)
python data_updater/data_updater.py &

# Start trading bot
python main.py &
```

### During Day:
- Monitor via dashboard at `http://localhost:8501`
- Check "Maker Rewards" tab to see estimated earnings
- Adjust market selection if needed via dashboard

### Evening:
- Review "Trade Log" for fills
- Check positions in "Positions & Orders"
- Stop bot if desired: `pkill -f "python.*main.py"`

---

## Troubleshooting

### "No markets found in SQLite"
 Run `python data_updater/data_updater.py` first

### "Bot not starting"
 Check `.env` file has `PK`, `BROWSER_ADDRESS`

### "Orders being cancelled too often"
 Check main.log - rate limiting should show "cooldown" messages

### "No reward data in dashboard"
 Bot must run for 5+ minutes first

### "Dashboard won't load"
� `pip install streamlit plotly psutil`

---

## Next Steps

1. Read `IMPROVEMENTS.md` for detailed feature documentation
2. Read `CLAUDE.md` for trading logic details
3. Customize parameters using `python manage_markets.py hyper`
4. Set up Discord webhook for notifications (optional)

---

## Support

Check logs first:
```bash
tail -100 main.log
tail -100 data_updater.log
```

Common issues documented in `IMPROVEMENTS.md` � Troubleshooting section.
