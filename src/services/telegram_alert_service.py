import asyncio
from telegram import Bot
from typing import Dict, List
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class TelegramAlertService:
    def __init__(self):
        self.bot = None
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self._available = False

        if settings.TELEGRAM_BOT_TOKEN:
            try:
                self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                self._available = True
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.warning(f"Telegram unavailable: {e}")
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not set. Running without Telegram alerts.")

    async def send_alert(self, message: str, parse_mode: str = "HTML"):
        """Send alert message to Telegram"""
        if not self._available:
            logger.debug("Telegram alert skipped (not configured)")
            return
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    async def signal_detected(self, signal_data: Dict):
        """Alert for new signal detected"""
        message = f"""
🎯 <b>New Signal Detected</b>

Token: {signal_data.get('token_name', 'Unknown')} ({signal_data.get('token_symbol', '???')})
Chain: {signal_data['chain'].upper()}
Score: {signal_data['signal_score']}/100

📊 <b>Breakdown:</b>
• Holder Health: {signal_data.get('holder_health_score', 0)}/25
• Liquidity: {signal_data.get('liquidity_score', 0)}/20
• Momentum: {signal_data.get('momentum_score', 0)}/20
• Smart Money: {signal_data.get('smart_money_score', 0)}/20
• Creator Trust: {signal_data.get('creator_trust_score', 0)}/15

💰 Liquidity: ${signal_data.get('liquidity_usd', 0):,.2f}
📈 24h Volume: ${signal_data.get('volume_24h', 0):,.2f}
🧠 Smart Wallets: {signal_data.get('smart_wallets_count', 0)}

⏳ Waiting for Claude analysis...
        """
        await self.send_alert(message)
    
    async def claude_decision(self, signal_data: Dict, decision: Dict):
        """Alert for Claude's decision"""
        action_emoji = {"BUY": "🚀", "WATCH": "👀", "SKIP": "❌"}
        
        message = f"""
🤖 <b>Claude Decision</b>

Token: {signal_data.get('token_name', 'Unknown')}
Action: {action_emoji.get(decision['action'], '❓')} <b>{decision['action']}</b>
Confidence: {decision['confidence']}/100

💭 <b>Reasoning:</b>
{decision['reasoning']}
        """
        await self.send_alert(message)
    
    async def trade_executed(self, trade_data: Dict):
        """Alert for executed trade"""
        message = f"""
✅ <b>Trade Executed</b>

Token: {trade_data.get('token_name', 'Unknown')} ({trade_data.get('token_symbol', '???')})
Chain: {trade_data['chain'].upper()}
Entry Price: ${trade_data['execution_price']:.8f}
Position Size: ${trade_data['position_size_usd']:,.2f}
Confidence: {trade_data.get('claude_confidence', 0)}/100

📋 Order ID: {trade_data['order_id']}
⛽ Slippage: {trade_data.get('slippage', 0):.2%}
        """
        await self.send_alert(message)
    
    async def trade_closed(self, trade_data: Dict):
        """Alert for closed trade"""
        pnl_emoji = "🟢" if trade_data['pnl_usd'] > 0 else "🔴"
        
        message = f"""
{pnl_emoji} <b>Trade Closed</b>

Token: {trade_data.get('token_name', 'Unknown')}
Exit Price: ${trade_data['exit_price']:.8f}
PnL: {pnl_emoji} ${trade_data['pnl_usd']:,.2f} ({trade_data['pnl_percent']:+.1f}%)
Hold Time: {trade_data.get('hold_time_hours', 0):.1f}h

🎯 Exit Reason: {trade_data['exit_reason']}
        """
        await self.send_alert(message)
    
    async def convergence_detected(self, convergence_data: Dict):
        """Alert for smart money convergence"""
        message = f"""
⚡ <b>Smart Money Convergence</b>

Token: {convergence_data.get('token_name', 'Unknown')}
Chain: {convergence_data['chain'].upper()}
Wallets Involved: {len(convergence_data['wallets_involved'])}
Time Window: {convergence_data['time_window_minutes']} minutes

🎯 Signal bypassing normal scoring - elevated priority!
        """
        await self.send_alert(message)
    
    async def stop_loss_triggered(self, trade_data: Dict):
        """Alert for stop loss"""
        message = f"""
🛑 <b>Stop Loss Triggered</b>

Token: {trade_data.get('token_name', 'Unknown')}
Loss: -${abs(trade_data['pnl_usd']):,.2f} ({trade_data['pnl_percent']:.1f}%)
Entry: ${trade_data['entry_price']:.8f}
Exit: ${trade_data['exit_price']:.8f}
        """
        await self.send_alert(message)
    
    async def daily_summary(self, stats: Dict):
        """Send daily trading summary"""
        win_rate = (stats['trades_won'] / max(stats['total_trades'], 1)) * 100
        
        message = f"""
📊 <b>Daily Summary</b>

💰 Total PnL: ${stats['total_pnl']:,.2f}
📈 Trades: {stats['trades_won']}W / {stats['trades_lost']}L ({win_rate:.1f}%)
🎯 Best Trade: +${stats.get('best_trade_pnl', 0):,.2f}
📉 Worst Trade: ${stats.get('worst_trade_pnl', 0):,.2f}

🔍 Signals Scanned: {stats['signals_scanned']}
✅ Passed Security: {stats['signals_passed_security']}
🧠 Claude Calls: {stats['claude_calls_made']}/{settings.MAX_CLAUDE_CALLS_PER_HOUR}
        """
        await self.send_alert(message)
    
    async def risk_limit_triggered(self, limit_type: str, current_loss: float):
        """Alert for risk limit triggers"""
        message = f"""
⚠️ <b>Risk Limit Triggered</b>

Limit Type: {limit_type.replace('_', ' ').title()}
Current Loss: -${abs(current_loss):,.2f}

🛑 Trading has been halted automatically.
        """
        await self.send_alert(message)
    
    async def api_health_issue(self, service: str, error: str):
        """Alert for API health issues"""
        message = f"""
🚨 <b>API Health Alert</b>

Service: {service}
Issue: {error}

Trading may be affected until resolved.
        """
        await self.send_alert(message)

telegram_service = TelegramAlertService()
