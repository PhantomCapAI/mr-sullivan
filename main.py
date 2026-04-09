import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.tasks.scheduler import start_scheduler, stop_scheduler
from src.api import auth, signals, trades, portfolio, stats
from src.database import engine
from src.models.base import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Mr. Sullivan Trading System...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Start background scheduler
    await start_scheduler()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Mr. Sullivan Trading System...")
    await stop_scheduler()

# Create FastAPI app
app = FastAPI(
    title="Mr. Sullivan - AI Trading Agent",
    description="Multi-chain AI-powered memecoin trading system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Mr. Sullivan Trading System is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
