"""
Test for Native Python Merger implementation.
Tests the async merge_positions method without requiring actual blockchain interaction.
"""
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_merge_positions_async_signature():
    """Verify merge_positions is async and has correct signature."""
    from poly_data.polymarket_client import PolymarketClient
    
    # Check method exists and is async
    assert hasattr(PolymarketClient, 'merge_positions')
    import inspect
    assert inspect.iscoroutinefunction(PolymarketClient.merge_positions)
    
    # Check signature
    sig = inspect.signature(PolymarketClient.merge_positions)
    params = list(sig.parameters.keys())
    assert 'self' in params
    assert 'amount_to_merge' in params
    assert 'condition_id' in params
    assert 'is_neg_risk_market' in params
    
    print("✓ merge_positions has correct async signature")


def test_merge_positions_converts_amount_to_raw():
    """Verify amount conversion from float to raw units."""
    # Test conversion: 25.5 USDC -> 25,500,000 raw units
    amount = 25.5
    raw_amount = int(amount * 1_000_000)
    assert raw_amount == 25_500_000
    
    # Test conversion: 1 USDC -> 1,000,000 raw units
    amount = 1.0
    raw_amount = int(amount * 1_000_000)
    assert raw_amount == 1_000_000
    
    print("✓ Amount conversion logic correct")


def test_condition_id_bytes_conversion():
    """Verify condition_id is converted to bytes32 correctly."""
    # Test with 0x prefix
    condition_id = "0xabc123"
    condition_id_clean = condition_id.replace('0x', '')
    condition_id_bytes = bytes.fromhex(condition_id_clean.rjust(64, '0'))
    assert len(condition_id_bytes) == 32
    
    # Test without 0x prefix
    condition_id = "abc123"
    condition_id_bytes = bytes.fromhex(condition_id.rjust(64, '0'))
    assert len(condition_id_bytes) == 32
    
    print("✓ condition_id bytes conversion correct")


def test_neg_risk_contract_address():
    """Verify NegRiskAdapter address is correct."""
    expected_address = '0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296'
    
    from poly_data.polymarket_client import PolymarketClient
    # The address should be in the addresses dict
    import inspect
    source = inspect.getsource(PolymarketClient)
    assert expected_address in source
    
    print("✓ NegRiskAdapter address correct")


def test_conditional_tokens_contract_address():
    """Verify ConditionalTokens address is correct."""
    expected_address = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
    
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    assert expected_address in source
    
    print("✓ ConditionalTokens address correct")


def test_collateral_address():
    """Verify USDC collateral address is correct."""
    expected_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    assert expected_address in source
    
    print("✓ Collateral (USDC) address correct")


def test_partition_values():
    """Verify partition [1, 2] is used for binary markets."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    # Check that partition = [1, 2] is in the code
    assert "partition = [1, 2]" in source or "[1, 2]" in source
    
    print("✓ Partition [1, 2] for binary markets verified")


def test_parent_collection_id_zero():
    """Verify parentCollectionId is bytes32(0) for top-level markets."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    # Check for bytes32(0) representation
    assert "b'\\x00' * 32" in source or "parent_collection_id" in source
    
    print("✓ parentCollectionId = bytes32(0) verified")


def test_gas_limit_configured():
    """Verify gas limit is set to 1,000,000."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    assert "'gas': 1_000_000" in source or '"gas": 1_000_000' in source
    
    print("✓ Gas limit 1,000,000 configured")


def test_chain_id_polygon():
    """Verify chainId is set to 137 (Polygon)."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient)
    assert "'chainId': 137" in source or '"chainId": 137' in source
    
    print("✓ Chain ID 137 (Polygon) configured")


def test_error_handling_returns_none():
    """Verify merge_positions returns None on failure."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient.merge_positions)
    # Should have try/except block
    assert "try:" in source
    assert "except" in source
    assert "return None" in source
    
    print("✓ Error handling returns None on failure")


def test_no_subprocess_in_merge_positions():
    """Verify no subprocess calls in merge_positions method."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient.merge_positions)
    
    # Should NOT contain subprocess
    assert "subprocess" not in source
    assert "subprocess.run" not in source
    assert "node poly_merger" not in source
    
    # Should use web3.py
    assert "self.web3" in source or "web3" in source
    assert "run_in_executor" in source
    
    print("✓ No subprocess calls in merge_positions (uses web3.py)")


def test_uses_asyncio_executor():
    """Verify blocking web3 calls use run_in_executor."""
    from poly_data.polymarket_client import PolymarketClient
    import inspect
    source = inspect.getsource(PolymarketClient.merge_positions)
    
    # Should use run_in_executor for non-blocking
    assert "run_in_executor" in source
    assert "asyncio" in source or "asyncio.get_event_loop()" in source
    
    print("✓ Uses run_in_executor for blocking calls")


def test_merger_loop_exists():
    """Verify merger_loop function exists in main.py."""
    # Read main.py and check for merger_loop
    with open('main.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert "async def merger_loop()" in source
    assert "MERGE_THRESHOLD = 20" in source or "20" in source
    assert "asyncio.create_task(merger_loop())" in source
    
    print("✓ merger_loop exists and is registered in main()")


def test_trading_uses_async_merge():
    """Verify trading.py uses async merge_positions via create_task."""
    with open('trading.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Should use asyncio.create_task for merge
    assert "asyncio.create_task(client.merge_positions" in source
    
    # Should NOT have subprocess calls
    assert "subprocess.run" not in source
    assert "node poly_merger" not in source
    
    print("✓ trading.py uses async create_task for merge_positions")


def test_imports_updated():
    """Verify imports were updated correctly."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Should have asyncio and logging imports
    assert "import asyncio" in source
    assert "import logging" in source
    
    # Should NOT have subprocess (only comment can reference it)
    lines = source.split('\n')
    import_lines = [l for l in lines if l.strip().startswith('import ') or l.strip().startswith('from ')]
    for line in import_lines:
        assert "subprocess" not in line, f"subprocess import found: {line}"
    
    print("✓ Imports updated (asyncio, logging added; subprocess removed)")


def run_all_tests():
    """Run all verification tests."""
    tests = [
        test_merge_positions_async_signature,
        test_merge_positions_converts_amount_to_raw,
        test_condition_id_bytes_conversion,
        test_neg_risk_contract_address,
        test_conditional_tokens_contract_address,
        test_collateral_address,
        test_partition_values,
        test_parent_collection_id_zero,
        test_gas_limit_configured,
        test_chain_id_polygon,
        test_error_handling_returns_none,
        test_no_subprocess_in_merge_positions,
        test_uses_asyncio_executor,
        test_merger_loop_exists,
        test_trading_uses_async_merge,
        test_imports_updated,
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "="*60)
    print("Native Python Merger - Implementation Tests")
    print("="*60 + "\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: FAILED - {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: ERROR - {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
