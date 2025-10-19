"""
Scheduler for Historical Data Loader
Runs daily at 4:30 PM IST to fetch and store previous day's market data
"""

import os
import sys
from pathlib import Path
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from core.utils.logger import setup_logging, get_logger
from services.data_service.load.historical_batch_loader import HistoricalDataLoader

# Setup logging
setup_logging(
    service_name="historical_data_scheduler",
    log_level=os.getenv("LOG_LEVEL", "INFO")
)
logger = get_logger(__name__)

# Timezone
IST = ZoneInfo("Asia/Kolkata")


class HistoricalDataScheduler:
    """
    APScheduler-based scheduler for historical data loading
    
    Runs daily at configured time (default: 4:30 PM IST)
    """
    
    def __init__(self, schedule_time: str = "16:30"):
        """
        Initialize scheduler
        
        Args:
            schedule_time: Time to run daily in HH:MM format (IST)
        """
        self.schedule_time = schedule_time
        hour, minute = map(int, schedule_time.split(":"))
        
        # Initialize loader
        self.loader = HistoricalDataLoader(schedule_time=schedule_time)
        
        # Initialize scheduler
        self.scheduler = BlockingScheduler(timezone=IST)
        
        # Add job
        self.scheduler.add_job(
            self._run_job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=IST),
            id='daily_historical_load',
            name='Daily Historical Data Load',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600  # Allow 1 hour grace period
        )
        
        logger.info(f"✅ Scheduler configured to run daily at {schedule_time} IST")
    
    def _run_job(self):
        """Execute the scheduled job"""
        try:
            start_time = datetime.now(IST)
            
            logger.info(f"{'=' * 80}")
            logger.info(f"� HEARTBEAT - Starting scheduled historical data load")
            logger.info(f"   Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')} IST")
            logger.info(f"{'=' * 80}")
            
            self.loader.run_scheduled_job()
            
            end_time = datetime.now(IST)
            duration = (end_time - start_time).total_seconds()
            duration_minutes = int(duration / 60)
            duration_seconds = int(duration % 60)
            
            logger.info(f"{'=' * 80}")
            logger.info(f"💓 HEARTBEAT - Scheduled job completed successfully")
            logger.info(f"   Duration: {duration_minutes}m {duration_seconds}s")
            logger.info(f"   Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')} IST")
            logger.info(f"{'=' * 80}")
            
        except Exception as e:
            logger.error(f"❌ Scheduled job failed: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler (blocking)"""
        logger.info("🚀 Starting Historical Data Scheduler...")
        logger.info(f"   Schedule: Daily at {self.schedule_time} IST")
        logger.info(f"   Next run: {self.scheduler.get_jobs()[0].next_run_time}")
        logger.info(f"💓 Scheduler heartbeat active - waiting for schedule...")
        
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("💓 HEARTBEAT - Scheduler stopped by user")
            self.scheduler.shutdown()
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}", exc_info=True)
            self.scheduler.shutdown()
            raise
    
    def run_now(self):
        """Manually trigger the job immediately (for testing)"""
        logger.info("🔧 Manually triggering job (test mode)")
        self._run_job()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Historical Data Scheduler")
    parser.add_argument(
        "--schedule-time",
        default="16:30",
        help="Daily schedule time in HH:MM format (IST)"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run job immediately instead of scheduling"
    )
    
    args = parser.parse_args()
    
    # Create scheduler
    scheduler = HistoricalDataScheduler(schedule_time=args.schedule_time)
    
    if args.run_now:
        # Run immediately and exit
        scheduler.run_now()
    else:
        # Start scheduler (blocking)
        scheduler.start()


if __name__ == "__main__":
    main()
