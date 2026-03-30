import httpx
import asyncio
import hashlib
import time
import uuid
from typing import Dict, List, Optional, Any
from config.settings import settings
from src.redis_client import redis_client
import logging
import ed25519
import binascii

logger = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    pass

class GMGNService:
    def __init__(self):
        self.base_url = "https://gmgn.ai/api/v1"
        self.api_key = settings.GMGN_API_KEY
        self.private_key = ed25519.SigningKey(binascii.unhexlify(settings.GMGN_ED25519_PRIVATE_KEY))
        self.rate_limit_window = 60
        self.max_requests_per_window = settings.GMGN_RATE_LIMIT_PER_MINUTE
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300
        
    async def _check_circuit_breaker(self) -> bool:
        failures = await redis_client.get("gmgn_failures") or 0
        if failures >= self.circuit_breaker_threshold:
            last_failure = await redis_client.get("gmgn_last_failure") or 0
            if time.time() - last_failure < self.circuit_breaker_timeout:
                return False
        return True
    
    async def _record_failure(self):
        failures = await redis_client.get("gmgn_failures") or 0
        await redis_client.set("gmgn_failures", failures + 1, ttl=self.circuit_breaker_timeout)
        await redis_client.set("gmgn_last_failure", time.time())
    
    async def _record_success(self):
        await redis_client.set("gmgn_failures", 0, ttl=1)
    
    def _create_headers(self, timestamp: int, client_id: str) -> Dict[str, str]:
        """Create authenticated headers for GMGN API"""
        # Create signature for trading operations
        message = f"{timestamp}{client_id}".encode()
        signature = self.private_key.sign(message)
        
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Timestamp": str(timestamp),
            "X-Client-ID": client_id,
            "X-Signature": binascii.hexlify(signature).decode()
        }
    
    async def _make_request(self, endpoint: str, params: Dict = None, method: str = "GET") -> Dict:
        if not await self._check_circuit_breaker():
            raise CircuitBreakerError("GMGN API circuit breaker is open")
        
        # Rate limiting check
        current_requests = await redis_client.get("gmgn_rate_limit") or 0
        if current_requests >= self.max_requests_per_window:
            raise Exception("Rate limit exceeded")
        
        try:
            timestamp = int(time.time())
            client_id = str(uuid.uuid4())
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = self._create_headers(timestamp, client_id)
                
                if method == "GET":
                    response = await client.get(
                        f"{self.base_url}/{endpoint}",
                        headers=headers,
                        params=params or {}
                    )
                else:
                    response = await client.post(
                        f"{self.base_url}/{endpoint}",
                        headers=headers,
                        json=params or {}
                    )
                
                response.raise_for_status()
                
                # Update rate limit counter
                await redis_client.increment("gmgn_rate_limit", ttl=self.rate_limit_window)
                
                await self._record_success()
                return response.json()
                
        except Exception as e:
            await self._record_failure()
            logger.error(f"GMGN API error: {e}")
            raise
    
    async def get_token_info(self, token_address: str, chain: str = "sol") -> Dict:
        cache_key = f"gmgn_token_info:{chain}:{token_address}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "token/info",
            params={"chain": chain, "address": token_address}
        )
        await redis_client.set(cache_key, result, ttl=60)  # 1 min cache
        return result
    
    async def get_token_security(self, token_address: str, chain: str = "sol") -> Dict:
        cache_key = f"gmgn_security:{chain}:{token_address}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "token/security",
            params={"chain": chain, "address": token_address}
        )
        await redis_client.set(cache_key, result, ttl=300)  # 5 min cache
        return result
    
    async def get_token_pool_info(self, token_address: str, chain: str = "sol") -> Dict:
        cache_key = f"gmgn_pool:{chain}:{token_address}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "token/pool_info",
            params={"chain": chain, "address": token_address}
        )
        await redis_client.set(cache_key, result, ttl=120)  # 2 min cache
        return result
    
    async def get_trending_tokens(self, chain: str = "sol", limit: int = 100) -> List[Dict]:
        cache_key = f"gmgn_trending:{chain}:{limit}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "market/trending",
            params={"chain": chain, "limit": limit}
        )
        
        await redis_client.set(cache_key, result, ttl=120)  # 2 min cache
        return result.get("data", [])
    
    async def get_trenches(self, stage: str = "migrated", chain: str = "sol") -> List[Dict]:
        cache_key = f"gmgn_trenches:{chain}:{stage}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "trenches",
            params={"stage": stage, "chain": chain}
        )
        
        await redis_client.set(cache_key, result, ttl=120)  # 2 min cache
        return result.get("data", [])
    
    async def get_top_traders(self, token_address: str, chain: str = "sol") -> List[Dict]:
        cache_key = f"gmgn_top_traders:{chain}:{token_address}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request(
            "market/top_traders",
            params={"chain": chain, "address": token_address}
        )
        
        await redis_client.set(cache_key, result, ttl=300)  # 5 min cache
        return result.get("data", [])
    
    async def get_user_holdings(self) -> Dict:
        """Get current portfolio holdings"""
        result = await self._make_request("user/holdings")
        return result
    
    async def get_user_balance(self, chain: str = "sol") -> Dict:
        """Get wallet balance for chain"""
        result = await self._make_request(
            "user/balance",
            params={"chain": chain}
        )
        return result
    
    async def get_trade_quote(self, token_address: str, amount_usd: float, chain: str = "sol") -> Dict:
        """Get quote for trade before execution"""
        result = await self._make_request(
            "trade/quote",
            params={
                "token_address": token_address,
                "amount_usd": amount_usd,
                "chain": chain
            }
        )
        return result
    
    async def execute_swap(self, trade_data: Dict) -> Dict:
        """Execute trade via GMGN"""
        result = await self._make_request(
            "trade/swap",
            params=trade_data,
            method="POST"
        )
        return result
    
    async def get_order_status(self, order_id: str) -> Dict:
        """Get status of executed order"""
        result = await self._make_request(
            "trade/order_status",
            params={"order_id": order_id}
        )
        return result

gmgn_service = GMGNService()
