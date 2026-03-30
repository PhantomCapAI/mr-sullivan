from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean, Text
from sqlalchemy.sql import func
from src.models.base import Base
import enum

class TradeDirection(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String(255), nullable=False, index=True)
    token_name = Column(String(255))
    chain = Column(String(50), nullable=False, index=True)
    
    # Trade details
    direction = Column(Enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float)
    exit_price = Column(Float)
    position_size_usd = Column(Float, nullable=False)
    
    # P&L
    pnl_usd = Column(Float)
    pnl_percent = Column(Float)
    
    # Status
    is_closed = Column(Boolean, default=False)
    exit_reason = Column(String(100))
    
    # Order IDs
    buy_order_id = Column(String(255))
    sell_order_id = Column(String(255))
    
    # Hold time
    hold_time_seconds = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
