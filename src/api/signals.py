from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from src.database import get_db_transaction
from src.models.signal import Signal
from src.api.auth import verify_token
from pydantic import BaseModel

router = APIRouter()

class SignalResponse(BaseModel):
    id: int
    token_address: str
    token_name: Optional[str]
    chain: str
    signal_score: int
    action_taken: str
    created_at: str

@router.get("/", response_model=List[SignalResponse])
async def get_signals(
    chain: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    current_user: str = Depends(verify_token)
):
    """Get recent signals"""
    with get_db_transaction() as db:
        query = db.query(Signal)
        
        if chain:
            query = query.filter(Signal.chain == chain)
        
        signals = query.order_by(Signal.created_at.desc()).limit(limit).all()
        
        return [
            SignalResponse(
                id=signal.id,
                token_address=signal.token_address,
                token_name=signal.token_name,
                chain=signal.chain,
                signal_score=signal.signal_score,
                action_taken=signal.action_taken.value,
                created_at=str(signal.created_at)
            )
            for signal in signals
        ]
