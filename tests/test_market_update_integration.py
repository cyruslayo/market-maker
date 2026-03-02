import unittest
import pandas as pd
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import update_selected_markets

class TestMarketUpdateIntegration(unittest.TestCase):
    
    @patch('update_selected_markets.get_discovery_markets')
    @patch('update_selected_markets.get_target_markets')
    @patch('update_selected_markets.add_market')
    @patch('update_selected_markets.remove_market')
    def test_market_selection_pipeline(self, mock_remove, mock_add, mock_get_target, mock_get_discovery):
        """Test the market selection pipeline with filtering and correlation limits"""
        
        # Mock currently selected markets (empty)
        current_df = pd.DataFrame(columns=['question', 'max_size', 'condition_id', 'rationale'])
        mock_get_target.return_value = current_df
        
        # Source markets
        source_df = pd.DataFrame([
            {
                'question': 'Will Bitcoin hit 100k?',
                'rewards_daily_rate': 350,  # High reward -> max_aggressive
                'volatility_sum': 10,
                'spread': 0.02,
                'best_bid': 0.50,
                'best_ask': 0.52,
                'gm_reward_per_100': 2.5,
                'min_size': 50,
                'condition_id': '1',
                'token1': 't1',
                'token2': 't2',
                'neg_risk': 'FALSE'
            },
            {
                'question': 'Who will win US election?',
                'rewards_daily_rate': 200,  # Moderate reward -> aggressive
                'volatility_sum': 15,
                'spread': 0.04,
                'best_bid': 0.40,
                'best_ask': 0.44,
                'gm_reward_per_100': 1.5,
                'min_size': 50,
                'condition_id': '4',
                'token1': 't7',
                'token2': 't8',
                'neg_risk': 'TRUE'
            }
        ])
        mock_get_discovery.return_value = source_df
        
        # Call function
        update_selected_markets.update_selected_markets(replace_existing=True)
        
        # Verify add_market was called twice (once for each market)
        self.assertEqual(mock_add.call_count, 2)
        
        # Verify the first call (Bitcoin) - should have max_aggressive params ramped down
        # trade_size = max(int(200 * 0.25), 50) = 50
        # max_size = max(int(500 * 0.25), 50 * 2) = 125
        first_call_args = mock_add.call_args_list[0][1]
        self.assertEqual(first_call_args['condition_id'], '1')
        self.assertEqual(first_call_args['trade_size'], 50)
        self.assertEqual(first_call_args['max_size'], 125)
        self.assertEqual(first_call_args['param_type'], 'max_aggressive')
        
        # Verify the second call (Election)
        # trade_size = max(int(100 * 0.25), 50) = 50
        # max_size = max(int(300 * 0.25), 50 * 2) = 100
        second_call_args = mock_add.call_args_list[1][1]
        self.assertEqual(second_call_args['condition_id'], '4')
        self.assertEqual(second_call_args['trade_size'], 50)
        self.assertEqual(second_call_args['max_size'], 100)
        self.assertEqual(second_call_args['param_type'], 'aggressive')

if __name__ == '__main__':
    unittest.main()
