#!/usr/bin/env python3
import subprocess
import time
import argparse
import sys
import os

scenarios = [
    "normal_trending",
    "flash_crash",
    "low_volume_trap",
    "correlated_crash",
    "max_aggressive_sizing"
]

def run_papertrade(hours=48):
    print("=" * 60)
    print(f"STARTING PAPER TRADING GAUNTLET ({hours} HOURS)")
    print("=" * 60)
    print("The bot will run against the live polymarket order book.")
    print("This will test the new protective bounds over a long period:")
    for s in scenarios:
        print(f" - {s}")
    
    cmd = [sys.executable, "paper_main.py"]
    
    print("\nStarting process. Press Ctrl+C to stop early and view the report.")
    try:
        process = subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Run for specified hours
        time.sleep(hours * 3600)
        
        print(f"\nCompleted {hours} hours of paper trading.")
        process.terminate()
        process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping paper trade gauntlet early...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the 48-hour paper trading gauntlet to validate new quoting and risk strategies.")
    parser.add_argument("--hours", type=float, default=48.0, help="Hours to run paper trading.")
    args = parser.parse_args()
    
    run_papertrade(args.hours)
