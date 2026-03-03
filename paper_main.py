import gc
import sys
import os
import time
import asyncio
import traceback
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

from poly_data.data_utils import update_markets, update_positions, update_orders
from poly_data.websocket_handlers import connect_market_websocket, connect_user_websocket
import poly_data.global_state as global_state
from poly_data.data_processing import remove_from_performing
from poly_data.db_utils import init_db

# Simulation modules
from simulation.matching_engine import LiveMatchingEngine
from simulation.paper_client import PaperTradingClient

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
        logging.FileHandler('paper_main.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

def print_paper_report():
    engine = global_state.client.matching_engine

    pnl = engine.get_pnl_summary()
    mtm_value  = pnl["mtm_value"]
    cost_basis = pnl["cost_basis"]
    realized   = pnl["realized_pnl"]
    unrealized = pnl["unrealized_pnl"]
    total_pnl  = pnl["total_pnl"]

    total_portfolio_mtm = engine.usdc_balance + mtm_value

    print("\n" + "="*55)
    print("       PAPER TRADING REPORT")
    print("="*55)

    print("\n--- Portfolio Snapshot ---")
    print(f"  USDC Balance:              ${engine.usdc_balance:>10.2f}")
    print(f"  Position Value (cost):     ${cost_basis:>10.2f}")
    print(f"  Position Value (MTM):      ${mtm_value:>10.2f}  ← live mid-price")
    print(f"  Total Portfolio (MTM):     ${total_portfolio_mtm:>10.2f}")

    print("\n--- P&L Breakdown ---")
    sign = lambda v: "+" if v >= 0 else ""
    print(f"  Realized P&L:    {sign(realized)}${realized:>8.4f}")
    print(f"  Unrealized P&L:  {sign(unrealized)}${unrealized:>8.4f}  (MTM vs cost)")
    print(f"  Total P&L:       {sign(total_pnl)}${total_pnl:>8.4f}")

    print("\n--- Execution Stats ---")
    fills = len(engine.trade_history)
    misses = len(engine.missed_fills)
    miss_rate = misses / (fills + misses) * 100 if (fills + misses) > 0 else 0.0
    print(f"  Successful Fills:          {fills}")
    print(f"  Latency Misses:            {misses}  ({miss_rate:.1f}%)")

    if engine.missed_fills:
        avg_latency = sum(m["latency_ms"] for m in engine.missed_fills) / misses
        print(f"  Avg Latency on Misses:     {avg_latency:.1f} ms")

    if engine.pnl_history:
        best  = max(engine.pnl_history, key=lambda r: r["cumulative_pnl"])
        worst = min(engine.pnl_history, key=lambda r: r["cumulative_pnl"])
        print(f"\n--- P&L Trajectory ---")
        print(f"  Peak Cumulative P&L:  ${best['cumulative_pnl']:>+.4f}")
        print(f"  Trough Cumulative:    ${worst['cumulative_pnl']:>+.4f}")

    print("="*55 + "\n")


def update_paper_once():
    """
    Initialize the paper application state.
    We fetch live market structures but overwrite positions and orders using our local mock state.
    """
    update_markets()
    # Pull current positions locally from matching engine
    update_positions(avgOnly=False)
    update_orders()
    logger.info(f"Loaded {len(global_state.df)} markets for Paper Trading.")

def remove_from_pending():
    try:
        current_time = time.time()
        for col in list(global_state.performing.keys()):
            for trade_id in list(global_state.performing[col]):
                try:
                    if current_time - global_state.performing_timestamps[col].get(trade_id, current_time) > 15:
                        remove_from_performing(col, trade_id)
                except:
                    pass
    except:
        pass

async def paper_update_loop():
    i = 1
    while True:
        await asyncio.sleep(10)
        try:
            remove_from_pending()
            
            # Use real Poly queries or sync local state depending on logic,
            # but since PaperClient reads from matching_engine, update_positions syncs local state.
            update_positions(avgOnly=True)
            update_orders()
            
            if i % 6 == 0:
                update_markets()
                
            if i % 30 == 0:
                print_paper_report()
                
            i += 1
            if i > 30:
                i = 1
        except Exception as e:
            logger.error(f"Error in paper_update_loop: {e}")

async def paper_merger_loop():
    MERGE_THRESHOLD = 20
    SLEEP_INTERVAL = 30
    
    while True:
        await asyncio.sleep(SLEEP_INTERVAL)
        try:
            if global_state.client is None or global_state.df is None:
                continue
                
            positions = global_state.get_state_snapshot()['positions']
            for _, row in global_state.df.iterrows():
                try:
                    condition_id = row.get('condition_id')
                    token1 = row.get('token1')
                    token2 = row.get('token2')
                    is_neg_risk = row.get('neg_risk') == 'TRUE'
                    
                    if not condition_id or not token1 or not token2:
                        continue
                    
                    pos1 = positions.get(str(token1), {'size': 0})['size']
                    pos2 = positions.get(str(token2), {'size': 0})['size']
                    
                    merge_amount = min(pos1, pos2)
                    if merge_amount > MERGE_THRESHOLD:
                        logger.info(f"PAPER Merger triggered: {condition_id}, amount={merge_amount:.2f}")
                        asyncio.create_task(
                            global_state.client.merge_positions(merge_amount, condition_id, is_neg_risk)
                        )
                except Exception as e:
                    continue
        except Exception as e:
            logger.error(f"Error in paper_merger_loop: {e}")

async def main():
    logger.info("=" * 80)
    logger.info("STARTING PAPER TRADING BOT")
    logger.info("=" * 80)

    # Run DB schema migration (adds new columns to existing DBs if needed)
    init_db()

    try:
        # Initialize paper components
        matching_engine = LiveMatchingEngine(initial_usdc=1000.0)
        
        # global_state.client becomes the Paper wrapper
        global_state.client = PaperTradingClient(matching_engine=matching_engine)
        logger.info("[SUCCESS] Paper Trading Client initialized")
    except Exception as e:
        logger.error(f"[FAILED] Initialization failed: {e}")
        return

    try:
        global_state.all_tokens = []
        update_paper_once()
    except Exception as e:
        logger.error(f"Failed to load initial market data: {e}")
        return

    logger.info(f"Subscribing to WebSocket for {len(global_state.subscribed_assets)} tokens")

    asyncio.create_task(paper_update_loop())
    asyncio.create_task(paper_merger_loop())
    
    # Optional graceful shutdown task to print report on exit
    def handle_exception(loop, context):
        msg = context.get("exception", context["message"])
        logger.error(f"Caught exception: {msg}")
        print_paper_report()
        sys.exit(1)
        
    asyncio.get_event_loop().set_exception_handler(handle_exception)

    backoff_time = 5
    while True:
        try:
            # Connect to live market data (triggers our hook)
            await asyncio.gather(
                connect_market_websocket(list(global_state.subscribed_assets)),
                # We skip the user websocket or use it purely for real account monitoring
                # depending on setup, but the paper engine fills orders itself via market hook.
                # connect_user_websocket() 
            )
            backoff_time = 5 
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPaper trading stopped by user.")
        print_paper_report()
