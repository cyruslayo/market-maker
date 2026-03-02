import gc  # Garbage collection
import time  # Time functions
import asyncio  # Asynchronous I/O
import traceback  # Exception handling
import logging  # Logging for debugging
import pandas as pd  # For reading Google Sheets
from poly_data.polymarket_client import PolymarketClient
from poly_data.data_utils import update_markets, update_positions, update_orders
from poly_data.websocket_handlers import connect_market_websocket, connect_user_websocket
import poly_data.global_state as global_state
from poly_data.data_processing import remove_from_performing
from poly_data.position_snapshot import log_position_snapshot
from dotenv import load_dotenv

# Configure logging
import sys

# Force UTF-8 encoding for standard output/error on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main.log', encoding='utf-8'),  # Log to file
        logging.StreamHandler(sys.stdout)  # Log to console
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

def update_once():
    """
    Initialize the application state by fetching market data, positions, and orders.
    """
    update_markets()  # Get market information from Google Sheets
    update_positions()  # Get current positions from Polymarket
    update_orders()  # Get current orders from Polymarket
    logger.info(f"Loaded {len(global_state.df)} markets from All Markets sheet")

def remove_from_pending():
    """
    Clean up stale trades that have been pending for too long (>15 seconds).
    """
    try:
        current_time = time.time()
        for col in list(global_state.performing.keys()):
            for trade_id in list(global_state.performing[col]):
                try:
                    if current_time - global_state.performing_timestamps[col].get(trade_id, current_time) > 15:
                        logger.info(f"Removing stale entry {trade_id} from {col} after 15 seconds")
                        remove_from_performing(col, trade_id)
                except:
                    logger.error(f"Error removing trade {trade_id} from {col}: {traceback.format_exc()}")
    except:
        logger.error(f"Error in remove_from_pending: {traceback.format_exc()}")

async def update_periodically():
    """
    Asynchronous function that periodically updates market data, positions, and orders.
    - Positions and orders every 10 seconds
    - Market data every 60 seconds (every 6 cycles)
    - Position snapshots every 5 minutes (every 30 cycles)
    - Stale pending trades removed each cycle
    """
    i = 1
    balance_history = []
    
    while True:
        await asyncio.sleep(10)  # Update every 10 seconds
        try:
            remove_from_pending()
            update_positions(avgOnly=True)
            update_orders()
            
            # --- Drawdown Circuit Breaker Logic ---
            try:
                current_time = pd.Timestamp.utcnow().tz_localize(None)
                if global_state.client is not None and not getattr(global_state, 'trade_halt', False):
                    # In a real scenario we'd get real-time balances, but get_total_balance is synchronously blocked. 
                    # We will handle errors smoothly.
                    # Fix M4: Run synchronous balance calls in a thread to avoid blocking the event loop
                    usdc_balance = await asyncio.to_thread(lambda: float(global_state.client.get_usdc_balance() or 0))
                    pos_balance = await asyncio.to_thread(lambda: float(global_state.client.get_pos_balance() or 0))
                    total_balance = usdc_balance + pos_balance
                    
                    if total_balance > 0:
                        balance_history = [(t, b) for t, b in balance_history if (current_time - t).total_seconds() <= 86400]
                        balance_history.append((current_time, total_balance))
                        
                        hourly_history = [b for t, b in balance_history if (current_time - t).total_seconds() <= 3600]
                        hourly_max = max(hourly_history) if hourly_history else 0
                        daily_max = max([b for t, b in balance_history]) if balance_history else 0
                        
                        if hourly_max > 0:
                            hourly_drop = (hourly_max - total_balance) / hourly_max
                            if hourly_drop > 0.02 and len(hourly_history) > 10:  # > 2% hourly drawdown, require some history
                                logger.critical(f"CIRCUIT BREAKER: 2% Hourly Drawdown! Dropped from {hourly_max:.2f} to {total_balance:.2f} ({hourly_drop:.2%})")
                                global_state.trade_halt = True
                                try:
                                    global_state.client.cancel_all()
                                except:
                                    pass
                                
                        if daily_max > 0 and not getattr(global_state, 'trade_halt', False):
                            daily_drop = (daily_max - total_balance) / daily_max
                            if daily_drop > 0.05 and len(balance_history) > 10:  # > 5% daily drawdown
                                logger.critical(f"CIRCUIT BREAKER: 5% Daily Drawdown! Dropped from {daily_max:.2f} to {total_balance:.2f} ({daily_drop:.2%})")
                                global_state.trade_halt = True
                                try:
                                    global_state.client.cancel_all()
                                except:
                                    pass
            except Exception as e:
                logger.error(f"Error in circuit breaker logic: {e}")
            # ----------------------------------------
            
            if i % 6 == 0:  # Every 60 seconds
                update_markets()
            if i % 30 == 0:  # Every 5 minutes (300 seconds)
                log_position_snapshot()
            i += 1
            if i > 30:
                i = 1
        except Exception as e:
            logger.error(f"Error in update_periodically: {e}")

