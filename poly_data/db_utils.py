import sqlite3
import pandas as pd
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Use absolute path to ensure all scripts point to the same database file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'polymarket.db')

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Target Markets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS target_markets (
            condition_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            token1 TEXT NOT NULL,
            token2 TEXT NOT NULL,
            max_size REAL NOT NULL,
            trade_size REAL NOT NULL,
            param_type TEXT NOT NULL,
            neg_risk BOOLEAN NOT NULL DEFAULT 0
        )
    ''')

    # Hyperparameters Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hyperparameters (
            type TEXT NOT NULL,
            param TEXT NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY (type, param)
        )
    ''')

    # Seed complete default hyperparameters using INSERT OR IGNORE so existing
    # user-customised values are never overwritten.
    logger.info("Ensuring default hyperparameters are present...")
    defaults = [
        # ── 'default' type ── used as fallback when param_type is unknown
        ('default', 'spread',                0.05),
        ('default', 'max_size',           1000.0),
        ('default', 'trade_size',          100.0),
        ('default', 'min_size',              5.0),
        ('default', 'volatility_threshold',  0.5),
        ('default', 'take_profit_threshold', 2.0),
        ('default', 'sleep_period',          4.0),
        # ── 'standard' type ── used when param_type='standard'
        ('standard', 'spread',                0.05),
        ('standard', 'max_size',           1000.0),
        ('standard', 'trade_size',          100.0),
        ('standard', 'min_size',              5.0),
        ('standard', 'volatility_threshold',  0.5),
        ('standard', 'take_profit_threshold', 2.0),
        ('standard', 'sleep_period',          4.0),
        # ── 'MockMarketConfig' type ──
        ('MockMarketConfig', 'spread',                0.05),
        ('MockMarketConfig', 'max_size',           1000.0),
        ('MockMarketConfig', 'trade_size',          100.0),
        ('MockMarketConfig', 'min_size',              5.0),
        ('MockMarketConfig', 'volatility_threshold',  0.5),
        ('MockMarketConfig', 'take_profit_threshold', 2.0),
        ('MockMarketConfig', 'sleep_period',          4.0),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO hyperparameters (type, param, value) VALUES (?, ?, ?)",
        defaults
    )
    
    conn.commit()
    
    # Trade Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            condition_id TEXT NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            size REAL NOT NULL,
            maker_reward REAL,
            pnl REAL
        )
    ''')

    # All Markets (Discovery) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS all_markets (
            condition_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            market_slug TEXT,
            answer1 TEXT,
            answer2 TEXT,
            token1 TEXT NOT NULL,
            token2 TEXT NOT NULL,
            best_bid REAL,
            best_ask REAL,
            spread REAL,
            rewards_daily_rate REAL,
            gm_reward_per_100 REAL,
            volatility_sum REAL,
            "3_hour" REAL DEFAULT 0,
            min_size REAL,
            max_spread REAL,
            tick_size REAL,
            neg_risk BOOLEAN DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migrate existing all_markets tables that are missing new columns
    new_cols = [
        ('answer1', 'TEXT'),
        ('answer2', 'TEXT'),
        ('3_hour', 'REAL DEFAULT 0'),
    ]
    for col_name, col_type in new_cols:
        try:
            cursor.execute(f'ALTER TABLE all_markets ADD COLUMN "{col_name}" {col_type}')
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()
    logger.info("[OK] SQLite database initialized successfully.")

def get_target_markets() -> pd.DataFrame:
    """Returns all active target markets as a pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM target_markets", conn)
    conn.close()
    
    # Convert neg_risk back to string 'TRUE'/'FALSE' to maintain compatibility with existing code
    if not df.empty and 'neg_risk' in df.columns:
        df['neg_risk'] = df['neg_risk'].apply(lambda x: 'TRUE' if x else 'FALSE')
        
    return df

def get_hyperparameters() -> Dict[str, Dict[str, float]]:
    """Returns all hyperparameters nested by type."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type, param, value FROM hyperparameters")
    rows = cursor.fetchall()
    conn.close()

    hyperparams = {}
    for type_name, param, value in rows:
        if type_name not in hyperparams:
            hyperparams[type_name] = {}
        hyperparams[type_name][param] = value
        
    return hyperparams

def add_market(condition_id: str, question: str, token1: str, token2: str, 
               max_size: float, trade_size: float, param_type: str, neg_risk: bool = False):
    """Adds a new market to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO target_markets 
            (condition_id, question, token1, token2, max_size, trade_size, param_type, neg_risk)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (condition_id, question, token1, token2, max_size, trade_size, param_type, neg_risk))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add market: {e}")
        return False
    finally:
        conn.close()

def remove_market(condition_id: str):
    """Removes a market from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM target_markets WHERE condition_id = ?", (condition_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def set_hyperparameter(type_name: str, param: str, value: float):
    """Sets a hyperparameter value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO hyperparameters (type, param, value)
        VALUES (?, ?, ?)
    ''', (type_name, param, value))
    conn.commit()
    conn.close()

