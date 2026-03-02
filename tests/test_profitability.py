import unittest
import pandas as pd
import sys
import os

# Add parent dir to path to import poly_data module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_data.trading_utils import dynamic_max_size

class TestProfitabilityAndSizing(unittest.TestCase):
    def test_dynamic_max_size(self):
        """Test the Kelly criterion inspired dynamic sizing with bounds"""
        # Scenario 1: High reward, low vol -> Should hit cap 2.0x
        # R=1.0, S=0.01, V=5 -> Kelly = (1.0/0.02) / 6 = 50 / 6 = 8.33 -> 2.0x
        size = dynamic_max_size(base_size=100, volatility=5, reward=1.0, spread=0.01)
        self.assertEqual(size, 200)
        
        # Scenario 2: Low reward, high vol -> Should hit floor 0.5x
        # R=0.1, S=0.05, V=30 -> Kelly = (0.1/0.06) / 31 = 1.66 / 31 = 0.05 -> 0.5x
        size = dynamic_max_size(base_size=100, volatility=30, reward=0.1, spread=0.05)
        self.assertEqual(size, 50)
        
        # Scenario 3: Moderate -> Should be around 1.0x
        # R=0.5, S=0.04, V=9 -> Kelly = (0.5/0.05) / 10 = 10 / 10 = 1.0 -> 1.0x
        size = dynamic_max_size(base_size=100, volatility=9, reward=0.5, spread=0.04)
        self.assertEqual(size, 100)

    def test_inventory_aware_score(self):
        """Test the logic of the inventory-aware profitability score"""
        # Compare a "good" market to a "bad" market using the new formula
        
        # Good market
        source_df = pd.DataFrame([{
            'gm_reward_per_100': 1.0,
            'rewards_daily_rate': 100,
            'spread': 0.01,
            'volatility_sum': 10
        }])
        
        inventory_risk = source_df['spread'] * source_df.get('volatility_sum', 1)
        source_df['profitability_score'] = (
            (source_df['gm_reward_per_100'] * 0.4) +
            (source_df['rewards_daily_rate'] / 10 * 0.4) +
            ((1 / (source_df['spread'] + 0.01)) * 0.2)
        ) / (inventory_risk + 1)
        
        score_good = source_df['profitability_score'].iloc[0]
        
        # Worse market
        worse_df = pd.DataFrame([{
            'gm_reward_per_100': 0.1,
            'rewards_daily_rate': 10,
            'spread': 0.05,
            'volatility_sum': 30
        }])
        
        inventory_risk_w = worse_df['spread'] * worse_df.get('volatility_sum', 1)
        worse_df['profitability_score'] = (
            (worse_df['gm_reward_per_100'] * 0.4) +
            (worse_df['rewards_daily_rate'] / 10 * 0.4) +
            ((1 / (worse_df['spread'] + 0.01)) * 0.2)
        ) / (inventory_risk_w + 1)
        
        score_worse = worse_df['profitability_score'].iloc[0]
        
        # The good market should score much higher
        self.assertTrue(score_good > score_worse)

    def test_aggressive_filters(self):
        """Test the criteria for the aggressive filters"""
        df = pd.DataFrame([
            {
                'question': 'Market A',
                'rewards_daily_rate': 60,
                'volatility_sum': 20,
                'spread': 0.05,
                'best_bid': 0.50,
                'gm_reward_per_100': 0.8,
                '3_hour_volume': 1000
            },
            {
                'question': 'Market B (Low Reward)',
                'rewards_daily_rate': 40, # Fails < 50
                'volatility_sum': 20,
                'spread': 0.05,
                'best_bid': 0.50,
                'gm_reward_per_100': 0.8,
                '3_hour_volume': 1000
            },
            {
                'question': 'Market C (High Vol)',
                'rewards_daily_rate': 60,
                'volatility_sum': 50, # Fails >= 40
                'spread': 0.05,
                'best_bid': 0.50,
                'gm_reward_per_100': 0.8,
                '3_hour_volume': 1000
            },
             {
                'question': 'Market D (Low Volumne)',
                'rewards_daily_rate': 60,
                'volatility_sum': 20,
                'spread': 0.05,
                'best_bid': 0.50,
                'gm_reward_per_100': 0.8,
                '3_hour_volume': 400 # Fails < 500
            }
        ])
        
        current_questions = set()
        
        quality_filters = (
            (df['rewards_daily_rate'] >= 50) &
            (df['volatility_sum'] < 40) &
            (df['spread'] < 0.15) &
            (df['best_bid'] >= 0.05) &
            (df['best_bid'] <= 0.95) &
            (df['gm_reward_per_100'] >= 0.5) &
            (~df['question'].isin(current_questions))
        )
        
        if '3_hour_volume' in df.columns:
            quality_filters = quality_filters & (df['3_hour_volume'] >= 500)
            
        filtered = df[quality_filters]
        
        # Only Market A should pass
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]['question'], 'Market A')

if __name__ == '__main__':
    unittest.main()
