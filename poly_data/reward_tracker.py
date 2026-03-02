"""
Reward Tracker - Estimates and logs maker rewards for each market
"""

import time
from datetime import datetime
import poly_data.global_state as global_state
from poly_data.gspread import get_spreadsheet
import traceback

FEE_CURVE_PARAMS = {
    'crypto': {'exponent': 2, 'fee_rate': 0.25},
    'other':  {'exponent': 1, 'fee_rate': 0.0175},
}

_reward_worksheet = None
_reward_spreadsheet = None
_last_snapshot_time = {}


def estimate_order_reward(price, size, mid_price=None, max_spread=None, daily_rate=None, market_type='other'):
    """Estimate maker fee-equivalent reward using 2026 fee-curve weighted formula.
    
    Note: mid_price, max_spread, and daily_rate are deprecated and unused.
    They are kept for backwards compatibility with existing callers.
    """
    try:
        key = 'crypto' if 'crypto' in str(market_type).lower() else 'other'
        params = FEE_CURVE_PARAMS[key]
        exponent = params['exponent']
        fee_rate = params['fee_rate']

        p = price
        fee_equivalent = size * p * fee_rate * (p * (1 - p)) ** exponent
        return max(0.0, fee_equivalent)
    except Exception as e:
        print(f"Error calculating reward: {e}")
        return 0


def log_market_snapshot(market_id, market_name):
    """Log a snapshot of current orders and estimate rewards for a market."""
    global _reward_worksheet, _reward_spreadsheet, _last_snapshot_time

    try:
        current_time = time.time()
        last_snapshot = _last_snapshot_time.get(market_id, 0)
        if current_time - last_snapshot < 300:
            return
        _last_snapshot_time[market_id] = current_time

        if global_state.df is None:
            return

        market_row = global_state.df[global_state.df['condition_id'] == market_id]
        if market_row.empty:
            return
        market_row = market_row.iloc[0]

        if _reward_spreadsheet is None:
            _reward_spreadsheet = get_spreadsheet()
            if _reward_spreadsheet is None:
                # Silently fail if sheets are not configured (e.g. credentials missing)
                return

        if _reward_worksheet is None:
            try:
                _reward_worksheet = _reward_spreadsheet.worksheet('Maker Rewards')
            except:
                _reward_worksheet = _reward_spreadsheet.add_worksheet(
                    title='Maker Rewards', rows=10000, cols=15
                )
                headers = [
                    'Timestamp', 'Market', 'Token', 'Side', 'Open Orders',
                    'Order Price', 'Mid Price', 'Distance from Mid',
                    'Position Size', 'Est. Fee Equivalent', 'Daily Rate',
                    'Max Spread %', 'Status', 'Market Type'
                ]
                _reward_worksheet.update('A1', [headers])

        if market_id in global_state.all_data:
            bids = global_state.all_data[market_id]['bids']
            asks = global_state.all_data[market_id]['asks']
            if len(bids) > 0 and len(asks) > 0:
                best_bid = list(bids.keys())[-1]
                best_ask = list(asks.keys())[-1]
                mid_price = (best_bid + best_ask) / 2
            else:
                mid_price = 0.5
        else:
            mid_price = 0.5

        market_type = str(market_row.get('market_type', market_row.get('category', 'other')))
        # Warn if falling back to default - helps detect column name changes
        if 'market_type' not in market_row and 'category' not in market_row:
            print(f"Warning: No market_type or category column found for {market_name}, defaulting to 'other'")

        for token_name in ['token1', 'token2']:
            token_id = str(market_row[token_name])
            answer = market_row['answer1'] if token_name == 'token1' else market_row['answer2']
            orders = global_state.orders.get(token_id, {'buy': {'price': 0, 'size': 0}, 'sell': {'price': 0, 'size': 0}})
            position = global_state.positions.get(token_id, {'size': 0, 'avgPrice': 0})

            if orders['buy']['size'] > 0:
                buy_reward = estimate_order_reward(
                    orders['buy']['price'], orders['buy']['size'], mid_price,
                    market_row['max_spread'], market_row['rewards_daily_rate'],
                    market_type=market_type
                )
                # Convert all values to native Python types for JSON serialization
                row = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(market_name)[:80], str(answer)[:30], 'BUY', float(orders['buy']['size']),
                    float(orders['buy']['price']), float(mid_price),
                    float(abs(orders['buy']['price'] - mid_price)), float(position['size']),
                    float(round(buy_reward, 4)), float(market_row['rewards_daily_rate']),
                    float(market_row['max_spread']), 'Active', str(market_type)
                ]
                _reward_worksheet.append_row(row, value_input_option='USER_ENTERED')

            if orders['sell']['size'] > 0:
                sell_reward = estimate_order_reward(
                    orders['sell']['price'], orders['sell']['size'], mid_price,
                    market_row['max_spread'], market_row['rewards_daily_rate'],
                    market_type=market_type
                )
                # Convert all values to native Python types for JSON serialization
                row = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(market_name)[:80], str(answer)[:30], 'SELL', float(orders['sell']['size']),
                    float(orders['sell']['price']), float(mid_price),
                    float(abs(orders['sell']['price'] - mid_price)), float(position['size']),
                    float(round(sell_reward, 4)), float(market_row['rewards_daily_rate']),
                    float(market_row['max_spread']), 'Active', str(market_type)
                ]
                _reward_worksheet.append_row(row, value_input_option='USER_ENTERED')

        print(f"Logged reward snapshot for {market_name[:50]}...")
        return True

    except Exception as e:
        print(f"Failed to log reward snapshot: {e}")
        traceback.print_exc()
        return False


def reset_reward_cache():
    """Reset the cached worksheet"""
    global _reward_worksheet, _reward_spreadsheet
    _reward_worksheet = None
    _reward_spreadsheet = None
