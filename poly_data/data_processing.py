import json
from sortedcontainers import SortedDict
import poly_data.global_state as global_state
import poly_data.CONSTANTS as CONSTANTS
import asyncio
import logging
import time
from trading import perform_trade
from poly_data.data_utils import set_position, set_order, update_positions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_processing.log')
    ]
)
logger = logging.getLogger(__name__)


def initialize_market_data(asset):
    """Initialize market data in global_state if not already present."""
    if asset not in global_state.all_data:
        logger.info(f"Initializing market data for asset: {asset}")
        global_state.all_data[asset] = {
            'bids': SortedDict(),
            'asks': SortedDict()
        }


def process_book_data(asset, json_data):
    """Process book data for a given asset."""
    initialize_market_data(asset)
    global_state.all_data[asset]['bids'].clear()
    global_state.all_data[asset]['asks'].clear()
    global_state.all_data[asset]['bids'].update(
        {float(entry['price']): float(entry['size']) for entry in json_data['bids']})
    global_state.all_data[asset]['asks'].update(
        {float(entry['price']): float(entry['size']) for entry in json_data['asks']})


def process_price_change(asset, side, price_level, new_size):
    """Process price change for a given asset and side."""
    book = global_state.all_data[asset]['bids'] if side == 'bids' else global_state.all_data[asset]['asks']
    if new_size == 0:
        if price_level in book:
            del book[price_level]
    else:
        book[price_level] = new_size


def _resolve_condition_id(token_or_condition_id: str) -> str | None:
    """
    Bug 3 / Bug 5 fix: perform_trade() looks up df[condition_id == market], so it always
    needs a condition_id.  The market WebSocket sends individual token IDs as 'market'.
    This helper maps a token_id → condition_id via global_state.df when needed.
    If the string is already a condition_id (present in df) it is returned unchanged.
    """
    if global_state.df is None or global_state.df.empty:
        return token_or_condition_id

    # Already a condition_id?
    if token_or_condition_id in global_state.df['condition_id'].values:
        return token_or_condition_id

    # Try resolving as a token_id (token1 or token2)
    match = global_state.df[
        (global_state.df['token1'].astype(str) == token_or_condition_id) |
        (global_state.df['token2'].astype(str) == token_or_condition_id)
    ]
    if not match.empty:
        return match.iloc[0]['condition_id']

    return None  # Unknown — let caller decide


