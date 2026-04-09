import json
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

from config.settings import settings


class RedisClient:
    def __init__(self):
        self.client = None
        self._available = False

        if settings.REDIS_URL:
            try:
                import redis.asyncio as redis_lib
                self.client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
                self._available = True
                logger.info("Redis client initialized")
            except Exception as e:
                logger.warning(f"Redis unavailable: {e}. Running without cache.")
        else:
            logger.warning("REDIS_URL not set. Running without Redis (in-memory fallback).")

        # In-memory fallback
        self._mem: dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        if self._available and self.client:
            try:
                value = await self.client.get(key)
                return json.loads(value) if value else None
            except Exception:
                pass
        return self._mem.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        self._mem[key] = value
        if self._available and self.client:
            try:
                await self.client.set(key, json.dumps(value, default=str), ex=ttl)
                return True
            except Exception:
                pass
        return True

    async def acquire_lock(self, key: str, timeout: int = 30) -> bool:
        lock_key = f"lock:{key}"
        if self._available and self.client:
            try:
                result = await self.client.set(lock_key, "1", nx=True, ex=timeout)
                return bool(result)
            except Exception:
                pass
        # In-memory fallback: always succeed (single instance)
        return True

    async def release_lock(self, key: str) -> bool:
        if self._available and self.client:
            try:
                await self.client.delete(f"lock:{key}")
            except Exception:
                pass
        return True

    async def increment(self, key: str, ttl: int = 3600) -> int:
        self._mem[key] = self._mem.get(key, 0) + 1
        if self._available and self.client:
            try:
                pipe = self.client.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                result = await pipe.execute()
                return result[0]
            except Exception:
                pass
        return self._mem[key]


redis_client = RedisClient()
