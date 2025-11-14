# Deployment Guide - Render

This guide will walk you through deploying the Options Tracker app on Render's free tier.

## Prerequisites

1. GitHub account
2. Render account (free) - https://render.com
3. This code pushed to a GitHub repository

## Step 1: Push to GitHub

```bash
# Initialize git repository (if not already done)
git init
git add .
git commit -m "Initial commit - Options Tracker"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/options-tracker.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Render

### A. Create Account
1. Go to https://render.com
2. Sign up with GitHub
3. Authorize Render to access your repositories

### B. Create New Service from Render Dashboard
1. Click "New +" → "Blueprint"
2. Connect your GitHub repository (options-tracker)
3. Render will automatically detect the `render.yaml` file
4. Click "Apply" - this will create:
   - PostgreSQL database
   - Backend API service
   - Frontend static site

### C. Wait for Initial Deployment
- Database: ~2 minutes
- Backend: ~5-10 minutes (first build)
- Frontend: ~3-5 minutes

## Step 3: Configure Environment Variables

After initial deployment completes:

### Backend Service
1. Go to Render Dashboard → options-tracker-api
2. Go to "Environment" tab
3. Add environment variable:
   - Key: `FRONTEND_URL`
   - Value: (copy your frontend URL from Render, e.g., `https://options-tracker-frontend.onrender.com`)
4. Click "Save Changes"

### Frontend Service
1. Go to Render Dashboard → options-tracker-frontend
2. Go to "Environment" tab
3. Add environment variable:
   - Key: `VITE_API_URL`
   - Value: (copy your backend URL from Render + `/api`, e.g., `https://options-tracker-api.onrender.com/api`)
4. Click "Save Changes"

## Step 4: Trigger Redeployment

After adding environment variables:

1. Backend service: Click "Manual Deploy" → "Deploy latest commit"
2. Frontend service: Click "Manual Deploy" → "Deploy latest commit"

Wait 5-10 minutes for redeployment.

## Step 5: Verify Deployment

1. Open your frontend URL
2. You should see the Options Tracker dashboard
3. Try adding a symbol (e.g., AAPL) to your watchlist
4. Click "Refresh Data" to fetch options data

## Important Notes

### Free Tier Limitations

**Backend:**
- Goes to sleep after 15 minutes of inactivity
- Takes ~30 seconds to wake up on first request
- 750 hours/month compute time

**Database:**
- 1 GB storage
- Expires after 90 days (can extend for free)

**Frontend:**
- 100 GB bandwidth/month
- Always on (no sleep)

### Background Scheduler

The scheduler will run automatically:
- Every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
- End-of-day update at 4:30 PM ET
- Weekend analysis on Saturday at 10:00 AM ET

**Note:** On free tier, the backend sleeps after inactivity, so scheduled jobs won't run when asleep. Consider:
- Upgrading to a paid plan (~$7/month) for always-on service
- Using external cron service to ping your API periodically

### Database Migration

The app automatically creates all required tables on first startup. No manual migration needed!

## Troubleshooting

### Backend won't start
- Check logs in Render dashboard
- Verify `DATABASE_URL` is set (should be automatic from database)
- Ensure all dependencies are in `requirements.txt`

### Frontend shows connection error
- Verify `VITE_API_URL` is correctly set
- Check backend is running (visit backend URL + `/`)
- Verify CORS settings allow your frontend URL

### Database connection error
- Ensure database is running (check Render dashboard)
- Verify `DATABASE_URL` environment variable exists
- Check database hasn't expired (free tier = 90 days)

## Updating Your App

```bash
# Make changes to your code
git add .
git commit -m "Your commit message"
git push origin main
```

Render will automatically detect the push and redeploy your services!

## Cost Estimate

**Free Tier (Current Setup):**
- $0/month
- Backend sleeps after 15 min inactivity
- Database expires after 90 days (renewable)

**Paid Tier (Always-On):**
- Backend: $7/month (512 MB RAM, always on)
- Database: $7/month (always on, no expiration)
- Frontend: Free
- **Total: ~$14/month**

## Support

For issues:
- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