async def merger_loop():
    """
    Background task that monitors positions and triggers merges when possible.
    
    Runs every 30 seconds, checking for markets where both YES and NO positions
    exist and can be merged to recover USDC collateral. This eliminates the
    P99 latency spikes from the previous subprocess-based approach.
    """
    MERGE_THRESHOLD = 20  # Minimum position size to trigger merge
    SLEEP_INTERVAL = 30   # Seconds between checks
    
    while True:
        await asyncio.sleep(SLEEP_INTERVAL)
        
        try:
            # Check if client and df are initialized
            if global_state.client is None or global_state.df is None:
                logger.debug("Merger loop: client or market data not ready, skipping")
                continue
            
            # Get current positions snapshot (thread-safe)
            positions = global_state.get_state_snapshot()['positions']
            
            # Iterate through all markets in the dataframe
            for _, row in global_state.df.iterrows():
                try:
                    condition_id = row.get('condition_id')
                    token1 = row.get('token1')  # YES token
                    token2 = row.get('token2')  # NO token
                    is_neg_risk = row.get('neg_risk') == 'TRUE'
                    
                    if not condition_id or not token1 or not token2:
                        continue
                    
                    # Get position sizes for both tokens
                    pos1 = positions.get(str(token1), {'size': 0, 'avgPrice': 0})['size']
                    pos2 = positions.get(str(token2), {'size': 0, 'avgPrice': 0})['size']
                    
                    # Calculate merge amount (minimum of both positions)
                    merge_amount = min(pos1, pos2)
                    
                    # Trigger merge if above threshold
                    if merge_amount > MERGE_THRESHOLD:
                        logger.info(f"Merger triggered: {condition_id}, amount={merge_amount:.2f}, "
                                  f"token1_pos={pos1:.2f}, token2_pos={pos2:.2f}")
                        
                        # Fire-and-forget merge call (background task)
                        asyncio.create_task(
                            global_state.client.merge_positions(merge_amount, condition_id, is_neg_risk)
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing market for merge: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in merger_loop: {e}")

async def main():
    """
    Main application entry point. Initializes client, data, and manages websocket connections.
    """
    # Initialize client with error handling
    try:
        logger.info("=" * 80)
        logger.info("STARTING POLYMARKET TRADING BOT")
        logger.info("=" * 80)
        global_state.client = PolymarketClient()
        logger.info("✓ Polymarket client initialized successfully")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("Please check your .env file and ensure PK and BROWSER_ADDRESS are set correctly.")
        return
    except RuntimeError as e:
        logger.error(f"❌ Authentication error: {e}")
        logger.error("Please verify your private key and API credentials are valid.")
        return
    except Exception as e:
        logger.error(f"❌ Unexpected error during client initialization: {e}")
        logger.error(traceback.format_exc())
        return

    # Initialize state and fetch initial data
    try:
        global_state.all_tokens = []
        update_once()
        logger.info(f"After initial updates: orders={global_state.orders}, positions={global_state.positions}")
    except Exception as e:
        logger.error(f"❌ Failed to load initial market data: {e}")
        logger.error("Please check your Google Sheets configuration and network connection.")
        return

    # Subscribe to WebSocket using subscribed_assets (token IDs), not condition_ids
    # subscribed_assets is populated by update_markets() in data_utils.py
    logger.info(f"Subscribing to WebSocket for {len(global_state.subscribed_assets)} token IDs: {global_state.subscribed_assets}")

    logger.info(
        f"There are {len(global_state.df)} markets, {len(global_state.positions)} positions, and {len(global_state.orders)} orders. Starting positions: {global_state.positions}")

    # Start periodic updates as an async task
    asyncio.create_task(update_periodically())
    
    # Start merger loop background task
    asyncio.create_task(merger_loop())
    logger.info("✓ Merger loop started (checking every 30 seconds for mergeable positions)")

    # Main loop - maintain websocket connections with backoff
    backoff_time = 5
    while True:
        try:
            # Connect to market and user websockets simultaneously
            # Subscribe using token IDs from subscribed_assets, not condition_ids
            await asyncio.gather(
                connect_market_websocket(list(global_state.subscribed_assets)),
                connect_user_websocket()
            )
            logger.info("Reconnecting to the websocket")
            backoff_time = 5  # Reset backoff on success
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, 60)  # Exponential backoff up to 60 seconds

if __name__ == "__main__":
    asyncio.run(main())