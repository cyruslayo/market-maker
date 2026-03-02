import sys
import argparse
from poly_data.db_utils import init_db, add_market, remove_market, set_hyperparameter, get_db_data

def setup_argparse():
    parser = argparse.ArgumentParser(description="Manage Polymarket Target Markets in SQLite DB")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init DB Command
    subparsers.add_parser("init", help="Initialize the database schema")

    # Add Market Command
    parser_add = subparsers.add_parser("add", help="Add a new target market")
    parser_add.add_argument("condition_id", type=str, help="Market condition ID (0x...)")
    parser_add.add_argument("--question", type=str, required=True, help="Market question text")
    parser_add.add_argument("--token1", type=str, required=True, help="Token 1 ID (YES)")
    parser_add.add_argument("--token2", type=str, required=True, help="Token 2 ID (NO)")
    parser_add.add_argument("--max_size", type=float, default=1000.0, help="Max position size")
    parser_add.add_argument("--trade_size", type=float, default=100.0, help="Size per trade")
    parser_add.add_argument("--param_type", type=str, default="MockMarketConfig", help="Hyperparameter linking")
    parser_add.add_argument("--neg_risk", action="store_true", help="Is this a negative risk market?")

    # Remove Market Command
    parser_remove = subparsers.add_parser("remove", help="Remove a target market")
    parser_remove.add_argument("condition_id", type=str, help="Market condition ID to remove")

    # Set Hyperparameter Command
    parser_hyper = subparsers.add_parser("hyper", help="Set a hyperparameter")
    parser_hyper.add_argument("type", type=str, help="Config type (e.g., MockMarketConfig)")
    parser_hyper.add_argument("param", type=str, help="Parameter name (e.g., spread)")
    parser_hyper.add_argument("value", type=float, help="Parameter numeric value")

    # List Command
    subparsers.add_parser("list", help="List all active target markets and configs")

    return parser.parse_args()

def main():
    args = setup_argparse()

    if args.command == "init":
        init_db()
        print("Database initialized successfully.")
    
    elif args.command == "add":
        success = add_market(
            args.condition_id, args.question, args.token1, args.token2,
            args.max_size, args.trade_size, args.param_type, args.neg_risk
        )
        if success:
            print(f"Successfully added market: {args.condition_id}")
        else:
            print("Failed to add market. Check logs.")
            
    elif args.command == "remove":
        success = remove_market(args.condition_id)
        if success:
            print(f"Successfully removed market: {args.condition_id}")
        else:
            print(f"Market not found: {args.condition_id}")
            
    elif args.command == "hyper":
        set_hyperparameter(args.type, args.param, args.value)
        print(f"Successfully set {args.type}.{args.param} = {args.value}")
        
    elif args.command == "list":
        try:
            df, params = get_db_data()
            print("\n=== TARGET MARKETS ===")
            if df.empty:
                print("No markets found.")
            else:
                print(df[['condition_id', 'question', 'trade_size']].to_string())
                
            print("\n=== HYPERPARAMETERS ===")
            if not params:
                print("No hyperparameters found.")
            else:
                for type_name, config in params.items():
                    print(f"[{type_name}]")
                    for k, v in config.items():
                        print(f"  {k}: {v}")
        except Exception as e:
            print(f"Error fetching data (did you run 'init' first?): {e}")

if __name__ == "__main__":
    main()
