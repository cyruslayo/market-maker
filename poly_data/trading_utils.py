from web3 import Web3
try:
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    # For web3.py v6+, geth_poa_middleware is used instead
    from web3.middleware import geth_poa_middleware
    ExtraDataToPOAMiddleware = geth_poa_middleware
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from dotenv import load_dotenv
import os
import math
import poly_data.global_state as global_state

load_dotenv()

# OFI (Order Flow Imbalance) constants for adaptive spread model
OFI_IMBALANCE_THRESHOLD = 0.7
OFI_ALPHA_WIDE = 1.8
OFI_ALPHA_NORMAL = 1.0


def get_clob_client():
    host = "https://clob.polymarket.com"
    key = os.getenv("PK")
    browser_address = os.getenv("BROWSER_ADDRESS")
    chain_id = POLYGON
    web3 = Web3(Web3.HTTPProvider(os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")))
    # Add POA middleware for Polygon
    try:
        web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except AttributeError:
        # For web3.py v6+, middleware is added differently
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    # Handle both old and new web3.py versions
    if hasattr(Web3, 'to_checksum_address'):
        checksum_address = Web3.to_checksum_address(browser_address)
    else:
        checksum_address = Web3.toChecksumAddress(browser_address)

    return ClobClient(
        host=host,
        key=key,
        chain_id=chain_id,
        funder=checksum_address,
        signature_type=2
    )

def _resolve_all_data_key(token_id: str) -> str | None:
    """
    Resolve a token ID to the actual key used in global_state.all_data.

    The WebSocket sends market IDs in 0x-hex form (e.g. '0x753b97e8...') while
    the DB stores them as large decimal integers. Both forms represent the same
    256-bit number. Try both representations so lookups always succeed regardless
    of which format was used when the book was first stored.
    """
    if token_id in global_state.all_data:
        return token_id  # already correct (decimal form)

    # Try: decimal string → 0x-hex string
    try:
        hex_form = hex(int(token_id))   # '0xabc...'
        if hex_form in global_state.all_data:
            return hex_form
    except (ValueError, TypeError):
        pass

    # Try: 0x-hex string → decimal string
    if token_id.startswith('0x') or token_id.startswith('0X'):
        try:
            dec_form = str(int(token_id, 16))
            if dec_form in global_state.all_data:
                return dec_form
        except (ValueError, TypeError):
            pass

    return None  # not found in either form


def get_best_bid_ask_deets(market, name, size, deviation_threshold=0.05):
    # Normalize market key: WS may store books under 0x-hex while the caller
    # passes a decimal token ID (or vice-versa). Resolve to whichever form exists.
    resolved = _resolve_all_data_key(market)
    if resolved is None:
        # Book not yet received for this token — return empty deets gracefully
        return {
            'best_bid': None, 'best_bid_size': 0,
            'best_ask': None, 'best_ask_size': 0,
            'top_bid': None, 'top_ask': None,
            'second_best_bid': None, 'second_best_ask': None,
            'bid_sum_within_n_percent': 0, 'ask_sum_within_n_percent': 0,
        }
    market = resolved

    best_bid, best_bid_size, second_best_bid, second_best_bid_size, top_bid = find_best_price_with_size(global_state.all_data[market]['bids'], size, reverse=True)
    best_ask, best_ask_size, second_best_ask, second_best_ask_size, top_ask = find_best_price_with_size(global_state.all_data[market]['asks'], size, reverse=False)
    
    # Handle None values in mid_price calculation
    if best_bid is not None and best_ask is not None:
        mid_price = (best_bid + best_ask) / 2
        bid_sum_within_n_percent = sum(size for price, size in global_state.all_data[market]['bids'].items() if best_bid <= price <= mid_price * (1 + deviation_threshold))
        ask_sum_within_n_percent = sum(size for price, size in global_state.all_data[market]['asks'].items() if mid_price * (1 - deviation_threshold) <= price <= best_ask)
    else:
        mid_price = None
        bid_sum_within_n_percent = 0
        ask_sum_within_n_percent = 0

    if name == 'token2':
        # Handle None values before arithmetic operations
        if all(x is not None for x in [best_bid, best_ask, second_best_bid, second_best_ask, top_bid, top_ask]):
            best_bid, second_best_bid, top_bid, best_ask, second_best_ask, top_ask = 1 - best_ask, 1 - second_best_ask, 1 - top_ask, 1 - best_bid, 1 - second_best_bid, 1 - top_bid
            best_bid_size, second_best_bid_size, best_ask_size, second_best_ask_size = best_ask_size, second_best_ask_size, best_bid_size, second_best_bid_size
            bid_sum_within_n_percent, ask_sum_within_n_percent = ask_sum_within_n_percent, bid_sum_within_n_percent
        else:
            # Handle case where some prices are None - use available values or defaults
            if best_bid is not None and best_ask is not None:
                best_bid, best_ask = 1 - best_ask, 1 - best_bid
                best_bid_size, best_ask_size = best_ask_size, best_bid_size
            if second_best_bid is not None:
                second_best_bid = 1 - second_best_bid
            if second_best_ask is not None:
                second_best_ask = 1 - second_best_ask
            if top_bid is not None:
                top_bid = 1 - top_bid
            if top_ask is not None:
                top_ask = 1 - top_ask
            bid_sum_within_n_percent, ask_sum_within_n_percent = ask_sum_within_n_percent, bid_sum_within_n_percent



    #return as dictionary
    return {
        'best_bid': best_bid,
        'best_bid_size': best_bid_size,
        'second_best_bid': second_best_bid,
        'second_best_bid_size': second_best_bid_size,
        'top_bid': top_bid,
        'best_ask': best_ask,
        'best_ask_size': best_ask_size,
        'second_best_ask': second_best_ask,
        'second_best_ask_size': second_best_ask_size,
        'top_ask': top_ask,
        'bid_sum_within_n_percent': bid_sum_within_n_percent,
        'ask_sum_within_n_percent': ask_sum_within_n_percent
    }


def find_best_price_with_size(price_dict, min_size, reverse=False):
    lst = list(price_dict.items())

    if reverse:
        lst.reverse()
    
    best_price, best_size = None, None
    second_best_price, second_best_size = None, None
    top_price = None
    set_best = False

    for price, size in lst:
        if top_price is None:
            top_price = price

        if set_best:
            second_best_price, second_best_size = price, size
            break

        if size > min_size:
            if best_price is None:
                best_price, best_size = price, size
                set_best = True

    return best_price, best_size, second_best_price, second_best_size, top_price

def get_reward_optimized_price(mid_price, max_spread, tick_size, side='buy'):
    """
    Calculate the price that optimizes Polymarket maker rewards.

    Polymarket's reward formula: S = ((v - s) / v)^2
    Where:
        v = max_spread / 100 (maximum spread in decimal form)
        s = |price - mid_price| (distance from mid price)

    The reward is maximized when the price is placed at an optimal distance
    from the mid price, balancing reward rate with fill probability.

    Args:
        mid_price (float): Current mid-market price
        max_spread (float): Maximum spread percentage for rewards (e.g., 5 for 5%)
        tick_size (float): Minimum price increment
        side (str): 'buy' or 'sell'

    Returns:
        float: Optimal price rounded to tick_size
    """
    v = max_spread / 100  # Convert to decimal

    # Optimal distance is approximately 15% of max spread
    # More aggressive to stay competitive and get faster fills
    optimal_distance = v * 0.15

    if side == 'buy':
        optimal_price = mid_price - optimal_distance
    else:  # sell
        optimal_price = mid_price + optimal_distance

    # Round to tick size
    if optimal_price > 0:
        optimal_price = round(optimal_price / tick_size) * tick_size
        optimal_price = round(optimal_price, len(str(tick_size).split('.')[1]) if '.' in str(tick_size) else 0)

    return optimal_price


def get_order_prices(best_bid, best_bid_size, top_bid, best_ask, best_ask_size, top_ask, avgPrice, row):
    """
    Calculate optimal bid and ask prices considering:
    1. Current order book state
    2. Polymarket reward optimization
    3. Market liquidity
    4. Order Flow Imbalance (OFI) adaptive spread
    """

    # Calculate mid price for reward optimization
    mid_price = (top_bid + top_ask) / 2

    # Compute Order Flow Imbalance (OFI) from queue depth
    total_depth = best_bid_size + best_ask_size
    imbalance = (best_bid_size - best_ask_size) / total_depth if total_depth > 0 else 0

    # Determine alpha multipliers based on imbalance direction
    alpha_bid = OFI_ALPHA_WIDE if imbalance < -OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    alpha_ask = OFI_ALPHA_WIDE if imbalance > OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL

    # Calculate adaptive optimal distances (base 0.12 multiplier from research)
    v = row['max_spread'] / 100
    bid_optimal_distance = v * 0.12 * alpha_bid
    ask_optimal_distance = v * 0.12 * alpha_ask

    # Compute reward-optimized prices with adaptive spread
    reward_bid = round_to_tick(mid_price - bid_optimal_distance, row['tick_size'])
    reward_ask = round_to_tick(mid_price + ask_optimal_distance, row['tick_size'])

    # Start with competitive prices (just inside best bid/ask)
    bid_price = best_bid + row['tick_size']
    ask_price = best_ask - row['tick_size']

    # If liquidity is low, match the best price
    if best_bid_size < row['min_size'] * 1.5:
        bid_price = best_bid

    if best_ask_size < 250 * 1.5:
        ask_price = best_ask

    # Blend reward-optimized price with competitive price
    # Weight towards reward price if we're already competitive
    if bid_price < reward_bid:
        # We can move closer to reward-optimized price
        bid_price = max(bid_price, reward_bid - row['tick_size'])

    if ask_price > reward_ask:
        # We can move closer to reward-optimized price
        ask_price = min(ask_price, reward_ask + row['tick_size'])

    # Sanity checks: don't cross the spread
    if bid_price >= top_ask:
        bid_price = top_bid

    if ask_price <= top_bid:
        ask_price = top_ask

    if bid_price == ask_price:
        bid_price = top_bid
        ask_price = top_ask

    # Ensure sell price is above average cost
    if ask_price <= avgPrice and avgPrice > 0:
        ask_price = avgPrice

    return bid_price, ask_price



def round_to_tick(price, tick_size):
    """
    Round price to nearest tick size.

    Args:
        price (float): Price to round
        tick_size (float): Minimum price increment

    Returns:
        float: Price rounded to tick_size
    """
    rounded = round(price / tick_size) * tick_size
    decimals = len(str(tick_size).split('.')[1]) if '.' in str(tick_size) else 0
    return round(rounded, decimals)


def round_down(number, decimals):
    factor = 10 ** decimals
    return math.floor(number * factor) / factor

def round_up(number, decimals):
    factor = 10 ** decimals
    return math.ceil(number * factor) / factor

def dynamic_max_size(base_size, volatility, reward, spread):
    # Scale inverse to volatility, direct to reward/spread ratio
    kelly_scalar = (reward / (spread + 0.01)) / (volatility + 1)
    # Cap the multiplier between 0.5x and 2.0x of base size
    multiplier = min(max(kelly_scalar, 0.5), 2.0)
    return int(base_size * multiplier)

def get_buy_sell_amount(position, bid_price, row, max_size, other_token_position=0):
    import os
    buy_amount = 0
    sell_amount = 0

    base_max = row.get('max_size', row.get('trade_size', 50))
    # Using the passed-in max_size instead of recalculating
    # This avoids M2 (double counting)
    # Scale trade_size proportionally based on the provided max_size vs base_max
    
    # Scale trade_size proportionally
    trade_size = int(row.get('trade_size', 25) * (max_size / base_max)) if base_max > 0 else row.get('trade_size', 25)
    if trade_size < row.get('min_size', 5):
        trade_size = row.get('min_size', 5)
    
    # Check if two-sided market making mode is enabled
    TWO_SIDED_MARKET_MAKING = os.getenv('TWO_SIDED_MARKET_MAKING', 'false').lower() == 'true'
    
    # Calculate total exposure across both sides
    total_exposure = position + other_token_position
    
    # If we haven't reached max_size on either side, continue building
    if position < max_size:
        # Continue quoting trade_size amounts until we reach max_size
        remaining_to_max = max_size - position
        buy_amount = min(trade_size, remaining_to_max)
        
        # TWO-SIDED MARKET MAKING MODE: Place sell orders even without position
        if TWO_SIDED_MARKET_MAKING:
            # For true market making, always quote both sides
            # Sell amount = trade_size (even if position = 0, for market making liquidity)
            sell_amount = trade_size
        else:
            # ORIGINAL BEHAVIOR: Only sell if we have substantial position (to allow for exit when needed)
            if position >= trade_size:
                sell_amount = min(position, trade_size)
            else:
                sell_amount = 0
    else:
        # We've reached max_size, implement progressive exit strategy
        # Always offer to sell trade_size amount when at max_size
        sell_amount = min(position, trade_size)
        
        # Continue quoting to buy if total exposure warrants it
        if total_exposure < max_size * 2:  # Allow some flexibility for market making
            buy_amount = trade_size
        else:
            buy_amount = 0

    # Ensure minimum order size compliance
    if buy_amount > 0.7 * row['min_size'] and buy_amount < row['min_size']:
        buy_amount = row['min_size']

    # Apply multiplier for low-priced assets
    if bid_price < 0.1 and buy_amount > 0:
        multiplier = row.get('multiplier', '')
        if multiplier != '' and multiplier is not None:
            try:
                print(f"Multiplying buy amount by {int(multiplier)}")
                buy_amount = buy_amount * int(multiplier)
            except (ValueError, TypeError):
                pass  # Skip if multiplier is invalid

    return buy_amount, sell_amount

