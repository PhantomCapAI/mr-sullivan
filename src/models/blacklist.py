from sqlalchemy import Column, String, Text, Integer, Decimal, DateTime
from .base import BaseModel

class Blacklist(BaseModel):
    __tablename__ = "blacklist"
    
    token_address = Column(String(50), primary_key=True)
    chain = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)
    original_signal_score = Column(Integer)
    loss_amount = Column(Decimal(15, 2))
    blacklisted_at = Column(DateTime(timezone=True), nullable=False)
