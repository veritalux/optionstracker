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

MASSIVE_API_KEY = os.getenv('MASSIVE_API_KEY')
if not MASSIVE_API_KEY:
    logger.warning("MASSIVE_API_KEY not found in environment variables")

MASSIVE_BASE_URL = "https://api.massive.com"

class DataFetcher:
    def __init__(self):
        self.session = None
        self.api_key = MASSIVE_API_KEY

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

    def _make_api_request(self, endpoint: str, params: dict = None, retries: int = 3) -> Optional[dict]:
        """Make a request to Massive API with retry logic"""
        if params is None:
            params = {}
        params['apiKey'] = self.api_key

        url = f"{MASSIVE_BASE_URL}{endpoint}"

        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Check for API error messages
                if data.get("status") == "ERROR":
                    logger.error(f"Massive API error: {data.get('error', 'Unknown error')}")
                    return None

                if data.get("status") == "NOT_AUTHORIZED":
                    logger.error(f"Massive API authorization error: {data.get('message', 'Not authorized')}")
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
                    endpoint = f"/v3/reference/tickers/{symbol.upper()}"
                    data = self._make_api_request(endpoint)
                    if data and data.get('status') == 'OK':
                        result = data.get('results', {})
                        company_name = result.get('name', symbol.upper())
                    else:
                        company_name = symbol.upper()
                except:
                    company_name = symbol.upper()

            # Create new symbol
            new_symbol = Symbol(
                symbol=symbol.upper(),
                company_name=company_name,
                sector="",  # Could be populated from Massive ticker details
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
        """Fetch stock price data from Massive API

        Note: Free tier has delayed data. Using historical dates for demonstration.
        """
        try:
            # NOTE: Free tier has delayed data (typically end-of-day from previous days)
            # Using a date range that we know has data available
            # In production with paid tier, use datetime.now()

            # Use data from early 2024 (guaranteed to be available on free tier)
            end_date = datetime(2024, 6, 30)
            if period == "1mo":
                start_date = end_date - timedelta(days=30)
            elif period == "5d":
                start_date = end_date - timedelta(days=5)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=30)  # Default to 1 month

            # Format dates for API
            from_date = start_date.strftime('%Y-%m-%d')
            to_date = end_date.strftime('%Y-%m-%d')

            # Massive API: /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
            endpoint = f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/{from_date}/{to_date}"

            data = self._make_api_request(endpoint)

            if not data or data.get('status') != 'OK' or 'results' not in data:
                logger.warning(f"No data returned for {symbol}")
                return None

            results = data['results']
            if not results:
                logger.warning(f"Empty results for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(results)

            # Massive API uses: v=volume, vw=volume weighted avg, o=open, c=close, h=high, l=low, t=timestamp(ms), n=transactions
            df['Date'] = pd.to_datetime(df['t'], unit='ms')
            df['Open'] = df['o'].astype(float)
            df['High'] = df['h'].astype(float)
            df['Low'] = df['l'].astype(float)
            df['Close'] = df['c'].astype(float)
            df['Volume'] = df['v'].astype(int)
            df['Symbol'] = symbol.upper()

            # Select only the columns we need
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Symbol']]

            # Sort by date
            df = df.sort_values('Date')

            return df

        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            return None

    def fetch_options_data(self, symbol: str, date: str = None) -> Dict[str, pd.DataFrame]:
        """Fetch options chain data from Massive API

        Note: Free tier provides contract metadata only. Pricing data, Greeks, and IV
        require a paid subscription. This method returns contract structure with
        placeholder values for unavailable data.
        """
        try:
            # Massive API endpoint for options contracts
            endpoint = f"/v3/reference/options/contracts"
            params = {
                'underlying_ticker': symbol.upper(),
                'limit': 250,  # Maximum allowed
                'order': 'asc',
                'sort': 'expiration_date'
            }

            data = self._make_api_request(endpoint, params)

            if not data or data.get('status') != 'OK' or 'results' not in data:
                logger.warning(f"No options data available for {symbol}")
                return {}

            contracts = data['results']
            if not contracts:
                logger.warning(f"Empty options contracts for {symbol}")
                return {}

            # Convert to DataFrame
            df = pd.DataFrame(contracts)

            # Group by expiration date
            options_data = {}
            unique_expirations = df['expiration_date'].unique()

            # Limit to first 6 expiration dates to match previous behavior
            for exp_date in sorted(unique_expirations)[:6]:
                exp_df = df[df['expiration_date'] == exp_date].copy()

                # Split into calls and puts
                calls = exp_df[exp_df['contract_type'] == 'call'].copy()
                puts = exp_df[exp_df['contract_type'] == 'put'].copy()

                # Format to match expected structure
                def format_options_df(opt_df):
                    if opt_df.empty:
                        return opt_df

                    # Map Massive API column names to our format
                    opt_df['contractSymbol'] = opt_df['ticker']
                    opt_df['strike'] = pd.to_numeric(opt_df['strike_price'], errors='coerce')

                    # NOTE: The following fields are NOT available on the free tier
                    # Setting placeholder values - these would need a paid subscription
                    opt_df['lastPrice'] = 0.0
                    opt_df['bid'] = 0.0
                    opt_df['ask'] = 0.0
                    opt_df['volume'] = 0
                    opt_df['openInterest'] = 0
                    opt_df['impliedVolatility'] = 0.0
                    opt_df['delta'] = 0.0
                    opt_df['gamma'] = 0.0
                    opt_df['theta'] = 0.0
                    opt_df['vega'] = 0.0
                    opt_df['rho'] = 0.0

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

            logger.info(f"Fetched {len(contracts)} options contracts for {symbol} across {len(options_data)} expiration dates")
            logger.warning(f"Options pricing data unavailable - requires paid Massive API subscription")

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
                else:
                    results[f"{symbol}_options"] = False

                # Add delay between symbols to respect rate limits (5 calls/min for free tier)
                if i < len(symbols) - 1:  # Don't sleep after the last symbol
                    time.sleep(13)  # 13 seconds ensures we stay under 5 calls/min (Massive free tier)

            logger.info(f"Completed update for all symbols. Success rate: {sum(results.values())}/{len(results)}")
            return results

        except Exception as e:
            logger.error(f"Error updating symbols: {str(e)}")
            return {}

    def get_current_stock_price(self, symbol: str) -> Optional[float]:
        """Get the most recent stock price for a symbol

        Note: Real-time quotes require paid subscription.
        This method returns historical daily close price (free tier uses older data).
        """
        try:
            # NOTE: Free tier has delayed data. Using historical date with available data.
            # In production with paid tier, use datetime.now()
            # Using last trading day from our test period
            yesterday = '2024-06-27'
            today = '2024-06-28'

            endpoint = f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/{yesterday}/{today}"
            data = self._make_api_request(endpoint)

            if data and data.get('status') == 'OK' and 'results' in data:
                results = data['results']
                if results:
                    # Get the most recent close price
                    latest = results[-1]
                    return float(latest['c'])

            logger.warning(f"No recent price data for {symbol} - real-time quotes require paid subscription")
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
