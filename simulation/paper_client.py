import os
import asyncio
import logging
import random
import time
import uuid
import pandas as pd
from poly_data.polymarket_client import PolymarketClient

logger = logging.getLogger(__name__)

class PaperTradingClient:
    """
    PaperTradingClient wraps PolymarketClient.
    Reads (e.g., get_order_book) go to the live API.
    Writes (e.g., create_order, merge_positions) are intercepted and 
    forwarded to the LiveMatchingEngine after a simulated execution latency.
    Positions and balances are sourced completely from the local LiveMatchingEngine.
    """
    def __init__(self, matching_engine, pk='default'):
        logger.info("Initializing PaperTradingClient for forward-testing...")
        
        # Instantiate real client purely for reading market data and websocket auth
        self.real_client = PolymarketClient(pk=pk)
        
        # Reference to local matching engine that tracks state
        self.matching_engine = matching_engine
        
        # Expose properties standard PolymarketClient exposes
        self.browser_wallet = self.real_client.browser_wallet
        self.key = self.real_client.key

    # ==========================
    # STOCHASTIC LATENCY INJECTOR
    # ==========================
    
    async def _delayed_execution(self, command_type, delay_params, **kwargs):
        """
        Applies a random delay before passing the execution command to the matching engine.
        """
        mu, sigma, min_delay = delay_params
        
        # Calculate random latency in ms
        delay_ms = max(min_delay, random.gauss(mu, sigma))
        
        # Apply delay
        await asyncio.sleep(delay_ms / 1000.0)
        
        # Pass the execution down to the matching engine after delay
        if command_type == 'create_order':
            return self.matching_engine.submit_order(latency_ms=delay_ms, **kwargs)
        elif command_type == 'cancel_all_asset':
            return self.matching_engine.cancel_all_asset(latency_ms=delay_ms, **kwargs)
        elif command_type == 'cancel_all_market':
            return self.matching_engine.cancel_all_market(latency_ms=delay_ms, **kwargs)
        elif command_type == 'merge_positions':
            return await self.matching_engine.merge_positions(latency_ms=delay_ms, **kwargs)
            
    # ==========================
    # INTERCEPTED WRITE COMMANDS
    # ==========================
    
    def create_order(self, marketId, action, price, size, neg_risk=False):
        timestamp = time.time()
        
        # Standard API latency profile (e.g. 35ms +/- 10ms, minimum 5ms)
        delay_params = (35, 10, 5) 
        order_id = f"paper_{uuid.uuid4().hex[:8]}"
        
        # Fire-and-forget the actual order submission with latency
        asyncio.create_task(
            self._delayed_execution(
                'create_order', 
                delay_params,
                order_id=order_id,
                market_id=str(marketId),
                action=action,
                price=price,
                size=size,
                neg_risk=neg_risk,
                timestamp=timestamp
            )
        )
        
        # Return a mock successful api response format synchronously
        return {
            "orderID": order_id, 
            "status": "PENDING"
        }

    def cancel_all_asset(self, asset_id):
        timestamp = time.time()
        delay_params = (35, 10, 5)
        
        asyncio.create_task(
            self._delayed_execution(
                'cancel_all_asset',
                delay_params,
                asset_id=str(asset_id),
                timestamp=timestamp
            )
        )

    def cancel_all_market(self, marketId):
        timestamp = time.time()
        delay_params = (35, 10, 5)
        
        asyncio.create_task(
            self._delayed_execution(
                'cancel_all_market',
                delay_params,
                market_id=str(marketId),
                timestamp=timestamp
            )
        )

    async def merge_positions(self, amount_to_merge: float, condition_id: str, is_neg_risk_market: bool) -> str:
        timestamp = time.time()
        # On-chain RPC calls have higher latency (150ms +/- 30ms, minimum 50ms)
        delay_params = (150, 30, 50)
        
        tx_hash = await self._delayed_execution(
            'merge_positions',
            delay_params,
            amount_to_merge=amount_to_merge,
            condition_id=condition_id,
            is_neg_risk_market=is_neg_risk_market,
            timestamp=timestamp
        )
        return tx_hash

    # ==========================
    # INTERCEPTED STATE COMMANDS
    # ==========================
    
    def get_usdc_balance(self):
        return self.matching_engine.get_usdc_balance()

    def get_pos_balance(self):
        return self.matching_engine.get_pos_balance()

    def get_total_balance(self):
        return self.get_usdc_balance() + self.get_pos_balance()

    def get_all_positions(self):
        return self.matching_engine.get_all_positions()

    def get_raw_position(self, tokenId):
        return self.matching_engine.get_raw_position(tokenId)

    def get_position(self, tokenId):
        return self.matching_engine.get_position(tokenId)

    def get_all_orders(self):
        return self.matching_engine.get_all_orders()

    def get_market_orders(self, market):
        return self.matching_engine.get_market_orders(market)

    # ==========================
    # PASSTHROUGH READ DATA 
    # ==========================
    
    def get_order_book(self, market):
        return self.real_client.get_order_book(market)
