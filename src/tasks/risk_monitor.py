import logging
from decimal import Decimal
from datetime import datetime, timedelta
from src.database import get_db_transaction
from src.models.trade import Trade
from src.models.portfolio import Portfolio
from src.services.telegram_alert_service import telegram_service
from config.settings import settings

logger = logging.getLogger(__name__)

async def check_risk_limits():
    """Check various risk limits and halt trading if necessary"""
    try:
        with get_db_transaction() as db:
            # Check daily loss limit
            await check_daily_loss_limit(db)
            
            # Check weekly loss limit
            await check_weekly_loss_limit(db)
            
            # Check maximum open positions
            await check_max_open_positions(db)
            
    except Exception as e:
        logger.error(f"Risk monitor error: {e}")

async def check_daily_loss_limit(db):
    """Check if daily loss limit is exceeded"""
    try:
        today = datetime.utcnow().date()
        
        # Get today's closed trades
        daily_trades = db.query(Trade).filter(
            Trade.is_closed == True,
            Trade.closed_at >= today,
            Trade.closed_at < today + timedelta(days=1)
        ).all()
        
        if not daily_trades:
            return
        
        total_pnl = sum(trade.pnl_usd for trade in daily_trades if trade.pnl_usd)
        
        if total_pnl < 0:  # We have losses
            loss_percent = abs(total_pnl) / sum(trade.position_size_usd for trade in daily_trades) * 100
            
            if loss_percent >= settings.DAILY_LOSS_LIMIT_PERCENT:
                await telegram_service.risk_limit_triggered("daily_loss_limit", total_pnl)
                logger.critical(f"Daily loss limit exceeded: {loss_percent:.1f}% (${total_pnl:.2f})")
                
                # Close all open positions immediately
                await emergency_close_all_positions(db)
        
    except Exception as e:
        logger.error(f"Daily loss limit check error: {e}")

async def check_weekly_loss_limit(db):
    """Check if weekly loss limit is exceeded"""
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get week's closed trades
        weekly_trades = db.query(Trade).filter(
            Trade.is_closed == True,
            Trade.closed_at >= week_ago
        ).all()
        
        if not weekly_trades:
            return
        
        total_pnl = sum(trade.pnl_usd for trade in weekly_trades if trade.pnl_usd)
        
        if total_pnl < 0:  # We have losses
            loss_percent = abs(total_pnl) / sum(trade.position_size_usd for trade in weekly_trades) * 100
            
            if loss_percent >= settings.WEEKLY_LOSS_LIMIT_PERCENT:
                await telegram_service.risk_limit_triggered("weekly_loss_limit", total_pnl)
                logger.critical(f"Weekly loss limit exceeded: {loss_percent:.1f}% (${total_pnl:.2f})")
                
                # Close all open positions immediately
                await emergency_close_all_positions(db)
        
    except Exception as e:
        logger.error(f"Weekly loss limit check error: {e}")

async def check_max_open_positions(db):
    """Check if maximum open positions exceeded"""
    try:
        open_positions = db.query(Portfolio).count()
        
        if open_positions > settings.MAX_OPEN_POSITIONS:
            logger.warning(f"Maximum open positions exceeded: {open_positions}/{settings.MAX_OPEN_POSITIONS}")
            # This is handled in trade execution, just log for monitoring
        
    except Exception as e:
        logger.error(f"Max positions check error: {e}")

async def emergency_close_all_positions(db):
    """Emergency close all open positions"""
    try:
        from src.services.trade_execution_service import trade_execution_service
        
        open_positions = db.query(Portfolio).all()
        
        logger.critical(f"Emergency closing {len(open_positions)} positions due to risk limits")
        
        for position in open_positions:
            try:
                await trade_execution_service.execute_sell_trade(position, "emergency_risk_limit")
            except Exception as e:
                logger.error(f"Emergency close failed for {position.token_address}: {e}")
        
    except Exception as e:
        logger.error(f"Emergency close all positions error: {e}")