def log_trade(condition_id: str, side: str, price: float, size: float, maker_reward: float = 0.0, pnl: float = 0.0):
    """Logs a trade execution."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trade_logs (condition_id, side, price, size, maker_reward, pnl)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (condition_id, side, price, size, maker_reward, pnl))
    conn.commit()
    conn.close()

def save_all_markets(df: pd.DataFrame):
    """Saves the global market scan results to the all_markets table."""
    if df.empty:
        return
    
    conn = get_connection()
    try:
        # Create a temp copy for processing
        temp_df = df.copy()
        
        # Ensure correct column names for DB
        # Mapping from data_updater.py column names to DB column names if necessary
        # Most names match already.
        
        # Add last_updated timestamp
        temp_df['last_updated'] = datetime.now().isoformat()
        
        # Convert neg_risk to boolean if it matches 'TRUE'/'FALSE' strings
        if 'neg_risk' in temp_df.columns:
            temp_df['neg_risk'] = temp_df['neg_risk'].apply(lambda x: 1 if str(x).upper() == 'TRUE' or x == 1 else 0)

        # Select columns that exist in both DataFrame and table
        db_cols = [
            'condition_id', 'question', 'market_slug', 'answer1', 'answer2',
            'token1', 'token2',
            'best_bid', 'best_ask', 'spread', 'rewards_daily_rate',
            'gm_reward_per_100', 'volatility_sum', '3_hour', 'min_size',
            'max_spread', 'tick_size', 'neg_risk', 'last_updated'
        ]
        
        # Filter df to only include these columns (if they exist)
        final_cols = [c for c in db_cols if c in temp_df.columns]
        save_df = temp_df[final_cols]
        
        # Insert using pandas
        save_df.to_sql('all_markets', conn, if_exists='replace', index=False)
        conn.commit()
        logger.info(f"Saved {len(save_df)} markets to all_markets table.")
    except Exception as e:
        logger.error(f"Failed to save all_markets: {e}")
    finally:
        conn.close()

def get_db_data() -> Tuple[pd.DataFrame, Dict[str, Dict[str, float]]]:
    """Replacement for get_sheet_df() - returns (markets_df, hyperparams_dict)

    The returned DataFrame is the JOIN of target_markets (config) and all_markets
    (live data), so that all columns expected by trading.py (tick_size, min_size,
    max_spread, best_bid, spread, etc.) are present.
    """
    target_df = get_target_markets()
    hyperparams = get_hyperparameters()

    if target_df.empty:
        return target_df, hyperparams

    # Enrich with live market data from all_markets
    discovery_df = get_discovery_markets()
    if not discovery_df.empty:
        # Convert neg_risk back to string in discovery_df to keep type consistent
        if 'neg_risk' in discovery_df.columns:
            discovery_df['neg_risk'] = discovery_df['neg_risk'].apply(
                lambda x: 'TRUE' if x else 'FALSE'
            )
        # Columns from all_markets that target_markets lacks
        extra_cols = [c for c in discovery_df.columns if c != 'condition_id' and c not in target_df.columns]
        merge_cols = ['condition_id'] + extra_cols
        merged = target_df.merge(
            discovery_df[merge_cols],
            on='condition_id',
            how='left'
        )
    else:
        merged = target_df.copy()

    # Safety defaults for critical columns that trading.py always reads
    if 'tick_size' not in merged.columns or merged['tick_size'].isna().any():
        merged['tick_size'] = merged.get('tick_size', pd.Series([0.01] * len(merged))).fillna(0.01)
    for col, default in [
        ('min_size', 5.0), ('max_spread', 5.0), ('best_bid', 0.5), ('best_ask', 0.5),
        ('spread', 0.05), ('rewards_daily_rate', 0.0), ('gm_reward_per_100', 0.0),
        ('volatility_sum', 0.0), ('3_hour', 0.0),
        ('answer1', 'Yes'), ('answer2', 'No'),
    ]:
        if col not in merged.columns:
            merged[col] = default
        else:
            merged[col] = merged[col].fillna(default)

    return merged, hyperparams

def get_discovery_markets() -> pd.DataFrame:
    """Returns the results of the global market scan."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM all_markets", conn)
        return df
    except Exception as e:
        logger.error(f"Failed to fetch discovery markets: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
