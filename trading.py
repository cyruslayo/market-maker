import gc                       # Garbage collection
import os                       # Operating system interface
import json                     # JSON handling
import asyncio                  # Asynchronous I/O
import traceback                # Exception handling
import pandas as pd             # Data analysis library
import math                     # Mathematical functions
from datetime import datetime   # Date and time handling

import poly_data.global_state as global_state
import poly_data.CONSTANTS as CONSTANTS

# Import utility functions for trading
from poly_data.trading_utils import get_best_bid_ask_deets, get_order_prices, get_buy_sell_amount, round_down, round_up, dynamic_max_size
from poly_data.data_utils import set_position
from poly_data.trade_logger import log_trade_to_sheets
from poly_data.reward_tracker import log_market_snapshot

# Create directory for storing position risk information
if not os.path.exists('positions/'):
    os.makedirs('positions/')

def send_buy_order(order):
    """
    Create a BUY order for a specific token.
    
    This function:
    1. Cancels any existing orders for the token only if needed
    2. Checks if the order price is within acceptable range
    3. Creates a new buy order if conditions are met
    
    Args:
        order (dict): Order details including token, price, size, and market parameters
    """
    client = global_state.client

    # Only cancel existing orders if we need to make significant changes
    existing_buy_size = order['orders']['buy']['size']
    existing_buy_price = order['orders']['buy']['price']
    existing_sell_size = order['orders']['sell']['size']
    
    # Cancel orders if price changed significantly or size needs major adjustment
    price_diff = abs(existing_buy_price - order['price']) if existing_buy_price > 0 else 0
    size_diff = abs(existing_buy_size - order['size']) if existing_buy_size > 0 else 0

    # FIX 1: Don't cancel if there's no existing order (prevents "inf" price_diff cancellations)
    # FIX 2: Only cancel if there's actually an order that needs updating
    should_cancel = False
    if existing_buy_size > 0:  # Only check if order actually exists
        should_cancel = (
            price_diff > 0.015 or  # Cancel if price diff > 1.5 cents
            size_diff > order['size'] * 0.25  # Cancel if size diff > 25%
        )
    
    # FIX 3: Only cancel if we have orders to cancel (buy or sell)
    # Note: API limitation - can't cancel only buy orders, must cancel all for asset
    # But we only cancel if we actually need to update buy order
    if should_cancel and (existing_buy_size > 0 or existing_sell_size > 0):
        print(f"Cancelling orders (updating buy) - price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
        client.cancel_all_asset(order['token'])
    elif existing_buy_size > 0 and not should_cancel:
        print(f"Keeping existing buy orders - minor changes: price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
        return  # Don't place new order if existing one is fine
    # If no existing buy order, just place new one (no cancellation needed)

    # Calculate minimum acceptable price based on market spread
    incentive_start = order['mid_price'] - order['max_spread']/100

    trade = True

    # Don't place orders that are below incentive threshold
    if order['price'] < incentive_start:
        trade = False

    if trade:
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        if order['price'] >= 0.1 and order['price'] < 0.9:
            print(f'Creating new order for {order["size"]} at {order["price"]}')
            print(order['token'], 'BUY', order['price'], order['size'])

            # Get position before trade
            position_before = order['position']

            # Place order
            result = client.create_order(
                order['token'],
                'BUY',
                order['price'],
                order['size'],
                True if order['neg_risk'] == 'TRUE' else False
            )

            # Log trade to Google Sheets
            try:
                log_trade_to_sheets({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': 'BUY',
                    'market': order.get('question', 'Unknown'),
                    'price': order['price'],
                    'size': order['size'],
                    'order_id': result.get('orderID', 'N/A') if result else 'FAILED',
                    'status': 'PLACED' if result else 'FAILED',
                    'token_id': order['token'],
                    'neg_risk': order['neg_risk'] == 'TRUE',
                    'position_before': position_before,
                    'position_after': position_before,  # Will update when filled
                    'notes': f"Mid: ${order['mid_price']:.4f}, Spread: {order['max_spread']:.1f}%"
                })
            except Exception as e:
                print(f"⚠️  Trade logging failed: {e}")
        else:
            print("Not creating buy order because its outside acceptable price range (0.1-0.9)")
    else:
        print(f'Not creating new order because order price of {order["price"]} is less than incentive start price of {incentive_start}. Mid price is {order["mid_price"]}')


def send_sell_order(order):
    """
    Create a SELL order for a specific token.
    
    This function:
    1. Cancels any existing orders for the token only if needed
    2. Creates a new sell order with the specified parameters
    
    Args:
        order (dict): Order details including token, price, size, and market parameters
    """
    client = global_state.client

    # Only cancel existing orders if we need to make significant changes
    existing_sell_size = order['orders']['sell']['size']
    existing_sell_price = order['orders']['sell']['price']
    existing_buy_size = order['orders']['buy']['size']

    # FIX 4: Wider threshold for sell orders (hedging orders should be more stable)
    # Use 5 cents instead of 1.5 cents for sell orders
    SELL_PRICE_THRESHOLD = 0.05  # 5 cents for sell orders (hedging)
    SELL_SIZE_THRESHOLD = 0.30   # 30% for sell orders (more lenient)
    
    # Cancel orders if price changed significantly or size needs major adjustment
    price_diff = abs(existing_sell_price - order['price']) if existing_sell_price > 0 else 0
    size_diff = abs(existing_sell_size - order['size']) if existing_sell_size > 0 else 0

    # FIX 1: Don't cancel if there's no existing order
    # FIX 2: Use wider thresholds for sell orders (hedging should be stable)
    should_cancel = False
    if existing_sell_size > 0:  # Only check if order actually exists
        should_cancel = (
            price_diff > SELL_PRICE_THRESHOLD or  # 5 cents for sell orders (wider tolerance)
            size_diff > order['size'] * SELL_SIZE_THRESHOLD  # 30% for sell orders
        )
    
    # FIX 3: Only cancel if we have orders to cancel
    # Note: API limitation - can't cancel only sell orders, must cancel all for asset
    # But we only cancel if we actually need to update sell order
    if should_cancel and (existing_sell_size > 0 or existing_buy_size > 0):
        print(f"Cancelling orders (updating sell) - price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
        client.cancel_all_asset(order['token'])
    elif existing_sell_size > 0 and not should_cancel:
        print(f"Keeping existing sell orders - minor changes: price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
        return  # Don't place new order if existing one is fine
    # If no existing sell order, just place new one (no cancellation needed)

    print(f'Creating new order for {order["size"]} at {order["price"]}')

    # Get position before trade
    position_before = order['position']

    # Place order
    result = client.create_order(
        order['token'],
        'SELL',
        order['price'],
        order['size'],
        True if order['neg_risk'] == 'TRUE' else False
    )

    # Log trade to Google Sheets
    try:
        log_trade_to_sheets({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': 'SELL',
            'market': order.get('question', 'Unknown'),
            'price': order['price'],
            'size': order['size'],
            'order_id': result.get('orderID', 'N/A') if result else 'FAILED',
            'status': 'PLACED' if result else 'FAILED',
            'token_id': order['token'],
            'neg_risk': order['neg_risk'] == 'TRUE',
            'position_before': position_before,
            'position_after': position_before,  # Will update when filled
            'notes': f"Mid: ${order.get('mid_price', 0):.4f}, Avg Price: ${order.get('avgPrice', 0):.4f}"
        })
    except Exception as e:
        print(f"⚠️  Trade logging failed: {e}")

# Dictionary to store locks for each market to prevent concurrent trading on the same market
market_locks = {}

async def perform_trade(market):
    """
    Main trading function that handles market making for a specific market.

    This function:
    1. Merges positions when possible to free up capital
    2. Analyzes the market to determine optimal bid/ask prices
    3. Manages buy and sell orders based on position size and market conditions
    4. Implements risk management with stop-loss and take-profit logic

    Args:
        market (str): The market ID count (condition_id) to trade on
    """
    # Fix H1: Enforce circuit breaker globally
    if getattr(global_state, 'trade_halt', False):
        return

    # Create a lock for this market if it doesn't exist
    if market not in market_locks:
        market_locks[market] = asyncio.Lock()

    # Use lock to prevent concurrent trading on the same market
    async with market_locks[market]:
        try:
            client = global_state.client
            state = global_state.get_state_snapshot()

            def get_position_from_state(token_id):
                token_id = str(token_id)
                return state['positions'].get(token_id, {'size': 0, 'avgPrice': 0})

            def get_order_from_state(token_id):
                token_id = str(token_id)
                order = state['orders'].get(token_id, {'buy': {'price': 0, 'size': 0}, 'sell': {'price': 0, 'size': 0}})
                if 'buy' not in order:
                    order['buy'] = {'price': 0, 'size': 0}
                if 'sell' not in order:
                    order['sell'] = {'price': 0, 'size': 0}
                return order

            # Get market details from the configuration
            row = global_state.df[global_state.df['condition_id'] == market].iloc[0]      
            # Determine decimal precision from tick size (safe against None/int tick sizes)
            try:
                tick_str = str(float(row['tick_size']))
                round_length = len(tick_str.split(".")[1]) if "." in tick_str else 2
            except Exception:
                round_length = 2  # fallback: 2 decimal places

            # Get trading parameters for this market type
            PARAM_DEFAULTS = {
                'spread': 0.05, 'max_size': 1000.0, 'trade_size': 100.0, 'min_size': 5.0,
                'volatility_threshold': 0.5, 'take_profit_threshold': 2.0, 'sleep_period': 4.0,
            }
            param_type = row.get('param_type', 'default')
            params = global_state.params.get(param_type) or global_state.params.get('default') or {}
            # Merge with defaults so any missing key always has a safe value
            params = {**PARAM_DEFAULTS, **params}
            
            # Create a list with both outcomes for the market
            deets = [
                {'name': 'token1', 'token': row['token1'], 'answer': row['answer1']}, 
                {'name': 'token2', 'token': row['token2'], 'answer': row['answer2']}
            ]

            print(f"\n\n{pd.Timestamp.utcnow().tz_localize(None)}: {row['question']}")

            # ------- POSITION MERGING LOGIC -------
            pos_1 = get_position_from_state(row['token1'])['size']
            pos_2 = get_position_from_state(row['token2'])['size']
            amount_to_merge = min(pos_1, pos_2)
            
            if float(amount_to_merge) > CONSTANTS.MIN_MERGE_SIZE:
                pos_1_act = client.get_position(row['token1'])[0]
                pos_2_act = client.get_position(row['token2'])[0]
                amount_to_merge_act = min(pos_1_act, pos_2_act)
                scaled_amt = amount_to_merge_act / 10**6
                
                if scaled_amt > CONSTANTS.MIN_MERGE_SIZE:
                    print(f"Merging {scaled_amt:.2f} positions")
                    asyncio.create_task(client.merge_positions(scaled_amt, market, row['neg_risk'] == 'TRUE'))
                    set_position(row['token1'], 'SELL', scaled_amt, 0, 'merge')
                    set_position(row['token2'], 'SELL', scaled_amt, 0, 'merge')
                    state = global_state.get_state_snapshot()

            AGGRESSIVE_MODE = os.getenv('AGGRESSIVE_MODE', 'false').lower() == 'true'

            # ------- TRADING LOGIC FOR EACH OUTCOME -------
            for detail in deets:
                token = int(detail['token'])
                orders = get_order_from_state(token)

                # Market Depth
                # Bug 1 fix: all_data is keyed by individual token IDs, not condition_id.
                # Pass the specific token for this outcome side so the book lookup hits the right key.
                book_deets = get_best_bid_ask_deets(str(token), detail['name'], 100, 0.1)
                if book_deets['best_bid'] is None:
                    book_deets = get_best_bid_ask_deets(str(token), detail['name'], 20, 0.1)
                
                best_bid = round(book_deets['best_bid'], round_length) if book_deets['best_bid'] else 0
                best_ask = round(book_deets['best_ask'], round_length) if book_deets['best_ask'] else 0
                top_bid = round(book_deets['top_bid'], round_length) if book_deets['top_bid'] else 0
                top_ask = round(book_deets['top_ask'], round_length) if book_deets['top_ask'] else 0
                
                try:
                    overall_ratio = (book_deets['bid_sum_within_n_percent']) / (book_deets['ask_sum_within_n_percent'])
                except:
                    overall_ratio = 0

                # Positions
                pos_state = get_position_from_state(token)
                position = pos_state['size']
                avgPrice = pos_state['avgPrice']
                
                if position > 0 and avgPrice == 0:
                    from poly_data.data_utils import update_positions
                    update_positions(avgOnly=False)
                    state = global_state.get_state_snapshot()
                    pos_state = get_position_from_state(token)
                    position = pos_state['size']
                    avgPrice = pos_state['avgPrice']
                
                position = round_down(position, 2)
                
                # Prices
                bid_price, ask_price = get_order_prices(
                    best_bid, book_deets['best_bid_size'], top_bid, 
                    best_ask, book_deets['best_ask_size'], top_ask, avgPrice, row
                )

                # Fix H2 / M2: Shared and persistent Dynamic sizing
                base_max = row.get('max_size', row.get('trade_size', 50))
                volatility = row.get('volatility_sum', 1)
                reward = row.get('gm_reward_per_100', 0)
                spread_val = row.get('spread', 0.05) if row.get('spread', 0) > 0 else 0.05
                max_size = dynamic_max_size(base_max, volatility, reward, spread_val)
                
                # Fix M1: Refined Inventory Skew (more aggressive exit)
                if position > 0 and max_size > 0:
                    inventory_ratio = position / max_size
                    if inventory_ratio > 0.4:
                        bid_skew = int((inventory_ratio - 0.4) * 6) * row['tick_size']
                        ask_skew = int((inventory_ratio - 0.4) * 8) * row['tick_size']
                        bid_price -= bid_skew
                        ask_price -= ask_skew
                        print(f"Inventory Skew ({detail['name']}): Bid -{bid_skew:.4f}, Ask -{ask_skew:.4f}")

                bid_price = round(bid_price, round_length)
                ask_price = round(ask_price, round_length)
                mid_price = (top_bid + top_ask) / 2
                
                other_token = int(global_state.REVERSE_TOKENS[str(token)])
                other_position = get_position_from_state(other_token)['size']
                
                # Fix M2: Pass max_size to avoid double calc
                buy_amount, sell_amount = get_buy_sell_amount(position, bid_price, row, max_size, other_position)

                # Setup common order info
                order = {
                    "token": token,
                    "mid_price": mid_price,
                    "neg_risk": row['neg_risk'],
                    "max_spread": row['max_spread'],
                    "position": position,
                    'orders': orders,
                    'token_name': detail['name'],
                    'row': row,
                    'avgPrice': avgPrice,
                    'question': row['question']
                }
                
                fname = 'positions/' + str(market) + '.json'

                # ========== AGGRESSIVE MODE BYPASS ==========
                if AGGRESSIVE_MODE:
                    print(f"🔥🔥🔥 AGGRESSIVE MODE: {detail['answer']} 🔥🔥🔥")
                    # Simplified aggressive placement without safety blocks
                    if sell_amount > 0 and avgPrice > 0:
                        tp_price = round_up(avgPrice + (avgPrice * params['take_profit_threshold']/100), round_length)
                        order['price'] = tp_price
                        order['size'] = sell_amount
                        send_sell_order(order)
                    if buy_amount >= row['min_size'] and position < max_size:
                        order['price'] = round_down(bid_price, round_length)
                        order['size'] = buy_amount
                        send_buy_order(order)
                    continue

                # ------- SELL / RISK MGMT LOGIC -------
                TWO_SIDED = os.getenv('TWO_SIDED_MARKET_MAKING', 'false').lower() == 'true'
                if sell_amount > 0 and (avgPrice > 0 or TWO_SIDED):
                    order['size'] = sell_amount
                    order['price'] = ask_price
                    
                    # Risk Assessment
                    n_deets = get_best_bid_ask_deets(market, detail['name'], 100, 0.1)
                    curr_mid = (n_deets['best_bid'] + n_deets['best_ask']) / 2 if n_deets['best_bid'] else mid_price
                    curr_spread = (n_deets['best_ask'] - n_deets['best_bid']) if n_deets['best_bid'] else 0.05
                    loss_abs = avgPrice - curr_mid
                    
                    tier = 0
                    if avgPrice > 0 and loss_abs > 0:
                        if loss_abs > curr_spread * 2.0: tier = 3
                        elif loss_abs > curr_spread * 1.0: tier = 2
                        elif loss_abs > curr_spread * 0.5: tier = 1
                    
                    # Fix M3: Graduated Response
                    adaptive_vol = params['volatility_threshold'] + (row.get('rewards_daily_rate', 0) / 100) * 5
                    if tier > 0 or (row.get('3_hour', 0) > adaptive_vol):
                        risk_details = {'time': str(pd.Timestamp.utcnow()), 'question': row['question']}
                        if tier == 1:
                            order['size'] = sell_amount * 0.5
                            risk_details['msg'] = f"Reducing size (Tier 1 stop) Loss: {loss_abs:.4f}"
                        elif tier == 2:
                            risk_details['msg'] = f"Selling full (Tier 2 stop) Loss: {loss_abs:.4f}"
                        else:
                            risk_details['msg'] = f"Emergency Exit (Tier 3 stop) Loss: {loss_abs:.4f}"
                        
                        # Slippage Guard (Tier 3)
                        if tier == 3 and (n_deets['best_bid'] < curr_mid * 0.95):
                            order['price'] = max(curr_mid * 0.95, 0.01)
                            print("Slippage Guard active!")
                        else:
                            order['price'] = max(n_deets['best_bid'], 0.01) if n_deets['best_bid'] else ask_price

                        print(f"Risk Triggered: {risk_details['msg']}")
                        send_sell_order(order)
                        
                        if tier >= 2:
                            client.cancel_all_asset(token)
                            sleep_hrs = params['sleep_period']
                            risk_details['sleep_till'] = str(pd.Timestamp.utcnow() + pd.Timedelta(hours=sleep_hrs))
                            open(fname, 'w').write(json.dumps(risk_details))
                            continue
                    
                    # Normal Take Profit logic
                    tp_price = round_up(avgPrice + (avgPrice * params['take_profit_threshold']/100), round_length)
                    if avgPrice > 0: order['price'] = tp_price
                    
                    if orders['sell']['size'] == 0:
                        send_sell_order(order)
                    else:
                        price_diff = abs(orders['sell']['price'] - float(order['price'])) / float(order['price']) * 100 if order['price'] > 0 else 0
                        if price_diff > 2 or orders['sell']['size'] < position * 0.97:
                            send_sell_order(order)

                # ------- BUY LOGIC -------
                # Fix H2: Already use max_size from top
                reward_ok = True
                gm_reward = float(row.get('gm_reward_per_100', 0) or 0)
                if gm_reward > 0 and gm_reward < 0.5: reward_ok = False
                
                if position < max_size and buy_amount >= row['min_size'] and reward_ok:
                    can_buy = True
                    if os.path.exists(fname):
                        r_data = json.load(open(fname))
                        if pd.Timestamp.utcnow() < pd.to_datetime(r_data.get('sleep_till', '2000-01-01')):
                            can_buy = False
                    
                    if can_buy:
                        # Bug 2 fix: 'best_bid' is a local var computed above — not a sheet column.
                        price_change = abs(bid_price - best_bid) if best_bid else 0
                        if row['3_hour'] > params['volatility_threshold'] * 2 or price_change > 0.15:
                            client.cancel_all_asset(token)
                        else:
                            rev_token = global_state.REVERSE_TOKENS[str(token)]
                            if get_position_from_state(rev_token)['size'] > row['min_size']:
                                print("Opposing position exists. Skipping buy.")
                                continue
                            
                            order['price'] = round_down(bid_price, round_length)
                            order['size'] = buy_amount
                            
                            if best_bid > orders['buy']['price'] or (position + orders['buy']['size'] < 0.95 * max_size):
                                send_buy_order(order)

            try:
                log_market_snapshot(market, row['question'])
            except: pass

        except Exception as e:
            print(f"Error in perform_trade for {market}: {e}")
            traceback.print_exc()

        gc.collect()
        await asyncio.sleep(2)