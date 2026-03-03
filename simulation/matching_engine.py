import logging
import time
import uuid
import pandas as pd
import poly_data.global_state as global_state

logger = logging.getLogger(__name__)

class LiveMatchingEngine:
    def __init__(self, initial_usdc=1000.0):
        self.usdc_balance = initial_usdc
        self.positions = {}
        self.orders = {}
        
        self.pnl_history = []
        self.trade_history = []
        self.missed_fills = []

    def _get_reserved_usdc(self):
        """Calculates USDC tied up in open limit orders."""
        reserved = 0
        for order in self.orders.values():
            if order["status"] == "OPEN":
                market_id = order["market_id"]
                size = order["size"]
                price = order["price"]
                action = order["action"]
                
                if action == "BUY":
                    reserved += size * price
                elif action == "SELL":
                    pos_size = self.positions.get(market_id, {}).get("size", 0)
                    if pos_size < size:
                        # Uncovered portion requires collateral = size * price 
                        # because we place NO side at (1 - price)
                        uncovered = size - pos_size
                        reserved += uncovered * price
        return reserved

    def submit_order(self, latency_ms, order_id, market_id, action, price, size, neg_risk, timestamp):
        """Strict Margin Checks before logging the order."""
        available_usdc = self.usdc_balance - self._get_reserved_usdc()
        
        if action == "BUY":
            cost = price * size
            if available_usdc < cost:
                logger.warning(f"MARGIN REJECT: Insufficient USDC for BUY {size} @ {price}. Need {cost}, Available {available_usdc}")
                return
        elif action == "SELL":
            # Check if we have token or enough USDC to short
            pos_size = self.positions.get(str(market_id), {}).get("size", 0)
            if pos_size < size:
                uncovered = size - pos_size
                short_cost = uncovered * price
                if available_usdc < short_cost:
                    logger.warning(f"MARGIN REJECT: Insufficient USDC to SHORT {uncovered} @ {price}. Need {short_cost}, Available {available_usdc}")
                    return

        # Accepted
        self.orders[order_id] = {
            "market_id": str(market_id),
            "action": action,
            "price": float(price),
            "size": float(size),
            "timestamp": timestamp,
            "latency_ms": latency_ms,
            "status": "OPEN",
            "neg_risk": neg_risk,
            "missed_alert_fired": False
        }
        logger.debug(f"Order Accepted: {order_id} - {action} {size} @ {price}")
        return {"orderID": order_id, "status": "PENDING"}

    def cancel_all_asset(self, latency_ms, asset_id, timestamp):
        asset_id = str(asset_id)
        for order_id, order in self.orders.items():
            if order["market_id"] == asset_id and order["status"] == "OPEN":
                order["status"] = "CANCELED"
                
    def cancel_all_market(self, latency_ms, market_id, timestamp):
        market_id = str(market_id)
        for order_id, order in self.orders.items():
            if order["market_id"] == market_id and order["status"] == "OPEN":
                order["status"] = "CANCELED"

    async def merge_positions(self, latency_ms, amount_to_merge, condition_id, is_neg_risk_market, timestamp):
        """Simulates merging YES and NO tokens to reclaim USDC."""
        try:
            row = global_state.df[global_state.df['condition_id'] == condition_id]
            if len(row) > 0:
                t1 = str(row.iloc[0]['token1'])
                t2 = str(row.iloc[0]['token2'])
                
                p1 = self.positions.get(t1, {}).get("size", 0)
                p2 = self.positions.get(t2, {}).get("size", 0)
                
                mergeable = min(p1, p2, amount_to_merge)
                if mergeable > 0:
                    self.positions[t1]["size"] -= mergeable
                    self.positions[t2]["size"] -= mergeable
                    self.usdc_balance += mergeable
                    logger.info(f"🔄 PAPER MERGE: {mergeable} reclaimed. New USDC: {self.usdc_balance:.2f}")
                    
        except Exception as e:
            logger.error(f"Paper merge failed: {e}")
            
        return f"paper_tx_{uuid.uuid4().hex[:8]}"

    def process_market_update(self, market_id, best_bid, best_ask, last_trade_price=None):
        """
        Evaluates whether live price action crossed any standing mock orders.
        """
        market_id = str(market_id)
        current_time = time.time()
        
        for order_id, order in list(self.orders.items()):
            if order["status"] != "OPEN" or order["market_id"] != market_id:
                continue
                
            active_time = order["timestamp"] + (order["latency_ms"] / 1000.0)
            is_active = current_time >= active_time
            
            p = order["price"]
            action = order["action"]
            
            fill_met = False
            if action == "BUY":
                if best_ask is not None and best_ask <= p:
                    fill_met = True
                elif last_trade_price is not None and last_trade_price <= p:
                    fill_met = True
            elif action == "SELL":
                if best_bid is not None and best_bid >= p:
                    fill_met = True
                elif last_trade_price is not None and last_trade_price >= p:
                    fill_met = True
                    
            if fill_met:
                if is_active:
                    self._execute_fill(order_id)
                else:
                    if not order.get("missed_alert_fired"):
                        order["missed_alert_fired"] = True
                        logger.info(f"LATENCY MISS on {order_id}: {action} {p}. Passed live threshold during latency!")
                        self.missed_fills.append({
                            "order_id": order_id,
                            "timestamp": current_time,
                            "latency_ms": order["latency_ms"]
                        })

    def _execute_fill(self, order_id):
        order = self.orders[order_id]
        order["status"] = "FILLED"
        
        market_id = order["market_id"]
        action = order["action"]
        price = order["price"]
        size = order["size"]
        
        if market_id not in self.positions:
            self.positions[market_id] = {"size": 0, "avgPrice": 0.0}
            
        pos = self.positions[market_id]
        realized_pnl = 0.0

        if action == "BUY":
            cost = price * size
            self.usdc_balance -= cost
            prev_size = pos["size"]
            prev_avg = pos["avgPrice"]
            new_size = prev_size + size
            new_avg = ((prev_size * prev_avg) + (size * price)) / new_size if new_size > 0 else 0
            self.positions[market_id] = {"size": new_size, "avgPrice": new_avg}
            # No realized P&L on a pure buy; it accrues when we sell.
            realized_pnl = 0.0

        elif action == "SELL":
            avg_cost = pos["avgPrice"]

            if pos["size"] >= size:
                # --- Standard sell of held tokens ---
                self.positions[market_id]["size"] -= size
                proceeds = price * size
                self.usdc_balance += proceeds
                # Realized P&L = proceeds minus cost basis of the shares sold
                realized_pnl = proceeds - (avg_cost * size)
            else:
                # --- Partial sell + short (mint complementary token) ---
                held = pos["size"]
                shorted_size = size - held

                # 1) Sell held tokens at the fill price
                if held > 0:
                    held_proceeds = held * price
                    self.usdc_balance += held_proceeds
                    realized_pnl += held_proceeds - (avg_cost * held)
                    self.positions[market_id]["size"] = 0

                # 2) Mint a complementary (NO) token pair and immediately sell the YES side
                #    Cost to mint one pair = 1 USDC; we receive 1 YES + 1 NO.
                #    We sell the YES at `price`, keeping the NO token.
                #    Net cost of the NO token = 1 - price.
                opp_token = global_state.REVERSE_TOKENS.get(market_id)
                if opp_token:
                    mint_cost = shorted_size * 1.0          # 1 USDC per pair
                    yes_proceeds = shorted_size * price      # sell YES side immediately
                    net_no_cost = mint_cost - yes_proceeds   # = shorted_size * (1 - price)
                    self.usdc_balance -= net_no_cost

                    if opp_token not in self.positions:
                        self.positions[opp_token] = {"size": 0, "avgPrice": 0.0}

                    opp_pos = self.positions[opp_token]
                    o_prev_size = opp_pos["size"]
                    o_prev_avg = opp_pos["avgPrice"]
                    o_price = 1.0 - price   # effective cost basis of the NO token

                    o_new_size = o_prev_size + shorted_size
                    o_new_avg = ((o_prev_size * o_prev_avg) + (shorted_size * o_price)) / o_new_size if o_new_size > 0 else 0
                    self.positions[opp_token] = {"size": o_new_size, "avgPrice": o_new_avg}
                    # Realized P&L from the short-mint side = 0 (we just opened a new position)
                else:
                    # No complement known – treat as naked sell, deduct position
                    proceeds = price * size
                    self.usdc_balance += proceeds
                    realized_pnl += proceeds - (avg_cost * size)
                    self.positions[market_id]["size"] = max(0, pos["size"] - size)
                    
        logger.info(f"✅ PAPER FILL: {action} {size} of {market_id[:6]} @ {price}. USDC: {self.usdc_balance:.2f} | Realized P&L: ${realized_pnl:+.4f}")

        fill_record = {
            "order_id": order_id,
            "market_id": market_id,
            "action": action,
            "price": price,
            "size": size,
            "timestamp": time.time(),
            "latency_ms": order["latency_ms"],
            "realized_pnl": realized_pnl,
        }
        self.trade_history.append(fill_record)
        self.pnl_history.append({
            "timestamp": fill_record["timestamp"],
            "realized_pnl": realized_pnl,
            "cumulative_pnl": sum(r["realized_pnl"] for r in self.pnl_history) + realized_pnl,
            "usdc_balance": self.usdc_balance,
        })

    # ==========================
    # GETTERS FOR CLIENT WRAPPER
    # ==========================
    
    def get_usdc_balance(self): return self.usdc_balance

    def get_pos_balance(self):
        """Returns position value at average cost basis (not current market price)."""
        return sum(p["size"] * p["avgPrice"] for p in self.positions.values())

    def get_mid_price(self, token_id: str) -> float | None:
        """Returns the live mid-price for a token from the in-memory order book."""
        try:
            book = global_state.all_data.get(token_id)
            if book is None:
                return None
            bids = book.get("bids", {})
            asks = book.get("asks", {})
            best_bid = max(bids.keys()) if bids else None
            best_ask = min(asks.keys()) if asks else None
            if best_bid is not None and best_ask is not None:
                return (best_bid + best_ask) / 2.0
            if best_bid is not None:
                return best_bid
            if best_ask is not None:
                return best_ask
        except Exception:
            pass
        return None

    def get_pos_balance_mtm(self) -> float:
        """Returns position value marked to live mid-price.
        Falls back to average cost for tokens with no live book."""
        total = 0.0
        for token_id, pos in self.positions.items():
            size = pos["size"]
            if size <= 0:
                continue
            mid = self.get_mid_price(token_id)
            price = mid if mid is not None else pos["avgPrice"]
            total += size * price
        return total

    def get_pnl_summary(self) -> dict:
        """Returns a snap-shot of realized P&L and current unrealized P&L."""
        realized = sum(r["realized_pnl"] for r in self.pnl_history)
        cost_basis = self.get_pos_balance()          # at avg cost
        mtm_value  = self.get_pos_balance_mtm()      # at live mid
        unrealized  = mtm_value - cost_basis
        return {
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": realized + unrealized,
            "cost_basis": cost_basis,
            "mtm_value": mtm_value,
        }

    def get_all_positions(self):
        res = [{"asset": k, "size": v["size"], "avgPrice": v["avgPrice"]} 
               for k, v in self.positions.items() if v["size"] > 0]
        return pd.DataFrame(res) if res else pd.DataFrame(columns=["asset", "size", "avgPrice"])

    def get_raw_position(self, tokenId):
        return int(self.positions.get(str(tokenId), {}).get("size", 0) * 1e6)

    def get_position(self, tokenId):
        shares = self.positions.get(str(tokenId), {}).get("size", 0)
        return int(shares * 1e6), max(0, shares)

    def get_all_orders(self):
        res = [{"asset_id": o["market_id"], "side": o["action"], "price": o["price"], 
                "original_size": o["size"], "size_matched": 0} 
               for o in self.orders.values() if o["status"] == "OPEN"]
        return pd.DataFrame(res) if res else pd.DataFrame(columns=['asset_id', 'side', 'price', 'original_size', 'size_matched'])

    def get_market_orders(self, market):
        df = self.get_all_orders()
        return df[df['asset_id'] == str(market)] if len(df) > 0 else df
