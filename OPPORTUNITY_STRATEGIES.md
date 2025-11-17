# Enhanced Opportunity Detection - Trading Strategies

This document explains the sophisticated options trading strategies implemented in the opportunity detection system, all based on established financial principles and proper use of the Greeks.

## Available Data

The system leverages comprehensive market data from the IVolatility API:

### Greeks
- **Delta (Δ)**: Rate of change in option price per $1 move in underlying stock
- **Gamma (Γ)**: Rate of change in Delta per $1 move in underlying stock
- **Theta (Θ)**: Time decay - option value lost per day
- **Vega (ν)**: Sensitivity to 1% change in implied volatility
- **Rho (ρ)**: Sensitivity to 1% change in interest rates

### Pricing & Liquidity
- Bid, Ask, Last Price
- Bid-Ask Spread (absolute and percentage)
- Volume and Open Interest

### Volatility Metrics
- Implied Volatility (IV)
- IV Rank: Current IV vs. 52-week range (0-100)
- IV Percentile: Historical distribution
- Historical Volatility (20-day and 30-day)

## Opportunity Types

### 1. Premium Selling Opportunities (`premium_sell`)

**Financial Strategy:** Credit strategies - selling overpriced premium in high volatility environments

**Criteria:**
- IV Rank > 60% (preferably >80%)
- High Theta magnitude (>$0.02/day) - time decay working for you
- High Vega - benefit from IV contraction after selling
- Delta > 0.10 - enough premium to make it worthwhile
- Good liquidity (tight spreads, volume >10, OI >50)
- 20-60 days to expiration (optimal time decay zone)

**Best Used For:**
- Covered calls
- Cash-secured puts
- Credit spreads
- Iron condors

**Risk Considerations:**
- Assignment risk if exercised
- Unlimited risk on naked positions
- Directional risk (use delta)

**Scoring (0-100):**
- Base: 40 points
- IV Rank >80%: +25 points
- High Theta: +15 points
- High Vega: +10 points
- Liquidity: +10 points

---

### 2. Premium Buying Opportunities (`premium_buy`)

**Financial Strategy:** Debit strategies - buying cheap premium in low volatility environments

**Criteria:**
- IV Rank < 40% (preferably <20%)
- High Vega (>0.05) - benefit from IV expansion
- Low Theta magnitude - minimize time decay cost
- 30-90 days to expiration (enough time for thesis to play out)
- Good liquidity for entry/exit

**Best Used For:**
- Long calls/puts (directional plays)
- Debit spreads
- Calendar spreads
- LEAPS (longer-term options)

**Risk Considerations:**
- Limited risk (premium paid)
- Time decay works against you
- Need volatility increase or strong directional move

**Scoring (0-100):**
- Base: 40 points
- IV Rank <20%: +25 points
- High Vega: +15 points
- Low Theta: +10 points
- Liquidity: +10 points

---

### 3. Gamma Scalping Opportunities (`gamma_scalp`)

**Financial Strategy:** Delta-neutral trading capturing volatility through rebalancing

**Criteria:**
- High Gamma (>0.01) - large delta changes for small stock moves
- Low Theta relative to Gamma - minimize decay cost
- Near ATM (0.95-1.05 moneyness) - maximum gamma
- 7-45 days to expiration (gamma peaks near expiration)
- Excellent liquidity (needed for frequent rebalancing)
- Gamma/Theta ratio > 0.5

**How It Works:**
1. Buy ATM option (long gamma, long vega)
2. As stock moves up: delta increases → sell stock to stay delta-neutral
3. As stock moves down: delta decreases → buy stock to stay delta-neutral
4. Profit from buying low and selling high repeatedly

**Best Used For:**
- Professional/active traders
- High volatility markets
- Stocks with frequent price movements

**Risk Considerations:**
- Transaction costs can erode profits
- Requires active monitoring
- Theta decay in low volatility
- Works best with realized volatility > implied volatility

**Scoring (0-100):**
- Base: 45 points
- High Gamma: +20 points
- Close to ATM: +15 points
- Gamma/Theta ratio: +10 points
- Excellent liquidity: +10 points

---

### 4. Mispricing Opportunities (`overpriced`/`underpriced`)

**Financial Strategy:** Arbitrage - exploit differences between theoretical and market prices

**Criteria:**
- Market price deviates >15% from Black-Scholes theoretical value
- Good liquidity (spread <10%)
- Greeks align with mispricing direction

**How It Works:**
- Compare market price to Black-Scholes model
- **Overpriced**: Market > Theoretical → SELL the option
- **Underpriced**: Market < Theoretical → BUY the option

