#!/usr/bin/env python3
"""
Alpha Vantage API Diagnostic Tool
Run this to check if your API key is working correctly
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv()

# Import after dotenv is loaded
from data_fetcher import DataFetcher
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("=" * 70)
    print("ALPHA VANTAGE API DIAGNOSTIC")
    print("=" * 70)

    # Check environment
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        print("\n❌ ERROR: ALPHA_VANTAGE_API_KEY not found in environment!")
        print("   Make sure you have a .env file with your API key")
        return 1

    print(f"\n✓ API Key found: {api_key[:8]}...{api_key[-4:]}")

    # Initialize fetcher
    fetcher = DataFetcher()

    # Test stock data
    print("\n" + "-" * 70)
    print("TEST 1: Fetching Stock Data for AAPL")
    print("-" * 70)

    stock_data = fetcher.fetch_stock_data('AAPL', period='5d')
    if stock_data is not None and not stock_data.empty:
        print(f"✓ SUCCESS: Retrieved {len(stock_data)} days of stock data")
        print(f"  Latest date: {stock_data.iloc[-1]['Date']}")
        print(f"  Latest close: ${stock_data.iloc[-1]['Close']:.2f}")
    else:
        print("❌ FAILED: No stock data returned")
        return 1

    # Test current price
    print("\n" + "-" * 70)
    print("TEST 2: Fetching Current Price for AAPL")
    print("-" * 70)

    current_price = fetcher.get_current_stock_price('AAPL')
    if current_price:
        print(f"✓ SUCCESS: Current price ${current_price:.2f}")
    else:
        print("❌ FAILED: Could not get current price")
        return 1

    # Test options data
    print("\n" + "-" * 70)
    print("TEST 3: Fetching Options Data for AAPL")
    print("-" * 70)

    options_data = fetcher.fetch_options_data('AAPL')
    if options_data:
        total_calls = sum(len(chains['calls']) for chains in options_data.values())
        total_puts = sum(len(chains['puts']) for chains in options_data.values())
        print(f"✓ SUCCESS: Retrieved options data")
        print(f"  Expirations: {len(options_data)}")
        print(f"  Total calls: {total_calls}")
        print(f"  Total puts: {total_puts}")
        print(f"  Total contracts: {total_calls + total_puts}")

        # Check for Greeks
        first_exp = list(options_data.keys())[0]
        sample = options_data[first_exp]['calls'].iloc[0]
        has_greeks = 'delta' in sample and 'gamma' in sample
        print(f"  Greeks included: {'YES' if has_greeks else 'NO'}")
    else:
        print("❌ FAILED: No options data returned")
        return 1

    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED - API IS WORKING CORRECTLY")
    print("=" * 70)

    fetcher.close_session()
    return 0

if __name__ == "__main__":
    sys.exit(main())
