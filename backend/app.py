from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging
import os

from models import (
    get_db, create_tables, Symbol, StockPrice, OptionContract,
    OptionPrice, IVAnalysis, TradingOpportunity, UserWatchlist
)
from data_fetcher import DataFetcher
from scheduler import DataUpdateScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Options Tracker API", version="1.0.0")

# Initialize scheduler
scheduler = DataUpdateScheduler()

# CORS middleware - allow frontend URL from environment
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [FRONTEND_URL]

# In development, also allow localhost variations
if "localhost" in FRONTEND_URL or "127.0.0.1" in FRONTEND_URL:
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class SymbolCreate(BaseModel):
    symbol: str
    company_name: Optional[str] = None

class SymbolResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    sector: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class StockPriceResponse(BaseModel):
    id: int
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int

    class Config:
        from_attributes = True

class OptionContractResponse(BaseModel):
    id: int
    contract_symbol: str
    expiry_date: datetime
    strike_price: float
    option_type: str
    is_active: bool

    class Config:
        from_attributes = True

class OptionPriceResponse(BaseModel):
    id: int
    contract_id: int
    timestamp: datetime
    bid: float
    ask: float
    last_price: float
    volume: int
    open_interest: int
    implied_volatility: Optional[float]
    delta: Optional[float]
    gamma: Optional[float]
    theta: Optional[float]
    vega: Optional[float]
    rho: Optional[float]
    bid_ask_spread: Optional[float]
    spread_percentage: Optional[float]

    class Config:
        from_attributes = True

class IVAnalysisResponse(BaseModel):
    id: int
    symbol_id: int
    timestamp: datetime
    current_iv: float
    iv_rank: float
    iv_percentile: float
    hv_20d: Optional[float]
    hv_30d: Optional[float]

    class Config:
        from_attributes = True

