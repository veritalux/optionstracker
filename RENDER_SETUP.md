# Render Deployment Setup Guide

## Prerequisites
- Render account: https://render.com
- Alpha Vantage API key: https://www.alphavantage.co/support/#api-key
- GitHub repository connected to Render

## Step-by-Step Deployment

### 1. Set Up Environment Variables in Render

After deploying your service to Render, you **must** configure these environment variables:

#### Backend Service (options-tracker-api)

Go to: **Render Dashboard → Your Service → Environment**

Add these environment variables:

| Key | Value | Notes |
|-----|-------|-------|
| `ALPHA_VANTAGE_API_KEY` | `6LW0BLNL4ZGV1Z86` | Your API key |
| `FRONTEND_URL` | Your frontend URL | e.g., `https://options-tracker-frontend.onrender.com` |
| `PYTHON_VERSION` | `3.12.0` | Already in render.yaml |
| `DATABASE_URL` | Auto-configured | Automatically set by Render |

**Important:** Click **"Save Changes"** after adding each variable. Render will automatically redeploy.

### 2. Verify API Key is Loaded

After deployment, check your service logs in Render:

```
✓ Good: "API Key loaded successfully"
✗ Bad:  "ALPHA_VANTAGE_API_KEY not found in environment variables"
```

### 3. Test the API

Once deployed, visit:
```
https://your-app.onrender.com/
```

You should see:
```json
{"status": "healthy", "message": "Options Tracker API"}
```

### 4. Common Issues

#### Issue: "API is not returning any data"
**Cause:** `ALPHA_VANTAGE_API_KEY` environment variable not set in Render dashboard

**Solution:**
1. Go to Render Dashboard → Environment
2. Add `ALPHA_VANTAGE_API_KEY` with your API key
3. Click "Save Changes"
4. Wait for automatic redeployment (2-3 minutes)

#### Issue: 503 Service Unavailable
**Cause:** Alpha Vantage API temporary outage (rare)

**Solution:** Wait 30 seconds and try again. The code has built-in retry logic.

#### Issue: Rate Limiting
**Free tier limits (2025):**
- **25 API calls per day** (NOT 500!)
- 5 API calls per minute
- End-of-day data only (no intraday updates)

**Solution:**
- Each symbol uses 2 API calls (stock + options)
- Max ~12 symbols can be updated per day
- The code automatically handles rate limiting with 13-second delays
- Consider updating different symbols on different days for larger watchlists

### 5. Testing Options Data

To test if options data is working on Render:

```bash
curl https://your-app.onrender.com/api/symbols/AAPL/options
```

Should return a list of option contracts.

### 6. Database Migrations

If you need to reset the database:

```bash
# In Render Shell
cd backend
python models.py
```

This will create all necessary tables.

## Environment Variable Reference

### Required Variables

- **ALPHA_VANTAGE_API_KEY**: Your Alpha Vantage API key
  - Get it from: https://www.alphavantage.co/support/#api-key
  - Free tier: 25 calls/day, 5 calls/min (end-of-day data only)
  - Used for: Stock prices, options chains (with Greeks!), company data
  - Max ~12 symbols per day (2 calls per symbol)

- **FRONTEND_URL**: URL of your frontend service
  - Used for: CORS configuration
  - Example: `https://options-tracker-frontend.onrender.com`

### Auto-Configured Variables

- **DATABASE_URL**: PostgreSQL connection string (set by Render)
- **PORT**: Service port (set by Render)

## Monitoring

### Check Logs
Render Dashboard → Your Service → Logs

Look for:
```
INFO:data_fetcher:Updating data for AAPL (1/3)
INFO:data_fetcher:Stored 4 stock price records for AAPL
INFO:data_fetcher:Stored 870 price records for AAPL
```

### Health Check
The `/` endpoint serves as a health check.

**Healthy response:**
```json
{"status": "healthy", "message": "Options Tracker API"}
```

## Rate Limiting Strategy

The application is configured for Alpha Vantage free tier constraints:

- **25 API calls per day limit** - Each symbol uses 2 calls (stock + options)
- **5 calls per minute limit** - 13-second delay between symbols
- **End-of-day data only** - Free tier does not provide intraday updates
- **Automatic retry** with exponential backoff for transient errors
- **Warning system** - Alerts when you're about to exceed daily limit

**For larger watchlists:**
- Update different symbols on alternating days
- Consider upgrading to Alpha Vantage premium (higher limits)
- Focus on your most important symbols

## Troubleshooting Commands

### Access Render Shell

```bash
# View environment variables
env | grep ALPHA_VANTAGE

# Test API connection
python test_api.py

# Check database tables
python -c "from models import *; create_tables(); print('Tables created')"
```

## Security Notes

- ✅ DO set `ALPHA_VANTAGE_API_KEY` in Render dashboard
- ❌ DON'T commit `.env` file to git (it's in .gitignore)
- ❌ DON'T hardcode API keys in render.yaml
- ✅ DO use `sync: false` for sensitive env vars in render.yaml

## Next Steps After Deployment

1. Add some test symbols:
   ```bash
   curl -X POST https://your-app.onrender.com/api/symbols \
     -H "Content-Type: application/json" \
     -d '{"symbol": "AAPL"}'
   ```

2. Trigger data update:
   ```bash
   curl -X POST https://your-app.onrender.com/api/update-all
   ```

3. Check opportunities:
   ```bash
   curl https://your-app.onrender.com/api/opportunities
   ```

## Support

If you encounter issues:
1. Check Render service logs
2. Verify environment variables are set
3. Run diagnostic: `python test_api.py`
4. Check Alpha Vantage API status: https://www.alphavantage.co

---

**Last Updated:** 2025-11-16
**Alpha Vantage Free Tier:** 25 calls/day, 5 calls/min (end-of-day data)
