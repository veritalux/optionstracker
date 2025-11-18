# Background Worker Service

## Overview

The Options Tracker uses a **separate background worker service** to handle all scheduled data refresh tasks. This architectural separation ensures:

- **API Responsiveness**: Web API performance isn't affected by data refresh operations
- **Reliability**: Scheduled jobs continue even if the API restarts
- **Scalability**: Worker and API services can be scaled independently
- **Resource Management**: Data-intensive tasks don't compete with API requests

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Render Services                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │   Frontend       │         │   API Service    │         │
│  │  Static Site     │────────▶│  (FastAPI)       │         │
│  │                  │         │  - Web endpoints │         │
│  └──────────────────┘         │  - Manual        │         │
│                                │    triggers      │         │
│                                └──────────────────┘         │
│                                         │                    │
│                                         │ Shared DB          │
│                                         ▼                    │
│                                ┌─────────────────┐          │
│                                │   PostgreSQL    │          │
│                                │    Database     │          │
│                                └─────────────────┘          │
│                                         ▲                    │
│                                         │ Shared DB          │
│                                         │                    │
│                                ┌──────────────────┐         │
│                                │  Worker Service  │         │
│                                │  (Background)    │         │
│                                │  - Scheduled     │         │
│                                │    updates       │         │
│                                │  - Data refresh  │         │
│                                └──────────────────┘         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Worker Service Details

### Location
`backend/worker.py`

### What It Does

The worker runs **4 scheduled jobs**:

1. **Quick Update** (Every 15 minutes)
   - Runs Monday-Friday, 9:30 AM - 4:00 PM ET (market hours)
   - Updates stock prices and Greeks for quick intraday data

2. **End-of-Day Update** (4:30 PM ET)
   - Runs Monday-Friday after market close
   - Comprehensive update of all data and analysis

3. **Weekend Analysis** (Saturday 10:00 AM ET)
   - Weekly opportunity review
   - Prepares data for the upcoming week

4. **Continuous Refresh** (Every 20 minutes, 24/7)
   - Stock price updates
   - Options data and Greeks
   - IV analysis
   - Trading opportunity scanning

### Data Refreshed

- **Stock Prices**: OHLC (Open, High, Low, Close), Volume
- **Options Data**: Contracts, bid/ask, last price, volume, open interest
- **Greeks**: Delta, Gamma, Theta, Vega, Rho
- **IV Analysis**: Current IV, IV Rank, IV Percentile, Historical Volatility
- **Opportunities**: Greeks-based trading strategies

## Deployment on Render

### Service Configuration

The worker is defined in `render.yaml`:

```yaml
- type: worker
  name: options-tracker-worker
  runtime: python
  plan: starter
  buildCommand: "pip install -r backend/requirements.txt"
  startCommand: "cd backend && python worker.py"
  envVars:
    - key: PYTHON_VERSION
      value: 3.12.0
    - key: DATABASE_URL
      fromDatabase:
        name: options-tracker-db
        property: connectionString
    - key: IVOLATILITY_API_KEY
      sync: false
```

### Environment Variables

The worker requires these environment variables (same as API):

| Variable | Purpose | Set Where |
|----------|---------|-----------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-configured by Render |
| `IVOLATILITY_API_KEY` | IVolatility API authentication | Render Dashboard (manual) |
| `PYTHON_VERSION` | Python runtime version | render.yaml |

### Deployment Steps

#### Option 1: Deploy via Blueprint (Recommended)

1. Push changes to your repository:
   ```bash
   git push origin main
   ```

2. The worker will be automatically created from `render.yaml`

3. Set the `IVOLATILITY_API_KEY` in the Render dashboard:
   - Go to the worker service
   - Navigate to **Environment** tab
   - Add `IVOLATILITY_API_KEY` variable

#### Option 2: Manual Deployment via Dashboard

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Background Worker**
3. Connect your repository
4. Configure:
   - **Name**: `options-tracker-worker`
   - **Runtime**: Python 3.12
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && python worker.py`
5. Add environment variables:
   - `DATABASE_URL`: Link to `options-tracker-db`
   - `IVOLATILITY_API_KEY`: Your API key
6. Click **Create Background Worker**

#### Option 3: Deploy via Render CLI

```bash
# Authenticate
export RENDER_API_KEY=your_api_key

# Deploy using render.yaml
render services create --from-yaml render.yaml

# Or create manually via API
curl -X POST https://api.render.com/v1/services \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "background_worker",
    "name": "options-tracker-worker",
    "ownerId": "YOUR_OWNER_ID",
    "repo": "https://github.com/veritalux/optionstracker",
    "branch": "main",
    "rootDir": "backend",
    "buildCommand": "pip install -r requirements.txt",
    "startCommand": "python worker.py",
    "plan": "starter"
  }'
```

## Monitoring the Worker

### View Logs

**Via Render CLI:**
```bash
render logs -s options-tracker-worker
```

**Via Render Dashboard:**
1. Go to your worker service
2. Click the **Logs** tab
3. View real-time output

### Expected Log Output

```
============================================================
Options Tracker Background Worker Starting
============================================================
✓ Database tables verified
Initializing data update scheduler...
✓ Signal handlers registered (SIGTERM, SIGINT)
✓ Scheduler started successfully

