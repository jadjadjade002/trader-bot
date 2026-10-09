"""Isolated demo tester warm-up. Never production/VM or live trading."""
import argparse
from research.run_v23_tuning import execute

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    # One day can complete before native-agent inventory observes its process.
    execute(args.prefix + "_smoke", start="2026.09.01", end="2026.10.01", timeout=180)
