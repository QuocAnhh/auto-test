"""
Enhanced API client với connection pooling và rate limiting
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
import logging
import json
from dataclasses import dataclass

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
            logger.warning("httpx not available, falling back to requests")
        
        # Rate limiting
        self.rate_limiter = asyncio.Semaphore(self.config.rate_limit_per_second)
        self.last_request_time = {}
        
        # Initialize Redis if available
        if REDIS_AVAILABLE and redis_url and self.config.enable_caching:
            try:
                self.redis_client = aioredis.from_url(redis_url)
                logger.info("✅ Redis caching enabled")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.redis_client = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client and hasattr(self.client, 'aclose'):
            await self.client.aclose()
        if self.redis_client:
            await self.redis_client.close()
    
    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache"""
        if not self.redis_client:
            return None
        try:
            cached = await self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
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
            logger.debug(f"Cache set error: {e}")
        
    async def fetch_conversation_batch(self, conversation_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple conversations với connection pooling và caching"""
        
        async def fetch_single(conv_id: str) -> Dict[str, Any]:
            # Check cache first
            cache_key = f"conv:{conv_id}:messages"
            cached_data = await self._get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {conv_id}")
                return {
                    "conversation_id": conv_id,
                    "data": cached_data,
                    "status": "success",
                    "cached": True
                }
            
            async with self.rate_limiter:
                # Adaptive rate limiting
                await self._adaptive_sleep()
                
                try:
                    if HTTPX_AVAILABLE and self.client:
                        response = await self.client.get(f"/conversations/{conv_id}/messages")
                        response.raise_for_status()
                        data = response.json()
                    else:
                        # Fallback to sync requests (wrapped in thread)
                        import requests
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None, 
                            lambda: requests.get(f"{self.base_url}/conversations/{conv_id}/messages", timeout=self.config.timeout)
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
                    logger.error(f"Error fetching {conv_id}: {e}")
                    return {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "status": "error"
                    }
        
        # Fetch all conversations concurrently
        start_time = time.time()
        tasks = [fetch_single(conv_id) for conv_id in conversation_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        elapsed = time.time() - start_time
        success_count = len([r for r in results if r.get("status") == "success"])
        cache_hits = len([r for r in results if r.get("cached")])
        
        logger.info(f"✅ Fetched {success_count}/{len(conversation_ids)} conversations in {elapsed:.1f}s")
        logger.info(f"📦 Cache hits: {cache_hits}/{len(conversation_ids)} ({cache_hits/len(conversation_ids)*100:.1f}%)")
        
        return results
    
    async def _adaptive_sleep(self):
        """Adaptive rate limiting based on system load"""
        # Simple adaptive sleep - can be enhanced with more sophisticated algorithms
        base_sleep = 1.0 / self.config.rate_limit_per_second
        await asyncio.sleep(base_sleep)

# Usage example in batch_evaluator.py:
"""
async with HighPerformanceAPIClient(base_url) as api_client:
    api_results = await api_client.fetch_conversation_batch(conversation_ids)
"""
