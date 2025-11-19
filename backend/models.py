from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    company_name = Column(String)
    sector = Column(String)
    is_active = Column(Boolean, default=True)  # Whether symbol is still tradeable (not delisted)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stock_prices = relationship("StockPrice", back_populates="symbol_rel")
    option_contracts = relationship("OptionContract", back_populates="symbol_rel")
    watchlist_entries = relationship("UserWatchlist", back_populates="symbol_rel")

class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"))
    timestamp = Column(DateTime, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    volume = Column(Integer)
    
    # Relationship
    symbol_rel = relationship("Symbol", back_populates="stock_prices")

class OptionContract(Base):
    __tablename__ = "option_contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"))
    contract_symbol = Column(String, unique=True, index=True)
    expiry_date = Column(DateTime)
    strike_price = Column(Float)
    option_type = Column(String)  # 'call' or 'put'
    is_active = Column(Boolean, default=True)
    
    # Relationships
    symbol_rel = relationship("Symbol", back_populates="option_contracts")
    option_prices = relationship("OptionPrice", back_populates="contract")

class OptionPrice(Base):
    __tablename__ = "option_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("option_contracts.id"))
    timestamp = Column(DateTime, index=True)
    bid = Column(Float)
    ask = Column(Float)
    last_price = Column(Float)
    volume = Column(Integer)
    open_interest = Column(Integer)
    
    # Calculated values
    implied_volatility = Column(Float)
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)
    rho = Column(Float)
    
    # Analysis metrics
    bid_ask_spread = Column(Float)
    spread_percentage = Column(Float)
    time_value = Column(Float)
    intrinsic_value = Column(Float)
    
    # Relationship
    contract = relationship("OptionContract", back_populates="option_prices")

class IVAnalysis(Base):
    __tablename__ = "iv_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"))
    timestamp = Column(DateTime, index=True)
    current_iv = Column(Float)
    iv_rank = Column(Float)  # 0-100 percentile vs 1 year range
    iv_percentile = Column(Float)  # 0-100 percentile vs historical distribution
    hv_20d = Column(Float)  # 20-day historical volatility
    hv_30d = Column(Float)  # 30-day historical volatility
    
class TradingOpportunity(Base):
    __tablename__ = "trading_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("option_contracts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    opportunity_type = Column(String)  # 'overpriced', 'underpriced', 'high_iv', etc.
    score = Column(Float)  # 0-100 confidence score
    description = Column(String)
    is_active = Column(Boolean, default=True)

    # Relationships
    contract = relationship("OptionContract", backref="opportunities")
    
class UserWatchlist(Base):
    __tablename__ = "user_watchlists"

    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)  # Whether this watchlist entry is active

    # Relationship
    symbol_rel = relationship("Symbol", back_populates="watchlist_entries")

# Database setup
# Use PostgreSQL in production (Render), SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./options_tracker.db")

# SQLite-specific connection args
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL - configured for concurrent scheduled jobs
    # Handle Render's postgres:// vs postgresql:// prefix
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Verify connections before using
        pool_size=20,            # Increased from default 5 to handle concurrent jobs
        max_overflow=30,         # Increased from default 10 for peak loads
        pool_recycle=3600,       # Recycle connections after 1 hour
        pool_timeout=60          # Wait up to 60s for connection (increased from 30s)
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
