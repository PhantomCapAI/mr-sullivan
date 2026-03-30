from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from src.database import get_db_transaction
from src.models.daily_stat import DailyStat
from src.api.auth import verify_token
from pydantic import BaseModel

router = APIRouter()

class StatsResponse(BaseModel):
    date: str
    chain: str
    signals_scanned: int
    trades_executed: int
    total_pnl: float

@router.get("/daily", response_model=List[StatsResponse])
async def get_daily_stats(
    days: int = Query(7, le=30),
    current_user: str = Depends(verify_token)
):
    """Get daily statistics"""
    with get_db_transaction() as db:
        start_date = datetime.utcnow().date() - timedelta(days=days)
        
        stats = db.query(DailyStat).filter(
            DailyStat.date >= start_date
        ).order_by(DailyStat.date.desc()).all()
        
        return [
            StatsResponse(
                date=str(stat.date),
                chain=stat.chain,
                signals_scanned=stat.signals_scanned,
                trades_executed=stat.trades_executed,
                total_pnl=stat.total_pnl
            )
            for stat in stats
        ]
