"""
Unit tests for reward_tracker.py - Fee-Curve Weighted Reward Tracker
"""

import unittest
from poly_data.reward_tracker import estimate_order_reward, FEE_CURVE_PARAMS


class TestEstimateOrderReward(unittest.TestCase):
    """Test the 2026 fee-curve weighted reward formula."""

    def test_fee_curve_params_structure(self):
        """Verify FEE_CURVE_PARAMS has required keys and values."""
        self.assertIn('crypto', FEE_CURVE_PARAMS)
        self.assertIn('other', FEE_CURVE_PARAMS)
        
        # Check crypto params
        self.assertEqual(FEE_CURVE_PARAMS['crypto']['exponent'], 2)
        self.assertEqual(FEE_CURVE_PARAMS['crypto']['fee_rate'], 0.25)
        
        # Check other params
        self.assertEqual(FEE_CURVE_PARAMS['other']['exponent'], 1)
        self.assertEqual(FEE_CURVE_PARAMS['other']['fee_rate'], 0.0175)

    def test_ac1_crypto_produces_higher_fee_than_sports(self):
        """AC1: Crypto market produces higher fee equivalent than sports/other market."""
        price = 0.5
        size = 100
        
        crypto_reward = estimate_order_reward(price, size, market_type='crypto')
        sports_reward = estimate_order_reward(price, size, market_type='sports')
        
        self.assertGreater(crypto_reward, sports_reward,
                          f"Crypto ({crypto_reward}) should be > Sports ({sports_reward})")

    def test_ac2_default_market_type_is_other(self):
        """AC2: Default market_type='other' works without explicit argument."""
        price = 0.5
        size = 100
        
        # Call without market_type parameter
        reward = estimate_order_reward(price, size)
        
        self.assertIsInstance(reward, float)
        self.assertGreaterEqual(reward, 0.0)
        
        # Verify it matches explicit 'other' call
        other_reward = estimate_order_reward(price, size, market_type='other')
        self.assertEqual(reward, other_reward)

    def test_ac3_case_insensitive_crypto_detection(self):
        """AC3: Case-insensitive crypto detection for various market_type values."""
        price = 0.5
        size = 100
        
        test_cases = ['Crypto', 'CRYPTO', 'crypto-btc', 'Crypto Market', 'myCrypto']
        
        for market_type in test_cases:
            with self.subTest(market_type=market_type):
                reward = estimate_order_reward(price, size, market_type=market_type)
                expected_crypto_reward = estimate_order_reward(price, size, market_type='crypto')
                
                self.assertEqual(reward, expected_crypto_reward,
                                f"'{market_type}' should use crypto params")

    def test_ac4_non_negative_floor(self):
        """AC4: Return value is always >= 0 for valid price/size inputs."""
        test_cases = [
            (0.01, 0),      # minimum price, zero size
            (0.01, 100),    # minimum price
            (0.5, 1000000), # mid price, large size
            (0.99, 100),    # maximum price
            (0.99, 0),      # maximum price, zero size
        ]
        
        for price, size in test_cases:
            with self.subTest(price=price, size=size):
                for market_type in ['crypto', 'other', 'sports']:
                    reward = estimate_order_reward(price, size, market_type=market_type)
                    self.assertGreaterEqual(reward, 0.0,
                                           f"Reward should be >= 0 for price={price}, size={size}, type={market_type}")

    def test_formula_calculation_crypto(self):
        """Verify formula calculation for crypto markets."""
        # Test at price=0.5, size=100
        # fee_equivalent = 100 * 0.5 * 0.25 * (0.5 * 0.5)^2
        # = 50 * 0.25 * 0.0625
        # = 50 * 0.015625
        # = 0.78125
        price = 0.5
        size = 100
        expected = 0.78125
        
        result = estimate_order_reward(price, size, market_type='crypto')
        self.assertAlmostEqual(result, expected, places=4)

    def test_formula_calculation_other(self):
        """Verify formula calculation for other markets."""
        # Test at price=0.5, size=100
        # fee_equivalent = 100 * 0.5 * 0.0175 * (0.5 * 0.5)^1
        # = 50 * 0.0175 * 0.25
        # = 50 * 0.004375
        # = 0.21875
        price = 0.5
        size = 100
        expected = 0.21875
        
        result = estimate_order_reward(price, size, market_type='other')
        self.assertAlmostEqual(result, expected, places=4)

    def test_backwards_compatibility_with_positional_args(self):
        """Verify old-style positional calls still work."""
        # Old API: estimate_order_reward(price, size, mid_price, max_spread, daily_rate)
        reward = estimate_order_reward(0.5, 100, 0.5, 10.0, 100.0)
        self.assertIsInstance(reward, float)
        self.assertGreaterEqual(reward, 0.0)

    def test_price_zero_returns_zero(self):
        """Edge case: price=0 should return 0."""
        result = estimate_order_reward(0.0, 100, market_type='crypto')
        self.assertEqual(result, 0.0)

    def test_size_zero_returns_zero(self):
        """Edge case: size=0 should return 0."""
        result = estimate_order_reward(0.5, 0, market_type='crypto')
        self.assertEqual(result, 0.0)


class TestFeeCurveParams(unittest.TestCase):
    """Test FEE_CURVE_PARAMS constant configuration."""

    def test_crypto_has_higher_fee_rate(self):
        """Crypto fee_rate should be higher than other fee_rate."""
        crypto_rate = FEE_CURVE_PARAMS['crypto']['fee_rate']
        other_rate = FEE_CURVE_PARAMS['other']['fee_rate']
        self.assertGreater(crypto_rate, other_rate)

    def test_crypto_has_higher_exponent(self):
        """Crypto exponent should be higher than other exponent."""
        crypto_exp = FEE_CURVE_PARAMS['crypto']['exponent']
        other_exp = FEE_CURVE_PARAMS['other']['exponent']
        self.assertGreater(crypto_exp, other_exp)


if __name__ == '__main__':
    unittest.main()
