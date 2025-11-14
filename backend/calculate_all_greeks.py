"""
Calculate Greeks for all option prices in the database
"""
from sqlalchemy.orm import Session
from models import SessionLocal, Symbol, StockPrice, OptionContract, OptionPrice
from calculations import OptionsCalculator
from data_fetcher import DataFetcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_greeks_for_all_options():
    """Calculate Greeks for all option prices"""
    db = SessionLocal()
    calculator = OptionsCalculator()
    fetcher = DataFetcher()

    try:
        # Get all active symbols
        symbols = db.query(Symbol).filter(Symbol.is_active == True).all()

        total_updated = 0
        total_contracts = 0

        for symbol_obj in symbols:
            logger.info(f"Processing {symbol_obj.symbol}...")

            # Get current stock price
            stock_price = fetcher.get_current_stock_price(symbol_obj.symbol)

            if not stock_price:
                # Try from database
                latest_price = db.query(StockPrice).filter(
                    StockPrice.symbol_id == symbol_obj.id
                ).order_by(StockPrice.timestamp.desc()).first()

                if latest_price:
                    stock_price = latest_price.close_price
                else:
                    logger.warning(f"No stock price found for {symbol_obj.symbol}, skipping")
                    continue

            logger.info(f"  Stock price: ${stock_price:.2f}")

            # Get all active contracts for this symbol
            contracts = db.query(OptionContract).filter(
                OptionContract.symbol_id == symbol_obj.id,
                OptionContract.is_active == True
            ).all()

            symbol_updated = 0

            for contract in contracts:
                total_contracts += 1

                # Get the most recent price for this contract
                latest_option_price = db.query(OptionPrice).filter(
                    OptionPrice.contract_id == contract.id
                ).order_by(OptionPrice.timestamp.desc()).first()

                if not latest_option_price:
                    continue

                # Skip if no IV or IV is too low
                if not latest_option_price.implied_volatility or latest_option_price.implied_volatility < 0.001:
                    continue

                # Skip if no last price
                if not latest_option_price.last_price or latest_option_price.last_price <= 0:
                    continue

                try:
                    # Calculate time to expiry
                    time_to_expiry = calculator.calculate_time_to_expiry(contract.expiry_date)

                    # Calculate Greeks
                    greeks = calculator.calculate_greeks(
                        stock_price=stock_price,
                        strike_price=contract.strike_price,
                        time_to_expiry=time_to_expiry,
                        volatility=latest_option_price.implied_volatility,
                        option_type=contract.option_type
                    )

                    # Update the option price record
                    latest_option_price.delta = greeks['delta']
                    latest_option_price.gamma = greeks['gamma']
                    latest_option_price.theta = greeks['theta']
                    latest_option_price.vega = greeks['vega']
                    latest_option_price.rho = greeks['rho']

                    # Calculate intrinsic and time value
                    intrinsic = calculator.calculate_intrinsic_value(
                        stock_price, contract.strike_price, contract.option_type
                    )
                    latest_option_price.intrinsic_value = intrinsic
                    latest_option_price.time_value = calculator.calculate_time_value(
                        latest_option_price.last_price, intrinsic
                    )

                    symbol_updated += 1
                    total_updated += 1

                    # Commit every 100 contracts to avoid memory issues
                    if total_updated % 100 == 0:
                        db.commit()
                        logger.info(f"  Updated {total_updated} contracts so far...")

                except Exception as e:
                    logger.error(f"  Error calculating Greeks for contract {contract.id}: {str(e)}")
                    continue

            # Commit after each symbol
            db.commit()
            logger.info(f"  Updated {symbol_updated} contracts for {symbol_obj.symbol}")

        logger.info(f"\n" + "="*60)
        logger.info(f"COMPLETE: Updated Greeks for {total_updated}/{total_contracts} contracts")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Error in Greeks calculation: {str(e)}")
        db.rollback()
    finally:
        db.close()
        fetcher.close_session()

if __name__ == "__main__":
    logger.info("Starting Greeks calculation for all options...")
    calculate_greeks_for_all_options()
    logger.info("Greeks calculation complete!")
