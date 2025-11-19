"""
Enhanced Trading Opportunity Detection Using Greeks and Financial Strategies

Based on established options trading principles:
- High IV Rank (>80): Premium selling strategies (high theta, high vega)
- Low IV Rank (<20): Premium buying strategies (high vega, low cost)
- Mispricing: Black-Scholes vs market price deviations
- Gamma Scalping: High gamma + low theta near ATM
- Delta Opportunities: Directional plays with favorable risk/reward
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
    IVAnalysis, TradingOpportunity, UserWatchlist
)
from calculations import OptionsCalculator

logger = logging.getLogger(__name__)


class EnhancedOpportunityDetector:
    """
    Advanced opportunity detection using Greeks and established trading strategies
    """

    def __init__(self, db_session: Session):
        """
        Initialize enhanced opportunity detector

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.calculator = OptionsCalculator()

        # Strategy-based thresholds
        self.IV_RANK_HIGH = 80.0  # High IV for selling premium
        self.IV_RANK_MID_HIGH = 60.0  # Moderately high IV
        self.IV_RANK_MID_LOW = 40.0  # Moderately low IV
        self.IV_RANK_LOW = 20.0  # Low IV for buying premium

        self.MISPRICING_THRESHOLD = 0.15  # 15% deviation
        self.TIGHT_SPREAD = 5.0  # <5% spread is excellent
        self.ACCEPTABLE_SPREAD = 10.0  # <10% spread is tradable

        self.MIN_VOLUME = 10  # Minimum volume for liquidity
        self.MIN_OPEN_INTEREST = 50  # Minimum OI for liquidity

        self.MIN_SCORE = 50.0  # Minimum score to save

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

    def calculate_liquidity_score(self, latest_price: OptionPrice) -> float:
        """
        Calculate liquidity score (0-100) based on spread, volume, OI

        Higher scores = better liquidity
        """
        score = 0.0

        # Spread component (40 points max)
        if latest_price.spread_percentage:
            if latest_price.spread_percentage < self.TIGHT_SPREAD:
                score += 40
            elif latest_price.spread_percentage < self.ACCEPTABLE_SPREAD:
                score += 30 * (1 - (latest_price.spread_percentage - self.TIGHT_SPREAD) /
                              (self.ACCEPTABLE_SPREAD - self.TIGHT_SPREAD))

        # Volume component (30 points max)
        if latest_price.volume > 0:
            if latest_price.volume >= 100:
                score += 30
            elif latest_price.volume >= 50:
                score += 20
            elif latest_price.volume >= 10:
                score += 10

        # Open interest component (30 points max)
        if latest_price.open_interest:
            if latest_price.open_interest >= 1000:
                score += 30
            elif latest_price.open_interest >= 500:
                score += 20
            elif latest_price.open_interest >= 100:
                score += 10

        return min(score, 100)

    def detect_premium_selling_opportunity(
        self,
        symbol: Symbol,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect premium selling opportunities (credit strategies)

        Criteria:
        - High IV Rank (>60%)
        - High Theta (time decay working for seller)
        - High Vega (benefit from IV contraction)
        - Good liquidity
        - Not too far OTM (delta > 0.15 for reasonable premium)

        Best for: Covered calls, cash-secured puts, credit spreads
        """
        try:
            # Get IV analysis
            recent_iv = self.db.query(IVAnalysis).filter(
                IVAnalysis.symbol_id == symbol.id
            ).order_by(IVAnalysis.timestamp.desc()).first()

            if not recent_iv or recent_iv.iv_rank < self.IV_RANK_MID_HIGH:
                return None

            # Check Greeks
            if not latest_price.theta or not latest_price.vega or not latest_price.delta:
                return None

            # High theta is negative and large in magnitude (good for sellers)
            theta_magnitude = abs(latest_price.theta)
            if theta_magnitude < 0.02:  # Too little time decay
                return None

            # Check delta for reasonable premium collection
            delta_magnitude = abs(latest_price.delta)
            if delta_magnitude < 0.10:  # Too far OTM, minimal premium
                return None

            # Calculate time to expiry
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)
            days_to_expiry = time_to_expiry * 365

            # Best for 20-60 days out
            if days_to_expiry < 7 or days_to_expiry > 90:
                return None

            # Calculate score
            base_score = 40

            # IV rank contribution (0-25 points)
            if recent_iv.iv_rank >= self.IV_RANK_HIGH:
                base_score += 25
            else:
                base_score += 15 * (recent_iv.iv_rank - self.IV_RANK_MID_HIGH) / (self.IV_RANK_HIGH - self.IV_RANK_MID_HIGH)

            # Theta contribution (0-15 points)
            # Higher theta magnitude = better for selling
            theta_score = min(theta_magnitude / 0.10 * 15, 15)
            base_score += theta_score

            # Vega contribution (0-10 points)
            # Higher vega = more to gain from IV contraction
            if latest_price.vega > 0.20:
                base_score += 10
            elif latest_price.vega > 0.10:
                base_score += 5

            # Liquidity bonus (0-10 points)
            liquidity_score = self.calculate_liquidity_score(latest_price)
            base_score += min(liquidity_score / 10, 10)

            # Get mid price
            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            description = (
                f"PREMIUM SELL: {symbol.symbol} {contract.option_type.upper()} "
                f"${contract.strike_price:.0f} exp {contract.expiry_date.strftime('%m/%d')} "
                f"(IV Rank: {recent_iv.iv_rank:.0f}%, Theta: ${theta_magnitude:.3f}/day, "
                f"Premium: ${mid_price:.2f}, Delta: {delta_magnitude:.2f})"
            )

            return {
                'contract_id': contract.id,
                'opportunity_type': 'premium_sell',
                'score': min(base_score, 100),
                'description': description,
                'metadata': {
                    'iv_rank': recent_iv.iv_rank,
                    'theta': latest_price.theta,
                    'vega': latest_price.vega,
                    'delta': latest_price.delta,
                    'premium': mid_price,
                    'days_to_expiry': days_to_expiry
                }
            }

        except Exception as e:
            logger.error(f"Error detecting premium sell opportunity: {str(e)}")
            return None

    def detect_premium_buying_opportunity(
        self,
        symbol: Symbol,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect premium buying opportunities (debit strategies)

        Criteria:
        - Low IV Rank (<40%)
        - High Vega (benefit from IV expansion)
        - Lower Theta (minimize time decay cost)
        - Good liquidity
        - Reasonable delta (directional exposure)

        Best for: Long calls/puts, debit spreads, calendar spreads
        """
        try:
            # Get IV analysis
            recent_iv = self.db.query(IVAnalysis).filter(
                IVAnalysis.symbol_id == symbol.id
            ).order_by(IVAnalysis.timestamp.desc()).first()

            if not recent_iv or recent_iv.iv_rank > self.IV_RANK_MID_LOW:
                return None

            # Check Greeks
            if not latest_price.theta or not latest_price.vega or not latest_price.delta:
                return None

            # Lower theta magnitude is better for buyers
            theta_magnitude = abs(latest_price.theta)

            # High vega for IV expansion potential
            if latest_price.vega < 0.05:
                return None

            # Calculate time to expiry
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)
            days_to_expiry = time_to_expiry * 365

            # Prefer longer duration for low IV plays (30-90 days)
            if days_to_expiry < 20 or days_to_expiry > 120:
                return None

            # Calculate score
            base_score = 40

            # IV rank contribution (0-25 points)
            # Lower IV rank = better for buying
            if recent_iv.iv_rank <= self.IV_RANK_LOW:
                base_score += 25
            else:
                base_score += 15 * (self.IV_RANK_MID_LOW - recent_iv.iv_rank) / (self.IV_RANK_MID_LOW - self.IV_RANK_LOW)

            # Vega contribution (0-15 points)
            # Higher vega = more to gain from IV expansion
            vega_score = min(latest_price.vega / 0.30 * 15, 15)
            base_score += vega_score

            # Theta contribution (0-10 points)
            # Lower theta magnitude = less decay cost
            if theta_magnitude < 0.02:
                base_score += 10
            elif theta_magnitude < 0.05:
                base_score += 5

            # Liquidity bonus (0-10 points)
            liquidity_score = self.calculate_liquidity_score(latest_price)
            base_score += min(liquidity_score / 10, 10)

            # Get mid price
            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            delta_magnitude = abs(latest_price.delta)

            description = (
                f"PREMIUM BUY: {symbol.symbol} {contract.option_type.upper()} "
                f"${contract.strike_price:.0f} exp {contract.expiry_date.strftime('%m/%d')} "
                f"(IV Rank: {recent_iv.iv_rank:.0f}%, Vega: {latest_price.vega:.2f}, "
                f"Cost: ${mid_price:.2f}, Delta: {delta_magnitude:.2f})"
            )

            return {
                'contract_id': contract.id,
                'opportunity_type': 'premium_buy',
                'score': min(base_score, 100),
                'description': description,
                'metadata': {
                    'iv_rank': recent_iv.iv_rank,
                    'theta': latest_price.theta,
                    'vega': latest_price.vega,
                    'delta': latest_price.delta,
                    'cost': mid_price,
                    'days_to_expiry': days_to_expiry
                }
            }

        except Exception as e:
            logger.error(f"Error detecting premium buy opportunity: {str(e)}")
            return None

    def detect_gamma_scalping_opportunity(
        self,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect gamma scalping opportunities

        Criteria:
        - High Gamma (large delta changes per stock move)
        - Low Theta (minimize decay cost)
        - Near ATM (maximize gamma)
        - Near expiration (7-30 days)
        - Good liquidity for frequent trading

        Best for: Active traders in volatile markets
        """
        try:
            if not latest_price.gamma or not latest_price.theta or not latest_price.delta:
                return None

            # Check gamma magnitude
            gamma_magnitude = abs(latest_price.gamma)
            if gamma_magnitude < 0.01:  # Too low for effective scalping
                return None

            # Calculate moneyness (how close to ATM)
            moneyness = stock_price / contract.strike_price
            if contract.option_type == 'put':
                moneyness = contract.strike_price / stock_price

            # Prefer near ATM (0.95 to 1.05)
            if moneyness < 0.90 or moneyness > 1.10:
                return None

            # Time to expiry - gamma peaks near expiration
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)
            days_to_expiry = time_to_expiry * 365

            if days_to_expiry < 7 or days_to_expiry > 45:
                return None

            # Gamma/Theta ratio - want high gamma, low theta cost
            theta_magnitude = abs(latest_price.theta)
            if theta_magnitude == 0:
                return None

            gamma_theta_ratio = gamma_magnitude / theta_magnitude

            if gamma_theta_ratio < 0.5:  # Theta cost too high relative to gamma
                return None

            # Check liquidity - critical for scalping
            liquidity_score = self.calculate_liquidity_score(latest_price)
            if liquidity_score < 50:  # Need good liquidity
                return None

            # Calculate score
            base_score = 45

            # Gamma contribution (0-20 points)
            gamma_score = min(gamma_magnitude / 0.05 * 20, 20)
            base_score += gamma_score

            # Moneyness contribution (0-15 points)
            # Closer to ATM = better
            atm_distance = abs(1.0 - moneyness)
            moneyness_score = 15 * (1 - atm_distance / 0.10)
            base_score += max(moneyness_score, 0)

            # Gamma/Theta ratio (0-10 points)
            ratio_score = min(gamma_theta_ratio / 2.0 * 10, 10)
            base_score += ratio_score

            # Liquidity contribution (0-10 points)
            base_score += min(liquidity_score / 10, 10)

            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            description = (
                f"GAMMA SCALP: {contract.option_type.upper()} ${contract.strike_price:.0f} "
                f"exp {contract.expiry_date.strftime('%m/%d')} "
                f"(Gamma: {gamma_magnitude:.3f}, G/T Ratio: {gamma_theta_ratio:.1f}, "
                f"Stock: ${stock_price:.2f}, Moneyness: {moneyness:.2%})"
            )

            return {
                'contract_id': contract.id,
                'opportunity_type': 'gamma_scalp',
                'score': min(base_score, 100),
                'description': description,
                'metadata': {
                    'gamma': latest_price.gamma,
                    'theta': latest_price.theta,
                    'gamma_theta_ratio': gamma_theta_ratio,
                    'moneyness': moneyness,
                    'days_to_expiry': days_to_expiry,
                    'liquidity_score': liquidity_score
                }
            }

        except Exception as e:
            logger.error(f"Error detecting gamma scalping opportunity: {str(e)}")
            return None

    def detect_mispricing_opportunity(
        self,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Enhanced mispricing detection with Greek validation

        Compares market price to Black-Scholes theoretical value
        Validates with Greek alignment
        """
        try:
            if not latest_price.implied_volatility or latest_price.implied_volatility <= 0:
                return None

            # Calculate theoretical price
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)
            if time_to_expiry <= 0:
                return None

            theoretical_price = self.calculator.calculate_theoretical_price(
                stock_price=stock_price,
                strike_price=contract.strike_price,
                time_to_expiry=time_to_expiry,
                volatility=latest_price.implied_volatility,
                option_type=contract.option_type
            )

            if theoretical_price <= 0:
                return None

            # Get market price
            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            if mid_price <= 0:
                return None

            # Calculate mispricing
            mispricing_pct = (mid_price - theoretical_price) / theoretical_price

            # Need significant mispricing
            if abs(mispricing_pct) < self.MISPRICING_THRESHOLD:
                return None

            # Check liquidity - critical for mispricing arbitrage
            liquidity_score = self.calculate_liquidity_score(latest_price)
            if liquidity_score < 40:  # Need reasonable liquidity
                return None

            # Calculate score
            base_score = 50

            # Mispricing magnitude (0-30 points)
            mispricing_score = min(abs(mispricing_pct) / 0.30 * 30, 30)
            base_score += mispricing_score

            # Liquidity contribution (0-20 points)
            base_score += min(liquidity_score / 5, 20)

            opportunity_type = 'overpriced' if mispricing_pct > 0 else 'underpriced'
            action = 'SELL' if mispricing_pct > 0 else 'BUY'

            description = (
                f"MISPRICING ({action}): {contract.option_type.upper()} "
                f"${contract.strike_price:.0f} exp {contract.expiry_date.strftime('%m/%d')} "
                f"is {abs(mispricing_pct)*100:.1f}% {opportunity_type}. "
                f"Market: ${mid_price:.2f}, Fair: ${theoretical_price:.2f}"
            )

            return {
                'contract_id': contract.id,
                'opportunity_type': opportunity_type,
                'score': min(base_score, 100),
                'description': description,
                'metadata': {
                    'market_price': mid_price,
                    'theoretical_price': theoretical_price,
                    'mispricing_pct': mispricing_pct * 100,
                    'liquidity_score': liquidity_score
                }
            }

        except Exception as e:
            logger.error(f"Error detecting mispricing: {str(e)}")
            return None

    def detect_high_delta_opportunity(
        self,
        symbol: Symbol,
        contract: OptionContract,
        latest_price: OptionPrice,
        stock_price: float
    ) -> Optional[Dict]:
        """
        Detect directional opportunities with favorable delta

        Criteria:
        - High delta (>0.70) for stock replacement
        - Low theta cost relative to delta
        - Good liquidity
        - Reasonable time to expiration
        """
        try:
            if not latest_price.delta or not latest_price.theta:
                return None

            delta_magnitude = abs(latest_price.delta)

            # Need high delta for stock replacement
            if delta_magnitude < 0.65:
                return None

            # Calculate time to expiry
            time_to_expiry = self.calculator.calculate_time_to_expiry(contract.expiry_date)
            days_to_expiry = time_to_expiry * 365

            # Prefer 30-120 days
            if days_to_expiry < 20 or days_to_expiry > 180:
                return None

            # Check liquidity
            liquidity_score = self.calculate_liquidity_score(latest_price)
            if liquidity_score < 30:
                return None

            # Delta/Theta ratio
            theta_magnitude = abs(latest_price.theta)
            if theta_magnitude > 0:
                delta_theta_ratio = delta_magnitude / theta_magnitude
            else:
                delta_theta_ratio = 0

            # Calculate score
            base_score = 45

            # Delta contribution (0-20 points)
            delta_score = (delta_magnitude - 0.65) / 0.35 * 20
            base_score += min(delta_score, 20)

            # Delta/Theta ratio (0-15 points)
            if delta_theta_ratio > 15:
                base_score += 15
            elif delta_theta_ratio > 10:
                base_score += 10
            elif delta_theta_ratio > 5:
                base_score += 5

            # Liquidity (0-10 points)
            base_score += min(liquidity_score / 10, 10)

            # ITM/OTM status (0-10 points)
            intrinsic = self.calculator.calculate_intrinsic_value(
                stock_price, contract.strike_price, contract.option_type
            )
            mid_price = (latest_price.bid + latest_price.ask) / 2 if (latest_price.bid > 0 and latest_price.ask > 0) else latest_price.last_price

            if mid_price > 0:
                itm_pct = intrinsic / mid_price if intrinsic > 0 else 0
                if itm_pct > 0.7:  # Deeply ITM
                    base_score += 10
                elif itm_pct > 0.5:
                    base_score += 5

            description = (
                f"HIGH DELTA: {symbol.symbol} {contract.option_type.upper()} "
                f"${contract.strike_price:.0f} exp {contract.expiry_date.strftime('%m/%d')} "
                f"(Delta: {delta_magnitude:.2f}, D/T: {delta_theta_ratio:.1f}, "
                f"Stock: ${stock_price:.2f})"
            )

            return {
                'contract_id': contract.id,
                'opportunity_type': 'high_delta',
                'score': min(base_score, 100),
                'description': description,
                'metadata': {
                    'delta': latest_price.delta,
                    'theta': latest_price.theta,
                    'delta_theta_ratio': delta_theta_ratio,
                    'days_to_expiry': days_to_expiry
                }
            }

        except Exception as e:
            logger.error(f"Error detecting high delta opportunity: {str(e)}")
            return None

    def scan_symbol_opportunities(
        self,
        symbol: Symbol,
        save_to_db: bool = True
    ) -> List[Dict]:
        """
        Scan all opportunities for a specific symbol using enhanced detection

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

                # Run all enhanced detection algorithms
                detectors = [
                    lambda: self.detect_premium_selling_opportunity(symbol, contract, latest_price, stock_price),
                    lambda: self.detect_premium_buying_opportunity(symbol, contract, latest_price, stock_price),
                    lambda: self.detect_gamma_scalping_opportunity(contract, latest_price, stock_price),
                    lambda: self.detect_mispricing_opportunity(contract, latest_price, stock_price),
                    lambda: self.detect_high_delta_opportunity(symbol, contract, latest_price, stock_price),
                ]

                for detector in detectors:
                    try:
                        opp = detector()
                        if opp and opp['score'] >= self.MIN_SCORE:
                            opportunities.append(opp)
                    except Exception as e:
                        logger.error(f"Detector error: {str(e)}")
                        continue

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

            # Get all symbols from active watchlist entries
            symbols = self.db.query(Symbol).join(
                UserWatchlist, Symbol.id == UserWatchlist.symbol_id
            ).filter(UserWatchlist.is_active == True).all()

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


# Alias for backwards compatibility
OpportunityDetector = EnhancedOpportunityDetector


if __name__ == "__main__":
    """Test enhanced opportunity detection"""
    from models import SessionLocal, create_tables

    create_tables()
    db = SessionLocal()

    detector = EnhancedOpportunityDetector(db)

    print("Enhanced Opportunity Detection Test")
    print("=" * 80)

    # Scan all opportunities
    opportunities = detector.scan_all_opportunities(save_to_db=True)

    for symbol, opps in opportunities.items():
        print(f"\n{symbol}: {len(opps)} opportunities")
        for opp in sorted(opps, key=lambda x: x['score'], reverse=True)[:5]:
            print(f"  [{opp['score']:.0f}] {opp['opportunity_type']}: {opp['description']}")

    db.close()