class OpportunityResponse(BaseModel):
    id: int
    contract_id: int
    timestamp: datetime
    opportunity_type: str
    score: float
    description: str
    is_active: bool
    contract: Optional[OptionContractResponse]

    class Config:
        from_attributes = True

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on startup"""
    create_tables()
    logger.info("Database tables created/verified")

    # Start the background scheduler
    scheduler.start()
    logger.info("Background scheduler started")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    scheduler.stop()
    logger.info("Background scheduler stopped")

# Health check endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Options Tracker API"}

# Symbol endpoints
@app.post("/api/symbols", response_model=SymbolResponse)
async def create_symbol(
    symbol_data: SymbolCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Add a new symbol to the watchlist"""
    fetcher = DataFetcher()

    success = fetcher.add_symbol_to_watchlist(
        symbol_data.symbol,
        symbol_data.company_name
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to add symbol")

    # Get the created symbol
    symbol = db.query(Symbol).filter(
        Symbol.symbol == symbol_data.symbol.upper()
    ).first()

    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found after creation")

    # Schedule background data fetch
    background_tasks.add_task(fetch_symbol_data, symbol_data.symbol.upper())

    fetcher.close_session()
    return symbol

@app.get("/api/symbols", response_model=List[SymbolResponse])
async def get_symbols(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Get all symbols in the watchlist"""
    query = db.query(Symbol)

    if is_active is not None:
        query = query.filter(Symbol.is_active == is_active)

    symbols = query.all()
    return symbols

@app.get("/api/symbols/{symbol}", response_model=SymbolResponse)
async def get_symbol(symbol: str, db: Session = Depends(get_db)):
    """Get a specific symbol"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    return symbol_obj

@app.delete("/api/symbols/{symbol}")
async def delete_symbol(symbol: str, db: Session = Depends(get_db)):
    """Deactivate a symbol (soft delete)"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    symbol_obj.is_active = False
    db.commit()

    return {"message": f"Symbol {symbol} deactivated"}

# Stock price endpoints
@app.get("/api/symbols/{symbol}/prices", response_model=List[StockPriceResponse])
async def get_stock_prices(
    symbol: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get stock price history for a symbol"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    query = db.query(StockPrice).filter(
        StockPrice.symbol_id == symbol_obj.id
    )

    if start_date:
        query = query.filter(StockPrice.timestamp >= start_date)
    if end_date:
        query = query.filter(StockPrice.timestamp <= end_date)

    prices = query.order_by(StockPrice.timestamp.desc()).limit(limit).all()
    return prices

# Option contract endpoints
@app.get("/api/symbols/{symbol}/options", response_model=List[OptionContractResponse])
async def get_option_contracts(
    symbol: str,
    option_type: Optional[str] = None,
    min_expiry: Optional[datetime] = None,
    max_expiry: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get option contracts for a symbol"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    query = db.query(OptionContract).filter(
        OptionContract.symbol_id == symbol_obj.id,
        OptionContract.is_active == True
    )

    if option_type:
        query = query.filter(OptionContract.option_type == option_type.lower())
    if min_expiry:
        query = query.filter(OptionContract.expiry_date >= min_expiry)
    if max_expiry:
        query = query.filter(OptionContract.expiry_date <= max_expiry)

    contracts = query.order_by(OptionContract.expiry_date).all()
    return contracts

@app.get("/api/options/{contract_id}/prices", response_model=List[OptionPriceResponse])
async def get_option_prices(
    contract_id: int,
    start_date: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get price history for an option contract"""
    query = db.query(OptionPrice).filter(
        OptionPrice.contract_id == contract_id
    )

    if start_date:
        query = query.filter(OptionPrice.timestamp >= start_date)

    prices = query.order_by(OptionPrice.timestamp.desc()).limit(limit).all()

    if not prices:
        raise HTTPException(status_code=404, detail="No prices found for this contract")

    return prices

# IV Analysis endpoints
@app.get("/api/symbols/{symbol}/iv-analysis", response_model=List[IVAnalysisResponse])
async def get_iv_analysis(
    symbol: str,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Get IV analysis history for a symbol"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    analysis = db.query(IVAnalysis).filter(
        IVAnalysis.symbol_id == symbol_obj.id
    ).order_by(IVAnalysis.timestamp.desc()).limit(limit).all()

    return analysis

# Trading opportunities endpoints
@app.get("/api/opportunities", response_model=List[OpportunityResponse])
async def get_opportunities(
    is_active: bool = True,
    min_score: Optional[float] = None,
    opportunity_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get trading opportunities"""
    query = db.query(TradingOpportunity).options(joinedload(TradingOpportunity.contract))

    if is_active is not None:
        query = query.filter(TradingOpportunity.is_active == is_active)
    if min_score:
        query = query.filter(TradingOpportunity.score >= min_score)
    if opportunity_type:
        query = query.filter(TradingOpportunity.opportunity_type == opportunity_type)

    opportunities = query.order_by(
        TradingOpportunity.score.desc()
    ).limit(limit).all()

    return opportunities

@app.get("/api/symbols/{symbol}/opportunities", response_model=List[OpportunityResponse])
async def get_symbol_opportunities(
    symbol: str,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """Get opportunities for a specific symbol"""
    symbol_obj = db.query(Symbol).filter(
        Symbol.symbol == symbol.upper()
    ).first()

    if not symbol_obj:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Get opportunities through option contracts
    opportunities = db.query(TradingOpportunity).options(
        joinedload(TradingOpportunity.contract)
    ).join(
        OptionContract,
        TradingOpportunity.contract_id == OptionContract.id
    ).filter(
        OptionContract.symbol_id == symbol_obj.id,
        TradingOpportunity.is_active == is_active
    ).order_by(TradingOpportunity.score.desc()).all()

    return opportunities

# Data update endpoints
@app.post("/api/update/{symbol}")
async def update_symbol_data(
    symbol: str,
    background_tasks: BackgroundTasks
):
    """Trigger data update for a specific symbol"""
    background_tasks.add_task(fetch_symbol_data, symbol.upper())
    return {"message": f"Data update scheduled for {symbol}"}

@app.post("/api/update-all")
async def update_all_symbols(background_tasks: BackgroundTasks):
    """Trigger data update for all active symbols"""
    background_tasks.add_task(fetch_all_symbols_data)
    return {"message": "Data update scheduled for all symbols"}

# Dashboard summary endpoint
@app.get("/api/dashboard")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary data"""
    # Count active symbols
    symbol_count = db.query(Symbol).filter(Symbol.is_active == True).count()

    # Count active opportunities
    opportunity_count = db.query(TradingOpportunity).filter(
        TradingOpportunity.is_active == True
    ).count()

    # Get recent high-score opportunities
    top_opportunities = db.query(TradingOpportunity).filter(
        TradingOpportunity.is_active == True
    ).order_by(TradingOpportunity.score.desc()).limit(5).all()

    # Get symbols with most opportunities
    from sqlalchemy import func
    symbol_stats = db.query(
        Symbol.symbol,
        Symbol.company_name,
        func.count(TradingOpportunity.id).label('opportunity_count')
    ).join(
        OptionContract, Symbol.id == OptionContract.symbol_id
    ).join(
        TradingOpportunity, OptionContract.id == TradingOpportunity.contract_id
    ).filter(
        TradingOpportunity.is_active == True
    ).group_by(Symbol.id).order_by(
        func.count(TradingOpportunity.id).desc()
    ).limit(10).all()

    return {
        "symbol_count": symbol_count,
        "opportunity_count": opportunity_count,
        "top_opportunities": top_opportunities,
        "hot_symbols": [
            {
                "symbol": s.symbol,
                "company_name": s.company_name,
                "opportunity_count": s.opportunity_count
            }
            for s in symbol_stats
        ]
    }

# Background task functions
async def fetch_symbol_data(symbol: str):
    """Background task to fetch data for a symbol"""
    logger.info(f"Fetching data for {symbol}")
    fetcher = DataFetcher()

    # Fetch stock data
    stock_data = fetcher.fetch_stock_data(symbol)
    if stock_data is not None:
        fetcher.store_stock_data(symbol, stock_data)

    # Fetch options data
    options_data = fetcher.fetch_options_data(symbol)
    if options_data:
        fetcher.store_options_data(symbol, options_data)

    fetcher.close_session()
    logger.info(f"Completed data fetch for {symbol} (Greeks included from Alpha Vantage)")

async def fetch_all_symbols_data():
    """Background task to fetch data for all symbols"""
    logger.info("Fetching data for all symbols")
    fetcher = DataFetcher()
    results = fetcher.update_all_symbols()
    fetcher.close_session()
    logger.info(f"Completed data fetch for all symbols: {results} (Greeks included from Alpha Vantage)")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
