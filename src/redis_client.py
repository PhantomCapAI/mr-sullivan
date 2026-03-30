import redis.asyncio as redis
from config.settings import settings
import json
from typing import Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._connection_tested = False
    
    async def _ensure_connection(self):
        if not self._connection_tested:
            try:
                await self.client.ping()
                self._connection_tested = True
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                raise
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            await self._ensure_connection()
            value = await self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            await self._ensure_connection()
            serialized_value = json.dumps(value, default=str)
            await self.client.set(key, serialized_value, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def acquire_lock(self, key: str, timeout: int = 30) -> bool:
        try:
            await self._ensure_connection()
            result = await self.client.set(f"lock:{key}", "1", nx=True, ex=timeout)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis LOCK error for key {key}: {e}")
            return False
    
    async def release_lock(self, key: str) -> bool:
        try:
            await self.client.delete(f"lock:{key}")
            return True
        except Exception as e:
            logger.error(f"Redis UNLOCK error for key {key}: {e}")
            return False
    
    async def increment(self, key: str, ttl: int = 3600) -> int:
        try:
            await self._ensure_connection()
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            result = await pipe.execute()
            return result[0]
        except Exception as e:
            logger.error(f"Redis INCREMENT error for key {key}: {e}")
            return 0

redis_client = RedisClient()
