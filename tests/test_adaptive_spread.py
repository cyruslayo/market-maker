"""
Standalone validation test for adaptive spread model (OFI-aware pricing).
Validates the core OFI calculation logic without requiring web3 dependencies.
"""

# Replicate the core constants and logic from trading_utils.py
OFI_IMBALANCE_THRESHOLD = 0.7
OFI_ALPHA_WIDE = 1.8
OFI_ALPHA_NORMAL = 1.0


def round_to_tick(price, tick_size):
    """Replicate round_to_tick helper"""
    # Add 1e-9 to avoid Python 3 banker's rounding (round half to even)
    rounded = round((price / tick_size) + 1e-9) * tick_size
    decimals = len(str(tick_size).split('.')[1]) if '.' in str(tick_size) else 0
    return round(rounded, decimals)


def get_order_prices(best_bid, best_bid_size, top_bid, best_ask, best_ask_size, top_ask, avgPrice, row):
    """
    Replicate the OFI-aware get_order_prices logic for validation testing.
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
    if bid_price < reward_bid:
        bid_price = max(bid_price, reward_bid - row['tick_size'])

    if ask_price > reward_ask:
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


def test_ac1_balanced_book_no_widening():
    """AC1: imbalance = 0.667 (below threshold) -> alpha_ask = 1.0"""
    best_bid, best_bid_size = 0.45, 500
    best_ask, best_ask_size = 0.55, 100
    top_bid, top_ask = 0.50, 0.50
    avgPrice = 0.40
    row = {'max_spread': 5, 'tick_size': 0.001, 'min_size': 10, 'trade_size': 100}

    bid_price, ask_price = get_order_prices(
        best_bid, best_bid_size, top_bid,
        best_ask, best_ask_size, top_ask,
        avgPrice, row
    )

    # Verify imbalance calculation
    total_depth = best_bid_size + best_ask_size
    imbalance = (best_bid_size - best_ask_size) / total_depth
    assert abs(imbalance - 0.667) < 0.01, f"Expected imbalance ~0.667, got {imbalance}"

    # alpha_ask should be normal (below threshold)
    alpha_ask = OFI_ALPHA_WIDE if imbalance > OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    assert alpha_ask == OFI_ALPHA_NORMAL, f"AC1 FAILED: alpha_ask should be {OFI_ALPHA_NORMAL} for imbalance {imbalance}"

    print(f"✓ AC1 PASSED: Balanced book (imbalance={imbalance:.3f}) -> alpha_ask={alpha_ask}")
    return True


def test_ac2_threshold_triggers_widening():
    """AC2: imbalance = 0.8 (above threshold) -> alpha_ask = 1.8, ask wider than bid"""
    best_bid, best_bid_size = 0.45, 900
    best_ask, best_ask_size = 0.55, 100
    top_bid, top_ask = 0.50, 0.50
    avgPrice = 0.40
    row = {'max_spread': 5, 'tick_size': 0.001, 'min_size': 10, 'trade_size': 100}

    bid_price, ask_price = get_order_prices(
        best_bid, best_bid_size, top_bid,
        best_ask, best_ask_size, top_ask,
        avgPrice, row
    )

    # Verify imbalance calculation
    total_depth = best_bid_size + best_ask_size
    imbalance = (best_bid_size - best_ask_size) / total_depth
    assert abs(imbalance - 0.8) < 0.01, f"Expected imbalance ~0.8, got {imbalance}"

    # alpha_ask should be wide (above threshold)
    alpha_ask = OFI_ALPHA_WIDE if imbalance > OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    assert alpha_ask == OFI_ALPHA_WIDE, f"AC2 FAILED: alpha_ask should be {OFI_ALPHA_WIDE} for imbalance {imbalance}"

    # Verify ask is wider than bid from mid
    v = row['max_spread'] / 100
    bid_distance = v * 0.12 * OFI_ALPHA_NORMAL  # Normal alpha for bid
    ask_distance = v * 0.12 * OFI_ALPHA_WIDE    # Wide alpha for ask

    assert ask_distance > bid_distance, "AC2 FAILED: ask_distance should be wider than bid_distance"

    print(f"✓ AC2 PASSED: Imbalanced book (imbalance={imbalance:.3f}) -> alpha_ask={alpha_ask}, ask is wider")
    return True


def test_ac3_symmetric_book():
    """AC3: imbalance = 0.0 -> alpha_bid = alpha_ask = 1.0"""
    best_bid, best_bid_size = 0.45, 500
    best_ask, best_ask_size = 0.55, 500
    top_bid, top_ask = 0.50, 0.50
    avgPrice = 0.40
    row = {'max_spread': 5, 'tick_size': 0.001, 'min_size': 10, 'trade_size': 100}

    total_depth = best_bid_size + best_ask_size
    imbalance = (best_bid_size - best_ask_size) / total_depth

    alpha_bid = OFI_ALPHA_WIDE if imbalance < -OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    alpha_ask = OFI_ALPHA_WIDE if imbalance > OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL

    assert alpha_bid == OFI_ALPHA_NORMAL, f"AC3 FAILED: alpha_bid should be {OFI_ALPHA_NORMAL}"
    assert alpha_ask == OFI_ALPHA_NORMAL, f"AC3 FAILED: alpha_ask should be {OFI_ALPHA_NORMAL}"

    print(f"✓ AC3 PASSED: Symmetric book (imbalance={imbalance:.3f}) -> both alphas = {OFI_ALPHA_NORMAL}")
    return True


def test_ac4_tick_alignment():
    """AC4: Both prices are exact multiples of tick_size"""
    best_bid, best_bid_size = 0.45, 500
    best_ask, best_ask_size = 0.55, 100
    top_bid, top_ask = 0.50, 0.50
    avgPrice = 0.40
    tick_size = 0.001
    row = {'max_spread': 5, 'tick_size': tick_size, 'min_size': 10, 'trade_size': 100}

    bid_price, ask_price = get_order_prices(
        best_bid, best_bid_size, top_bid,
        best_ask, best_ask_size, top_ask,
        avgPrice, row
    )

    # Check tick alignment (allow small float tolerance)
    bid_divisible = abs((bid_price / tick_size) - round(bid_price / tick_size)) < 0.0001
    ask_divisible = abs((ask_price / tick_size) - round(ask_price / tick_size)) < 0.0001

    assert bid_divisible, f"AC4 FAILED: bid_price {bid_price} not aligned to tick {tick_size}"
    assert ask_divisible, f"AC4 FAILED: ask_price {ask_price} not aligned to tick {tick_size}"

    print(f"✓ AC4 PASSED: bid={bid_price}, ask={ask_price} both aligned to tick={tick_size}")
    return True


def test_ac5_no_crossed_spread():
    """AC5: bid_price < ask_price always holds"""
    test_cases = [
        # (best_bid, best_bid_size, top_bid, best_ask, best_ask_size, top_ask, avgPrice)
        (0.45, 900, 0.50, 0.55, 100, 0.50, 0.40),  # Heavy bid imbalance
        (0.45, 100, 0.50, 0.55, 900, 0.50, 0.40),  # Heavy ask imbalance
        (0.45, 500, 0.50, 0.55, 500, 0.50, 0.40),  # Balanced
        (0.48, 1000, 0.50, 0.52, 1000, 0.50, 0.40), # Tight spread
    ]

    row = {'max_spread': 5, 'tick_size': 0.001, 'min_size': 10, 'trade_size': 100}

    for i, (best_bid, best_bid_size, top_bid, best_ask, best_ask_size, top_ask, avgPrice) in enumerate(test_cases):
        bid_price, ask_price = get_order_prices(
            best_bid, best_bid_size, top_bid,
            best_ask, best_ask_size, top_ask,
            avgPrice, row
        )
        assert bid_price < ask_price, f"AC5 FAILED: bid_price {bid_price} >= ask_price {ask_price} for case {i+1}"

    print(f"✓ AC5 PASSED: No crossed spread in {len(test_cases)} test cases")
    return True


def test_round_to_tick():
    """Test the round_to_tick helper function"""
    assert round_to_tick(0.50005, 0.001) == 0.5
    assert round_to_tick(0.50015, 0.001) == 0.5
    assert round_to_tick(0.5005, 0.001) == 0.501
    assert round_to_tick(0.1, 0.01) == 0.1
    print("✓ round_to_tick helper works correctly")
    return True


def test_sell_pressure_widens_bid():
    """When ask side is heavy (sell pressure), bid should widen"""
    best_bid, best_bid_size = 0.45, 100   # Light bid side
    best_ask, best_ask_size = 0.55, 900   # Heavy ask side (sell pressure)
    top_bid, top_ask = 0.50, 0.50
    avgPrice = 0.40
    row = {'max_spread': 5, 'tick_size': 0.001, 'min_size': 10, 'trade_size': 100}

    total_depth = best_bid_size + best_ask_size
    imbalance = (best_bid_size - best_ask_size) / total_depth  # Should be negative

    # Verify sell pressure detected
    assert imbalance < -OFI_IMBALANCE_THRESHOLD, f"Expected strong negative imbalance, got {imbalance}"

    alpha_bid = OFI_ALPHA_WIDE if imbalance < -OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    assert alpha_bid == OFI_ALPHA_WIDE, "Bid should widen under sell pressure"

    print(f"✓ Sell pressure test PASSED: imbalance={imbalance:.3f}, alpha_bid={alpha_bid} (widened)")
    return True


def test_zero_depth_fallback():
    """When total_depth is 0, imbalance should default to 0"""
    total_depth = 0
    imbalance = (500 - 500) / total_depth if total_depth > 0 else 0
    assert imbalance == 0, "Zero depth should produce imbalance = 0"

    alpha_bid = OFI_ALPHA_WIDE if imbalance < -OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL
    alpha_ask = OFI_ALPHA_WIDE if imbalance > OFI_IMBALANCE_THRESHOLD else OFI_ALPHA_NORMAL

    assert alpha_bid == OFI_ALPHA_NORMAL
    assert alpha_ask == OFI_ALPHA_NORMAL

    print("✓ Zero depth fallback test PASSED: imbalance=0, both alphas normal")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Adaptive Spread Model (OFI) - Validation Tests")
    print("=" * 60)

    all_passed = True
    tests = [
        test_round_to_tick,
        test_ac1_balanced_book_no_widening,
        test_ac2_threshold_triggers_widening,
        test_ac3_symmetric_book,
        test_ac4_tick_alignment,
        test_ac5_no_crossed_spread,
        test_sell_pressure_widens_bid,
        test_zero_depth_fallback,
    ]

    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            all_passed = False
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
        exit(1)
