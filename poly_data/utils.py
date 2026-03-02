import pandas as pd
from poly_data.db_utils import get_db_data
import os
from dotenv import load_dotenv

def get_sheet_df():
    """
    Legacy wrapper function to maintain compatibility with existing market getters.
    Now routes completely through the embedded SQLite database.
    """
    load_dotenv()
    
    # Still respect the paper-trading mock toggle if they want hardcoded dummy data without a DB
    if os.getenv("MOCK_SHEETS", "false").lower() == "true":
        print("Mocking SQLite Data for Paper Trading override")
        
        # MOCK SELECTED MARKETS
        df_selected = pd.DataFrame([
            {
                'question': 'Will OpenAI release GPT-5 before 2026?',
                'max_size': 1000,
                'trade_size': 100,
                'param_type': 'standard',
                'comments': 'Mock market'
            }
        ])
        
        # MOCK ALL MARKETS (Crucial for condition_id extraction)
        df_all = pd.DataFrame([
            {
                'question': 'Will OpenAI release GPT-5 before 2026?',
                'condition_id': '0xb96f8c42bda63901b000851ec6fc1564f061d40dc7802b1f0907409af567ef40',
                'token1': '0x534c0e0e13768452f111eeb8055bf0dfb3eb6c3aa07212ebfbdd10c0bfd91e6b', # YES
                'token2': '0xbb25b7a0f7962c07ef248ba7fed64e56def9ebbb8d56ba10fa315ffabfc87611', # NO
                'neg_risk': 'FALSE'
            }
        ])
        
        # MOCK HYPERPARAMETERS
        hyperparams = {
            'MockMarketConfig': {
                'spread': 0.05
            }
        }
        
        df_merged = df_selected.merge(df_all, on='question', how='left')
        return df_merged, hyperparams

    try:
        df, hyperparams = get_db_data()
        print(f"Loaded {len(df)} markets and {len(hyperparams.keys())} configuration protocols from SQLite")
        return df, hyperparams
    except Exception as e:
        print(f"Critical Error: Failed to load from SQLite. Did you run `python manage_markets.py init`? Error: {e}")
        return pd.DataFrame(), {}