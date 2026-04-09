from sqlalchemy import Column, String, Numeric, DateTime, Index
from .base import BaseModel

class Portfolio(BaseModel):
    __tablename__ = "portfolio"
    
    token_address = Column(String(50), nullable=False)
    chain = Column(String(20), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    unrealized_pnl = Column(Numeric(15, 2), nullable=False)
    peak_price = Column(Numeric(20, 8), nullable=False)
    trailing_stop_price = Column(Numeric(20, 8), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    last_checked = Column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (
        Index('ix_portfolio_token_chain', 'token_address', 'chain'),
        Index('ix_portfolio_last_checked', 'last_checked'),
    )
