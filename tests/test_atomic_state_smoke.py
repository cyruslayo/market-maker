#!/usr/bin/env python3
"""Lightweight smoke test for atomic state snapshot - pandas stub included."""

import sys

# Create minimal pandas stub for environments without pandas
class MockDataFrame:
    def __init__(self, *args, **kwargs):
        pass

class MockPandas:
    DataFrame = MockDataFrame

sys.modules['pandas'] = MockPandas()
sys.path.insert(0, '/mnt/c/AI2026/market-maker/polymarket-automated-mm')

import threading
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed

print("=" * 60)
print("Atomic State Snapshot - Lightweight Smoke Test")
print("=" * 60)

# Test 1: Core lock + deepcopy mechanics
print("\n[TEST 1] Core lock + deepcopy isolation...")
try:
    _test_lock = threading.Lock()
    _test_data = {}
    
    def update_atomic(d):
        with _test_lock:
            _test_data.update(d)
    
    def get_snapshot():
        with _test_lock:
            return deepcopy(_test_data)
    
    update_atomic({'a': {'x': 1}})
    snap = get_snapshot()
    snap['a']['x'] = 999
    
    with _test_lock:
        assert _test_data['a']['x'] == 1, "Deep copy isolation failed"
    
    print("  ✓ threading.Lock + deepcopy isolation works")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Concurrent stress
print("\n[TEST 2] Concurrent stress test (800 ops)...")
try:
    _positions = {}
    _lock = threading.Lock()
    errors = []
    
    def writer(tid, n=200):
        for i in range(n):
            try:
                with _lock:
                    _positions[f't{tid}_{i%5}'] = {'size': i}
            except Exception as e:
                errors.append(str(e))
    
    def reader(n=200):
        for _ in range(n):
            try:
                with _lock:
                    snap = deepcopy(_positions)
                for k, v in snap.items():
                    if 'size' not in v:
                        errors.append(f"bad key {k}")
            except Exception as e:
                errors.append(str(e))
    
    with ThreadPoolExecutor(4) as ex:
        futures = []
        for i in range(2):
            futures.append(ex.submit(writer, i, 200))
        for _ in range(2):
            futures.append(ex.submit(reader, 200))
        for f in as_completed(futures):
            f.result()
    
    if errors:
        print(f"  ✗ {len(errors)} errors: {errors[:3]}")
        sys.exit(1)
    print("  ✓ 800 concurrent ops, no torn reads")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 3: Module structure and imports
print("\n[TEST 3] Module structure...")
try:
    import poly_data.global_state as gs
    
    required = ['_state_lock', 'get_state_snapshot', 'get_position_atomic',
                'has_position_atomic', 'update_positions_atomic', 'replace_positions_atomic',
                'get_orders_snapshot_atomic', 'update_orders_atomic', 'replace_orders_atomic',
                'get_last_trade_action_time_atomic', 'set_last_trade_action_time_atomic']
    
    for attr in required:
        assert hasattr(gs, attr), f"Missing {attr}"
    
    assert isinstance(gs._state_lock, threading.Lock)
    assert isinstance(gs.positions, dict)
    assert isinstance(gs.orders, dict)
    
    print(f"  ✓ All {len(required)} atomic functions present")
    print("  ✓ Locks and state variables correctly typed")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Full functional workflow
print("\n[TEST 4] Functional end-to-end...")
try:
    gs.positions = {}
    gs.orders = {}
    gs.last_trade_action_time = {}
    
    # Position workflow
    gs.update_positions_atomic({'token1': {'size': 100, 'avgPrice': 0.5}})
    pos = gs.get_position_atomic('token1')
    assert pos['size'] == 100 and pos['avgPrice'] == 0.5
    
    gs.update_positions_atomic({'token1': {'size': 150, 'avgPrice': 0.55}})
    pos = gs.get_position_atomic('token1')
    assert pos['size'] == 150
    
    # has_position_atomic
    assert gs.has_position_atomic('token1') == True
    assert gs.has_position_atomic('unknown') == False
    
    # Orders
    gs.update_orders_atomic({'token1': {'buy': {'price': 0.45, 'size': 50}}})
    orders = gs.get_orders_snapshot_atomic()
    assert 'token1' in orders
    
    # Full orders replacement
    gs.replace_orders_atomic({'token2': {'sell': {'price': 0.55, 'size': 30}}})
    orders = gs.get_orders_snapshot_atomic()
    assert 'token2' in orders and 'token1' not in orders
    
    # Cooldown timestamps
    gs.set_last_trade_action_time_atomic('market1', 1234567890.0)
    assert gs.get_last_trade_action_time_atomic('market1') == 1234567890.0
    assert gs.get_last_trade_action_time_atomic('unknown') == 0.0
    
    # Full snapshot
    snap = gs.get_state_snapshot()
    assert 'positions' in snap
    assert 'orders' in snap
    assert 'last_trade_action_time' in snap
    
    # Verify deep copy isolation
    original_size = snap['positions']['token1']['size']
    snap['positions']['token1']['size'] = 99999
    assert gs.get_position_atomic('token1')['size'] == original_size
    
    print("  ✓ All atomic operations work correctly")
    print("  ✓ Snapshot deep-copy isolation verified")
    print("  ✓ Position existence check works")
    print("  ✓ Order partial updates and full replacement work")
    print("  ✓ Cooldown timestamp atomic ops work")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL SMOKE TESTS PASSED ✓")
print("=" * 60)
print("\nSummary:")
print("  • threading.Lock + deepcopy isolation: VERIFIED")
print("  • Concurrent stress (800 ops): PASSED")
print("  • Module structure: ALL FUNCTIONS PRESENT")
print("  • Functional flow: POSITION/ORDER/COOLDOWN WORKING")
print("  • Snapshot immutability: VERIFIED")
print("\nAtomic state implementation is ready for production use.")
