"""
Trading opportunity detection and scoring algorithms
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging

from models import (
    Symbol, StockPrice, OptionContract, OptionPrice,
    IVAnalysis, TradingOpportunity
)
from calculations import OptionsCalculator

logger = logging.getLogger(__name__)


class OpportunityDetector:
    """
    Identifies and scores trading opportunities based on:
    - Mispricing vs theoretical value
    - IV rank extremes
    - Volume anomalies
    - Time value near expiration
    """

    def __init__(self, db_session: Session):
        """
        Initialize opportunity detector

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.calculator = OptionsCalculator()

        # Detection thresholds
        self.MISPRICING_THRESHOLD = 0.20  # 20% above/below theoretical
        self.IV_RANK_HIGH = 80.0  # IV rank >80% is expensive
        self.IV_RANK_LOW = 20.0   # IV rank <20% is cheap
        self.VOLUME_MULTIPLIER = 1.5  # 150% of average volume
        self.MIN_SCORE = 40.0  # Minimum score to save opportunity

    def get_current_stock_price(self, symbol_id: int) -> Optional[float]:
        """Get most recent stock price for a symbol"""
        try:
            latest = self.db.query(StockPrice).filter(
                StockPrice.symbol_id == symbol_id
            ).order_by(StockPrice.timestamp.desc()).first()

            return latest.close_price if latest else None

        except Exception as e:
            logger.error(f"Error getting stock price: {str(e)}")
            return None

    def calculate_average_volume(
        self,
        contract_id: int,
        days: int = 10
    ) -> float:
        """Calculate average volume for an option contract"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            volumes = self.db.query(OptionPrice.volume).filter(
                and_(
                    OptionPrice.contract_id == contract_id,
                    OptionPrice.timestamp >= cutoff_date,
                    OptionPrice.volume > 0
                )
            ).all()

            if not volumes:
                return 0.0

            avg_volume = np.mean([v[0] for v in volumes])
            return avg_volume

        except Exception as e:
            logger.error(f"Error calculating average volume: {str(e)}")
            return 0.0

    def detect_mispricing(
        self,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect options trading significantly above/below theoretical value

        Args:
            contract: Option contract
            latest_price: Most recent option price data
            stock_price: Current stock price

        Returns:
            Opportunity dict if detected, None otherwise
        """
        try:
            if not latest_price.implied_volatility or latest_price.implied_volatility <= 0:
                return None

            # Calculate theoretical price
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)

            theoretical_price = self.calculator.calculate_theoretical_price(
                stock_price=stock_price,
                strike_price=contract.strike_price,
                time_to_expiry=time_to_expiry,
                volatility=latest_price.implied_volatility,
                option_type=contract.option_type
            )

            if theoretical_price <= 0:
                return None

            # Calculate mid price
            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            if mid_price <= 0:
                return None

            # Calculate mispricing percentage
            mispricing_pct = (mid_price - theoretical_price) / theoretical_price

            if abs(mispricing_pct) >= self.MISPRICING_THRESHOLD:
                # Calculate score (0-100)
                base_score = min(abs(mispricing_pct) / self.MISPRICING_THRESHOLD * 50, 50)

                # Bonus for good liquidity (tight spread)
                if latest_price.spread_percentage:
                    if latest_price.spread_percentage < 5:
                        base_score += 20
                    elif latest_price.spread_percentage < 10:
                        base_score += 10

                # Bonus for volume
                if latest_price.volume > 100:
                    base_score += 15
                elif latest_price.volume > 50:
                    base_score += 10

                opportunity_type = 'overpriced' if mispricing_pct > 0 else 'underpriced'

                description = (
                    f"{contract.option_type.upper()} ${contract.strike_price} "
                    f"exp {contract.expiry_date.strftime('%Y-%m-%d')} is "
                    f"{opportunity_type} by {abs(mispricing_pct)*100:.1f}%. "
                    f"Market: ${mid_price:.2f}, Theoretical: ${theoretical_price:.2f}"
                )

                return {
                    'contract_id': contract.id,
                    'opportunity_type': opportunity_type,
                    'score': min(base_score, 100),
                    'description': description,
                    'metadata': {
                        'market_price': mid_price,
                        'theoretical_price': theoretical_price,
                        'mispricing_pct': mispricing_pct * 100
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error detecting mispricing: {str(e)}")
            return None

    def detect_iv_extremes(
        self,
        symbol: Symbol,
        contract: OptionContract,
        latest_price: OptionPrice
    ) -> Optional[Dict]:
        """
        Detect options with extreme IV rank (>80% or <20%)

        Args:
            symbol: Stock symbol
            contract: Option contract
            latest_price: Most recent option price data

        Returns:
            Opportunity dict if detected, None otherwise
        """
        try:
            # Get recent IV analysis
            recent_iv = self.db.query(IVAnalysis).filter(
                IVAnalysis.symbol_id == symbol.id
            ).order_by(IVAnalysis.timestamp.desc()).first()

            if not recent_iv:
                return None

            iv_rank = recent_iv.iv_rank

            if iv_rank >= self.IV_RANK_HIGH:
                # High IV - potential sell opportunity
                score = 40 + (iv_rank - self.IV_RANK_HIGH) / 20 * 30  # Scale from 40-70

                # Bonus for high theta (good for selling)
                if latest_price.theta and latest_price.theta < -0.05:
                    score += 15

                description = (
                    f"{symbol.symbol} {contract.option_type.upper()} ${contract.strike_price} "
                    f"has high IV rank of {iv_rank:.1f}% - potential premium selling opportunity. "
                    f"Current IV: {recent_iv.current_iv*100:.1f}%"
                )

                return {
                    'contract_id': contract.id,
                    'opportunity_type': 'high_iv',
                    'score': min(score, 100),
                    'description': description,
                    'metadata': {
                        'iv_rank': iv_rank,
                        'current_iv': recent_iv.current_iv * 100
                    }
                }

            elif iv_rank <= self.IV_RANK_LOW:
                # Low IV - potential buy opportunity
                score = 40 + (self.IV_RANK_LOW - iv_rank) / 20 * 30

                # Bonus for positive vega (benefits from IV increase)
                if latest_price.vega and latest_price.vega > 0.1:
                    score += 15

                description = (
                    f"{symbol.symbol} {contract.option_type.upper()} ${contract.strike_price} "
                    f"has low IV rank of {iv_rank:.1f}% - potential cheap premium buying opportunity. "
                    f"Current IV: {recent_iv.current_iv*100:.1f}%"
                )

                return {
                    'contract_id': contract.id,
                    'opportunity_type': 'low_iv',
                    'score': min(score, 100),
                    'description': description,
                    'metadata': {
                        'iv_rank': iv_rank,
                        'current_iv': recent_iv.current_iv * 100
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error detecting IV extremes: {str(e)}")
            return None

    def detect_volume_anomaly(
        self,
        contract: OptionContract,
        latest_price: OptionPrice
    ) -> Optional[Dict]:
        """
        Detect unusual volume (>150% of average)

        Args:
            contract: Option contract
            latest_price: Most recent option price data

        Returns:
            Opportunity dict if detected, None otherwise
        """
        try:
            if latest_price.volume <= 0:
                return None

            avg_volume = self.calculate_average_volume(contract.id, days=10)

            if avg_volume <= 0:
                return None

            volume_ratio = latest_price.volume / avg_volume

            if volume_ratio >= self.VOLUME_MULTIPLIER:
                score = 50 + min((volume_ratio - self.VOLUME_MULTIPLIER) * 20, 30)

                # Bonus for open interest
                if latest_price.open_interest and latest_price.open_interest > 500:
                    score += 10

                description = (
                    f"{contract.option_type.upper()} ${contract.strike_price} "
                    f"exp {contract.expiry_date.strftime('%Y-%m-%d')} has unusual volume. "
                    f"Current: {latest_price.volume}, Avg: {avg_volume:.0f} ({volume_ratio:.1f}x)"
                )

                return {
                    'contract_id': contract.id,
                    'opportunity_type': 'unusual_volume',
                    'score': min(score, 100),
                    'description': description,
                    'metadata': {
                        'current_volume': latest_price.volume,
                        'average_volume': avg_volume,
                        'volume_ratio': volume_ratio
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error detecting volume anomaly: {str(e)}")
            return None

    def detect_high_time_value_near_expiry(
        self,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect high time value near expiration (potential theta decay play)

        Args:
            contract: Option contract
            latest_price: Most recent option price data
            stock_price: Current stock price

        Returns:
            Opportunity dict if detected, None otherwise
        """
        try:
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)

            # Only check if within 30 days of expiration
            if time_to_expiry > (30 / 365.0):
                return None

            # Calculate intrinsic value
            intrinsic = self.calculator.calculate_intrinsic_value(
                stock_price, contract.strike_price, contract.option_type
            )

            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            if mid_price <= 0:
                return None

            time_value = mid_price - intrinsic
            time_value_pct = (time_value / mid_price * 100) if mid_price > 0 else 0

            # If time value is >50% of option price near expiration
            if time_value_pct >= 50 and time_value > 0.50:
                days_to_expiry = time_to_expiry * 365

                score = 45 + min(time_value_pct - 50, 30)

                # Bonus for high theta
                if latest_price.theta and latest_price.theta < -0.05:
                    score += 15

                description = (
                    f"{contract.option_type.upper()} ${contract.strike_price} "
                    f"exp in {days_to_expiry:.0f} days has high time value "
                    f"({time_value_pct:.1f}% of price, ${time_value:.2f}) - "
                    f"potential theta decay opportunity"
                )

                return {
                    'contract_id': contract.id,
                    'opportunity_type': 'high_time_value',
                    'score': min(score, 100),
                    'description': description,
                    'metadata': {
                        'time_value': time_value,
                        'time_value_pct': time_value_pct,
                        'days_to_expiry': days_to_expiry
                    }
                }

            return None

        except Exception as e:
            logger.error(f"Error detecting high time value: {str(e)}")
            return None

    def scan_symbol_opportunities(
        self,
        symbol: Symbol,
        save_to_db: bool = True
    ) -> List[Dict]:
        """
        Scan all opportunities for a specific symbol

        Args:
            symbol: Symbol to scan
            save_to_db: Whether to save opportunities to database

        Returns:
            List of detected opportunities
        """
        opportunities = []

        try:
            # Get current stock price
            stock_price = self.get_current_stock_price(symbol.id)
            if not stock_price:
                logger.warning(f"No stock price available for {symbol.symbol}")
                return opportunities

            # Get active option contracts
            contracts = self.db.query(OptionContract).filter(
                and_(
                    OptionContract.symbol_id == symbol.id,
                    OptionContract.is_active == True,
                    OptionContract.expiry_date > datetime.now()
                )
            ).all()

            logger.info(f"Scanning {len(contracts)} contracts for {symbol.symbol}")

            for contract in contracts:
                # Get latest price data
                latest_price = self.db.query(OptionPrice).filter(
                    OptionPrice.contract_id == contract.id
                ).order_by(OptionPrice.timestamp.desc()).first()

                if not latest_price:
                    continue

                # Run all detection algorithms
                detectors = [
                    lambda: self.detect_mispricing(contract, latest_price, stock_price),
                    lambda: self.detect_iv_extremes(symbol, contract, latest_price),
                    lambda: self.detect_volume_anomaly(contract, latest_price),
                    lambda: self.detect_high_time_value_near_expiry(contract, latest_price, stock_price)
                ]

                for detector in detectors:
                    opp = detector()
                    if opp and opp['score'] >= self.MIN_SCORE:
                        opportunities.append(opp)

            # Save to database if requested
            if save_to_db and opportunities:
                self._save_opportunities(opportunities)

            logger.info(f"Found {len(opportunities)} opportunities for {symbol.symbol}")

        except Exception as e:
            logger.error(f"Error scanning opportunities for {symbol.symbol}: {str(e)}")

        return opportunities

    def scan_all_opportunities(self, save_to_db: bool = True) -> Dict[str, List[Dict]]:
        """
        Scan opportunities for all active symbols

        Args:
            save_to_db: Whether to save opportunities to database

        Returns:
            Dictionary mapping symbols to their opportunities
        """
        all_opportunities = {}

        try:
            # Deactivate old opportunities
            if save_to_db:
                self.db.query(TradingOpportunity).update({'is_active': False})
                self.db.commit()

            # Get all active symbols
            symbols = self.db.query(Symbol).filter(Symbol.is_active == True).all()

            for symbol in symbols:
                opportunities = self.scan_symbol_opportunities(symbol, save_to_db=False)
                if opportunities:
                    all_opportunities[symbol.symbol] = opportunities

            # Save all opportunities
            if save_to_db:
                all_opps = [opp for opps in all_opportunities.values() for opp in opps]
                self._save_opportunities(all_opps)

            total_count = sum(len(opps) for opps in all_opportunities.values())
            logger.info(f"Total opportunities found: {total_count}")

        except Exception as e:
            logger.error(f"Error scanning all opportunities: {str(e)}")

        return all_opportunities

    def _save_opportunities(self, opportunities: List[Dict]) -> None:
        """Save opportunities to database"""
        try:
            for opp in opportunities:
                # Check if similar opportunity already exists
                existing = self.db.query(TradingOpportunity).filter(
                    and_(
                        TradingOpportunity.contract_id == opp['contract_id'],
                        TradingOpportunity.opportunity_type == opp['opportunity_type'],
                        TradingOpportunity.is_active == True
                    )
                ).first()

                if existing:
                    # Update existing
                    existing.score = opp['score']
                    existing.description = opp['description']
                    existing.timestamp = datetime.now()
                else:
                    # Create new
                    new_opp = TradingOpportunity(
                        contract_id=opp['contract_id'],
                        opportunity_type=opp['opportunity_type'],
                        score=opp['score'],
                        description=opp['description'],
                        is_active=True
                    )
                    self.db.add(new_opp)

            self.db.commit()
            logger.info(f"Saved {len(opportunities)} opportunities to database")

        except Exception as e:
            logger.error(f"Error saving opportunities: {str(e)}")
            self.db.rollback()


def main():
    """Test opportunity detection"""
    from models import SessionLocal, create_tables

    create_tables()
    db = SessionLocal()

    detector = OpportunityDetector(db)

    print("Opportunity Detection Test")
    print("-" * 60)

    # Scan all opportunities
    opportunities = detector.scan_all_opportunities(save_to_db=True)

    for symbol, opps in opportunities.items():
        print(f"\n{symbol}: {len(opps)} opportunities")
        for opp in sorted(opps, key=lambda x: x['score'], reverse=True)[:3]:
            print(f"  [{opp['score']:.0f}] {opp['opportunity_type']}: {opp['description'][:80]}...")

    db.close()


if __name__ == "__main__":
    main()
