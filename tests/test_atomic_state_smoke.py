"""
Smoke tests for atomic state snapshot implementation.
Tests threading.Lock + deepcopy isolation and all atomic state functions in global_state.py.

IMPORTANT: Previously this file stubbed sys.modules['pandas'] at module-level, which
poisoned the real pandas for all subsequent test files in the same pytest session.
Fixed to use a function-scoped mock that is guaranteed to be restored after each test.
"""

import sys
import threading
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock


def test_lock_and_deepcopy_isolation():
    """threading.Lock + deepcopy correctly isolates snapshots from mutation."""
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
    snap['a']['x'] = 999  # mutate snapshot

    with _test_lock:
        assert _test_data['a']['x'] == 1, "Deep copy isolation failed – mutation leaked into original"


def test_concurrent_stress_800_ops():
    """800 concurrent read/write ops produce no torn reads."""
    _positions = {}
    _lock = threading.Lock()
    errors: list[str] = []

    def writer(tid: int, n: int = 200):
        for i in range(n):
            try:
                with _lock:
                    _positions[f't{tid}_{i % 5}'] = {'size': i}
            except Exception as e:
                errors.append(str(e))

    def reader(n: int = 200):
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
        futures = [ex.submit(writer, i, 200) for i in range(2)]
        futures += [ex.submit(reader, 200) for _ in range(2)]
        for f in as_completed(futures):
            f.result()

    assert not errors, f"{len(errors)} concurrent errors: {errors[:3]}"


def test_global_state_module_structure():
    """All required atomic functions are present in global_state."""
    # Use a lightweight mock for pandas to avoid network/env deps, but SCOPED to this test.
    mock_pd = MagicMock()
    mock_pd.DataFrame = MagicMock(return_value=MagicMock())

    with patch.dict(sys.modules, {'pandas': mock_pd}):
        import importlib
        # Reload to pick up mock in this scope
        if 'poly_data.global_state' in sys.modules:
            gs = sys.modules['poly_data.global_state']
        else:
            import poly_data.global_state as gs

    required = [
        '_state_lock', 'get_state_snapshot', 'get_position_atomic',
        'has_position_atomic', 'update_positions_atomic', 'replace_positions_atomic',
        'get_orders_snapshot_atomic', 'update_orders_atomic', 'replace_orders_atomic',
        'get_last_trade_action_time_atomic', 'set_last_trade_action_time_atomic',
    ]
    import poly_data.global_state as gs
    for attr in required:
        assert hasattr(gs, attr), f"Missing atomic attribute: {attr}"

    assert isinstance(gs._state_lock, threading.Lock)
    assert isinstance(gs.positions, dict)
    assert isinstance(gs.orders, dict)


def test_global_state_functional_workflow():
    """Full functional end-to-end: positions, orders, cooldown timestamps, and snapshot isolation."""
    import poly_data.global_state as gs

    # Reset state (tests may run in any order)
    gs.positions = {}
    gs.orders = {}
    gs.last_trade_action_time = {}

    # --- Positions ---
    gs.update_positions_atomic({'token1': {'size': 100, 'avgPrice': 0.5}})
    pos = gs.get_position_atomic('token1')
    assert pos['size'] == 100 and pos['avgPrice'] == 0.5

    gs.update_positions_atomic({'token1': {'size': 150, 'avgPrice': 0.55}})
    assert gs.get_position_atomic('token1')['size'] == 150

    assert gs.has_position_atomic('token1') is True
    assert gs.has_position_atomic('unknown_token') is False

    # --- Orders ---
    gs.update_orders_atomic({'token1': {'buy': {'price': 0.45, 'size': 50}}})
    orders = gs.get_orders_snapshot_atomic()
    assert 'token1' in orders

    gs.replace_orders_atomic({'token2': {'sell': {'price': 0.55, 'size': 30}}})
    orders = gs.get_orders_snapshot_atomic()
    assert 'token2' in orders and 'token1' not in orders

    # --- Cooldown timestamps ---
    gs.set_last_trade_action_time_atomic('market1', 1234567890.0)
    assert gs.get_last_trade_action_time_atomic('market1') == 1234567890.0
    assert gs.get_last_trade_action_time_atomic('unknown_market') == 0.0

    # --- Snapshot deep-copy isolation ---
    snap = gs.get_state_snapshot()
    assert 'positions' in snap and 'orders' in snap and 'last_trade_action_time' in snap

    original_size = snap['positions']['token1']['size']
    snap['positions']['token1']['size'] = 99999  # mutate snapshot
    assert gs.get_position_atomic('token1')['size'] == original_size  # original unchanged
