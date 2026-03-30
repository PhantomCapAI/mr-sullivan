from fastapi import APIRouter, Depends
from typing import List
from src.database import get_db_transaction
from src.models.portfolio import Portfolio
from src.api.auth import verify_token
from pydantic import BaseModel

router = APIRouter()

class PositionResponse(BaseModel):
    id: int
    token_address: str
    chain: str
    quantity: float
    unrealized_pnl: Optional[float]
    entry_price: float

@router.get("/", response_model=List[PositionResponse])
async def get_positions(current_user: str = Depends(verify_token)):
    """Get current portfolio positions"""
    with get_db_transaction() as db:
        positions = db.query(Portfolio).all()
        
        return [
            PositionResponse(
                id=position.id,
                token_address=position.token_address,
                chain=position.chain,
                quantity=float(position.quantity),
                unrealized_pnl=float(position.unrealized_pnl) if position.unrealized_pnl else None,
                entry_price=float(position.entry_price)
            )
            for position in positions
        ]
