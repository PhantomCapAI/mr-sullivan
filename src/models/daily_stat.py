from sqlalchemy import Column, Integer, String, Float, Date
from src.models.base import Base

class DailyStat(Base):
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    chain = Column(String(50), nullable=False, index=True)
    
    # Signal stats
    signals_scanned = Column(Integer, default=0)
    signals_passed_security = Column(Integer, default=0)
    signals_scored_above_65 = Column(Integer, default=0)
    
    # Trade stats
    trades_executed = Column(Integer, default=0)
    trades_won = Column(Integer, default=0)
    trades_lost = Column(Integer, default=0)
    
    # PnL stats
    total_pnl = Column(Float, default=0.0)
    best_trade_pnl = Column(Float, default=0.0)
    worst_trade_pnl = Column(Float, default=0.0)
    
    # Performance metrics
    avg_hold_time = Column(Integer, default=0)  # in minutes
    claude_calls_made = Column(Integer, default=0)
    convergence_events = Column(Integer, default=0)
