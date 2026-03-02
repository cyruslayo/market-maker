import sqlite3
import pandas as pd

def analyze_trades():
    print("Connecting to polymarket.db...\n")
    conn = sqlite3.connect('polymarket.db')
    
    # 1. View all trade logs
    df_trades = pd.read_sql_query("SELECT * FROM trade_logs ORDER BY timestamp DESC", conn)
    print("=== RECENT TRADES ===")
    if df_trades.empty:
        print("No trades logged yet.\n")
    else:
        print(df_trades[['timestamp', 'condition_id', 'side', 'price', 'size']].head(10).to_string(), "\n")

    # 2. Calculate Total Volume
    if not df_trades.empty:
        total_volume = df_trades['size'].sum()
        print(f"Total Traded Volume: ${total_volume:.2f}")

    # 3. View Current Configured Markets
    df_markets = pd.read_sql_query("SELECT question, max_size, trade_size FROM target_markets", conn)
    print("\n=== ACTIVE MARKETS ===")
    if df_markets.empty:
        print("No active markets. Add some using: python manage_markets.py add")
    else:
        print(df_markets.to_string())

    conn.close()

if __name__ == "__main__":
    analyze_trades()