**Research Findings:**
- Mispricing is greater for deep OTM options
- Higher volatility increases mispricing
- Model assumes continuous hedging (not always realistic)

**Best Used For:**
- Market makers
- Sophisticated traders with hedging capability
- Statistical arbitrage

**Risk Considerations:**
- Model risk - Black-Scholes assumptions may not hold
- Execution risk - prices may move before trade
- Greeks may not be perfectly estimated

**Scoring (0-100):**
- Base: 50 points
- Mispricing magnitude: +30 points
- Liquidity: +20 points

---

### 5. High Delta Opportunities (`high_delta`)

**Financial Strategy:** Stock replacement - using deep ITM options as stock proxy

**Criteria:**
- Delta > 0.65 (high directional exposure)
- Delta/Theta ratio > 5 (directional benefit >> time decay cost)
- 30-120 days to expiration
- Good liquidity
- High intrinsic value percentage

**Best Used For:**
- Leveraged directional plays
- Capital efficiency (control more stock with less capital)
- Defined risk alternative to stock

**Advantages Over Stock:**
- Less capital required (leverage)
- Defined maximum loss (premium paid)
- Can sell further OTM calls against it (PMCC - Poor Man's Covered Call)

**Risk Considerations:**
- Still subject to time decay
- Less liquid than stock
- May have wider spreads

**Scoring (0-100):**
- Base: 45 points
- High Delta (>0.80): +20 points
- Delta/Theta ratio: +15 points
- Deep ITM: +10 points
- Liquidity: +10 points

---

## Liquidity Scoring

All opportunities are scored for liquidity (0-100):

**Spread Component (40 points max):**
- <5% spread: 40 points (excellent)
- 5-10% spread: 20-30 points (acceptable)
- >10% spread: penalized

**Volume Component (30 points max):**
- ≥100 contracts: 30 points
- 50-99 contracts: 20 points
- 10-49 contracts: 10 points

**Open Interest Component (30 points max):**
- ≥1,000: 30 points
- 500-999: 20 points
- 100-499: 10 points

**Minimum Requirements:**
- All strategies: Volume >10, OI >50
- Gamma Scalping: Liquidity score >50 (need frequent trading)
- Mispricing: Liquidity score >40 (need quick execution)

---

## IV Rank Strategy Guidelines

### High IV Rank (>80%)
**Action:** SELL premium
- Premium is expensive (high demand/fear)
- Collect inflated premium
- IV likely to contract (mean reversion)
- Strategies: covered calls, cash-secured puts, credit spreads, iron condors

### Moderate IV Rank (40-80%)
**Action:** Neutral strategies or wait
- Premium fairly priced
- Less edge in either direction
- Consider defined risk spreads

### Low IV Rank (<20%)
**Action:** BUY premium
- Premium is cheap (low demand/complacency)
- Cost is low
- IV likely to expand
- Strategies: long calls/puts, debit spreads, calendars

---

## Time to Expiration Guidelines

### 7-20 Days
- Maximum gamma (good for scalping)
- Maximum theta (good for sellers if IV is high)
- High risk - fast moves

### 20-60 Days
- Optimal for premium selling
- Good theta decay
- Still reasonable premium

### 30-90 Days
- Good for premium buying
- Time for thesis to develop
- Moderate theta decay

### 60-120 Days
- Calendar spreads
- LEAPS considerations
- Lower theta impact

---

## Integration with Broader Strategy

### Portfolio Management
- Diversify across opportunity types
- Balance delta exposure (directional risk)
- Monitor aggregate theta (time decay)
- Track vega exposure (volatility risk)

### Risk Management
- Never risk more than 1-2% per trade
- Use defined risk strategies when possible
- Monitor liquidity for exit capability
- Set stop losses based on Greeks changes

### Trade Execution
- Use limit orders (market orders increase slippage)
- Check bid-ask spread before entry
- Consider volume and OI
- Time entries around market conditions

---

## Data-Driven Approach

All opportunity detection is based on:
1. **Real-time Greeks** from IVolatility API
2. **Historical volatility metrics** (IV Rank, IV Percentile, HV)
3. **Liquidity analysis** (spreads, volume, OI)
4. **Theoretical pricing** (Black-Scholes model)
5. **Risk metrics** (Delta, Gamma, Theta, Vega alignment)

---

## Disclaimer

These strategies are based on established financial principles but carry risk:
- **No guarantee of profits** - markets are unpredictable
- **Model limitations** - Black-Scholes makes assumptions that may not hold
- **Execution risk** - slippage, fees, and spread costs
- **Market risk** - unexpected events can cause rapid moves
- **Liquidity risk** - ability to exit may be limited

**This is for educational purposes only. Not financial advice. Consult a licensed financial advisor before trading.**