async def process_data(json_datas, trade=True):
    """Process WebSocket data, handling both single dict and list of dicts."""
    # Ensure json_datas is a list
    if isinstance(json_datas, dict):
        json_datas = [json_datas]

    for json_data in json_datas:
        try:
            if not isinstance(json_data, dict):
                logger.error(f"Expected dict, got {type(json_data)}: {json_data}")
                continue

            event_type = json_data.get('event_type')
            if not event_type:
                logger.warning(f"No event_type in json_data: {json_data}")
                continue

            asset = json_data.get('market')
            if not asset:
                logger.warning(f"No market in json_data: {json_data}")
                continue

            # Validate market is in subscribed assets
            subscribed_assets = getattr(global_state, 'subscribed_assets', set())
            if asset not in subscribed_assets:
                # IN AGGRESSIVE MODE: Process ALL markets, not just subscribed ones
                import os
                if os.getenv('AGGRESSIVE_MODE', 'false').lower() != 'true':
                    logger.warning(f"Received data for unsubscribed market: {asset}, json_data: {json_data}")
                    continue
                else:
                    logger.info(f"AGGRESSIVE MODE: Processing unsubscribed market: {asset}")

            logger.info(f"Processing event_type: {event_type} for market: {asset}")

            if event_type == 'book':
                process_book_data(asset, json_data)
                if trade:
                    # Bug 3 fix: market WS sends token_id as 'market'; perform_trade needs condition_id.
                    condition_id = _resolve_condition_id(asset)
                    if condition_id:
                        await asyncio.create_task(perform_trade(condition_id))
                    else:
                        logger.warning(f"Cannot resolve condition_id for book asset: {asset}")
            elif event_type == 'price_change':
                # Check for 'price_changes' (new API) or 'changes' (legacy)
                changes = json_data.get('price_changes') or json_data.get('changes', [])
                if not changes:
                    logger.warning(f"No price_changes or changes in price_change event: {json_data}")
                    continue
                # Initialize market data if not present
                initialize_market_data(asset)
                for data in changes:
                    side = 'bids' if data['side'] == 'BUY' else 'asks'
                    price_level = float(data['price'])
                    new_size = float(data['size'])
                    process_price_change(asset, side, price_level, new_size)

                # Rate limit trading on price changes to reduce order churn.
                # Bug 5 fix: use condition_id as the cooldown key so market-WS and user-WS
                # rate-limiting share the same counter (perform_trade also uses condition_id).
                if trade:
                    condition_id = _resolve_condition_id(asset)
                    if not condition_id:
                        logger.warning(f"Cannot resolve condition_id for price_change asset: {asset}")
                        continue

                    current_time = time.time()
                    last_action = global_state.get_last_trade_action_time_atomic(condition_id)
                    time_since_last_action = current_time - last_action

                    # Only trigger trading if 30 seconds have passed since last action
                    if time_since_last_action >= 30:
                        global_state.set_last_trade_action_time_atomic(condition_id, current_time)
                        logger.info(f"Triggering trade for {condition_id} after {time_since_last_action:.1f}s cooldown")
                        await asyncio.create_task(perform_trade(condition_id))
                    else:
                        logger.debug(f"Skipping trade for {condition_id}, cooldown: {30 - time_since_last_action:.1f}s remaining")
            else:
                logger.warning(f"Unhandled event_type: {event_type}")
        except Exception as e:
            logger.error(f"Error processing data: {e}, json_data: {json_data}", exc_info=True)


def add_to_performing(col, id):
    """Add trade ID to performing set with timestamp."""
    if col not in global_state.performing:
        global_state.performing[col] = set()

    if col not in global_state.performing_timestamps:
        global_state.performing_timestamps[col] = {}

    global_state.performing[col].add(id)
    global_state.performing_timestamps[col][id] = time.time()


def remove_from_performing(col, id):
    """Remove trade ID from performing set and timestamps."""
    if col in global_state.performing:
        global_state.performing[col].discard(id)

    if col in global_state.performing_timestamps:
        global_state.performing_timestamps[col].pop(id, None)


