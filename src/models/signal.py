from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean, Text
from sqlalchemy.sql import func
from src.models.base import Base
import enum

class ActionTaken(enum.Enum):
    QUEUED = "queued"
    EXECUTED = "executed"
    SKIPPED = "skipped"

class ClaudeAction(enum.Enum):
    BUY = "BUY"
    WATCH = "WATCH"
    SKIP = "SKIP"

class Signal(Base):
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String(255), nullable=False, index=True)
    token_name = Column(String(255))
    chain = Column(String(50), nullable=False, index=True)
    
    # Scoring
    signal_score = Column(Integer, nullable=False)
    holder_health_score = Column(Integer, default=0)
    liquidity_score = Column(Integer, default=0)
    momentum_score = Column(Integer, default=0)
    smart_money_score = Column(Integer, default=0)
    creator_trust_score = Column(Integer, default=0)
    
    # Actions
    action_taken = Column(Enum(ActionTaken), default=ActionTaken.QUEUED)
    processed = Column(Boolean, default=False)
    
    # Claude analysis
    claude_action = Column(Enum(ClaudeAction), nullable=True)
    claude_confidence = Column(Integer, nullable=True)
    claude_reasoning = Column(Text, nullable=True)
    
    # Metrics
    smart_wallets_count = Column(Integer, default=0)
    fresh_wallet_rate = Column(Float, default=0.0)
    top_10_holder_rate = Column(Float, default=0.0)
    liquidity_usd = Column(Float, default=0.0)
    volume_24h = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
