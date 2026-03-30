from decimal import Decimal
from typing import Dict, Optional
from src.services.gmgn_service import gmgn_service
from src.redis_client import redis_client
from src.database import get_db_transaction
from src.models.trade import Trade, TradeDirection
from src.models.portfolio import Portfolio
from config.settings import settings
import logging
import time

logger = logging.getLogger(__name__)

class TradeExecutionService:
    def __init__(self):
        self.max_slippage = Decimal(str(settings.DEFAULT_SLIPPAGE_TOLERANCE))
        self.max_position_size = Decimal(str(settings.MAX_POSITION_SIZE_USD))
    
    async def execute_buy_trade(self, signal_data: Dict, claude_decision: Dict) -> Optional[Dict]:
        """Execute a buy trade with distributed locking"""
        token_address = signal_data["token_address"]
        chain = signal_data["chain"]
        
        # Acquire distributed lock for this token
        lock_key = f"trade_execution:{chain}:{token_address}"
        if not await redis_client.acquire_lock(lock_key, timeout=60):
            logger.warning(f"Could not acquire lock for {token_address}")
            return None
        
        try:
            return await self._execute_buy_trade_locked(signal_data, claude_decision)
        finally:
            await redis_client.release_lock(lock_key)
    
    async def _execute_buy_trade_locked(self, signal_data: Dict, claude_decision: Dict) -> Dict:
        """Execute buy trade with lock acquired"""
        with get_db_transaction() as db:
            try:
                token_address = signal_data["token_address"]
                chain = signal_data["chain"]
                
                # Check if we already have a position
                existing_position = db.query(Portfolio).filter(
                    Portfolio.token_address == token_address,
                    Portfolio.chain == chain
                ).first()
                
                if existing_position:
                    logger.info(f"Position already exists for {token_address}")
                    return {"status": "skipped", "reason": "position_exists"}
                
                # Check max open positions
                open_positions = db.query(Portfolio).count()
                if open_positions >= settings.MAX_OPEN_POSITIONS:
                    logger.info(f"Max open positions reached: {open_positions}")
                    return {"status": "skipped", "reason": "max_positions_reached"}
                
                # Calculate position size based on confidence
                confidence = claude_decision["confidence"]
                if confidence >= 90:
                    size_percent = 0.05  # 5%
                elif confidence >= 85:
                    size_percent = 0.035  # 3.5%
                elif confidence >= 80:
                    size_percent = 0.025  # 2.5%
                elif confidence >= 75:
                    size_percent = 0.015  # 1.5%
                else:
                    return {"status": "skipped", "reason": "confidence_too_low"}
                
                # Get current balance
                balance_info = await gmgn_service.get_user_balance(chain)
                available_balance = Decimal(str(balance_info.get("balance", 0)))
                
                position_size_usd = min(
                    available_balance * Decimal(str(size_percent)),
                    self.max_position_size
                )
                
                if position_size_usd < Decimal("10"):  # Minimum $10 trade
                    return {"status": "skipped", "reason": "insufficient_balance"}
                
                # Get quote first
                quote = await gmgn_service.get_trade_quote(
                    token_address=token_address,
                    amount_usd=float(position_size_usd),
                    chain=chain
                )
                
                estimated_slippage = Decimal(str(quote.get("slippage", 0)))
                if estimated_slippage > self.max_slippage:
                    logger.info(f"Slippage too high: {estimated_slippage:.2%}")
                    return {"status": "skipped", "reason": "slippage_too_high"}
                
                # Prepare trade data for GMGN
                trade_data = {
                    "token_address": token_address,
                    "chain": chain,
                    "direction": "buy",
                    "amount_usd": float(position_size_usd),
                    "max_slippage": float(self.max_slippage)
                }
                
                # Execute trade via GMGN
                execution_result = await gmgn_service.execute_swap(trade_data)
                
                if execution_result.get("status") != "success":
                    logger.error(f"Trade execution failed: {execution_result}")
                    return {"status": "failed", "reason": execution_result.get("error", "unknown_error")}
                
                entry_price = Decimal(str(execution_result["execution_price"]))
                quantity = Decimal(str(execution_result["quantity"]))
                actual_slippage = Decimal(str(execution_result.get("slippage", 0)))
                
                # Create trade record
                trade = Trade(
                    token_address=token_address,
                    token_name=signal_data.get("token_name"),
                    token_symbol=signal_data.get("token_symbol"),
                    chain=chain,
                    direction=TradeDirection.BUY,
                    entry_price=entry_price,
                    position_size_usd=position_size_usd,
                    quantity=quantity,
                    signal_score=signal_data["signal_score"],
                    claude_confidence=claude_decision["confidence"],
                    claude_reasoning=claude_decision["reasoning"],
                    entry_trigger="claude_buy_signal",
                    slippage_actual=actual_slippage,
                    gmgn_order_id=execution_result["order_id"]
                )
                
                db.add(trade)
                
                # Create portfolio position
                portfolio = Portfolio(
                    token_address=token_address,
                    chain=chain,
                    quantity=quantity,
                    entry_price=entry_price,
                    current_price=entry_price,
                    unrealized_pnl=Decimal("0"),
                    peak_price=entry_price,
                    trailing_stop_price=entry_price * (Decimal("1") - Decimal(str(settings.STOP_LOSS_PERCENT / 100))),
                    entry_time=trade.created_at,
                    last_checked=trade.created_at
                )
                
                db.add(portfolio)
                
                logger.info(f"Buy trade executed successfully: {execution_result['order_id']}")
                
                return {
                    "status": "executed",
                    "trade_id": str(trade.id),
                    "order_id": execution_result["order_id"],
                    "execution_price": float(entry_price),
                    "quantity": float(quantity),
                    "position_size_usd": float(position_size_usd),
                    "slippage": float(actual_slippage)
                }
                
            except Exception as e:
                logger.error(f"Trade execution error: {e}")
                raise
    
    async def execute_sell_trade(self, portfolio_position: Portfolio, exit_reason: str) -> Dict:
        """Execute a sell trade for existing position"""
        lock_key = f"trade_execution:{portfolio_position.chain}:{portfolio_position.token_address}"
        if not await redis_client.acquire_lock(lock_key, timeout=60):
            logger.warning(f"Could not acquire sell lock for {portfolio_position.token_address}")
            return {"status": "failed", "reason": "lock_timeout"}
        
        try:
            return await self._execute_sell_trade_locked(portfolio_position, exit_reason)
        finally:
            await redis_client.release_lock(lock_key)
    
    async def _execute_sell_trade_locked(self, portfolio_position: Portfolio, exit_reason: str) -> Dict:
        """Execute sell trade with lock acquired"""
        with get_db_transaction() as db:
            try:
                # Prepare sell trade data
                trade_data = {
                    "token_address": portfolio_position.token_address,
                    "chain": portfolio_position.chain,
                    "direction": "sell",
                    "quantity": float(portfolio_position.quantity),
                    "max_slippage": 0.08  # Allow higher slippage for emergency exits
                }
                
                # Execute sell via GMGN
                execution_result = await gmgn_service.execute_swap(trade_data)
                
                if execution_result.get("status") != "success":
                    logger.error(f"Sell execution failed: {execution_result}")
                    return {"status": "failed", "reason": execution_result.get("error", "unknown_error")}
                
                exit_price = Decimal(str(execution_result["execution_price"]))
                
                # Calculate PnL
                pnl_usd = (exit_price - portfolio_position.entry_price) * portfolio_position.quantity
                pnl_percent = (exit_price / portfolio_position.entry_price - 1) * 100
                
                # Find the original buy trade
                buy_trade = db.query(Trade).filter(
                    Trade.token_address == portfolio_position.token_address,
                    Trade.chain == portfolio_position.chain,
                    Trade.direction == TradeDirection.BUY,
                    Trade.is_closed == False
                ).first()
                
                if buy_trade:
                    # Update buy trade with exit info
                    buy_trade.exit_price = exit_price
                    buy_trade.pnl_usd = pnl_usd
                    buy_trade.pnl_percent = pnl_percent
                    buy_trade.exit_trigger = exit_reason
                    buy_trade.closed_at = db.query(db.func.now()).scalar()
                    buy_trade.is_closed = True
                    buy_trade.hold_time_seconds = int((buy_trade.closed_at - buy_trade.created_at).total_seconds())
                
                # Remove from portfolio
                db.delete(portfolio_position)
                
                logger.info(f"Sell trade executed: {execution_result['order_id']}, PnL: ${pnl_usd:.2f}")
                
                return {
                    "status": "executed",
                    "order_id": execution_result["order_id"],
                    "exit_price": float(exit_price),
                    "pnl_usd": float(pnl_usd),
                    "pnl_percent": float(pnl_percent),
                    "exit_reason": exit_reason
                }
                
            except Exception as e:
                logger.error(f"Sell execution error: {e}")
                raise

trade_execution_service = TradeExecutionService()