async def process_user_data(json_data):
    """Process user WebSocket data."""
    try:
        # Ensure json_data is a list
        if isinstance(json_data, dict):
            json_data = [json_data]

        for row in json_data:
            market = row.get('market')
            if not market:
                logger.warning(f"No market in user data: {row}")
                continue

            side = row.get('side', '').lower()
            token = row.get('asset_id')
            if not token or token not in global_state.REVERSE_TOKENS:
                logger.warning(f"Invalid or missing token in user data: {row}")
                continue

            col = f"{token}_{side}"

            if row.get('event_type') == 'trade':
                size = 0
                price = 0
                maker_outcome = ""
                taker_outcome = row.get('outcome', '')

                is_user_maker = False
                for maker_order in row.get('maker_orders', []):
                    if maker_order.get('maker_address', '').lower() == global_state.client.browser_wallet.lower():
                        logger.info("User is maker")
                        size = float(maker_order.get('matched_amount', 0))
                        price = float(maker_order.get('price', 0))
                        is_user_maker = True
                        maker_outcome = maker_order.get('outcome', '')
                        if maker_outcome == taker_outcome:
                            side = 'buy' if side == 'sell' else 'sell'
                        else:
                            token = global_state.REVERSE_TOKENS[token]

                if not is_user_maker:
                    size = float(row.get('size', 0))
                    price = float(row.get('price', 0))
                    logger.info("User is taker")

                logger.info(
                    f"TRADE EVENT FOR: {market}, ID: {row.get('id')}, STATUS: {row.get('status')}, SIDE: {row.get('side')}, MAKER OUTCOME: {maker_outcome}, TAKER OUTCOME: {taker_outcome}, PROCESSED SIDE: {side}, SIZE: {size}")

                if row.get('status') in ['CONFIRMED', 'FAILED']:
                    if row.get('status') == 'FAILED':
                        logger.info(f"Trade failed for {token}, updating positions")
                        await asyncio.sleep(2)
                        update_positions()
                        # Log failed trade
                        try:
                            from poly_data.trade_logger import log_trade_to_sheets
                            from datetime import datetime
                            log_trade_to_sheets({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'action': side.upper(),
                                'market': market,
                                'price': price,
                                'size': size,
                                'order_id': row.get('id', 'N/A'),
                                'status': 'FAILED',
                                'token_id': token,
                                'neg_risk': False,  # Will be determined from market data
                                'position_before': global_state.get_position_atomic(str(token)).get('size', 0),
                                'position_after': global_state.get_position_atomic(str(token)).get('size', 0),
                                'notes': 'Trade failed'
                            })
                        except Exception as e:
                            logger.warning(f"Could not log failed trade: {e}")
                    else:
                        remove_from_performing(col, row.get('id'))
                        logger.info(f"Confirmed. Performing is {len(global_state.performing.get(col, set()))}")
                        logger.info(f"Last trade update is {global_state.last_trade_update}")
                        logger.info(f"Performing is {global_state.performing}")
                        logger.info(f"Performing timestamps is {global_state.performing_timestamps}")
                        # Log filled trade
                        try:
                            from poly_data.trade_logger import log_trade_to_sheets
                            from datetime import datetime
                            pos_before = global_state.get_position_atomic(str(token)).get('size', 0)
                            update_positions()  # Update positions first
                            pos_after = global_state.get_position_atomic(str(token)).get('size', 0)
                            log_trade_to_sheets({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'action': side.upper(),
                                'market': market,
                                'price': price,
                                'size': size,
                                'order_id': row.get('id', 'N/A'),
                                'status': 'FILLED',
                                'token_id': token,
                                'neg_risk': False,  # Will be determined from market data
                                'position_before': pos_before,
                                'position_after': pos_after,
                                'notes': 'Trade filled and confirmed'
                            })
                        except Exception as e:
                            logger.warning(f"Could not log filled trade: {e}")
                        await asyncio.create_task(perform_trade(market))

                elif row.get('status') == 'MATCHED':
                    add_to_performing(col, row.get('id'))
                    logger.info(f"Matched. Performing is {len(global_state.performing.get(col, set()))}")
                    set_position(token, side, size, price)
                    logger.info(f"Position after matching is {global_state.get_position_atomic(str(token))}")
                    logger.info(f"Last trade update is {global_state.last_trade_update}")
                    logger.info(f"Performing is {global_state.performing}")
                    logger.info(f"Performing timestamps is {global_state.performing_timestamps}")
                    await asyncio.create_task(perform_trade(market))
                elif row.get('status') == 'MINED':
                    remove_from_performing(col, row.get('id'))

            elif row.get('event_type') == 'order':
                logger.info(
                    f"ORDER EVENT FOR: {market}, STATUS: {row.get('status')}, TYPE: {row.get('type')}, SIDE: {side}, ORIGINAL SIZE: {row.get('original_size')}, SIZE MATCHED: {row.get('size_matched')}")
                set_order(token, side, float(row.get('original_size', 0)) - float(row.get('size_matched', 0)),
                          row.get('price', 0))
                await asyncio.create_task(perform_trade(market))
            else:
                logger.warning(f"Unhandled user event_type: {row.get('event_type')}")
    except Exception as e:
        logger.error(f"Error processing user data: {e}, json_data: {json_data}", exc_info=True)