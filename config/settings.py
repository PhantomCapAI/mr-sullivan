from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///sullivan.db"

    # GMGN API
    GMGN_API_KEY: str = ""
    GMGN_ED25519_PRIVATE_KEY: str = "0" * 64  # Hex-encoded Ed25519 private key
    GMGN_RATE_LIMIT_PER_MINUTE: int = 100

    # Claude API
    ANTHROPIC_API_KEY: str = ""
    MAX_CLAUDE_CALLS_PER_HOUR: int = 100
    CLAUDE_CACHE_TTL_SECONDS: int = 1800

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = "1516882079"

    # Solana RPC
    RPC_URL: str = ""
    WS_URL: str = ""

    # Redis
    REDIS_URL: str = ""

    # Paper trading mode
    PAPER_TRADE: bool = True

    # Trading
    SUPPORTED_CHAINS: List[str] = ["sol", "base", "eth", "bsc"]
    MIN_SIGNAL_SCORE: int = 65
    MAX_OPEN_POSITIONS: int = 10

    # Risk Management
    TRAILING_STOP_PERCENT: float = 15.0
    TAKE_PROFIT_PERCENT: float = 100.0
    STOP_LOSS_PERCENT: float = 25.0
    DAILY_LOSS_LIMIT_PERCENT: float = 10.0
    WEEKLY_LOSS_LIMIT_PERCENT: float = 20.0

    # Position Sizing
    DEFAULT_POSITION_SIZE_USD: float = 100.0
    MAX_POSITION_SIZE_USD: float = 500.0
    DEFAULT_SLIPPAGE_TOLERANCE: float = 0.05

    # Authentication
    SECRET_KEY: str = "phantom-sullivan-paper-mode"
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = "phantom-sullivan-paper-mode"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"

settings = Settings()
