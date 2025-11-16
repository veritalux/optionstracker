import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models import Symbol, StockPrice, OptionContract, OptionPrice, get_db, create_tables
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key from environment
from dotenv import load_dotenv
load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
if not ALPHA_VANTAGE_API_KEY:
    logger.warning("ALPHA_VANTAGE_API_KEY not found in environment variables")

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# FREE TIER LIMITS (as of 2025):
# - 25 API calls per day (NOT 500!)
# - 5 API calls per minute
# - Data updates end-of-day only (no intraday updates)
# - Free endpoints: TIME_SERIES_DAILY, GLOBAL_QUOTE, HISTORICAL_OPTIONS, OVERVIEW
# - Premium only: REALTIME_OPTIONS, TIME_SERIES_DAILY_ADJUSTED

class DataFetcher:
    def __init__(self):
        self.session = None
        self.api_key = ALPHA_VANTAGE_API_KEY

    def get_session(self) -> Session:
        """Get database session"""
        if not self.session:
            from models import SessionLocal
            self.session = SessionLocal()
        return self.session

    def close_session(self):
        """Close database session"""
        if self.session:
            self.session.close()
            self.session = None

    def _make_api_request(self, params: dict, retries: int = 3) -> Optional[dict]:
        """Make a request to Alpha Vantage API with retry logic"""
        params['apikey'] = self.api_key

        for attempt in range(retries):
            try:
                response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Check for API error messages
                if "Error Message" in data:
                    logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                    return None

                if "Note" in data:
                    logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                    if attempt < retries - 1:
                        time.sleep(12)  # Wait 12 seconds before retry (free tier: 5 calls/min)
                        continue
                    return None

                return data

            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed (attempt {attempt + 1}/{retries}): {str(e)}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None

        return None

    def add_symbol_to_watchlist(self, symbol: str, company_name: str = None) -> bool:
        """Add a symbol to the database and watchlist"""
        try:
            db = self.get_session()

            # Check if symbol already exists
            existing = db.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if existing:
                logger.info(f"Symbol {symbol} already exists")
                return True

            # Get company info if not provided
            if not company_name:
                try:
                    params = {
                        'function': 'OVERVIEW',
                        'symbol': symbol
                    }
                    data = self._make_api_request(params)
                    if data:
                        company_name = data.get('Name', symbol.upper())
                    else:
                        company_name = symbol.upper()
                except:
                    company_name = symbol.upper()

            # Create new symbol
            new_symbol = Symbol(
                symbol=symbol.upper(),
                company_name=company_name,
                sector="",  # Could be populated from Alpha Vantage OVERVIEW
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

    def fetch_stock_data(self, symbol: str, period: str = "1mo") -> Optional[pd.DataFrame]:
        """Fetch stock price data from Alpha Vantage"""
        try:
            # Map period to outputsize
            outputsize = "compact" if period in ["1mo", "1d", "5d"] else "full"

            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': outputsize
            }

            data = self._make_api_request(params)

            if not data or 'Time Series (Daily)' not in data:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Convert to DataFrame
            time_series = data['Time Series (Daily)']
            df = pd.DataFrame.from_dict(time_series, orient='index')

            # Rename columns to match expected format
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

            # Convert data types
            df['Open'] = df['Open'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['Volume'] = df['Volume'].astype(int)

            # Reset index and convert to datetime
            df.reset_index(inplace=True)
            df.rename(columns={'index': 'Date'}, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df['Symbol'] = symbol.upper()

            # Filter by period if needed
            if period == "1mo":
                cutoff_date = datetime.now() - timedelta(days=30)
                df = df[df['Date'] >= cutoff_date]
            elif period == "5d":
                cutoff_date = datetime.now() - timedelta(days=5)
                df = df[df['Date'] >= cutoff_date]

            # Sort by date
            df = df.sort_values('Date')

            return df

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            return None

    def fetch_options_data(self, symbol: str, date: str = None) -> Dict[str, pd.DataFrame]:
        """Fetch options chain data from Alpha Vantage using HISTORICAL_OPTIONS

        Note: Free tier only supports HISTORICAL_OPTIONS (not REALTIME_OPTIONS)
        This provides complete historical options chains with Greeks and IV
        """
        try:
            params = {
                'function': 'HISTORICAL_OPTIONS',
                'symbol': symbol
            }

            # If no date specified, use most recent data (API defaults to latest)
            if date:
                params['date'] = date

            data = self._make_api_request(params)

            if not data or 'data' not in data:
                logger.warning(f"No options data available for {symbol}")
                return {}

            options_list = data['data']
            if not options_list:
                logger.warning(f"Empty options data for {symbol}")
                return {}

            # Convert to DataFrame
            df = pd.DataFrame(options_list)

            # Group by expiration date
            options_data = {}
            unique_expirations = df['expiration'].unique()

            # Limit to first 6 expiration dates to match previous behavior
            for exp_date in sorted(unique_expirations)[:6]:
                exp_df = df[df['expiration'] == exp_date].copy()

                # Split into calls and puts
                calls = exp_df[exp_df['type'] == 'call'].copy()
                puts = exp_df[exp_df['type'] == 'put'].copy()

                # Rename columns to match expected format
                def format_options_df(opt_df):
                    if opt_df.empty:
                        return opt_df

                    # Map Alpha Vantage column names to our format
                    opt_df['contractSymbol'] = opt_df['contractID']
                    opt_df['strike'] = pd.to_numeric(opt_df['strike'], errors='coerce')
                    opt_df['lastPrice'] = pd.to_numeric(opt_df.get('last', 0), errors='coerce')
                    opt_df['bid'] = pd.to_numeric(opt_df.get('bid', 0), errors='coerce')
                    opt_df['ask'] = pd.to_numeric(opt_df.get('ask', 0), errors='coerce')
                    opt_df['volume'] = pd.to_numeric(opt_df.get('volume', 0), errors='coerce').fillna(0).astype(int)
                    opt_df['openInterest'] = pd.to_numeric(opt_df.get('open_interest', 0), errors='coerce').fillna(0).astype(int)
                    opt_df['impliedVolatility'] = pd.to_numeric(opt_df.get('implied_volatility', 0), errors='coerce')

                    # Alpha Vantage provides Greeks - store them for later use
                    if 'delta' in opt_df.columns:
                        opt_df['delta'] = pd.to_numeric(opt_df['delta'], errors='coerce')
                    if 'gamma' in opt_df.columns:
                        opt_df['gamma'] = pd.to_numeric(opt_df['gamma'], errors='coerce')
                    if 'theta' in opt_df.columns:
                        opt_df['theta'] = pd.to_numeric(opt_df['theta'], errors='coerce')
                    if 'vega' in opt_df.columns:
                        opt_df['vega'] = pd.to_numeric(opt_df['vega'], errors='coerce')
                    if 'rho' in opt_df.columns:
                        opt_df['rho'] = pd.to_numeric(opt_df['rho'], errors='coerce')

                    return opt_df

                calls = format_options_df(calls)
                puts = format_options_df(puts)

                # Add metadata
                calls['option_type'] = 'call'
                calls['expiry_date'] = exp_date
                calls['symbol'] = symbol.upper()

                puts['option_type'] = 'put'
                puts['expiry_date'] = exp_date
                puts['symbol'] = symbol.upper()

                options_data[exp_date] = {
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
                for option_type, chain_data in chains.items():
                    for _, row in chain_data.iterrows():
                        try:
                            # Create or get option contract
                            contract_symbol = row['contractSymbol']

                            contract = db.query(OptionContract).filter(
                                OptionContract.contract_symbol == contract_symbol
                            ).first()

                            if not contract:
                                contract = OptionContract(
                                    symbol_id=symbol_obj.id,
                                    contract_symbol=contract_symbol,
                                    expiry_date=datetime.strptime(exp_date, '%Y-%m-%d'),
                                    strike_price=float(row['strike']),
                                    option_type=row['option_type'],
                                    is_active=True
                                )
                                db.add(contract)
                                db.flush()  # Get the ID
                                contracts_added += 1

                            # Store option price data - handle NaN values
                            def safe_float(val, default=0.0):
                                try:
                                    result = float(val)
                                    return result if not pd.isna(result) else default
                                except (ValueError, TypeError):
                                    return default

                            def safe_int(val, default=0):
                                try:
                                    result = float(val)  # Convert to float first to handle NaN
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
                                implied_volatility=safe_float(row.get('impliedVolatility', 0))
                            )

                            # Add Greeks from Alpha Vantage if available
                            if 'delta' in row and not pd.isna(row.get('delta')):
                                option_price.delta = safe_float(row.get('delta'))
                            if 'gamma' in row and not pd.isna(row.get('gamma')):
                                option_price.gamma = safe_float(row.get('gamma'))
                            if 'theta' in row and not pd.isna(row.get('theta')):
                                option_price.theta = safe_float(row.get('theta'))
                            if 'vega' in row and not pd.isna(row.get('vega')):
                                option_price.vega = safe_float(row.get('vega'))
                            if 'rho' in row and not pd.isna(row.get('rho')):
                                option_price.rho = safe_float(row.get('rho'))

                            # Calculate additional metrics
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

    def update_all_symbols(self) -> Dict[str, bool]:
        """
        Update data for all active symbols in the watchlist

        WARNING: Free tier limit is 25 API calls per day!
        Each symbol uses 2 calls (stock + options), so max ~12 symbols per day.
        For more symbols, consider:
        - Updating different symbols on different days
        - Upgrading to premium tier
        - Using less frequent updates (once per day)
        """
        try:
            db = self.get_session()
            symbols = db.query(Symbol).filter(Symbol.is_active == True).all()

            # Check if we're about to exceed daily limit
            estimated_calls = len(symbols) * 2  # 2 calls per symbol
            if estimated_calls > 25:
                logger.warning(
                    f"WARNING: {len(symbols)} symbols requires ~{estimated_calls} API calls. "
                    f"Free tier limit is 25 calls/day. Consider reducing symbols or upgrading."
                )

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
                else:
                    results[f"{symbol}_options"] = False

                # Add delay between symbols to respect rate limits
                # Free tier: 5 calls/min, 25 calls/day
                if i < len(symbols) - 1:  # Don't sleep after the last symbol
                    time.sleep(13)  # 13 seconds ensures we stay under 5 calls/min

            logger.info(f"Completed update for all symbols. Success rate: {sum(results.values())}/{len(results)}")
            return results

        except Exception as e:
            logger.error(f"Error updating symbols: {str(e)}")
            return {}

    def get_current_stock_price(self, symbol: str) -> Optional[float]:
        """Get the most recent stock price for a symbol"""
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol
            }

            data = self._make_api_request(params)

            if data and 'Global Quote' in data:
                quote = data['Global Quote']
                price = quote.get('05. price')
                if price:
                    return float(price)

            return None

        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {str(e)}")
            return None

def main():
    """Test the data fetcher"""
    # Initialize database
    create_tables()

    fetcher = DataFetcher()

    # Add some test symbols
    test_symbols = ['AAPL', 'MSFT', 'SPY']

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
    print("Data fetching complete!")

if __name__ == "__main__":
    main()
