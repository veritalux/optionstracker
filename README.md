# Options Tracker - Trading Analytics Dashboard

A full-stack web application for tracking options trading opportunities with real-time data, Greeks calculations, and automated opportunity detection.

## Features

- **Real-time Options Data**: Fetches live options chains and stock prices
- **Greeks Calculations**: Automatic Black-Scholes calculations for Delta, Gamma, Theta, Vega, Rho
- **Opportunity Detection**: Automated scanning for mispricing, unusual volume, and IV extremes
- **Watchlist Management**: Track multiple symbols and their options
- **Scheduled Updates**: Automatic data refresh every 15 minutes during market hours
- **Dashboard**: Visual analytics with top opportunities and hot symbols

## Tech Stack

### Backend
- **Python 3.11+** / FastAPI
- **PostgreSQL** (Production) / SQLite (Development)
- **SQLAlchemy** ORM
- **IVolatility API** for market data (stocks and options)
- **APScheduler** for background jobs

### Frontend
- **React 18** with Vite
- **Tailwind CSS**
- **Axios** for API calls

## IVolatility API Setup

### Getting Your API Key

1. Visit https://www.ivolatility.com/
2. Sign up for a 7-day free trial or choose a subscription plan
3. Get your API key from the dashboard

### Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
IVOLATILITY_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./options_tracker.db
FRONTEND_URL=http://localhost:5173
```

### API Data Available

The **7-day free trial** includes full functionality:
- ✅ Stock EOD prices (OHLCV data)
- ✅ Options chain structure (strikes, expirations)
- ✅ **Real-time options quotes with pricing** (bid/ask/last)
- ✅ **Implied volatility data**
- ✅ **Options Greeks** (delta, gamma, theta, vega, rho)
- ✅ Volume and open interest data

**API Endpoints Used:**
- `/equities/eod/stock-prices` - Stock prices
- `/equities/option-series` - Options chain
- `/equities/rt/options-rawiv` - Real-time options pricing, IV, and Greeks

The application fetches complete market data for options analysis and trading opportunity detection.

## Local Development

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Backend runs on http://localhost:8000

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173

## Deployment on Render

This app is configured for easy deployment on Render.

**Required Environment Variables:**
- `IVOLATILITY_API_KEY` - Your IVolatility API key
- `DATABASE_URL` - Automatically set by Render for PostgreSQL
- `FRONTEND_URL` - Your frontend URL on Render

## License

MIT

## Disclaimer

This application is for informational and educational purposes only. Not financial advice.
