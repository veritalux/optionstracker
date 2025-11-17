"""
IVolatility API Data Fetcher
Fetches stock and options data from IVolatility REST API
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import ivolatility as ivol
from sqlalchemy.orm import Session

from models import Symbol, StockPrice, OptionContract, OptionPrice, IVAnalysis, SessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key from environment
from dotenv import load_dotenv
load_dotenv()

IVOLATILITY_API_KEY = os.getenv('IVOLATILITY_API_KEY')
if not IVOLATILITY_API_KEY:
    logger.error("IVOLATILITY_API_KEY not found in environment variables")
    raise ValueError("IVOLATILITY_API_KEY is required")

# Configure IVolatility SDK
ivol.setLoginParams(apiKey=IVOLATILITY_API_KEY)

class IVolatilityDataFetcher:
    """Data fetcher using IVolatility API"""

    def __init__(self):
        self.session = None
        self.api_key = IVOLATILITY_API_KEY

    def get_session(self) -> Session:
        """Get database session"""
        if not self.session:
            self.session = SessionLocal()
        return self.session

    def close_session(self):
        """Close database session"""
        if self.session:
            self.session.close()
            self.session = None

    def add_symbol_to_watchlist(self, symbol: str, company_name: str = None) -> bool:
        """Add a symbol to the database and watchlist"""
        try:
            db = self.get_session()

            # Check if symbol already exists
            existing = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if existing:
                logger.info(f"Symbol {symbol} already exists")
                existing.is_active = True
                db.commit()
                return True

            # Get company info if not provided
            if not company_name:
                company_name = symbol.upper()

            # Create new symbol
            new_symbol = Symbol(
                symbol=symbol.upper(),
                company_name=company_name,
                sector="",
                is_active=True
            )

            db.add(new_symbol)
            db.commit()
            db.refresh(new_symbol)

            logger.info(f"Added symbol {symbol} to watchlist")
            return True

        except Exception as e:
            logger.error(f"Error adding symbol {symbol}: {str(e)}")
            db.rollback()
            return False

    def fetch_stock_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetch stock price data from IVolatility

        Args:
            symbol: Stock symbol
            days: Number of days of historical data to fetch

        Returns:
            DataFrame with stock price data or None on error
        """
        try:
            logger.info(f"Fetching stock data for {symbol} (last {days} days)")

            # Set up the API method
            getStockPrices = ivol.setMethod('/equities/eod/stock-prices')

            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)

            # Fetch data
            df = getStockPrices(
                symbol=symbol.upper(),
                **{
                    'from': from_date.strftime('%Y-%m-%d'),
                    'to': to_date.strftime('%Y-%m-%d')
                }
            )

            if df is None or df.empty:
                logger.warning(f"No stock data returned for {symbol}")
                return None

            # Rename columns to match our internal format
            df = df.rename(columns={
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })

            # Ensure Date is datetime
            df['Date'] = pd.to_datetime(df['Date'])
            df['Symbol'] = symbol.upper()

            # Sort by date
            df = df.sort_values('Date')

            logger.info(f"Fetched {len(df)} days of stock data for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            return None

    def fetch_options_chain(self, symbol: str, days_forward: int = 60) -> Optional[pd.DataFrame]:
        """
        Fetch options chain from IVolatility

        Args:
            symbol: Stock symbol
            days_forward: Number of days forward to get expirations

        Returns:
            DataFrame with options chain or None on error
        """
        try:
            logger.info(f"Fetching options chain for {symbol}")

            # Set up the API method
            getOptionsChain = ivol.setMethod('/equities/option-series')

            # Calculate date range
            today = datetime.now()
            expiry_end = today + timedelta(days=days_forward)

            # Fetch options chain
            df = getOptionsChain(
                symbol=symbol.upper(),
                expFrom=today.strftime('%Y-%m-%d'),
                expTo=expiry_end.strftime('%Y-%m-%d')
            )

            if df is None or df.empty:
                logger.warning(f"No options chain data returned for {symbol}")
                return None

            # Ensure expiration date is datetime
            df['expirationDate'] = pd.to_datetime(df['expirationDate'])

            logger.info(f"Fetched {len(df)} option contracts for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {str(e)}")
            return None

    def fetch_option_pricing(self, option_symbols: List[str]) -> Optional[pd.DataFrame]:
        """
        Fetch real-time pricing, IV, and Greeks for specific option contracts

        Args:
            option_symbols: List of option contract symbols (e.g., 'AAPL  251121C00270000')

        Returns:
            DataFrame with pricing and Greeks data or None on error
        """
        try:
            if not option_symbols:
                return None

            logger.info(f"Fetching pricing for {len(option_symbols)} option contracts")

            # Set up the API method for real-time options with IV
            getOptionPricing = ivol.setMethod('/equities/rt/options-rawiv')

            # Fetch pricing data (API accepts comma-separated symbols)
            # Process in batches of 50 to avoid URL length issues
            batch_size = 50
            all_data = []

            for i in range(0, len(option_symbols), batch_size):
                batch = option_symbols[i:i+batch_size]
                symbols_str = ','.join(batch)

                try:
                    df = getOptionPricing(symbols=symbols_str)
                    if df is not None and not df.empty:
                        all_data.append(df)
                except Exception as e:
                    logger.warning(f"Error fetching batch {i//batch_size + 1}: {str(e)}")
                    continue

                # Small delay between batches
                if i + batch_size < len(option_symbols):
                    time.sleep(0.5)

            if not all_data:
                logger.warning("No pricing data returned from API")
                return None

            # Combine all batches
            result_df = pd.concat(all_data, ignore_index=True) if len(all_data) > 1 else all_data[0]

            logger.info(f"Fetched pricing for {len(result_df)} option contracts")
            return result_df

        except Exception as e:
            logger.error(f"Error fetching option pricing: {str(e)}")
            return None

    def fetch_options_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        Fetch complete options data for a symbol with real-time pricing and Greeks

        Returns a dict organized by expiration date with calls and puts separated.
        """
        try:
            # Get the options chain
            chain_df = self.fetch_options_chain(symbol)

            if chain_df is None or chain_df.empty:
                return {}

            # Get unique expiration dates
            expirations = sorted(chain_df['expirationDate'].unique())

            options_data = {}

            # Fetch pricing for all contracts at once
            all_symbols = chain_df['OptionSymbol'].tolist()
            pricing_df = self.fetch_option_pricing(all_symbols)

            # Create a lookup dict for pricing data
            pricing_lookup = {}
            if pricing_df is not None and not pricing_df.empty:
                for _, row in pricing_df.iterrows():
                    pricing_lookup[row['symbol']] = row

            # Process each expiration date
            for exp_date in expirations[:6]:  # Limit to first 6 expirations
                exp_str = pd.to_datetime(exp_date).strftime('%Y-%m-%d')

                # Filter for this expiration
                exp_df = chain_df[chain_df['expirationDate'] == exp_date].copy()

                # Split into calls and puts
                calls = exp_df[exp_df['callPut'] == 'C'].copy()
                puts = exp_df[exp_df['callPut'] == 'P'].copy()

                # Format the data to match our expected structure
                def format_chain_data(df):
                    if df.empty:
                        return df

                    df = df.rename(columns={
                        'OptionSymbol': 'contractSymbol',
                        'strike': 'strike',
                        'expirationDate': 'expiry_date',
                        'callPut': 'option_type'
                    })

                    # Map C/P to call/put
                    df['option_type'] = df['option_type'].map({'C': 'call', 'P': 'put'})

                    # Merge pricing data
                    for idx, row in df.iterrows():
                        contract_symbol = row['contractSymbol']
                        pricing = pricing_lookup.get(contract_symbol, {})

                        df.at[idx, 'lastPrice'] = pricing.get('lastPrice', 0.0)
                        df.at[idx, 'bid'] = pricing.get('bidPrice', 0.0)
                        df.at[idx, 'ask'] = pricing.get('askPrice', 0.0)
                        df.at[idx, 'volume'] = pricing.get('cumulativeVolume', 0)
                        df.at[idx, 'openInterest'] = pricing.get('openInterest', 0)
                        df.at[idx, 'impliedVolatility'] = pricing.get('iv', 0.0)
                        df.at[idx, 'delta'] = pricing.get('delta', 0.0)
                        df.at[idx, 'gamma'] = pricing.get('gamma', 0.0)
                        df.at[idx, 'theta'] = pricing.get('theta', 0.0)
                        df.at[idx, 'vega'] = pricing.get('vega', 0.0)
                        df.at[idx, 'rho'] = pricing.get('rho', 0.0)

                    df['symbol'] = symbol.upper()

                    return df

                calls = format_chain_data(calls)
                puts = format_chain_data(puts)

                options_data[exp_str] = {
                    'calls': calls,
                    'puts': puts
                }

            return options_data

        except Exception as e:
            logger.error(f"Error fetching options data for {symbol}: {str(e)}")
            return {}

    def store_stock_data(self, symbol: str, stock_data: pd.DataFrame) -> bool:
        """Store stock price data in database"""
        try:
            db = self.get_session()

            # Get symbol ID
            symbol_obj = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False

            # Process each row
            for _, row in stock_data.iterrows():
                # Check if this timestamp already exists
                existing = db.query(StockPrice).filter(
                    StockPrice.symbol_id == symbol_obj.id,
                    StockPrice.timestamp == row['Date']
                ).first()

                if existing:
                    # Update existing record
                    existing.open_price = float(row['Open'])
                    existing.high_price = float(row['High'])
                    existing.low_price = float(row['Low'])
                    existing.close_price = float(row['Close'])
                    existing.volume = int(row['Volume'])
                else:
                    # Create new record
                    stock_price = StockPrice(
                        symbol_id=symbol_obj.id,
                        timestamp=row['Date'],
                        open_price=float(row['Open']),
                        high_price=float(row['High']),
                        low_price=float(row['Low']),
                        close_price=float(row['Close']),
                        volume=int(row['Volume'])
                    )
                    db.add(stock_price)

            db.commit()
            logger.info(f"Stored {len(stock_data)} stock price records for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error storing stock data for {symbol}: {str(e)}")
            db.rollback()
            return False

    def store_options_data(self, symbol: str, options_data: Dict) -> bool:
        """Store options data in database"""
        try:
            db = self.get_session()

            # Get symbol ID
            symbol_obj = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False

            contracts_added = 0
            prices_added = 0

            for exp_date, chains in options_data.items():
                for option_type_label, chain_data in chains.items():
                    for _, row in chain_data.iterrows():
                        try:
                            # Create or get option contract
                            contract_symbol = row['contractSymbol'].strip()

                            contract = db.query(OptionContract).filter(
                                OptionContract.contract_symbol == contract_symbol
                            ).first()

                            if not contract:
                                contract = OptionContract(
                                    symbol_id=symbol_obj.id,
                                    contract_symbol=contract_symbol,
                                    expiry_date=pd.to_datetime(exp_date),
                                    strike_price=float(row['strike']),
                                    option_type=row['option_type'],
                                    is_active=True
                                )
                                db.add(contract)
                                db.flush()  # Get the ID
                                contracts_added += 1

                            # Store option price data (even if zeros)
                            def safe_float(val, default=0.0):
                                try:
                                    result = float(val)
                                    return result if not pd.isna(result) else default
                                except (ValueError, TypeError):
                                    return default

                            def safe_int(val, default=0):
                                try:
                                    result = float(val)
                                    return int(result) if not pd.isna(result) else default
                                except (ValueError, TypeError):
                                    return default

                            option_price = OptionPrice(
                                contract_id=contract.id,
                                timestamp=datetime.now(),
                                bid=safe_float(row.get('bid', 0)),
                                ask=safe_float(row.get('ask', 0)),
                                last_price=safe_float(row.get('lastPrice', 0)),
                                volume=safe_int(row.get('volume', 0)),
                                open_interest=safe_int(row.get('openInterest', 0)),
                                implied_volatility=safe_float(row.get('impliedVolatility', 0)),
                                delta=safe_float(row.get('delta', 0)),
                                gamma=safe_float(row.get('gamma', 0)),
                                theta=safe_float(row.get('theta', 0)),
                                vega=safe_float(row.get('vega', 0)),
                                rho=safe_float(row.get('rho', 0))
                            )

                            # Calculate spreads if we have real data
                            bid = safe_float(row.get('bid', 0))
                            ask = safe_float(row.get('ask', 0))
                            if bid > 0 and ask > 0:
                                option_price.bid_ask_spread = ask - bid
                                mid_price = (bid + ask) / 2
                                if mid_price > 0:
                                    option_price.spread_percentage = (ask - bid) / mid_price * 100

                            db.add(option_price)
                            prices_added += 1

                        except Exception as e:
                            logger.error(f"Error processing option row: {str(e)}")
                            continue

            db.commit()
            logger.info(f"Stored {contracts_added} new contracts and {prices_added} price records for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error storing options data for {symbol}: {str(e)}")
            db.rollback()
            return False

    def calculate_and_store_iv_analysis(self, symbol: str) -> bool:
        """
        Calculate and store IV analysis (rank, percentile, HV) for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            True if successful, False otherwise
        """
        try:
            from calculations import OptionsCalculator
            import numpy as np

            db = self.get_session()
            calculator = OptionsCalculator()

            # Get symbol record
            symbol_obj = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_obj:
                logger.error(f"Symbol {symbol} not found in database")
                return False

            # Get recent stock prices for HV calculation
            stock_prices = db.query(StockPrice).filter(
                StockPrice.symbol_id == symbol_obj.id
            ).order_by(StockPrice.timestamp.desc()).limit(60).all()

            if len(stock_prices) < 20:
                logger.warning(f"Not enough stock price history for {symbol} to calculate HV")
                hv_20d = None
                hv_30d = None
            else:
                # Calculate historical volatility
                prices_df = pd.DataFrame([{
                    'timestamp': sp.timestamp,
                    'close': sp.close_price
                } for sp in reversed(stock_prices)])

                hv_20d = calculator.calculate_historical_volatility(
                    prices_df['close'], period_days=20
                )
                hv_30d = calculator.calculate_historical_volatility(
                    prices_df['close'], period_days=30
                )

            # Get all recent option prices to calculate average IV
            recent_options = db.query(OptionPrice).join(
                OptionContract, OptionPrice.contract_id == OptionContract.id
            ).filter(
                OptionContract.symbol_id == symbol_obj.id,
                OptionPrice.implied_volatility > 0
            ).order_by(OptionPrice.timestamp.desc()).limit(500).all()

            if not recent_options:
                logger.warning(f"No option data available for IV analysis for {symbol}")
                return False

            # Calculate average current IV
            current_ivs = [op.implied_volatility for op in recent_options if op.implied_volatility > 0]
            if not current_ivs:
                return False

            current_iv = np.mean(current_ivs)

            # Get historical IV data for rank/percentile calculation
            historical_iv_records = db.query(IVAnalysis).filter(
                IVAnalysis.symbol_id == symbol_obj.id
            ).order_by(IVAnalysis.timestamp.desc()).limit(365).all()

            if len(historical_iv_records) < 10:
                # Not enough history, use defaults
                iv_rank = 50.0
                iv_percentile = 50.0
            else:
                historical_iv_series = pd.Series([
                    record.current_iv for record in historical_iv_records
                ])
                iv_rank = calculator.calculate_iv_rank(current_iv, historical_iv_series)
                iv_percentile = calculator.calculate_iv_percentile(current_iv, historical_iv_series)

            # Create IV analysis record
            iv_analysis = IVAnalysis(
                symbol_id=symbol_obj.id,
                timestamp=datetime.now(),
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                hv_20d=hv_20d,
                hv_30d=hv_30d
            )

            db.add(iv_analysis)
            db.commit()

            logger.info(f"Calculated IV analysis for {symbol}: IV={current_iv*100:.1f}%, Rank={iv_rank:.1f}%")
            return True

        except Exception as e:
            logger.error(f"Error calculating IV analysis for {symbol}: {str(e)}")
            if db:
                db.rollback()
            return False

    def update_all_symbols(self) -> Dict[str, bool]:
        """Update data for all active symbols in the watchlist"""
        try:
            db = self.get_session()
            symbols = db.query(Symbol).filter(Symbol.is_active == True).all()

            results = {}

            for i, symbol_obj in enumerate(symbols):
                symbol = symbol_obj.symbol
                logger.info(f"Updating data for {symbol} ({i+1}/{len(symbols)})")

                # Fetch and store stock data
                stock_data = self.fetch_stock_data(symbol)
                if stock_data is not None:
                    results[f"{symbol}_stock"] = self.store_stock_data(symbol, stock_data)
                else:
                    results[f"{symbol}_stock"] = False

                # Fetch and store options data
                options_data = self.fetch_options_data(symbol)
                if options_data:
                    results[f"{symbol}_options"] = self.store_options_data(symbol, options_data)
                    # Calculate IV analysis after storing options
                    self.calculate_and_store_iv_analysis(symbol)
                else:
                    results[f"{symbol}_options"] = False

                # Small delay to be respectful to the API
                if i < len(symbols) - 1:
                    time.sleep(1)

            logger.info(f"Completed update for all symbols. Success rate: {sum(results.values())}/{len(results)}")
            return results

        except Exception as e:
            logger.error(f"Error updating symbols: {str(e)}")
            return {}

    def get_current_stock_price(self, symbol: str) -> Optional[float]:
        """Get the most recent stock price for a symbol"""
        try:
            df = self.fetch_stock_data(symbol, days=1)
            if df is not None and not df.empty:
                return float(df.iloc[-1]['Close'])
            return None
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {str(e)}")
            return None


# For backwards compatibility, create an alias
DataFetcher = IVolatilityDataFetcher


def main():
    """Test the IVolatility data fetcher"""
    from models import create_tables

    # Initialize database
    create_tables()

    fetcher = IVolatilityDataFetcher()

    # Add some test symbols
    test_symbols = ['AAPL', 'MSFT', 'GOOGL']

    for symbol in test_symbols:
        print(f"Adding {symbol} to watchlist...")
        fetcher.add_symbol_to_watchlist(symbol)

    # Update data for all symbols
    print("Updating data for all symbols...")
    results = fetcher.update_all_symbols()

    for key, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {key}")

    fetcher.close_session()
    print("\nData fetching complete!")
    print("\nOptions data now includes:")
    print("  ✓ Real-time pricing (bid/ask/last)")
    print("  ✓ Implied volatility")
    print("  ✓ Greeks (delta, gamma, theta, vega, rho)")
    print("  ✓ Volume and open interest")


if __name__ == "__main__":
    main()
