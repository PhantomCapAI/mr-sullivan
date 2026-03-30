import logging
from datetime import datetime, timedelta
from src.database import get_db_transaction
from src.models.trade import Trade
from src.models.signal import Signal, ActionTaken
from src.models.daily_stat import DailyStat
from src.services.telegram_alert_service import telegram_service
from config.settings import settings

logger = logging.getLogger(__name__)

async def collect_daily_stats():
    """Collect and store daily trading statistics"""
    try:
        yesterday = (datetime.utcnow() - timedelta(days=1)).date()
        
        with get_db_transaction() as db:
            for chain in settings.SUPPORTED_CHAINS:
                await collect_chain_stats(db, chain, yesterday)
        
        # Send daily summary
        await send_daily_summary(yesterday)
        
    except Exception as e:
        logger.error(f"Stats collection error: {e}")

async def collect_chain_stats(db, chain: str, date):
    """Collect stats for a specific chain and date"""
    try:
        # Check if stats already exist
        existing_stat = db.query(DailyStat).filter(
            DailyStat.date == date,
            DailyStat.chain == chain
        ).first()
        
        if existing_stat:
            logger.info(f"Stats already exist for {chain} on {date}")
            return
        
        # Signals stats
        signals_scanned = db.query(Signal).filter(
            Signal.chain == chain,
            Signal.created_at >= date,
            Signal.created_at < date + timedelta(days=1)
        ).count()
        
        signals_passed_security = db.query(Signal).filter(
            Signal.chain == chain,
            Signal.created_at >= date,
            Signal.created_at < date + timedelta(days=1),
            Signal.signal_score >= 1  # Passed initial screening
        ).count()
        
        signals_scored_above_65 = db.query(Signal).filter(
            Signal.chain == chain,
            Signal.created_at >= date,
            Signal.created_at < date + timedelta(days=1),
            Signal.signal_score >= 65
        ).count()
        
        # Trade stats
        daily_trades = db.query(Trade).filter(
            Trade.chain == chain,
            Trade.created_at >= date,
            Trade.created_at < date + timedelta(days=1)
        ).all()
        
        trades_executed = len(daily_trades)
        trades_won = len([t for t in daily_trades if t.pnl_usd and t.pnl_usd > 0])
        trades_lost = len([t for t in daily_trades if t.pnl_usd and t.pnl_usd <= 0])
        
        total_pnl = sum(t.pnl_usd for t in daily_trades if t.pnl_usd) or 0
        best_trade_pnl = max((t.pnl_usd for t in daily_trades if t.pnl_usd), default=0)
        worst_trade_pnl = min((t.pnl_usd for t in daily_trades if t.pnl_usd), default=0)
        
        # Average hold time in minutes
        hold_times = [t.hold_time_seconds for t in daily_trades if t.hold_time_seconds]
        avg_hold_time = int(sum(hold_times) / len(hold_times) / 60) if hold_times else 0
        
        # Claude calls (approximate)
        claude_calls_made = db.query(Signal).filter(
            Signal.chain == chain,
            Signal.created_at >= date,
            Signal.created_at < date + timedelta(days=1),
            Signal.claude_confidence.isnot(None)
        ).count()
        
        # Create daily stat record
        daily_stat = DailyStat(
            date=date,
            chain=chain,
            signals_scanned=signals_scanned,
            signals_passed_security=signals_passed_security,
            signals_scored_above_65=signals_scored_above_65,
            trades_executed=trades_executed,
            trades_won=trades_won,
            trades_lost=trades_lost,
            total_pnl=total_pnl,
            best_trade_pnl=best_trade_pnl,
            worst_trade_pnl=worst_trade_pnl,
            avg_hold_time=avg_hold_time,
            claude_calls_made=claude_calls_made,
            convergence_events=0  # Would need to track this separately
        )
        
        db.add(daily_stat)
        logger.info(f"Daily stats collected for {chain} on {date}")
        
    except Exception as e:
        logger.error(f"Chain stats collection error for {chain}: {e}")

async def send_daily_summary(date):
    """Send daily summary to Telegram"""
    try:
        with get_db_transaction() as db:
            # Get aggregate stats across all chains
            daily_stats = db.query(DailyStat).filter(DailyStat.date == date).all()
            
            if not daily_stats:
                return
            
            # Aggregate totals
            total_stats = {
                'signals_scanned': sum(s.signals_scanned for s in daily_stats),
                'signals_passed_security': sum(s.signals_passed_security for s in daily_stats),
                'total_trades': sum(s.trades_executed for s in daily_stats),
                'trades_won': sum(s.trades_won for s in daily_stats),
                'trades_lost': sum(s.trades_lost for s in daily_stats),
                'total_pnl': sum(s.total_pnl for s in daily_stats),
                'best_trade_pnl': max((s.best_trade_pnl for s in daily_stats), default=0),
                'worst_trade_pnl': min((s.worst_trade_pnl for s in daily_stats), default=0),
                'claude_calls_made': sum(s.claude_calls_made for s in daily_stats)
            }
            
            await telegram_service.daily_summary(total_stats)
            
    except Exception as e:
        logger.error(f"Daily summary error: {e}")
