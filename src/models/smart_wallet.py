from sqlalchemy import Column, String, Numeric, Integer, DateTime, Boolean, Index
from .base import BaseModel

class SmartWallet(BaseModel):
    __tablename__ = "smart_wallets"
    
    address = Column(String(50), primary_key=True)
    chain = Column(String(20), nullable=False)
    win_rate = Column(Numeric(5, 4), nullable=False)
    total_pnl = Column(Numeric(15, 2), nullable=False)
    avg_hold_time_minutes = Column(Integer, nullable=False)
    total_trades = Column(Integer, nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=False)
    tracked_since = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('ix_smart_wallets_chain', 'chain'),
        Index('ix_smart_wallets_win_rate', 'win_rate'),
        Index('ix_smart_wallets_is_active', 'is_active'),
    )