Active scheduled jobs:
  - Quick update: Every 15 min (Mon-Fri, 9:30 AM - 4:00 PM ET)
  - EOD update: 4:30 PM ET (Mon-Fri)
  - Weekend analysis: Saturday 10:00 AM ET
  - Continuous refresh: Every 20 min (24/7)

Worker is now running. Press Ctrl+C to stop.
============================================================
```

### Check Job Execution

Watch for logs like:
```
Starting continuous update...
Updating stock data for AAPL...
Updating options data for AAPL...
Calculating IV analysis for AAPL...
Scanning for trading opportunities...
Continuous update completed successfully
```

## Local Development

### Running the Worker Locally

```bash
cd backend

# Ensure dependencies are installed
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="your_database_url"
export IVOLATILITY_API_KEY="your_api_key"

# Run the worker
python worker.py
```

### Testing Without Scheduled Jobs

You can import and test scheduler functions directly:

```python
from scheduler import DataUpdateScheduler
from threading import Event

shutdown_event = Event()
scheduler = DataUpdateScheduler(shutdown_event=shutdown_event)

# Test individual update functions
scheduler.update_stock_data("AAPL")
scheduler.update_options_data("AAPL")
scheduler.calculate_and_store_iv_analysis("AAPL")
scheduler.scan_opportunities()
```

## Graceful Shutdown

The worker handles shutdown signals gracefully:

1. Receives `SIGTERM` or `SIGINT` signal
2. Sets shutdown event flag
3. Stops scheduler (prevents new jobs from starting)
4. Waits for running jobs to complete (up to 5 seconds)
5. Closes database connections
6. Exits cleanly

This ensures:
- No data corruption
- Proper connection cleanup
- Safe restarts and deployments

## Troubleshooting

### Worker Not Starting

**Check logs for errors:**
```bash
render logs -s options-tracker-worker --tail 100
```

**Common issues:**
- Missing `IVOLATILITY_API_KEY` environment variable
- Database connection failure (check `DATABASE_URL`)
- Python dependency installation failure

### Jobs Not Running

**Verify scheduler is active:**
- Check logs for "Scheduler started successfully"
- Look for job execution messages

**Check timezone:**
- Jobs use US Eastern Time (ET)
- Verify system time is correct

### High Resource Usage

**If worker uses too much memory/CPU:**
- Check job execution frequency in `scheduler.py`
- Consider reducing concurrent API calls in `data_fetcher.py`
- Upgrade to larger Render plan if needed

### Database Connection Issues

**If you see "QueuePool timeout" errors:**
- Increase connection pool size in `models.py`
- Check for long-running queries
- Ensure database is on same region as worker

## API Changes

### What Changed

The API (`backend/app.py`) **no longer runs the scheduler**. Changes made:

1. **Removed**: Scheduler initialization and startup
2. **Kept**: Manual trigger endpoints for on-demand updates
3. **Added**: Documentation comments explaining the separation

### Manual Trigger Endpoints (Still Available)

These API endpoints still allow manual data refresh:

```bash
# Update specific symbol
POST /api/update/AAPL

# Update all active symbols
POST /api/update-all

# Scan for trading opportunities
POST /api/opportunities/scan
```

These are useful for:
- Forcing immediate updates
- Testing data refresh logic
- Emergency manual refreshes

## Benefits of This Architecture

### Before (Single Service)
- ❌ API slow during data refresh
- ❌ Scheduled jobs interrupted by API restarts
- ❌ Can't scale API and background tasks independently
- ❌ Resource contention between web requests and data operations

### After (Separate Services)
- ✅ API always responsive
- ✅ Scheduled jobs continue regardless of API status
- ✅ Independent scaling (more API instances, single worker)
- ✅ Clear separation of concerns
- ✅ Easier debugging and monitoring

## Cost Considerations

**Render Pricing:**
- **Starter Plan**: $7/month per service
- **Free Plan**: Not recommended for workers (spins down after inactivity)

**Recommendation:**
- API: Starter plan ($7/month)
- Worker: Starter plan ($7/month)
- Database: Free plan (upgrade if needed)
- **Total**: ~$14/month

The worker should run on a **paid plan** to ensure:
- 24/7 operation
- No spin-down delays
- Reliable scheduled execution

## Next Steps

1. **Deploy the worker** using one of the methods above
2. **Monitor logs** to verify scheduled jobs are running
3. **Check database** to confirm data is being refreshed
4. **Set up alerts** in Render for worker failures (optional)
5. **Scale as needed** based on usage patterns

## Support

For issues or questions:
- Check Render service logs first
- Review `scheduler.py` for job configuration
- Consult `data_fetcher.py` for data operation details
- See `models.py` for database schema

## Related Files

- `backend/worker.py` - Worker service main script
- `backend/scheduler.py` - Scheduler and job definitions
- `backend/data_fetcher.py` - Data fetching logic
- `backend/models.py` - Database models
- `backend/app.py` - API service (scheduler removed)
- `render.yaml` - Render deployment configuration
