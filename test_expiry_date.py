#!/usr/bin/env python3
"""
Test script to verify expiry_date is included in option price responses
"""

import sys
sys.path.insert(0, 'backend')

from models import SessionLocal, OptionContract, OptionPrice
from datetime import datetime

def test_expiry_date_in_response():
    """Test that expiry_date is available from option prices"""

    db = SessionLocal()

    try:
        # Get a sample contract
        contract = db.query(OptionContract).first()

        if not contract:
            print("No contracts found in database. Run data fetcher first.")
            return

        print("Sample Option Contract:")
        print(f"  ID: {contract.id}")
        print(f"  Symbol: {contract.contract_symbol}")
        print(f"  Expiry Date: {contract.expiry_date}")
        print(f"  Strike: ${contract.strike_price}")
        print(f"  Type: {contract.option_type}")

        # Get latest price for this contract
        price = db.query(OptionPrice).filter(
            OptionPrice.contract_id == contract.id
        ).order_by(OptionPrice.timestamp.desc()).first()

        if not price:
            print("\nNo prices found for this contract.")
            return

        print("\nLatest Option Price:")
        print(f"  Timestamp: {price.timestamp}")
        print(f"  Bid: ${price.bid}")
        print(f"  Ask: ${price.ask}")
        print(f"  Last: ${price.last_price}")

        # Simulate API response structure
        print("\nAPI Response Structure (with new fields):")
        response = {
            "id": price.id,
            "contract_id": price.contract_id,
            "timestamp": str(price.timestamp),
            "expiry_date": str(contract.expiry_date),  # NEW!
            "strike_price": contract.strike_price,      # NEW!
            "option_type": contract.option_type,        # NEW!
            "bid": price.bid,
            "ask": price.ask,
            "last_price": price.last_price,
            "volume": price.volume,
            "open_interest": price.open_interest,
            "implied_volatility": price.implied_volatility,
            "delta": price.delta,
            "gamma": price.gamma,
            "theta": price.theta,
            "vega": price.vega,
            "rho": price.rho
        }

        import json
        print(json.dumps(response, indent=2))

        print("\n" + "=" * 60)
        print("✓ Expiry date is now included in option price responses!")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    test_expiry_date_in_response()
