#!/usr/bin/env python3
"""
Update Selected Markets: Remove outdated markets and replace with better options.
Supports filtering by minimum daily reward (--min-reward) or profitability-based selection.
"""

import pandas as pd
from data_updater.data_updater import get_spreadsheet
from gspread_dataframe import set_with_dataframe
from dotenv import load_dotenv
from datetime import datetime
import argparse
import os
import sys

# Add parent directory to path to allow importing from poly_data
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from poly_data.db_utils import get_discovery_markets, get_target_markets, add_market, remove_market

load_dotenv()

def compute_profitability_score(df):
    """
    Calculate Inventory-Aware Profitability Score (Fix L1 - deduplication).
    Rewards moderate volatility and tight spreads.
    """
    # Guard against missing columns
    spread = df.get('spread', 0.1)
    volatility = df.get('volatility_sum', 1)
    gm_reward = df.get('gm_reward_per_100', 0)
    daily_reward = df.get('rewards_daily_rate', 0)
    
    inventory_risk = spread * volatility
    score = (
        (gm_reward * 0.4) +
        (daily_reward / 10 * 0.4) +
        ((1 / (spread + 0.01)) * 0.2)
    ) / (inventory_risk + 1)
    return score

def update_selected_markets(min_daily_reward=None, max_markets=None, replace_existing=False):
    """
    Remove outdated markets and replace with better options.
    
    Args:
        min_daily_reward: If set, filter markets by minimum daily reward (in dollars)
        max_markets: Maximum number of markets to select (default: 5-6 for profitability, 10 for high reward)
        replace_existing: If True, replace all existing markets. If False, append.
    """
    CORRELATION_GROUPS = {
        'us_politics': ['election', 'trump', 'biden', 'democrat', 'republican', 'harris'],
        'crypto':      ['bitcoin', 'ethereum', 'btc', 'eth', 'crypto'],
        'macro':       ['fed', 'inflation', 'cpi', 'rate hike'],
    }
    MAX_EXPOSURE_PER_GROUP = 0.35  # No more than 35% of capital in correlated markets
    
    print("=" * 100)
    print("UPDATING SELECTED MARKETS")
    print("=" * 100)
    print()
    
    print(f"Connecting to SQLite database...")
    
    # Load current Selected Markets from SQLite
    current_df = get_target_markets()
    
    # Handle empty / missing columns (compatibility)
    if current_df.empty:
        print("Target Markets table is empty. Starting fresh.")
        current_df = pd.DataFrame(columns=['condition_id', 'question', 'token1', 'token2', 'max_size', 'trade_size', 'param_type', 'neg_risk'])
    
    # Ensure rationale column exists for existing markets
    if 'rationale' not in current_df.columns:
        current_df['rationale'] = ''
    
    print(f"Current markets: {len(current_df)}")
    if len(current_df) > 0:
        print("\nCurrent list:")
        for i, row in current_df.iterrows():
            print(f"  {i+1}. {row.get('question', 'N/A')[:70]}")
    print()
    
    # Fix L2: Removed outdated dead-date cleanup logic (Nov 2024)
    # Rationale: Logic was hardcoded and no longer relevant.
    
    print(f"\nMarkets after cleanup: {len(current_df)}")
    
    # Determine selection mode
    if min_daily_reward is not None:
        # HIGH REWARD MODE: Filter by minimum daily reward
        print(f"\n{'=' * 100}")
        print(f"HIGH REWARD MODE: Filtering by rewards_daily_rate >= ${min_daily_reward}")
        print("=" * 100)
        
        # Load All Markets from SQLite
        print("\nLoading markets from SQLite 'all_markets' table...")
        source_df = get_discovery_markets()
        
        if source_df.empty:
            print("❌ All Markets sheet is empty!")
            return
        
        print(f"✓ Loaded {len(source_df)} markets from All Markets\n")
        
        # Convert numeric columns
        numeric_cols = ['rewards_daily_rate', 'gm_reward_per_100', 'volatility_sum', 'spread', 
                       'best_bid', 'best_ask', 'min_size', '3_hour']
        for col in numeric_cols:
            if col in source_df.columns:
                source_df[col] = pd.to_numeric(source_df[col], errors='coerce')
        
        # Filter for high reward markets
        print(f"Filtering markets with rewards_daily_rate >= ${min_daily_reward}...")
        
        # Calculate Inventory-Aware Profitability Score (Fix L1)
        source_df['profitability_score'] = compute_profitability_score(source_df)
        
        # Get currently selected question names
        current_questions = set(current_df['question'].tolist()) if len(current_df) > 0 else set()
        
        # Applying aggressive filters
        quality_filters = (
            (source_df['rewards_daily_rate'] >= min_daily_reward) &
            (source_df['volatility_sum'] < 40) &
            (source_df['spread'] < 0.15) &
            (source_df['best_bid'] >= 0.05) &
            (source_df['best_bid'] <= 0.95) &
            (source_df['gm_reward_per_100'] >= 0.5) &
            (~source_df['question'].isin(current_questions))
        )
        
        # Note: '3_hour' in the db currently represents 3-hour volatility, not volume. 
        # Checking for '3_hour_volume' to avoid filtering out all markets if volume isn't available yet.
        if '3_hour_volume' in source_df.columns:
            quality_filters = quality_filters & (source_df['3_hour_volume'] >= 500)
            
        filtered = source_df[quality_filters].copy()
        
        if len(filtered) == 0:
            print(f"❌ No markets found matching criteria")
            return
            
        print(f"✓ Found {len(filtered)} high-reward markets\n")
        
        # Sort by profitability score (descending)
        filtered = filtered.sort_values('profitability_score', ascending=False)
        
        # Get currently selected question names (only filter if not replacing)
        if not replace_existing:
            current_questions = set(current_df['question'].tolist()) if len(current_df) > 0 else set()
            filtered = filtered[~filtered['question'].isin(current_questions)].copy()
        
        # Select top markets
        target_count = max_markets if max_markets else 10
        if replace_existing:
            needed = min(target_count, len(filtered))  # Take up to target_count
        else:
            needed = max(0, min(target_count - len(current_df), len(filtered)))
        
    else:
        # PROFITABILITY MODE: Original logic
        print(f"\n{'=' * 100}")
        print("PROFITABILITY MODE: Selecting markets by reward/volatility ratio")
        print("=" * 100)
        
        # Load All Markets from SQLite
        print("\nLoading markets from SQLite 'all_markets' table...")
        source_df = get_discovery_markets()
        
        # Convert numeric columns
        numeric_cols = ['gm_reward_per_100', 'volatility_sum', 'spread', 'rewards_daily_rate',
                       'best_bid', 'best_ask', '3_hour']
        for col in numeric_cols:
            if col in source_df.columns:
                source_df[col] = pd.to_numeric(source_df[col], errors='coerce')
        
        # Calculate Inventory-Aware Profitability Score (Fix L1)
        source_df['profitability_score'] = compute_profitability_score(source_df)
        
        # Get currently selected question names
        current_questions = set(current_df['question'].tolist()) if len(current_df) > 0 else set()
        
        # Aggressive filters
        quality_filters = (
            (source_df['rewards_daily_rate'] >= 50) &
            (source_df['volatility_sum'] < 40) &
            (source_df['spread'] < 0.15) &
            (source_df['best_bid'] >= 0.05) &
            (source_df['best_bid'] <= 0.95) &
            (source_df['gm_reward_per_100'] >= 0.5) &
            (~source_df['question'].isin(current_questions))
        )
        
        # Note: '3_hour' in the db currently represents 3-hour volatility, not volume. 
        # Checking for '3_hour_volume' to avoid filtering out all markets if volume isn't available yet.
        if '3_hour_volume' in source_df.columns:
            quality_filters = quality_filters & (source_df['3_hour_volume'] >= 500)
            
        filtered = source_df[quality_filters].copy()
        
        # Sort by profitability score
        filtered = filtered.sort_values('profitability_score', ascending=False)
        
        # Select top markets to replace (aim for 5-6 total markets)
        target_total = max_markets if max_markets else 5
        needed = max(0, target_total - len(current_df))
    
    if needed > 0:
        print(f"\n{'=' * 100}")
        print(f"ADDING UP TO {needed} NEW MARKETS:")
        print("=" * 100)
        
        # Prepare new market data
        new_markets = []
        current_portfolio = current_df.to_dict('records')
        total_capital = sum(float(m.get('max_size', 0)) for m in current_portfolio if pd.notna(m.get('max_size')))
        
        for _, row in filtered.iterrows():
            if len(new_markets) >= needed:
                break
            reward = row.get('gm_reward_per_100', 0)
            volatility = row.get('volatility_sum', 0)
            daily_reward = row.get('rewards_daily_rate', 0)
            min_size = row.get('min_size', 50)
            
            # Tiered sizing based on conviction
            if daily_reward >= 300 and volatility < 20:
                trade_size = 200
                max_size = 500
                param_type = 'max_aggressive'
            elif daily_reward >= 150:
                trade_size = 100
                max_size = 300
                param_type = 'aggressive'
            elif daily_reward >= 75:
                trade_size = 60
                max_size = 150
                param_type = 'moderate'
            else:
                trade_size = 30
                max_size = 80
                param_type = 'default'
            
            # Fix H3: Ramp-up (25% size) ONLY if market is actually new.
            # If it's already in the DB, it has graduated beyond the ramp-up phase.
            is_new = row['condition_id'] not in current_df['condition_id'].values if not current_df.empty else True
            
            if is_new:
                print(f"   🌱 New market detected: applying 25% ramp-up size")
                trade_size = max(int(trade_size * 0.25), min_size)
                max_size = max(int(max_size * 0.25), trade_size * 2)
            else:
                print(f"   📈 Existing market detected: using full {param_type} sizing")

            # Ensure trade_size >= min_size
            if trade_size < min_size:
                trade_size = min_size
                max_size = max(trade_size * 2, max_size)
                
            # Check correlation limits before adding
            projected_total_capital = total_capital + max_size
            is_valid = True
            
            if projected_total_capital > 0:
                for group, keywords in CORRELATION_GROUPS.items():
                    if any(kw in str(row['question']).lower() for kw in keywords):
                        group_exposure = max_size + sum(
                            float(m.get('max_size', 0)) for m in current_portfolio 
                            if pd.notna(m.get('max_size')) and m.get('max_size') != '' and
                               any(kw in str(m.get('question', '')).lower() for kw in keywords)
                        )
                        # Avoid instant rejection when portfolio is small by assuming a $2500 minimum intended portfolio size
                        effective_total = max(projected_total_capital, 2500)
                        if group_exposure / effective_total > MAX_EXPOSURE_PER_GROUP:
                            is_valid = False
                            print(f"Skipping {row['question'][:50]}... due to correlation limit on {group}")
                            break
                            
            if not is_valid:
                continue
                
            total_capital += max_size
            current_portfolio.append({'question': row['question'], 'max_size': max_size})
            
            # Generate detailed rationale
            rationale_parts = []
            
            # Daily reward (priority for high reward mode)
            if daily_reward >= 200:
                rationale_parts.append(f"Very high daily reward (${daily_reward:.0f}/day)")
            elif daily_reward >= 100:
                rationale_parts.append(f"High daily reward (${daily_reward:.0f}/day)")
            elif daily_reward >= 50:
                rationale_parts.append(f"Good daily reward (${daily_reward:.0f}/day)")
            elif daily_reward >= 10:
                rationale_parts.append(f"Daily reward (${daily_reward:.0f}/day)")
            
            # Percentage reward
            if reward >= 2.0:
                rationale_parts.append(f"High reward ({reward:.2f}% daily)")
            elif reward >= 1.0:
                rationale_parts.append(f"Good reward ({reward:.2f}% daily)")
            
            # Volatility
            if volatility < 10:
                rationale_parts.append(f"Low volatility ({volatility:.1f}) - safer")
            elif volatility < 15:
                rationale_parts.append(f"Moderate volatility ({volatility:.1f})")
            elif volatility < 25:
                rationale_parts.append(f"Higher volatility ({volatility:.1f}) - aggressive")
            
            # Spread
            spread_val = row.get('spread', 0)
            if spread_val < 0.02:
                rationale_parts.append("Tight spread - competitive pricing")
            elif spread_val < 0.05:
                rationale_parts.append("Reasonable spread")
            
            # Price range
            if 0.15 <= row.get('best_bid', 0) <= 0.85:
                rationale_parts.append("Price in optimal range (0.15-0.85)")
            
            # Profitability score (if available)
            if 'profitability_score' in row and pd.notna(row['profitability_score']):
                profitability_score = row['profitability_score']
                if profitability_score > 0.15:
                    rationale_parts.append("Excellent risk/reward ratio")
                elif profitability_score > 0.10:
                    rationale_parts.append("Good risk/reward ratio")
            
            rationale = " | ".join(rationale_parts) if rationale_parts else f"Reward: {reward:.2f}%, Vol: {volatility:.1f}"
            
            # Build comments
            if 'profitability_score' in row and pd.notna(row['profitability_score']):
                comments = f"Reward: {reward:.2f}%, Vol: {volatility:.1f}, Score: {row['profitability_score']:.3f}"
            else:
                comments = f"Reward: ${daily_reward:.0f}/day, Vol: {volatility:.1f}, Spread: {spread_val:.3f}"
            
            new_markets.append({
                'question': row['question'],
                'condition_id': row['condition_id'],
                'token1': row['token1'],
                'token2': row['token2'],
                'max_size': max_size,
                'trade_size': trade_size,
                'param_type': param_type,
                'neg_risk': row.get('neg_risk', False)
            })
            
            print(f"\n{len(new_markets)}. {row['question'][:75]}")
            if min_daily_reward:
                print(f"   Daily Reward: ${daily_reward:.2f} | Volatility: {volatility:.1f} | Spread: {spread_val:.4f}")
            else:
                print(f"   Reward: {reward:.2f}% | Volatility: {volatility:.1f} | "
                      f"Score: {row.get('profitability_score', 0):.3f}")
            print(f"   Price: ${row.get('best_bid', 0):.3f}-${row.get('best_ask', 0):.3f} | "
                  f"Daily Rate: ${daily_reward:.0f}")
            print(f"   Trade Size: ${trade_size} | Max Size: ${max_size} | Param: {param_type}")
        
        # Combine with existing or replace
        new_markets_df = pd.DataFrame(new_markets)
        if replace_existing:
            updated_df = new_markets_df
            print(f"\n✓ Replacing all markets with {len(new_markets)} high-reward markets")
        else:
            updated_df = pd.concat([current_df, new_markets_df], ignore_index=True)
            print(f"\n✓ Added {len(new_markets)} new markets (total: {len(updated_df)})")
    else:
        if replace_existing:
            updated_df = pd.DataFrame(columns=['question', 'max_size', 'trade_size', 'param_type', 'comments', 'rationale'])
            print("\nNo markets found matching criteria")
        else:
            updated_df = current_df
            print("\nNo replacements needed - already have enough good markets")
    
    # Ensure rationale and comments columns exist to avoid KeyErrors
    for col in ['rationale', 'comments']:
        if col not in updated_df.columns:
            updated_df[col] = ''
    
    # Update existing markets with rationale if missing
    # Merge with vol_df to get current metrics for existing markets
    if len(updated_df) > 0:
        # Get questions that need rationale
        questions_needing_rationale = updated_df[
            (updated_df['rationale'].isna()) | (updated_df['rationale'] == '')
        ]['question'].tolist()
        
        if len(questions_needing_rationale) > 0:
            # Match with vol_df to get metrics
            for idx, row in updated_df.iterrows():
                if pd.isna(row.get('rationale', '')) or row.get('rationale', '') == '':
                    # Find matching market in source_df
                    match = source_df[source_df['question'] == row['question']]
                    if len(match) > 0:
                        m = match.iloc[0]
                        reward = m['gm_reward_per_100']
                        volatility = m['volatility_sum']
                        spread = m['spread']
                        
                        rationale_parts = []
                        if reward >= 2.0:
                            rationale_parts.append(f"High reward ({reward:.2f}% daily)")
                        elif reward >= 1.0:
                            rationale_parts.append(f"Good reward ({reward:.2f}% daily)")
                        
                        if volatility < 10:
                            rationale_parts.append(f"Low volatility ({volatility:.1f}) - safer")
                        elif volatility < 15:
                            rationale_parts.append(f"Moderate volatility ({volatility:.1f})")
                        
                        if spread < 0.02:
                            rationale_parts.append("Tight spread - competitive pricing")
                        elif spread < 0.05:
                            rationale_parts.append("Reasonable spread")
                        
                        if 0.15 <= m['best_bid'] <= 0.85:
                            rationale_parts.append("Price in optimal range (0.15-0.85)")
                        
                        if m['rewards_daily_rate'] >= 10:
                            rationale_parts.append(f"High daily rate (${m['rewards_daily_rate']:.0f}/day)")
                        
                        profitability_score = reward / (volatility + 1) if pd.notna(volatility) else 0
                        if profitability_score > 0.15:
                            rationale_parts.append("Excellent risk/reward ratio")
                        elif profitability_score > 0.10:
                            rationale_parts.append("Good risk/reward ratio")
                        
                        updated_df.at[idx, 'rationale'] = " | ".join(rationale_parts) if rationale_parts else f"Reward: {reward:.2f}%, Vol: {volatility:.1f}"
    
    # Ensure all required columns are present for SQLite sync and display
    required_cols = ['condition_id', 'question', 'token1', 'token2', 'max_size', 'trade_size', 'param_type', 'neg_risk', 'rationale']
    for col in required_cols:
        if col not in updated_df.columns:
            updated_df[col] = ''
    
    # Reorder columns
    updated_df = updated_df[required_cols]
    
    # Update the SQLite database
    print(f"\n{'=' * 100}")
    print("UPDATING SQLite DATABASE...")
    print("=" * 100)
    
    try:
        # If replace_existing, we should probably clear the table first
        # But for safety, we'll just remove markets that are no longer in updated_df
        # Or better yet, use a clear/batch insert if supported by db_utils
        
        if replace_existing:
            # Simple way: get current, remove all
            current_ids = get_target_markets()['condition_id'].tolist()
            for cid in current_ids:
                remove_market(cid)
            print(f"✓ Cleared existing markets (replace=True)")

        # Sync updated_df to target_markets
        for _, row in updated_df.iterrows():
            add_market(
                condition_id=row['condition_id'],
                question=row['question'],
                token1=row['token1'],
                token2=row['token2'],
                max_size=row['max_size'],
                trade_size=row['trade_size'],
                param_type=row['param_type'],
                neg_risk=row['neg_risk'] == 'TRUE' if isinstance(row['neg_risk'], str) else bool(row['neg_risk'])
            )
        
        print(f"✓ Successfully updated SQLite with {len(updated_df)} target markets")
    except Exception as e:
        print(f"Error updating SQLite: {e}")
        raise
    
    print(f"\n✓ SUCCESS! Updated Selected Markets")
    print(f"\nFinal market list ({len(updated_df)} markets):")
    for i, row in updated_df.iterrows():
        print(f"  {i+1}. {row['question'][:70]}")
        print(f"     Trade: ${row['trade_size']}, Max: ${row['max_size']}, Param: {row['param_type']}")
        if 'rationale' in row and pd.notna(row['rationale']) and row['rationale'] != '':
            print(f"     Rationale: {row['rationale']}")
        elif 'comments' in row and pd.notna(row['comments']):
            print(f"     {row['comments']}")
        print()
    
    print("\nThe bot will start trading these markets within 60 seconds.")
    print("Monitor with: tail -f main.log")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Update Selected Markets with profitable markets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: Profitability-based selection (5-6 markets)
  python update_selected_markets.py
  
  # High reward mode: Select markets with >= $100/day
  python update_selected_markets.py --min-reward 100
  
  # High reward mode: Select top 15 markets with >= $150/day, replace existing
  python update_selected_markets.py --min-reward 150 --max-markets 15 --replace
        """
    )
    parser.add_argument('--min-reward', type=float, default=None,
                       help='Minimum daily reward in dollars (enables high reward mode)')
    parser.add_argument('--max-markets', type=int, default=None,
                       help='Maximum number of markets to select')
    parser.add_argument('--replace', action='store_true',
                       help='Replace all existing markets instead of appending')
    
    args = parser.parse_args()
    
    update_selected_markets(
        min_daily_reward=args.min_reward,
        max_markets=args.max_markets,
        replace_existing=args.replace
    )


