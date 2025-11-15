import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models import Symbol, StockPrice, OptionContract, OptionPrice, get_db, create_tables
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure yfinance to use proper headers to avoid being blocked
# This helps bypass rate limiting and blocking on cloud hosting platforms
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

class DataFetcher:
    def __init__(self):
        self.session = None
    
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
                    ticker = yf.Ticker(symbol, session=_session)
                    info = ticker.info
                    company_name = info.get('longName', symbol.upper())
                except:
                    company_name = symbol.upper()
            
            # Create new symbol
            new_symbol = Symbol(
                symbol=symbol.upper(),
                company_name=company_name,
                sector="",  # Could be populated from yfinance info
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
        """Fetch stock price data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol, session=_session)
            hist = ticker.history(period=period)
            
            if hist.empty:
                logger.warning(f"No data returned for {symbol}")
                return None
            
            # Clean up the data
            hist.reset_index(inplace=True)
            hist['Symbol'] = symbol.upper()
            
            return hist
            
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {str(e)}")
            return None
    
    def fetch_options_data(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch options chain data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol, session=_session)
            
            # Get options expiration dates
            options_dates = ticker.options
            if not options_dates:
                logger.warning(f"No options data available for {symbol}")
                return {}

            options_data = {}

            # Fetch options for next few expiration dates (limit to avoid rate limits)
            for exp_date in options_dates[:6]:  # First 6 expiration dates
                try:
                    opt_chain = ticker.option_chain(exp_date)

                    # Process calls
                    calls = opt_chain.calls.copy()
                    calls['option_type'] = 'call'
                    calls['expiry_date'] = exp_date
                    calls['symbol'] = symbol.upper()

                    # Process puts
                    puts = opt_chain.puts.copy()
                    puts['option_type'] = 'put'
                    puts['expiry_date'] = exp_date
                    puts['symbol'] = symbol.upper()

                    options_data[exp_date] = {
                        'calls': calls,
                        'puts': puts
                    }

                except Exception as e:
                    logger.error(f"Error fetching options for {symbol} {exp_date}: {str(e)}")
                    continue

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

                # Add a small delay between symbols to avoid rate limiting
                if i < len(symbols) - 1:  # Don't sleep after the last symbol
                    time.sleep(1)

            logger.info(f"Completed update for all symbols. Success rate: {sum(results.values())}/{len(results)}")
            return results

        except Exception as e:
            logger.error(f"Error updating symbols: {str(e)}")
            return {}
    
    def get_current_stock_price(self, symbol: str) -> Optional[float]:
        """Get the most recent stock price for a symbol"""
        try:
            ticker = yf.Ticker(symbol, session=_session)
            hist = ticker.history(period="1d")
            
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            
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
