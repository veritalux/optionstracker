"""
Background Worker Service for Options Tracker

This service handles all scheduled data refresh tasks:
- Market hours updates (every 15 min during trading hours)
- Continuous updates (every 20 min)
- End-of-day comprehensive updates
- Weekend analysis

This runs as a separate service from the API to ensure:
- API responsiveness isn't affected by data refresh tasks
- Scheduled jobs continue even if API restarts
- Independent scaling of worker and API services
"""

import logging
import signal
import time
from threading import Event
from datetime import datetime
import sys
import os

from scheduler import DataUpdateScheduler
from models import create_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Graceful shutdown event
shutdown_event = Event()


def handle_signal(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)"""
    signal_names = {
        signal.SIGTERM: 'SIGTERM',
        signal.SIGINT: 'SIGINT'
    }
    signal_name = signal_names.get(signum, f'Signal {signum}')
    logger.info(f"Received {signal_name} - initiating graceful shutdown...")
    shutdown_event.set()


def main():
    """Main worker function"""
    logger.info("=" * 60)
    logger.info("Options Tracker Background Worker Starting")
    logger.info("=" * 60)

    # Verify database connection
    try:
        create_tables()
        logger.info("✓ Database tables verified")
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        logger.error("Exiting...")
        sys.exit(1)

    # Initialize scheduler
    logger.info("Initializing data update scheduler...")
    scheduler = DataUpdateScheduler(shutdown_event=shutdown_event)

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    logger.info("✓ Signal handlers registered (SIGTERM, SIGINT)")

    # Start scheduler
    try:
        scheduler.start()
        logger.info("✓ Scheduler started successfully")
        logger.info("")
        logger.info("Active scheduled jobs:")
        logger.info("  - Quick update: Every 15 min (Mon-Fri, 9:30 AM - 4:00 PM ET)")
        logger.info("  - EOD update: 4:30 PM ET (Mon-Fri)")
        logger.info("  - Weekend analysis: Saturday 10:00 AM ET")
        logger.info("  - Continuous refresh: Every 20 min (24/7)")
        logger.info("")
        logger.info("Worker is now running. Press Ctrl+C to stop.")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Failed to start scheduler: {e}")
        sys.exit(1)

    # Main loop - keep worker alive until shutdown signal
    try:
        while not shutdown_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_event.set()

    # Graceful shutdown
    logger.info("")
    logger.info("=" * 60)
    logger.info("Shutting down worker...")
    logger.info("=" * 60)

    try:
        scheduler.stop()
        logger.info("✓ Scheduler stopped")

        # Give jobs a moment to complete
        logger.info("Waiting for running jobs to complete...")
        time.sleep(5)

        logger.info("✓ Worker shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        sys.exit(1)

    logger.info("Goodbye!")


if __name__ == "__main__":
    main()
