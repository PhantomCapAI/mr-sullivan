import asyncio
import logging
from decimal import Decimal
from src.database import get_db_transaction
from src.models.portfolio import Portfolio
from src.models.trade import Trade, TradeDirection
from src.services.gmgn_service import gmgn_service
from src.services.trade_execution_service import trade_execution_service
from src.services.telegram_alert_service import telegram_service
from config.settings import settings
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def monitor_portfolio_positions():
    """Monitor all open positions for exit conditions"""
    try:
        with get_db_transaction() as db:
            positions = db.query(Portfolio).all()
            
            if not positions:
                return
            
            logger.info(f"Monitoring {len(positions)} portfolio positions")
            
            for position in positions:
                try:
                    await monitor_single_position(position, db)
                    await asyncio.sleep(0.1)  # Brief pause between position checks
                except Exception as e:
                    logger.error(f"Error monitoring position {position.id}: {e}")
                    
    except Exception as e:
        logger.error(f"Portfolio monitor error: {e}")

async def monitor_single_position(position: Portfolio, db):
    """Monitor a single position for exit conditions"""
    try:
        # Get current price
        token_info = await gmgn_service.get_token_info(position.token_address, position.chain)
        current_price = Decimal(str(token_info.get('price', 0)))
        
        if current_price <= 0:
            logger.warning(f"Invalid price for {position.token_address}: {current_price}")
            return
        
        # Update position with current data
        position.current_price = current_price
        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
        position.last_checked = datetime.now(timezone.utc)
        
        # Update peak price for trailing stop
        if current_price > position.peak_price:
            position.peak_price = current_price
            # Update trailing stop price
            stop_loss_percent = Decimal(str(settings.TRAILING_STOP_PERCENT / 100))
            position.trailing_stop_price = current_price * (Decimal("1") - stop_loss_percent)
        
        pnl_percent = (current_price / position.entry_price - 1) * 100
        
        # Check exit conditions
        exit_reason = None
        
        # 1. Trailing stop loss
        if current_price <= position.trailing_stop_price:
            exit_reason = "trailing_stop_loss"
        
        # 2. Take profit target
        elif pnl_percent >= settings.TAKE_PROFIT_PERCENT:
            exit_reason = "take_profit"
        
        # 3. Maximum hold time (24 hours for high volatility tokens)
        elif position.entry_time:
            hours_held = (datetime.now(timezone.utc) - position.entry_time).total_seconds() / 3600
            if hours_held > 24:
                exit_reason = "max_hold_time"
        
        # 4. Emergency exit on severe drop (circuit breaker)
        elif pnl_percent <= -50:  # More severe than normal stop loss
            exit_reason = "emergency_exit"
        
        if exit_reason:
            logger.info(f"Exit condition triggered for {position.token_address}: {exit_reason}")
            
            # Execute sell trade
            execution_result = await trade_execution_service.execute_sell_trade(position, exit_reason)
            
            if execution_result.get('status') == 'executed':
                # Send trade closed alert
                trade_data = {
                    'token_name': position.token_address,  # Could get actual name from token_info
                    'exit_price': execution_result['exit_price'],
                    'pnl_usd': execution_result['pnl_usd'],
                    'pnl_percent': execution_result['pnl_percent'],
                    'exit_reason': exit_reason,
                    'hold_time_hours': (datetime.now(timezone.utc) - position.entry_time).total_seconds() / 3600 if position.entry_time else 0
                }
                
                if execution_result['pnl_usd'] < 0 and exit_reason == "trailing_stop_loss":
                    await telegram_service.stop_loss_triggered(trade_data)
                else:
                    await telegram_service.trade_closed(trade_data)
                
                logger.info(f"Position closed: {execution_result['order_id']}, PnL: ${execution_result['pnl_usd']:.2f}")
            else:
                logger.error(f"Failed to close position for {position.token_address}")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error monitoring position {position.token_address}: {e}")
