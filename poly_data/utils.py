import pandas as pd
from poly_data.db_utils import get_db_data, get_discovery_markets, add_market, get_hyperparameters
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def _auto_select_paper_markets(n=3):
    """
    Auto-select the top N real markets from the all_markets DB table
    for paper trading.  Returns (merged_df, hyperparams) or (None, None)
    if the discovery table is empty.
    """
    discovery_df = get_discovery_markets()
    if discovery_df.empty:
        return None, None

    # Filter for quality markets
    numeric_cols = ['gm_reward_per_100', 'volatility_sum', 'spread', 'best_bid',
                    'best_ask', 'rewards_daily_rate', 'min_size', 'max_spread',
                    'tick_size', '3_hour']
    for col in numeric_cols:
        if col in discovery_df.columns:
            discovery_df[col] = pd.to_numeric(discovery_df[col], errors='coerce')

    # Basic quality filters
    mask = pd.Series(True, index=discovery_df.index)
    if 'best_bid' in discovery_df.columns:
        mask &= (discovery_df['best_bid'] >= 0.10) & (discovery_df['best_bid'] <= 0.90)
    if 'gm_reward_per_100' in discovery_df.columns:
        mask &= discovery_df['gm_reward_per_100'] >= 0.3

    filtered = discovery_df[mask].copy()
    if filtered.empty:
        filtered = discovery_df.copy()  # fallback: use all

    # Sort by reward
    if 'gm_reward_per_100' in filtered.columns:
        filtered = filtered.sort_values('gm_reward_per_100', ascending=False)

    top = filtered.head(n)

    # Build a merged DataFrame that looks like get_db_data() output
    required_cols = ['condition_id', 'question', 'token1', 'token2', 'best_bid',
                     'best_ask', 'spread', 'rewards_daily_rate', 'gm_reward_per_100',
                     'volatility_sum', '3_hour', 'min_size', 'max_spread', 'tick_size',
                     'neg_risk', 'market_slug', 'answer1', 'answer2']

    for col in required_cols:
        if col not in top.columns:
            top[col] = '' if col in ('question', 'market_slug', 'answer1', 'answer2',
                                     'condition_id', 'token1', 'token2') else 0

    # Add trading config columns
    top['max_size'] = 200
    top['trade_size'] = 50
    top['param_type'] = 'default'

    # Safety defaults
    if 'neg_risk' in top.columns:
        top['neg_risk'] = top['neg_risk'].apply(
            lambda x: 'TRUE' if str(x).upper() == 'TRUE' or x == 1 else 'FALSE'
        )
    if 'answer1' not in top.columns or top['answer1'].isna().all():
        top['answer1'] = 'Yes'
    if 'answer2' not in top.columns or top['answer2'].isna().all():
        top['answer2'] = 'No'
    for col, default in [('tick_size', 0.01), ('min_size', 5.0), ('max_spread', 5.0),
                         ('3_hour', 0.0), ('spread', 0.05)]:
        if col in top.columns:
            top[col] = top[col].fillna(default)
        else:
            top[col] = default

    hyperparams = get_hyperparameters()
    if not hyperparams:
        hyperparams = {'default': {'spread': 0.05}}

    logger.info(f"Auto-selected {len(top)} real markets for paper trading")
    for _, row in top.iterrows():
        logger.info(f"  → {row.get('question', 'N/A')[:60]}  (reward: {row.get('gm_reward_per_100', 0):.2f})")

    return top.reset_index(drop=True), hyperparams


def get_sheet_df():
    """
    Legacy wrapper function to maintain compatibility with existing market getters.
    Now routes completely through the embedded SQLite database.
    """
    load_dotenv()
    
    # Paper-trading mock mode: auto-select real markets from DB for realistic simulation
    if os.getenv("MOCK_SHEETS", "false").lower() == "true":
        logger.info("MOCK_SHEETS=true → attempting to auto-select real markets from DB for paper trading")
        
        # Try loading real markets first
        df, hyperparams = _auto_select_paper_markets(n=3)
        if df is not None and not df.empty:
            print(f"✅ Paper Trading: Auto-selected {len(df)} REAL markets from DB")
            return df, hyperparams
        
        # Fallback: if DB is completely empty, warn loudly
        print("⚠️  WARNING: all_markets table is empty!")
        print("⚠️  You must run 'python data_updater/data_updater.py' first to populate market data.")
        print("⚠️  The paper trading bot CANNOT trade without real market data.")
        return pd.DataFrame(), {'default': {'spread': 0.05}}

    try:
        df, hyperparams = get_db_data()
        print(f"Loaded {len(df)} markets and {len(hyperparams.keys())} configuration protocols from SQLite")
        return df, hyperparams
    except Exception as e:
        print(f"Critical Error: Failed to load from SQLite. Did you run `python manage_markets.py init`? Error: {e}")
        return pd.DataFrame(), {}