"""
Background task scheduler for periodic data updates
Uses APScheduler to fetch data during market hours and analyze opportunities
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, time
import logging
import pytz

from models import SessionLocal, create_tables, Symbol, OptionContract, OptionPrice
from data_fetcher import DataFetcher
from opportunities import OpportunityDetector

logger = logging.getLogger(__name__)

# US Eastern Time (for market hours)
ET = pytz.timezone('US/Eastern')

class DataUpdateScheduler:
    """
    Manages scheduled data updates and opportunity scanning
    """

    def __init__(self):
        """Initialize scheduler"""
        self.scheduler = BackgroundScheduler()
        self.scheduler.timezone = ET
        self.is_running = False

        # Market hours (9:30 AM - 4:00 PM ET)
        self.market_open = time(9, 30)
        self.market_close = time(16, 0)

    def is_market_hours(self) -> bool:
        """
        Check if current time is during market hours

        Returns:
            True if during market hours, False otherwise
        """
        now = datetime.now(ET)

        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check if within market hours
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close

    def update_stock_data(self):
        """Update stock price data for all watchlist symbols"""
        logger.info("Starting scheduled stock data update")

        try:
            db = SessionLocal()
            fetcher = DataFetcher()

            symbols = db.query(Symbol).filter(Symbol.is_active == True).all()

            for symbol in symbols:
                try:
                    logger.info(f"Updating stock data for {symbol.symbol}")

                    # Fetch recent stock data
                    stock_data = fetcher.fetch_stock_data(symbol.symbol, days=1)

                    if stock_data is not None:
                        fetcher.store_stock_data(symbol.symbol, stock_data)
                        logger.info(f"Updated stock data for {symbol.symbol}")
                    else:
                        logger.warning(f"No stock data available for {symbol.symbol}")

                except Exception as e:
                    logger.error(f"Error updating {symbol.symbol}: {str(e)}")
                    continue

            fetcher.close_session()
            db.close()

            logger.info("Completed scheduled stock data update")

        except Exception as e:
            logger.error(f"Error in stock data update task: {str(e)}")

    def update_options_data(self):
        """Update options chain data for all watchlist symbols"""
        logger.info("Starting scheduled options data update")

        try:
            db = SessionLocal()
            fetcher = DataFetcher()

            symbols = db.query(Symbol).filter(Symbol.is_active == True).all()

            for symbol in symbols:
                try:
                    logger.info(f"Updating options data for {symbol.symbol}")

                    # Fetch options data
                    options_data = fetcher.fetch_options_data(symbol.symbol)

                    if options_data:
                        fetcher.store_options_data(symbol.symbol, options_data)
                        logger.info(f"Updated options data for {symbol.symbol}")
                    else:
                        logger.warning(f"No options data available for {symbol.symbol}")

                except Exception as e:
                    logger.error(f"Error updating options for {symbol.symbol}: {str(e)}")
                    continue

            fetcher.close_session()
            db.close()

            logger.info("Completed scheduled options data update")

        except Exception as e:
            logger.error(f"Error in options data update task: {str(e)}")

    def calculate_greeks(self):
        """
        Greeks calculation (deprecated)

        Note: Greeks are now provided directly by IVolatility API
        in the /equities/rt/options-rawiv endpoint and stored during data fetch.
        This method is kept for backward compatibility but does nothing.
        """
        logger.info("Greeks calculation skipped - Greeks provided by IVolatility API")
        return

    def scan_opportunities(self):
        """Scan for trading opportunities"""
        logger.info("Starting opportunity scan")

        try:
            db = SessionLocal()
            detector = OpportunityDetector(db)

            opportunities = detector.scan_all_opportunities(save_to_db=True)

            total_count = sum(len(opps) for opps in opportunities.values())

            logger.info(f"Completed opportunity scan: {total_count} opportunities found")

            # Log top opportunities
            for symbol, opps in opportunities.items():
                if opps:
                    top_opp = max(opps, key=lambda x: x['score'])
                    logger.info(f"  {symbol}: Best score {top_opp['score']:.0f} - {top_opp['opportunity_type']}")

            db.close()

        except Exception as e:
            logger.error(f"Error in opportunity scan task: {str(e)}")

    def comprehensive_update(self):
        """
        Comprehensive end-of-day update:
        - Update all stock data
        - Update all options data
        - Calculate Greeks
        - Scan opportunities
        """
        logger.info("=" * 60)
        logger.info("Starting comprehensive end-of-day update")
        logger.info("=" * 60)

        self.update_stock_data()
        self.update_options_data()
        self.calculate_greeks()
        self.scan_opportunities()

        logger.info("=" * 60)
        logger.info("Completed comprehensive update")
        logger.info("=" * 60)

    def quick_update(self):
        """
        Quick intraday update:
        - Update stock prices
        - Calculate Greeks for active positions
        - Quick opportunity scan
        """
        if not self.is_market_hours():
            logger.info("Market is closed, skipping quick update")
            return

        logger.info("Starting quick intraday update")

        self.update_stock_data()
        self.calculate_greeks()
        self.scan_opportunities()

        logger.info("Completed quick update")

    def start(self):
        """Start the scheduler with all jobs"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        logger.info("Starting data update scheduler")

        # Market hours updates (every 15 minutes, 9:30 AM - 4:00 PM ET, Mon-Fri)
        self.scheduler.add_job(
            self.quick_update,
            trigger=CronTrigger(
                day_of_week='mon-fri',
                hour='9-16',
                minute='*/15',
                timezone=ET
            ),
            id='quick_update',
            name='Quick intraday update (every 15 min during market hours)',
            replace_existing=True
        )

        # End-of-day comprehensive update (4:30 PM ET, Mon-Fri)
        self.scheduler.add_job(
            self.comprehensive_update,
            trigger=CronTrigger(
                day_of_week='mon-fri',
                hour=16,
                minute=30,
                timezone=ET
            ),
            id='eod_update',
            name='End-of-day comprehensive update',
            replace_existing=True
        )

        # Weekend historical analysis (Saturday 10:00 AM ET)
        self.scheduler.add_job(
            self.scan_opportunities,
            trigger=CronTrigger(
                day_of_week='sat',
                hour=10,
                minute=0,
                timezone=ET
            ),
            id='weekend_analysis',
            name='Weekend opportunity review',
            replace_existing=True
        )

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True

        logger.info("Scheduler started successfully")
        logger.info("Scheduled jobs:")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name} (ID: {job.id})")

    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Scheduler stopped")

    def run_manual_update(self, update_type: str = 'comprehensive'):
        """
        Manually trigger an update

        Args:
            update_type: Type of update ('comprehensive', 'quick', 'stocks', 'options', 'greeks', 'opportunities')
        """
        logger.info(f"Running manual {update_type} update")

        if update_type == 'comprehensive':
            self.comprehensive_update()
        elif update_type == 'quick':
            self.quick_update()
        elif update_type == 'stocks':
            self.update_stock_data()
        elif update_type == 'options':
            self.update_options_data()
        elif update_type == 'greeks':
            self.calculate_greeks()
        elif update_type == 'opportunities':
            self.scan_opportunities()
        else:
            logger.error(f"Unknown update type: {update_type}")

        logger.info(f"Completed manual {update_type} update")

    def get_status(self) -> dict:
        """
        Get scheduler status

        Returns:
            Dictionary with scheduler status information
        """
        jobs_info = []

        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs_info.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                })

        return {
            'is_running': self.is_running,
            'is_market_hours': self.is_market_hours(),
            'jobs': jobs_info
        }


# Global scheduler instance
_scheduler = None

def get_scheduler() -> DataUpdateScheduler:
    """Get the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DataUpdateScheduler()
    return _scheduler


def main():
    """Test the scheduler"""
    import time

    # Initialize database
    create_tables()

    scheduler = DataUpdateScheduler()

    print("Testing Data Update Scheduler")
    print("-" * 60)

    # Check market status
    print(f"Market is {'OPEN' if scheduler.is_market_hours() else 'CLOSED'}")
    print()

    # Test manual update
    print("Running manual comprehensive update...")
    scheduler.run_manual_update('comprehensive')
    print()

    # Start scheduler
    print("Starting scheduler...")
    scheduler.start()

    # Show status
    status = scheduler.get_status()
    print(f"\nScheduler Status:")
    print(f"  Running: {status['is_running']}")
    print(f"  Market Hours: {status['is_market_hours']}")
    print(f"\nScheduled Jobs:")
    for job in status['jobs']:
        print(f"  - {job['name']}")
        print(f"    Next run: {job['next_run']}")

    print("\nScheduler is running. Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped")


if __name__ == "__main__":
    main()
