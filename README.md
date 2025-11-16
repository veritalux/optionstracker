# Options Tracker - Trading Analytics Dashboard

A full-stack web application for tracking options trading opportunities with real-time data, Greeks calculations, and automated opportunity detection.

## Features

- **Options Data**: Fetches options contracts and stock data from Massive API (formerly Polygon.io)
- **Greeks Calculations**: Automatic Black-Scholes calculations for Delta, Gamma, Theta, Vega, Rho
- **Opportunity Detection**: Automated scanning for mispricing, unusual volume, and IV extremes
- **Watchlist Management**: Track multiple symbols and their options
- **Scheduled Updates**: Automatic data refresh every 15 minutes during market hours
- **Dashboard**: Visual analytics with top opportunities and hot symbols

> **Note:** Real-time options pricing, Greeks, and live quotes require a paid Massive API subscription. The free tier provides contract metadata and historical stock data.

## Tech Stack

### Backend
- **Python 3.12** / FastAPI
- **PostgreSQL** (Production) / SQLite (Development)
- **SQLAlchemy** ORM
- **Massive API** (formerly Polygon.io) for market data
- **APScheduler** for background jobs

### Frontend
- **React 18** with Vite
- **Tailwind CSS**
- **Axios** for API calls

## Deployment on Render

This app is configured for easy deployment on Render using the included render.yaml.

See DEPLOYMENT.md for detailed instructions.

## License

MIT

## Disclaimer

This application is for informational and educational purposes only. Not financial advice.
