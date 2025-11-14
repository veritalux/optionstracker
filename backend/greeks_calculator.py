import numpy as np
from scipy.stats import norm
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GreeksCalculator:
    """Calculate option Greeks using Black-Scholes model"""

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize Greeks calculator

        Args:
            risk_free_rate: Annual risk-free interest rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate

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
        return max(days_to_expiry / 365.0, 0.0001)  # Minimum time to avoid division by zero

    def calculate_d1_d2(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: Optional[float] = None
    ) -> tuple:
        """
        Calculate d1 and d2 for Black-Scholes formula

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility (as decimal, e.g., 0.25 for 25%)
            risk_free_rate: Risk-free rate (uses instance default if None)

        Returns:
            Tuple of (d1, d2)
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate

        # Ensure volatility is positive
        volatility = max(volatility, 0.0001)

        d1 = (np.log(stock_price / strike_price) +
              (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))

        d2 = d1 - volatility * np.sqrt(time_to_expiry)

        return d1, d2

    def calculate_delta(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate option delta

        Delta measures the rate of change of option price with respect to stock price.
        Range: Call [0, 1], Put [-1, 0]

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Delta value
        """
        try:
            d1, _ = self.calculate_d1_d2(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            )

            if option_type.lower() == 'call':
                delta = norm.cdf(d1)
            else:  # put
                delta = norm.cdf(d1) - 1

            return delta

        except Exception as e:
            logger.error(f"Error calculating delta: {str(e)}")
            return 0.0

    def calculate_gamma(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate option gamma

        Gamma measures the rate of change of delta with respect to stock price.
        Same for both calls and puts.

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            risk_free_rate: Risk-free rate

        Returns:
            Gamma value
        """
        try:
            d1, _ = self.calculate_d1_d2(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            )

            gamma = norm.pdf(d1) / (stock_price * volatility * np.sqrt(time_to_expiry))

            return gamma

        except Exception as e:
            logger.error(f"Error calculating gamma: {str(e)}")
            return 0.0

    def calculate_theta(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate option theta (per day)

        Theta measures the rate of change of option price with respect to time.
        Usually negative (time decay).

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Theta value (per day)
        """
        try:
            if risk_free_rate is None:
                risk_free_rate = self.risk_free_rate

            d1, d2 = self.calculate_d1_d2(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            )

            if option_type.lower() == 'call':
                theta = (-stock_price * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_expiry)) -
                        risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2))
            else:  # put
                theta = (-stock_price * norm.pdf(d1) * volatility / (2 * np.sqrt(time_to_expiry)) +
                        risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2))

            # Convert to per-day theta (divide by 365)
            theta_per_day = theta / 365.0

            return theta_per_day

        except Exception as e:
            logger.error(f"Error calculating theta: {str(e)}")
            return 0.0

    def calculate_vega(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate option vega (per 1% change in volatility)

        Vega measures the rate of change of option price with respect to volatility.
        Same for both calls and puts.

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            risk_free_rate: Risk-free rate

        Returns:
            Vega value (per 1% change in volatility)
        """
        try:
            d1, _ = self.calculate_d1_d2(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            )

            vega = stock_price * norm.pdf(d1) * np.sqrt(time_to_expiry)

            # Convert to per 1% change (divide by 100)
            vega_pct = vega / 100.0

            return vega_pct

        except Exception as e:
            logger.error(f"Error calculating vega: {str(e)}")
            return 0.0

    def calculate_rho(
        self,
        stock_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> float:
        """
        Calculate option rho (per 1% change in interest rate)

        Rho measures the rate of change of option price with respect to interest rate.

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Rho value (per 1% change in interest rate)
        """
        try:
            if risk_free_rate is None:
                risk_free_rate = self.risk_free_rate

            _, d2 = self.calculate_d1_d2(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            )

            if option_type.lower() == 'call':
                rho = strike_price * time_to_expiry * \
                      np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            else:  # put
                rho = -strike_price * time_to_expiry * \
                      np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)

            # Convert to per 1% change (divide by 100)
            rho_pct = rho / 100.0

            return rho_pct

        except Exception as e:
            logger.error(f"Error calculating rho: {str(e)}")
            return 0.0

    def calculate_all_greeks(
        self,
        stock_price: float,
        strike_price: float,
        expiry_date: datetime,
        volatility: float,
        option_type: str,
        risk_free_rate: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            expiry_date: Option expiration date
            volatility: Implied volatility (as decimal)
            option_type: 'call' or 'put'
            risk_free_rate: Risk-free rate

        Returns:
            Dictionary with all Greek values
        """
        time_to_expiry = self.calculate_time_to_expiry(expiry_date)

        greeks = {
            'delta': self.calculate_delta(
                stock_price, strike_price, time_to_expiry,
                volatility, option_type, risk_free_rate
            ),
            'gamma': self.calculate_gamma(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            ),
            'theta': self.calculate_theta(
                stock_price, strike_price, time_to_expiry,
                volatility, option_type, risk_free_rate
            ),
            'vega': self.calculate_vega(
                stock_price, strike_price, time_to_expiry,
                volatility, risk_free_rate
            ),
            'rho': self.calculate_rho(
                stock_price, strike_price, time_to_expiry,
                volatility, option_type, risk_free_rate
            ),
            'time_to_expiry': time_to_expiry
        }

        return greeks

    def calculate_intrinsic_value(
        self,
        stock_price: float,
        strike_price: float,
        option_type: str
    ) -> float:
        """
        Calculate intrinsic value of an option

        Args:
            stock_price: Current stock price
            strike_price: Option strike price
            option_type: 'call' or 'put'

        Returns:
            Intrinsic value
        """
        if option_type.lower() == 'call':
            return max(0, stock_price - strike_price)
        else:  # put
            return max(0, strike_price - stock_price)

    def calculate_time_value(
        self,
        option_price: float,
        intrinsic_value: float
    ) -> float:
        """
        Calculate time value of an option

        Args:
            option_price: Current option price
            intrinsic_value: Intrinsic value

        Returns:
            Time value
        """
        return max(0, option_price - intrinsic_value)


def main():
    """Test the Greeks calculator"""
    calc = GreeksCalculator(risk_free_rate=0.05)

    # Example parameters
    stock_price = 100
    strike_price = 105
    expiry_date = datetime(2024, 12, 31)
    volatility = 0.25  # 25%
    option_type = 'call'

    print("Testing Greeks Calculator")
    print("-" * 50)
    print(f"Stock Price: ${stock_price}")
    print(f"Strike Price: ${strike_price}")
    print(f"Expiry Date: {expiry_date}")
    print(f"Volatility: {volatility * 100}%")
    print(f"Option Type: {option_type}")
    print("-" * 50)

    greeks = calc.calculate_all_greeks(
        stock_price, strike_price, expiry_date,
        volatility, option_type
    )

    print("\nGreeks:")
    print(f"  Delta: {greeks['delta']:.4f}")
    print(f"  Gamma: {greeks['gamma']:.4f}")
    print(f"  Theta: {greeks['theta']:.4f} (per day)")
    print(f"  Vega: {greeks['vega']:.4f} (per 1% IV)")
    print(f"  Rho: {greeks['rho']:.4f} (per 1% rate)")
    print(f"\nTime to Expiry: {greeks['time_to_expiry']:.4f} years")

    intrinsic = calc.calculate_intrinsic_value(stock_price, strike_price, option_type)
    print(f"Intrinsic Value: ${intrinsic:.2f}")


if __name__ == "__main__":
    main()
