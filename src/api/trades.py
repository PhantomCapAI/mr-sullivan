from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from src.database import get_db_transaction
from src.models.trade import Trade
from src.api.auth import verify_token
from pydantic import BaseModel

router = APIRouter()

class TradeResponse(BaseModel):
    id: int
    token_address: str
    chain: str
    direction: str
    pnl_usd: Optional[float]
    created_at: str

@router.get("/", response_model=List[TradeResponse])
async def get_trades(
    chain: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    current_user: str = Depends(verify_token)
):
    """Get recent trades"""
    with get_db_transaction() as db:
        query = db.query(Trade)
        
        if chain:
            query = query.filter(Trade.chain == chain)
        
        trades = query.order_by(Trade.created_at.desc()).limit(limit).all()
        
        return [
            TradeResponse(
                id=trade.id,
                token_address=trade.token_address,
                chain=trade.chain,
                direction=trade.direction.value,
                pnl_usd=trade.pnl_usd,
                created_at=str(trade.created_at)
            )
            for trade in trades
        ]
