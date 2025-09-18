"""
Enhanced API client với connection pooling và rate limiting
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
import logging
import json
from dataclasses import dataclass
import math
import random

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class APIClientConfig:
    """Configuration for high-performance API client"""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    timeout: float = 30.0
    rate_limit_per_second: int = 50
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes

class HighPerformanceAPIClient:
    """API client tối ưu với connection pooling và rate limiting"""
    
    def __init__(self, base_url: str, config: APIClientConfig = None, redis_url: str = None):
        self.config = config or APIClientConfig()
        self.base_url = base_url
        self.redis_client = None
        
        # Initialize HTTP client
        if HTTPX_AVAILABLE:
            limits = httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections
            )
            
            self.client = httpx.AsyncClient(
                base_url=base_url,
                limits=limits,
                timeout=httpx.Timeout(self.config.timeout),
                http2=True  # Enable HTTP/2 for better performance
            )
        else:
            self.client = None
            pass  # httpx not available, falling back to requests
        
        # Token-bucket rate limiting (true RPS control)
        self._tokens = self.config.rate_limit_per_second
        self._bucket_capacity = max(1, self.config.rate_limit_per_second)
        self._token_lock = asyncio.Lock()
        self._token_available = asyncio.Condition(self._token_lock)
        self._refill_task = None
        
        # Initialize Redis if available
        if REDIS_AVAILABLE and redis_url and self.config.enable_caching:
            try:
                self.redis_client = aioredis.from_url(redis_url)
                pass  # Redis caching enabled
            except Exception as e:
                pass  # Redis connection failed
                self.redis_client = None
        
    async def __aenter__(self):
        # Start token refill loop
        if self._refill_task is None:
            self._refill_task = asyncio.create_task(self._refill_tokens_loop())
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client and hasattr(self.client, 'aclose'):
            await self.client.aclose()
        if self.redis_client:
            await self.redis_client.close()
        # Stop token refill loop
        if self._refill_task:
            self._refill_task.cancel()
            try:
                await self._refill_task
            except asyncio.CancelledError:
                pass
            self._refill_task = None

    async def _refill_tokens_loop(self):
        """Background task to refill tokens at a steady rate."""
        # Refill one token every interval seconds
        interval = 1.0 / max(1, self.config.rate_limit_per_second)
        try:
            while True:
                await asyncio.sleep(interval)
                async with self._token_lock:
                    if self._tokens < self._bucket_capacity:
                        self._tokens += 1
                        # Wake up one waiter
                        self._token_available.notify(1)
        except asyncio.CancelledError:
            return

    async def _acquire_token(self):
        """Wait until a rate-limit token is available."""
        async with self._token_lock:
            while self._tokens <= 0:
                await self._token_available.wait()
            self._tokens -= 1
    
    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache"""
        if not self.redis_client:
            return None
        try:
            cached = await self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            pass  # Cache get error
        return None
    
    async def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Set data to Redis cache"""
        if not self.redis_client:
            return
        try:
            await self.redis_client.setex(
                key, 
                self.config.cache_ttl, 
                json.dumps(data, default=str)
            )
        except Exception as e:
            pass  # Cache set error
        
    async def fetch_conversation_batch(self, conversation_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple conversations với connection pooling và caching"""
        
        async def fetch_single(conv_id: str) -> Dict[str, Any]:
            # Check cache first
            cache_key = f"conv:{conv_id}:messages"
            cached_data = await self._get_from_cache(cache_key)
            if cached_data:
                return {
                    "conversation_id": conv_id,
                    "data": cached_data,
                    "status": "success",
                    "cached": True
                }
            
            # True RPS control
            await self._acquire_token()

            try:
                if HTTPX_AVAILABLE and self.client:
                    response = await self.client.get(f"/api/conversations/{conv_id}/messages")
                    response.raise_for_status()
                    data = response.json()
                else:
                    # Fallback to sync requests (wrapped in thread)
                    import requests
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: requests.get(f"{self.base_url}/api/conversations/{conv_id}/messages", timeout=self.config.timeout)
                    )
                    response.raise_for_status()
                    data = response.json()

                # Cache the result
                await self._set_cache(cache_key, data)

                return {
                    "conversation_id": conv_id,
                    "data": data,
                    "status": "success",
                    "cached": False
                }
            except Exception as e:
                return {
                    "conversation_id": conv_id,
                    "error": str(e),
                    "status": "error"
                }
        
        start_time = time.time()
        tasks = [fetch_single(conv_id) for conv_id in conversation_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        elapsed = time.time() - start_time
        success_count = len([r for r in results if r.get("status") == "success"])
        cache_hits = len([r for r in results if r.get("cached")])
                
        return results
    

