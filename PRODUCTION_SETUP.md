# Production Setup Guide for Render

This guide will help you set up your Options Tracker on Render with data and opportunities.

## Step 1: Verify Environment Variables

In your Render dashboard for `options-tracker-api` service, ensure these environment variables are set:

```
IVOLATILITY_API_KEY=your_actual_api_key_here
FRONTEND_URL=https://options-tracker-frontend.onrender.com
DATABASE_URL=(automatically set by Render)
```

## Step 2: Add Symbols to Production Database

Once your backend is deployed, you need to add symbols via the API:

### Option A: Use curl commands

```bash
# Add SPY
curl -X POST https://options-tracker-backend.onrender.com/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "SPY", "company_name": "SPDR S&P 500 ETF"}'

# Add AAPL
curl -X POST https://options-tracker-backend.onrender.com/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "company_name": "Apple Inc."}'

# Add MSFT
curl -X POST https://options-tracker-backend.onrender.com/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "MSFT", "company_name": "Microsoft Corporation"}'

# Add TSLA
curl -X POST https://options-tracker-backend.onrender.com/api/symbols \
  -H "Content-Type: application/json" \
  -d '{"symbol": "TSLA", "company_name": "Tesla Inc."}'
```

### Option B: Use the Frontend

1. Go to https://options-tracker-frontend.onrender.com/watchlist
2. Click "Add Symbol"
3. Enter symbol and company name
4. Click Save

## Step 3: Trigger Initial Data Fetch

After adding symbols, trigger data fetch:

```bash
# Update all symbols at once
curl -X POST https://options-tracker-backend.onrender.com/api/update-all

# Or update individual symbols
curl -X POST https://options-tracker-backend.onrender.com/api/update/SPY
curl -X POST https://options-tracker-backend.onrender.com/api/update/AAPL
```

**Note:** This will take several minutes as it fetches:
- Stock price data (last 30 days)
- Options chains (all available contracts)
- Real-time pricing with IV and Greeks
- IV analysis calculations

## Step 4: Verify Data Was Loaded

Check that data was fetched successfully:

```bash
# Check symbols
curl https://options-tracker-backend.onrender.com/api/symbols

# Check stock prices for SPY
curl "https://options-tracker-backend.onrender.com/api/symbols/SPY/prices?limit=5"

# Check options for SPY
curl "https://options-tracker-backend.onrender.com/api/symbols/SPY/options?limit=5"
```

## Step 5: Check Opportunities

Once data is loaded, opportunities should be automatically detected:

```bash
# View all opportunities
curl "https://options-tracker-backend.onrender.com/api/opportunities?limit=10"

# View opportunities for specific symbol
curl "https://options-tracker-backend.onrender.com/api/symbols/SPY/opportunities"
```

## Step 6: View in Browser

Visit https://options-tracker-frontend.onrender.com/opportunities

You should now see trading opportunities!

## Automatic Updates

The backend scheduler will automatically:
- Update stock prices every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
- Perform comprehensive updates at end of day (4:30 PM ET)
- Scan for opportunities with each update

## Troubleshooting

### No opportunities showing?

1. **Check if symbols are added:**
   ```bash
   curl https://options-tracker-backend.onrender.com/api/symbols
   ```

2. **Check if data fetch completed:**
   ```bash
   curl "https://options-tracker-backend.onrender.com/api/symbols/SPY/prices?limit=1"
   ```

3. **Manually trigger opportunity scan:**
   - The opportunity scan runs automatically after each data update
   - Check backend logs in Render dashboard for any errors

### Backend not responding?

1. Check Render dashboard for service status
2. View logs for any errors
3. Ensure `IVOLATILITY_API_KEY` is set correctly
4. Verify database is connected

### Frontend shows "No opportunities found"?

1. Open browser DevTools (F12) → Network tab
2. Check if API calls are reaching the backend
3. Verify `VITE_API_URL` is set to: `https://options-tracker-backend.onrender.com/api`

## Production Best Practices

1. **Monitor API Usage**: IVolatility trial has limits
2. **Check Logs**: Watch Render logs for errors
3. **Database Backups**: Render free tier doesn't include automatic backups
4. **Rate Limiting**: Backend respects API rate limits with delays

## Sample Data Load Script

If you want to quickly populate with multiple symbols:

```bash
#!/bin/bash

# Array of symbols to add
symbols=(
  "SPY:SPDR S&P 500 ETF"
  "QQQ:Invesco QQQ Trust"
  "IWM:iShares Russell 2000 ETF"
  "AAPL:Apple Inc."
  "MSFT:Microsoft Corporation"
  "GOOGL:Alphabet Inc."
  "TSLA:Tesla Inc."
  "NVDA:NVIDIA Corporation"
)

API_URL="https://options-tracker-backend.onrender.com/api"

echo "Adding symbols..."
for item in "${symbols[@]}"; do
  IFS=':' read -r symbol name <<< "$item"
  echo "Adding $symbol..."
  curl -X POST "$API_URL/symbols" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"$symbol\", \"company_name\": \"$name\"}"
  echo ""
done

echo ""
echo "Triggering data fetch for all symbols..."
curl -X POST "$API_URL/update-all"

echo ""
echo "Done! Check status in Render logs."
echo "Opportunities will be available once data fetch completes."
```

Save this as `setup_production.sh`, make it executable (`chmod +x setup_production.sh`), and run it.
