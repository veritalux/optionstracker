# Massive API Migration Documentation

## Overview

This document describes the migration from Alpha Vantage API to Massive API (formerly Polygon.io) for the Options Tracker application.

## Migration Date

Migrated on: 2025-11-16

## API Changes

### Previous API: Alpha Vantage
- **Endpoints Used:**
  - `TIME_SERIES_DAILY` - Historical stock prices
  - `HISTORICAL_OPTIONS` - Options chains with Greeks and IV
  - `OVERVIEW` - Company information
  - `GLOBAL_QUOTE` - Current stock price
- **Rate Limits:** 5 calls/min, 500 calls/day (free tier)
- **Features:** Greeks (delta, gamma, theta, vega, rho) provided by API

### New API: Massive (Polygon.io)
- **Endpoints Used:**
  - `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}` - Historical stock OHLC data
  - `/v3/reference/options/contracts` - Options contract metadata
  - `/v3/reference/tickers/{ticker}` - Ticker/company information
- **Rate Limits:** 5 calls/min (free tier)
- **Base URL:** `https://api.massive.com`

## API Key Configuration

The Massive API key is configured in environment variables:

```bash
MASSIVE_API_KEY=your_api_key_here
```

Get your API key from: https://massive.com/dashboard

## Free Tier Limitations

### ✅ What's Available on Free Tier

1. **Stock Data**
   - Historical OHLC (Open, High, Low, Close) data
   - Volume data
   - 2 years of historical data at minute level granularity
   - End-of-day data (delayed)

2. **Options Contract Metadata**
   - Contract symbols/tickers
   - Strike prices
   - Expiration dates
   - Contract type (call/put)
   - Exercise style (American/European)
   - Shares per contract

3. **Reference Data**
   - Company names
   - Ticker information
   - Market details

### ❌ What Requires Paid Subscription

1. **Real-time Data**
   - Live stock quotes
   - Real-time options pricing
   - Intraday data

2. **Options Pricing Data**
   - Bid/Ask prices
   - Last traded price
   - Volume
   - Open interest
   - Implied volatility (IV)

3. **Greeks**
   - Delta
   - Gamma
   - Theta
   - Vega
   - Rho

## Code Changes

### Updated Files

1. **`backend/data_fetcher.py`**
   - Replaced `ALPHA_VANTAGE_API_KEY` with `MASSIVE_API_KEY`
   - Updated API base URL to `https://api.massive.com`
   - Rewrote `_make_api_request()` to use Massive API format
   - Updated `fetch_stock_data()` to use `/v2/aggs` endpoint
   - Updated `fetch_options_data()` to use `/v3/reference/options/contracts` endpoint
   - Updated `add_symbol_to_watchlist()` to use `/v3/reference/tickers` endpoint
   - Updated `get_current_stock_price()` to use aggregates endpoint
   - Added notes about free tier limitations using historical dates (2024-06-28) for demonstration

2. **`.env`**
   - Replaced `ALPHA_VANTAGE_API_KEY` with `MASSIVE_API_KEY`
   - Updated comments to reflect Massive API details

3. **`backend/.env.example`**
   - Added `MASSIVE_API_KEY` configuration example
   - Added documentation comments

## Data Structure Mapping

### Stock Data Response Mapping

**Alpha Vantage Format:**
```json
{
  "Time Series (Daily)": {
    "2024-01-01": {
      "1. open": "185.00",
      "2. high": "186.00",
      "3. low": "184.00",
      "4. close": "185.50",
      "5. volume": "50000000"
    }
  }
}
```

**Massive API Format:**
```json
{
  "results": [
    {
      "o": 185.00,     // open
      "h": 186.00,     // high
      "l": 184.00,     // low
      "c": 185.50,     // close
      "v": 50000000,   // volume
      "t": 1704067200000  // timestamp (ms)
    }
  ]
}
```

### Options Data Response Mapping

**Alpha Vantage Format:**
```json
{
  "data": [
    {
      "contractID": "AAPL240119C00150000",
      "strike": "150.00",
      "type": "call",
      "expiration": "2024-01-19",
      "last": "35.50",
      "bid": "35.20",
      "ask": "35.80",
      "delta": "0.85",
      "gamma": "0.02",
      // ... more fields
    }
  ]
}
```

**Massive API Format:**
```json
{
  "results": [
    {
      "ticker": "O:AAPL240119C00150000",
      "strike_price": 150.00,
      "contract_type": "call",
      "expiration_date": "2024-01-19",
      "exercise_style": "american",
      "shares_per_contract": 100
      // NOTE: Pricing and Greeks NOT available on free tier
    }
  ]
}
```

## Important Notes for Development

### Testing with Free Tier

Since the free tier has delayed data, the code uses historical dates for testing:

```python
# Using June 2024 data (guaranteed to be available on free tier)
end_date = datetime(2024, 6, 30)
```

### Production Deployment

For production use with real-time data:

1. **Upgrade to Paid Tier**
   - Visit https://massive.com/pricing
   - Choose a plan that includes options data and real-time quotes

2. **Update Date Logic**
   - Replace hardcoded historical dates with `datetime.now()`
   - Remove warning messages about free tier limitations

3. **Enable Real Data Fields**
   - Update `fetch_options_data()` to use actual pricing from API
   - Use real Greeks from the options snapshot endpoint
   - Enable real-time quote endpoints

## Placeholder Values

To maintain compatibility with the existing database schema and frontend, the following fields are set to placeholder values (0.0) when using the free tier:

- `lastPrice`
- `bid`
- `ask`
- `volume`
- `openInterest`
- `impliedVolatility`
- `delta`
- `gamma`
- `theta`
- `vega`
- `rho`

## Testing

Run the test script to verify the integration:

```bash
cd backend
python3 -c "
from data_fetcher import DataFetcher
fetcher = DataFetcher()

# Test stock data
stock_data = fetcher.fetch_stock_data('AAPL', period='5d')
print(f'Stock data: {len(stock_data)} days')

# Test options data
options_data = fetcher.fetch_options_data('AAPL')
print(f'Options data: {len(options_data)} expiration dates')

# Test current price
price = fetcher.get_current_stock_price('AAPL')
print(f'Current price: ${price:.2f}')
"
```

## Benefits of Massive API

1. **Better Structure** - More comprehensive reference data and metadata
2. **Active Development** - Massive (formerly Polygon.io) is actively maintained
3. **Scalability** - Clear upgrade path from free to paid tiers
4. **Documentation** - Extensive API documentation and examples
5. **Coverage** - Broader market coverage (stocks, options, crypto, forex, futures)

## Limitations to Address

To fully utilize this application's options tracking features, a paid Massive API subscription is required. The free tier is suitable for:
- Testing and development
- Learning options contract structures
- Viewing historical stock data
- Understanding the application architecture

## Support & Resources

- **Massive API Docs:** https://massive.com/docs/rest/
- **Pricing:** https://massive.com/pricing
- **Dashboard:** https://massive.com/dashboard
- **Support:** Contact Massive support for API questions

## Rollback Instructions

If you need to rollback to Alpha Vantage:

1. Restore the previous `data_fetcher.py` from git history
2. Update `.env` to use `ALPHA_VANTAGE_API_KEY` instead of `MASSIVE_API_KEY`
3. Restart the backend application

```bash
git checkout HEAD~1 -- backend/data_fetcher.py
# Update .env file
# Restart backend
```
