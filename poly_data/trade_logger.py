"""
Trade Logger - Logs all trades to SQLite in real-time
"""
from poly_data.db_utils import log_trade
import traceback
import logging

logger = logging.getLogger(__name__)

def log_trade_to_sheets(trade_data):
    """
    Legacy method name maintained for compatibility.
    Logs a trade execution directly into the local SQLite 'trade_logs' table.
    """
    try:
        # Extract required fields from the dictionary that the trading engine passes
        # Provide safe defaults if the engine misses a field
        condition_id = str(trade_data.get('market', trade_data.get('condition_id', 'Unknown'))) 
        side = trade_data.get('action', 'UNKNOWN')
        price = float(trade_data.get('price', 0.0))
        size = float(trade_data.get('size', 0.0))
        
        # PnL & Maker rewards are derived/logged elsewhere for paper trading right now, 
        # but the schema supports them.
        maker_reward = 0.0
        pnl = 0.0 
        
        # Execute the fast DB insert
        log_trade(
            condition_id=condition_id,
            side=side,
            price=price,
            size=size,
            maker_reward=maker_reward,
            pnl=pnl
        )
        logger.info(f"[SUCCESS] Trade logged to SQLite: {side} {size} @ ${price:.4f}")
        return True

    except Exception as e:
        logger.error(f"[FAILED] Failed to log trade to SQLite: {e}")
        traceback.print_exc()
        return False

def reset_worksheet_cache():
    """No-op for legacy compatibility"""
    pass
