import asyncio
import json
import websockets
import traceback
import ssl
import certifi
import logging

from poly_data.data_processing import process_data, process_user_data
import poly_data.global_state as global_state

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('websocket_handlers.log')
    ]
)
logger = logging.getLogger(__name__)

async def connect_market_websocket(chunk, max_retries=5, retry_delay=5):
    """
    Connect to Polymarket's market WebSocket API and process market updates.

    Args:
        chunk (list): List of token IDs to subscribe to
        max_retries (int): Maximum reconnection attempts
        retry_delay (int): Delay between reconnection attempts in seconds
    """
    uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(cafile=certifi.where())

    for attempt in range(max_retries):
        try:
            async with websockets.connect(uri, ping_interval=5, ping_timeout=None, ssl=ssl_context) as websocket:
                # Skip subscription if chunk is empty
                if not chunk:
                    logger.info("No tokens to subscribe to, maintaining WebSocket connection without subscription.")
                    try:
                        while True:
                            message = await websocket.recv()
                            try:
                                json_data = json.loads(message)
                                logger.debug(f"Received market WebSocket message: {json_data}")
                                # Wrap single dictionary in a list for process_data
                                if isinstance(json_data, dict):
                                    await process_data([json_data])
                                else:
                                    await process_data(json_data)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse market WebSocket message: {message}. Error: {e}")
                    except websockets.ConnectionClosed as e:
                        logger.warning(f"Market WebSocket closed: {e}")
                        logger.debug(traceback.format_exc())
                    return

                # Prepare and send subscription message
                message = {"assets_ids": chunk}
                await websocket.send(json.dumps(message))
                logger.info(f"Sent market subscription message: {message}")

                try:
                    # Process incoming market data indefinitely
                    while True:
                        message = await websocket.recv()
                        try:
                            json_data = json.loads(message)
                            logger.debug(f"Received market WebSocket message: {json_data}")
                            # Filter out unsubscribed markets
                            if isinstance(json_data, dict) and 'market' in json_data:
                                if json_data['market'] not in chunk:
                                    logger.warning(f"Ignoring data for unsubscribed market: {json_data['market']}")
                                    continue
                                
                                # ====== PAPER TRADING ENGINE HOOK ======
                                if hasattr(global_state.client, 'matching_engine'):
                                    try:
                                        m_id = json_data['market']
                                        b_bid = None
                                        b_ask = None
                                        l_trade = None
                                        
                                        # Process new price_changes
                                        changes = json_data.get('price_changes') or json_data.get('changes', [])
                                        for data in changes:
                                            price = float(data['price'])
                                            if data['side'] == 'BUY':
                                                if b_bid is None or price > b_bid:
                                                    b_bid = price
                                            else:
                                                if b_ask is None or price < b_ask:
                                                    b_ask = price
                                                    
                                        if b_bid is not None or b_ask is not None:
                                            global_state.client.matching_engine.process_market_update(
                                                market_id=m_id, best_bid=b_bid, best_ask=b_ask, last_trade_price=l_trade
                                            )
                                    except Exception as e:
                                        logger.error(f"Paper Trading Engine Hook failed: {e}")
                                # =======================================

                            # Wrap single dictionary in a list for process_data
                            if isinstance(json_data, dict):
                                await process_data([json_data])
                            else:
                                await process_data(json_data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse market WebSocket message: {message}. Error: {e}")
                        except Exception as e:
                            logger.error(f"Error processing market WebSocket message: {e}")
                            logger.debug(traceback.format_exc())
                except websockets.ConnectionClosed as e:
                    logger.warning(f"Market WebSocket closed: {e}")
                    logger.debug(traceback.format_exc())

        except Exception as e:
            logger.error(f"Exception in market WebSocket (attempt {attempt + 1}/{max_retries}): {e}")
            logger.debug(traceback.format_exc())
            if attempt < max_retries - 1:
                logger.info(f"Retrying market WebSocket connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Max retries reached for market WebSocket. Giving up.")
                break

async def connect_user_websocket(max_retries=5, retry_delay=5):
    """
    Connect to Polymarket's user WebSocket API and process order/trade updates.

    Args:
        max_retries (int): Maximum reconnection attempts
        retry_delay (int): Delay between reconnection attempts in seconds
    """
    uri = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(cafile=certifi.where())

    for attempt in range(max_retries):
        try:
            async with websockets.connect(uri, ping_interval=5, ping_timeout=None, ssl=ssl_context) as websocket:
                # Validate credentials exist before attempting authentication
                try:
                    api_key = global_state.client.client.creds.api_key
                    api_secret = global_state.client.client.creds.api_secret
                    api_passphrase = global_state.client.client.creds.api_passphrase
                except AttributeError as e:
                    logger.error(f"API credentials not initialized properly: {e}")
                    raise RuntimeError("Cannot connect to user WebSocket - credentials missing")

                # Prepare authentication message with API credentials
                message = {
                    "type": "user",
                    "auth": {
                        "apiKey": api_key,
                        "secret": api_secret,
                        "passphrase": api_passphrase
                    }
                }

                # Send authentication message
                await websocket.send(json.dumps(message))
                logger.info("Sent user WebSocket authentication message")

                try:
                    # Process incoming user data indefinitely
                    while True:
                        message = await websocket.recv()
                        try:
                            json_data = json.loads(message)
                            logger.debug(f"Received user WebSocket message: {json_data}")

                            # Check for authentication errors
                            if isinstance(json_data, dict):
                                if json_data.get('type') == 'error' or 'error' in json_data:
                                    error_msg = json_data.get('message', json_data.get('error', 'Unknown error'))
                                    logger.error(f"❌ User WebSocket authentication error: {error_msg}")
                                    if 'auth' in error_msg.lower() or 'credential' in error_msg.lower():
                                        raise RuntimeError(f"Authentication failed: {error_msg}")
                                elif json_data.get('type') == 'authenticated' or json_data.get('channel') == 'user':
                                    logger.info("✓ User WebSocket authenticated successfully")

                            await process_user_data(json_data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse user WebSocket message: {message}. Error: {e}")
                except websockets.ConnectionClosed as e:
                    logger.warning(f"User WebSocket closed: {e}")
                    logger.debug(traceback.format_exc())

        except Exception as e:
            logger.error(f"Exception in user WebSocket (attempt {attempt + 1}/{max_retries}): {e}")
            logger.debug(traceback.format_exc())
            if attempt < max_retries - 1:
                logger.info(f"Retrying user WebSocket connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("Max retries reached for user WebSocket. Giving up.")
                break