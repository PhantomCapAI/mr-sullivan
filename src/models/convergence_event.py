from sqlalchemy import Column, String, Integer, ARRAY, Index
from .base import BaseModel

class ConvergenceEvent(BaseModel):
    __tablename__ = "convergence_events"
    
    token_address = Column(String(50), nullable=False)
    chain = Column(String(20), nullable=False)
    wallets_involved = Column(ARRAY(String), nullable=False)
    time_window_minutes = Column(Integer, nullable=False)
    signal_strength = Column(Integer, nullable=False)
    action_taken = Column(String(100), nullable=False)
    
    __table_args__ = (
        Index('ix_convergence_token_chain', 'token_address', 'chain'),
        Index('ix_convergence_created_at', 'created_at'),
    )
