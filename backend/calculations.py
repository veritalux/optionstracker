"""
Options pricing helper functions

Note: Greeks calculations have been removed as they are now provided
directly by IVolatility API via the /equities/rt/options-rawiv endpoint.

This module now contains only helper functions for:
- Theoretical pricing (for mispricing detection)
- Intrinsic and time value calculations
- IV analysis (rank, percentile, historical volatility)
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional
import logging

try:
    from py_vollib.black_scholes import black_scholes as bs_price
    from py_vollib.black_scholes.implied_volatility import implied_volatility as bs_iv
except ImportError:
    logging.warning("py_vollib not available, using scipy fallback")
    bs_price = None

from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptionsCalculator:
    """
    Options pricing and analysis calculator

    Greeks are now provided by IVolatility API and stored directly.
    This calculator provides helper functions for pricing and analysis.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize calculator

        Args:
            risk_free_rate: Annual risk-free interest rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate
        self.use_py_vollib = bs_price is not None

    def calculate_time_to_expiry(self, expiry_date: datetime) -> float:
        """
        Calculate time to expiry in years

        Args:
            expiry_date: Option expiration date

        Returns:
            Time to expiry in years
        """
        now = datetime.now()
        days_to_expiry = (expiry_date - now).total_seconds() / 86400
        return max(days_to_expiry / 365.0, 0.0001)  # Minimum to avoid division by zero

    def calculate_theoretical_price(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate theoretical option price using Black-Scholes

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility (as decimal, e.g., 0.25 for 25%)
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Theoretical option price
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate

        flag = 'c' if option_type.lower() == 'call' else 'p'

        try:
            if self.use_py_vollib:
                price = bs_price(
                    flag=flag,
                    S=stock_price,
                    K=strike_price,
                    t=time_to_expiry,
                    r=risk_free_rate,
                    sigma=volatility
                )
                return price
            else:
                # Fallback to scipy implementation
                return self._bs_price_scipy(
                    stock_price, strike_price, time_to_expiry,
                    volatility, option_type, risk_free_rate
                )
        except Exception as e:
            logger.error(f"Error calculating theoretical price: {str(e)}")
            return 0.0

    def _bs_price_scipy(
        self,
        S: float, K: float, t: float,
        sigma: float, option_type: str, r: float
    ) -> float:
        """Scipy fallback for Black-Scholes pricing"""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        d2 = d1 - sigma * np.sqrt(t)

        if option_type.lower() == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * t) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * t) * norm.cdf(-d2) - S * norm.cdf(-d1)

        return price

    def calculate_implied_volatility(
        self,
        option_price: float,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate implied volatility from option price

        Args:
            option_price: Market price of the option
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Implied volatility or None if calculation fails
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate

        flag = 'c' if option_type.lower() == 'call' else 'p'

        try:
            if self.use_py_vollib:
                iv = bs_iv(
                    price=option_price,
                    S=stock_price,
                    K=strike_price,
                    t=time_to_expiry,
                    r=risk_free_rate,
                    flag=flag
                )
                return iv
            else:
                # Fallback to Newton-Raphson method
                return self._implied_vol_newton_raphson(
                    option_price, stock_price, strike_price,
                    time_to_expiry, option_type, risk_free_rate
                )
        except Exception as e:
            logger.warning(f"Could not calculate IV: {str(e)}")
            return None

    def _implied_vol_newton_raphson(
        self,
        target_price: float, S: float, K: float,
        t: float, option_type: str, r: float,
        max_iterations: int = 100, tolerance: float = 1e-5
    ) -> Optional[float]:
        """Newton-Raphson method for IV calculation"""
        sigma = 0.5  # Initial guess

        for _ in range(max_iterations):
            price = self._bs_price_scipy(S, K, t, sigma, option_type, r)
            vega_val = self._calculate_vega_scipy(S, K, t, sigma, r)

            diff = price - target_price

            if abs(diff) < tolerance:
                return sigma

            if vega_val == 0:
                return None

            sigma = sigma - diff / (vega_val * 100)  # Vega is per 1%

            if sigma <= 0:
                return None

        return None

    def _calculate_vega_scipy(self, S: float, K: float, t: float, sigma: float, r: float) -> float:
        """Calculate vega using scipy"""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        return S * norm.pdf(d1) * np.sqrt(t) / 100.0

    def calculate_intrinsic_value(
        self,
        stock_price: float,
        strike_price: float,
        option_type: str
    ) -> float:
        """Calculate intrinsic value of an option"""
        if option_type.lower() == 'call':
            return max(0, stock_price - strike_price)
        else:
            return max(0, strike_price - stock_price)

    def calculate_time_value(
        self,
        option_price: float,
        intrinsic_value: float
    ) -> float:
        """Calculate time value of an option"""
        return max(0, option_price - intrinsic_value)

    def calculate_iv_rank(
        self,
        current_iv: float,
        iv_history: pd.Series,
        period_days: int = 365
    ) -> float:
        """
        Calculate IV Rank (current IV vs 1-year high/low range)

        Args:
            current_iv: Current implied volatility
            iv_history: Historical IV time series
            period_days: Period in days (default 365)

        Returns:
            IV Rank as percentage (0-100)
        """
        try:
            # Get recent history
            recent_iv = iv_history.tail(period_days)

            if len(recent_iv) < 10:
                return 50.0  # Not enough data

            iv_min = recent_iv.min()
            iv_max = recent_iv.max()

            if iv_max == iv_min:
                return 50.0

            iv_rank = ((current_iv - iv_min) / (iv_max - iv_min)) * 100
            return max(0, min(100, iv_rank))

        except Exception as e:
            logger.error(f"Error calculating IV rank: {str(e)}")
            return 50.0

    def calculate_iv_percentile(
        self,
        current_iv: float,
        iv_history: pd.Series,
        period_days: int = 365
    ) -> float:
        """
        Calculate IV Percentile (current IV vs historical distribution)

        Args:
            current_iv: Current implied volatility
            iv_history: Historical IV time series
            period_days: Period in days

        Returns:
            IV Percentile as percentage (0-100)
        """
        try:
            recent_iv = iv_history.tail(period_days)

            if len(recent_iv) < 10:
                return 50.0

            percentile = (recent_iv < current_iv).sum() / len(recent_iv) * 100
            return max(0, min(100, percentile))

        except Exception as e:
            logger.error(f"Error calculating IV percentile: {str(e)}")
            return 50.0

    def calculate_historical_volatility(
        self,
        price_history: pd.Series,
        period_days: int = 30
    ) -> float:
        """
        Calculate historical volatility from price data

        Args:
            price_history: Historical price time series
            period_days: Period in days

        Returns:
            Historical volatility (annualized)
        """
        try:
            prices = price_history.tail(period_days + 1)

            if len(prices) < 10:
                return 0.0

            # Calculate log returns
            log_returns = np.log(prices / prices.shift(1)).dropna()

            # Annualized volatility
            daily_vol = log_returns.std()
            annual_vol = daily_vol * np.sqrt(252)  # 252 trading days

            return annual_vol

        except Exception as e:
            logger.error(f"Error calculating historical volatility: {str(e)}")
            return 0.0


def main():
    """Test the calculations"""
    calc = OptionsCalculator(risk_free_rate=0.05)

    print("Options Calculator Test")
    print("-" * 60)
    print(f"Using py_vollib: {calc.use_py_vollib}")
    print()

    # Test parameters
    S = 100.0  # Stock price
    K = 105.0  # Strike price
    t = 0.5    # 6 months to expiry
    r = 0.05   # 5% risk-free rate
    sigma = 0.25  # 25% volatility
    option_type = 'call'

    print(f"Parameters:")
    print(f"  Stock Price: ${S}")
    print(f"  Strike Price: ${K}")
    print(f"  Time to Expiry: {t} years")
    print(f"  Volatility: {sigma*100}%")
    print(f"  Risk-Free Rate: {r*100}%")
    print(f"  Option Type: {option_type}")
    print()

    # Calculate theoretical price
    price = calc.calculate_theoretical_price(S, K, t, sigma, option_type, r)
    print(f"Theoretical Price: ${price:.4f}")
    print()

    # Calculate intrinsic and time value
    intrinsic = calc.calculate_intrinsic_value(S, K, option_type)
    time_val = calc.calculate_time_value(price, intrinsic)
    print(f"Intrinsic Value: ${intrinsic:.4f}")
    print(f"Time Value: ${time_val:.4f}")
    print()

    print("Note: Greeks are now provided by Alpha Vantage API")


if __name__ == "__main__":
    main()
