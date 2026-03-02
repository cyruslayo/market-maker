import threading
from copy import deepcopy
import pandas as pd

# ============ Market Data ============

# List of all tokens being tracked
all_tokens = []

# Set of token IDs that are actively subscribed for trading
subscribed_assets = set()

# Mapping between tokens in the same market (YES->NO, NO->YES)
REVERSE_TOKENS = {}  

# Order book data for all markets
all_data = {}  

# Market configuration data from Google Sheets
df = None  

# ============ Client & Parameters ============

# Polymarket client instance
client = None

# Trading parameters from Google Sheets
params = {}

# Lock for thread-safe trading operations
lock = threading.Lock()

# Lock for thread-safe shared state transitions
_state_lock = threading.Lock()

# ============ Trading State ============

# Tracks trades that have been matched but not yet mined
# Format: {"token_side": {trade_id1, trade_id2, ...}}
performing = {}

# Timestamps for when trades were added to performing
# Used to clear stale trades
performing_timestamps = {}

# Timestamps for when positions were last updated
last_trade_update = {}

# Timestamps for when perform_trade was last called for each market
# Used to rate-limit trading actions and reduce order churn
last_trade_action_time = {}

# Current open orders for each token
# Format: {token_id: {'buy': {price, size}, 'sell': {price, size}}}
orders = {}

# Current positions for each token
# Format: {token_id: {'size': float, 'avgPrice': float}}
positions = {}

# Track if trading is halted by circuit breaker
trade_halt = False


def get_state_snapshot():
    """Return an immutable snapshot used by read-side trading logic."""
    with _state_lock:
        return {
            'positions': deepcopy(positions),
            'orders': deepcopy(orders),
            'last_trade_action_time': deepcopy(last_trade_action_time),
        }


def get_position_atomic(token_id):
    """Thread-safe position read with default shape."""
    token_id = str(token_id)
    with _state_lock:
        position = positions.get(token_id, {'size': 0, 'avgPrice': 0})
        return deepcopy(position)


def has_position_atomic(token_id) -> bool:
    """Thread-safe existence check for position keys."""
    token_id = str(token_id)
    with _state_lock:
        return token_id in positions


def update_positions_atomic(new_positions: dict):
    """Thread-safe partial position updates."""
    with _state_lock:
        positions.update(new_positions)


def replace_positions_atomic(new_positions: dict):
    """Thread-safe full replacement of the positions map."""
    global positions
    with _state_lock:
        positions = deepcopy(new_positions)


def get_orders_snapshot_atomic():
    """Thread-safe full orders snapshot."""
    with _state_lock:
        return deepcopy(orders)


def update_orders_atomic(new_orders: dict):
    """Thread-safe partial order updates."""
    with _state_lock:
        orders.update(new_orders)


def replace_orders_atomic(new_orders: dict):
    """Thread-safe full replacement of the orders map."""
    global orders
    with _state_lock:
        orders = deepcopy(new_orders)


def get_last_trade_action_time_atomic(token_id: str) -> float:
    """Thread-safe read of cooldown timestamps."""
    with _state_lock:
        return last_trade_action_time.get(token_id, 0.0)


def set_last_trade_action_time_atomic(token_id: str, timestamp: float):
    """Thread-safe write of cooldown timestamps."""
    with _state_lock:
        last_trade_action_time[token_id] = timestamp

