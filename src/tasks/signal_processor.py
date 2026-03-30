import asyncio
import logging
from typing import List
from src.database import get_db_transaction
from src.models.signal import Signal, ActionTaken, ClaudeAction
from src.services.reasoning_service import reasoning_service
from src.services.trade_execution_service import trade_execution_service
from src.services.telegram_alert_service import telegram_service

logger = logging.getLogger(__name__)

async def process_queued_signals():
    """Process queued signals with Claude analysis"""
    try:
        with get_db_transaction() as db:
            # Get unprocessed signals
            queued_signals = db.query(Signal).filter(
                Signal.action_taken == ActionTaken.QUEUED,
                Signal.processed == False
            ).order_by(Signal.signal_score.desc()).limit(5).all()
            
            if not queued_signals:
                return
            
            logger.info(f"Processing {len(queued_signals)} queued signals")
            
            for signal in queued_signals:
                try:
                    await process_single_signal(signal, db)
                    await asyncio.sleep(0.5)  # Brief pause between signals
                except Exception as e:
                    logger.error(f"Error processing signal {signal.id}: {e}")
                    
    except Exception as e:
        logger.error(f"Signal processor error: {e}")

async def process_single_signal(signal: Signal, db):
    """Process a single signal through Claude analysis and execution"""
    try:
        # Send alert about new signal
        signal_data = {
            'token_address': signal.token_address,
            'token_name': signal.token_name,
            'token_symbol': 'N/A',  # Would need to get from token info
            'chain': signal.chain,
            'signal_score': signal.signal_score,
            'holder_health_score': signal.holder_health_score,
            'liquidity_score': signal.liquidity_score,
            'momentum_score': signal.momentum_score,
            'smart_money_score': signal.smart_money_score,
            'creator_trust_score': signal.creator_trust_score,
            'smart_wallets_count': signal.smart_wallets_count,
            'fresh_wallet_rate': float(signal.fresh_wallet_rate),
            'top_10_holder_rate': float(signal.top_10_holder_rate),
            'liquidity_usd': float(signal.liquidity_usd),
            'volume_24h': float(signal.volume_24h)
        }
        
        await telegram_service.signal_detected(signal_data)
        
        # Get Claude's analysis
        claude_decision = await reasoning_service.analyze_signal(signal_data)
        
        if claude_decision:
            # Update signal with Claude's decision
            signal.claude_confidence = claude_decision['confidence']
            signal.claude_action = ClaudeAction(claude_decision['action'])
            signal.claude_reasoning = claude_decision['reasoning']
            
            # Send Claude decision alert
            await telegram_service.claude_decision(signal_data, claude_decision)
            
            # Execute trade if Claude says BUY and confidence is high enough
            if claude_decision['action'] == 'BUY' and claude_decision['confidence'] >= 75:
                execution_result = await trade_execution_service.execute_buy_trade(
                    signal_data, claude_decision
                )
                
                if execution_result and execution_result.get('status') == 'executed':
                    signal.action_taken = ActionTaken.EXECUTED
                    
                    # Send execution alert
                    trade_data = {
                        **signal_data,
                        **execution_result
                    }
                    await telegram_service.trade_executed(trade_data)
                    
                    logger.info(f"Trade executed for signal {signal.id}: {execution_result['order_id']}")
                else:
                    signal.action_taken = ActionTaken.SKIPPED
                    logger.info(f"Trade execution failed/skipped for signal {signal.id}")
            else:
                signal.action_taken = ActionTaken.SKIPPED
                logger.info(f"Signal {signal.id} skipped - Claude action: {claude_decision['action']}, confidence: {claude_decision['confidence']}")
        else:
            # Claude analysis failed
            signal.action_taken = ActionTaken.SKIPPED
            signal.claude_reasoning = "Claude analysis failed or rate limited"
            logger.warning(f"Claude analysis failed for signal {signal.id}")
        
        # Mark as processed
        signal.processed = True
        db.commit()
        
    except Exception as e:
        logger.error(f"Error processing signal {signal.id}: {e}")
        signal.processed = True
        signal.action_taken = ActionTaken.SKIPPED
        signal.claude_reasoning = f"Processing error: {str(e)}"
        db.commit()
