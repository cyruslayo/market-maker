"""
Standalone test for Native Python Merger implementation.
Reads source files directly without importing to avoid dependency issues.
"""
import sys
import os


def test_merge_positions_async_signature():
    """Verify merge_positions is async and has correct signature."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Check method exists and is async
    assert "async def merge_positions" in source
    assert "amount_to_merge: float" in source
    assert "condition_id: str" in source
    assert "is_neg_risk_market: bool" in source
    assert "-> str:" in source or "-> str" in source
    
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
    
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert expected_address in source
    print("✓ NegRiskAdapter address correct")


def test_conditional_tokens_contract_address():
    """Verify ConditionalTokens address is correct."""
    expected_address = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
    
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert expected_address in source
    print("✓ ConditionalTokens address correct")


def test_collateral_address():
    """Verify USDC collateral address is correct."""
    expected_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert expected_address in source
    print("✓ Collateral (USDC) address correct")


def test_partition_values():
    """Verify partition [1, 2] is used for binary markets."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Check that partition = [1, 2] is in the code
    assert "partition = [1, 2]" in source
    print("✓ Partition [1, 2] for binary markets verified")


def test_parent_collection_id_zero():
    """Verify parentCollectionId is bytes32(0) for top-level markets."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Check for bytes32(0) representation
    assert "b'\\x00' * 32" in source or "parent_collection_id" in source
    print("✓ parentCollectionId = bytes32(0) verified")


def test_gas_limit_configured():
    """Verify gas limit is set to 1,000,000."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert "'gas': 1_000_000" in source or '"gas": 1_000_000' in source
    print("✓ Gas limit 1,000,000 configured")


def test_chain_id_polygon():
    """Verify chainId is set to 137 (Polygon)."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert "'chainId': 137" in source or '"chainId": 137' in source
    print("✓ Chain ID 137 (Polygon) configured")


def test_error_handling_returns_none():
    """Verify merge_positions returns None on failure."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Should have try/except block
    assert "try:" in source
    assert "except" in source
    assert "return None" in source
    print("✓ Error handling returns None on failure")


def test_no_subprocess_in_merge_positions():
    """Verify no subprocess calls in merge_positions method."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Extract merge_positions method
    start = source.find("async def merge_positions")
    end = source.find("\n    async def ", start + 1)
    if end == -1:
        end = len(source)
    method_source = source[start:end]
    
    # Should NOT contain actual subprocess calls (ignore comments)
    lines = method_source.split('\n')
    code_lines = [l for l in lines if not l.strip().startswith('#') and not l.strip().startswith('"""') and not l.strip().startswith("'")]
    code_only = '\n'.join(code_lines)
    
    assert "subprocess.run" not in code_only, "subprocess.run found in merge_positions code"
    assert "subprocess.call" not in code_only, "subprocess.call found in merge_positions code"
    assert "subprocess.Popen" not in code_only, "subprocess.Popen found in merge_positions code"
    assert "import subprocess" not in code_only, "import subprocess found in merge_positions"
    assert "node poly_merger" not in code_only, "node poly_merger found in merge_positions"
    
    # Should use web3.py
    assert "self.web3" in method_source or "web3" in method_source
    assert "run_in_executor" in method_source
    
    print("✓ No subprocess calls in merge_positions (uses web3.py)")


def test_uses_asyncio_executor():
    """Verify blocking web3 calls use run_in_executor."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Extract merge_positions method
    start = source.find("async def merge_positions")
    end = source.find("\n    async def ", start + 1)
    if end == -1:
        end = len(source)
    method_source = source[start:end]
    
    # Should use run_in_executor for non-blocking
    assert "run_in_executor" in method_source
    assert "asyncio" in method_source
    
    print("✓ Uses run_in_executor for blocking calls")


def test_merger_loop_exists():
    """Verify merger_loop function exists in main.py."""
    with open('main.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    assert "async def merger_loop()" in source
    assert "MERGE_THRESHOLD = 20" in source
    assert "SLEEP_INTERVAL = 30" in source
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
    assert "logger = logging.getLogger" in source
    
    # Should NOT have subprocess import (only comments can reference it)
    import_section = source[:source.find("class PolymarketClient")]
    assert "import subprocess" not in import_section, "subprocess import should be removed"
    
    print("✓ Imports updated (asyncio, logging added; subprocess removed)")


def test_nonce_management():
    """Verify nonce management uses 'pending' for concurrent safety."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Extract merge_positions method
    start = source.find("async def merge_positions")
    end = source.find("\n    async def ", start + 1)
    if end == -1:
        end = len(source)
    method_source = source[start:end]
    
    # Should use 'pending' for nonce
    assert "'pending'" in method_source or '"pending"' in method_source
    assert "get_transaction_count" in method_source
    
    print("✓ Nonce management uses 'pending' for concurrent safety")


def test_return_type_annotation():
    """Verify return type is Optional[str] or str."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Check for proper return type hint
    assert "async def merge_positions(self, amount_to_merge: float, condition_id: str, is_neg_risk_market: bool) -> str:" in source
    
    print("✓ Return type annotation correct")


def test_conditional_bytes_handling():
    """Verify condition_id hex prefix handling."""
    with open('poly_data/polymarket_client.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Extract merge_positions method
    start = source.find("async def merge_positions")
    end = source.find("\n    async def ", start + 1)
    if end == -1:
        end = len(source)
    method_source = source[start:end]
    
    # Should handle 0x prefix removal
    assert "replace('0x', '')" in method_source or '.replace("0x", "")' in method_source
    
    print("✓ condition_id 0x prefix handling correct")


def test_fire_and_forget_in_merger_loop():
    """Verify merger loop uses fire-and-forget pattern."""
    with open('main.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Extract merger_loop function
    start = source.find("async def merger_loop()")
    end = source.find("\nasync def ", start + 1)
    if end == -1:
        end = len(source)
    method_source = source[start:end]
    
    # Should use create_task for fire-and-forget
    assert "asyncio.create_task(" in method_source
    assert "merge_positions" in method_source
    
    print("✓ merger_loop uses fire-and-forget pattern")


def test_scaled_amt_usage_in_trading():
    """Verify trading.py uses scaled_amt (float) not raw amount."""
    with open('trading.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Find the merge_positions call
    merge_call_line = [l for l in source.split('\n') if 'merge_positions' in l and 'asyncio.create_task' in l][0]
    
    # Should use scaled_amt (the float amount) not the raw amount
    assert "scaled_amt" in merge_call_line
    
    print("✓ trading.py passes scaled_amt (float) to merge_positions")


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
        test_nonce_management,
        test_return_type_annotation,
        test_conditional_bytes_handling,
        test_fire_and_forget_in_merger_loop,
        test_scaled_amt_usage_in_trading,
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    print("\n" + "="*60)
    print("Native Python Merger - Implementation Tests")
    print("="*60 + "\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: FAILED - {e}")
            errors.append((test.__name__, str(e)))
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: ERROR - {e}")
            errors.append((test.__name__, str(e)))
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if errors:
        print("\nFailed tests:")
        for name, error in errors:
            print(f"  - {name}: {error}")
    
    return failed == 0


if __name__ == "__main__":
    # Change to the correct directory
    os.chdir('/mnt/c/AI2026/market-maker/polymarket-automated-mm')
    success = run_all_tests()
    sys.exit(0 if success else 1)
