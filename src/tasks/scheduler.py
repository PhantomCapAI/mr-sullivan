import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from src.tasks.discovery import scan_for_signals
from src.tasks.signal_processor import process_queued_signals
from src.tasks.portfolio_monitor import monitor_portfolio_positions
from src.tasks.risk_monitor import check_risk_limits
from src.tasks.stats_collector import collect_daily_stats
from config.settings import settings

logger = logging.getLogger(__name__)

scheduler = None

async def start_scheduler():
    """Start the background task scheduler"""
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    scheduler = AsyncIOScheduler()
    
    # Signal discovery - every 2 minutes
    scheduler.add_job(
        scan_for_signals,
        trigger=IntervalTrigger(minutes=2),
        id='signal_discovery',
        name='Signal Discovery',
        max_instances=1,
        coalesce=True
    )
    
    # Signal processing - every 30 seconds
    scheduler.add_job(
        process_queued_signals,
        trigger=IntervalTrigger(seconds=30),
        id='signal_processing',
        name='Signal Processing',
        max_instances=1,
        coalesce=True
    )
    
    # Portfolio monitoring - every 60 seconds
    scheduler.add_job(
        monitor_portfolio_positions,
        trigger=IntervalTrigger(seconds=60),
        id='portfolio_monitor',
        name='Portfolio Monitor',
        max_instances=1,
        coalesce=True
    )
    
    # Risk monitoring - every 5 minutes
    scheduler.add_job(
        check_risk_limits,
        trigger=IntervalTrigger(minutes=5),
        id='risk_monitor',
        name='Risk Monitor',
        max_instances=1,
        coalesce=True
    )
    
    # Daily stats collection - at midnight UTC
    scheduler.add_job(
        collect_daily_stats,
        trigger=CronTrigger(hour=0, minute=0),
        id='daily_stats',
        name='Daily Stats Collection',
        max_instances=1,
        coalesce=True
    )
    
    scheduler.start()
    logger.info("Background scheduler started")

async def stop_scheduler():
    """Stop the background task scheduler"""
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("Background scheduler stopped")
    else:
        logger.warning("Scheduler not running")

def get_scheduler_status():
    """Get current scheduler status"""
    if scheduler is None:
        return {"status": "stopped", "jobs": []}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "status": "running",
        "jobs": jobs
    }
