# Poly-Maker

A robust automated market making bot for Polymarket prediction markets. This bot automates providing liquidity by maintaining intelligent, reward-optimized orders on both sides of the book.

## 🚀 Key Features

- **SQLite Core**: Built on a robust local SQLite database for trading logic and market discovery.
- **Aggressive Market Making**: Optimized for high-reward markets using an inventory-aware profitability score.
- **Dynamic Kelly Sizing**: Automatically scales position sizes based on reward-to-risk (volatility) ratios.
- **Tiered Risk Management**: Graduated stop-loss responses and slippage guards for high-volatility events.
- **Global Circuit Breakers**: Automatic trading halts based on portfolio-wide drawdown or volatility spikes.
- **Real-time Order Book Monitoring**: High-frequency updates via WebSockets.
- **Automated Position Merging**: Reclaims USDC collateral by merging opposing YES/NO positions.
- **Unified CLI Management**: Easy configuration of markets and hyperparameters via `manage_markets.py`.

---

## 🏗 Structure

- `poly_data`: Core trading logic, SQLite utilities, and Polymarket API clients.
- `data_updater`: Independent module for continuous market discovery and reward calculation.
- `poly_merger`: Capital efficiency tool for merging positions.
- `main.py`: The primary trading engine.
- `manage_markets.py`: Unified configuration and database management tool.

---

## 🛠 Installation & Setup

### 1. Requirements
- Python 3.9+
- Node.js (for high-efficiency position merging)
- A Polymarket account with API keys generated.

### 2. Clone and Install
```bash
git clone https://github.com/yourusername/poly-maker.git
cd poly-maker
pip install -r requirements.txt
```

### 3. Initialize SQL Database
The bot uses a local SQLite database (`polymarket.db`) to store market data and configurations.
```bash
python polymarket-automated-mm/manage_markets.py init
```

### 4. Configure Environment
Create a `.env` file in the root directory:
```env
PK=0x... (Your Private Key)
BROWSER_ADDRESS=0x... (Your Wallet Address)
POLYGON_RPC_URL=https://polygon-rpc.com
PAPER_TRADING=true (Set to false for live trading)
```

---

## 📈 Configuration Workflow

### Step 1: Discover Markets
Run the discovery scanner to populate the local database with profit metrics for all available markets.
```bash
python polymarket-automated-mm/data_updater/data_updater.py
```
*Note: Run this in a separate terminal to keep your market data fresh.*

### Step 2: Select Trading Targets
Choose which markets the bot should actively trade.
```bash
# Auto-select the top 5 markets by profitability score
python polymarket-automated-mm/update_selected_markets.py --max-markets 5 --replace
```

### Step 3: Manage Hyperparameters
Adjust spreads, trade sizes, and risk thresholds via the CLI.
```bash
# View current settings
python polymarket-automated-mm/manage_markets.py list

# Example: Change the 'standard' trading spread to 3%
python polymarket-automated-mm/manage_markets.py hyper standard spread 0.03

# Example: Change the max position size for the 'standard' protocol
python polymarket-automated-mm/manage_markets.py hyper standard max_size 500
```

---

## 🚀 Running the Bot

### Start Trading
```bash
python polymarket-automated-mm/main.py
```

### Monitoring
- **Logs**: Monitor `main.log` for real-time trading decisions.
- **Positions**: Run `python polymarket-automated-mm/check_positions.py` for a quick portfolio summary.
- **Dry Run**: Keep `PAPER_TRADING=true` in your `.env` to simulate trades without using real USDC.

---

## ⚙️ Hyperparameter Reference

| `spread` | The minimum profit margin between buy and sell orders. |
| `take_profit_threshold` | Exit position after reaching this % gain. |
| `stop_loss_threshold` | Exit position after reaching this % loss. |
| `volatility_threshold` | Maximum allowed volatility before the bot pauses trading. |
| `trade_size` | The dollar amount for each individual order. |
| `max_size` | The maximum total exposure allowed per market (dynamically adjusted). |

---

## 📈 Aggressive Strategy

The bot includes an **Aggressive Mode** targeting high-yield markets:
- **Profitability Scoring**: Uses `expected_pnl = (gm_reward * daily_rate) / (spread + 0.001)` to prioritize markets.
- **Conviction Tiers**: Automatically assigns trading parameters (`max_aggressive`, `aggressive`, `moderate`, `default`) based on daily reward rates.
- **Ramp-Up Graduation**: New markets start at 25% size and graduate to 100% once confirmed in the database, minimizing initial exposure risk.

## 🛡️ Risk Management

- **Tiered Stop-Loss**:
  - **Tier 1 (0.5x Spread)**: Reduces position size by 50%.
  - **Tier 2 (1.0x Spread)**: Exits full position and triggers cooldown.
  - **Tier 3 (2.0x Spread)**: Emergency exit with slippage-protected limit orders.
- **Inventory Skew**: Dynamically lowers bid/ask prices when inventory is high (above 40% of `max_size`) to encourage exits.
- **Portfolio Circuit Breakers**: Universal stop-trading trigger if total drawdown exceeds 5% in 24 hours.
- **Slippage Guard**: Prevents "market dumping" in Tier-3 exits if liquidity is too thin.

---

## ⚠️ Important Notes

- **Real Capital**: This bot interacts with real markets. Test thoroughly in `PAPER_TRADING` mode first.
- **Permissions**: Ensure your wallet has performed at least one manual trade on the Polymarket UI to initialize the proxy contract.
- **Capital Efficiency**: The `merger_loop` runs every 30 seconds to reclaim collateral. Ensure you have a small amount of MATIC/POL for gas.

---

## 📝 License

MIT
