from typing import Tuple, Dict, Optional
import logging

from .brand_specs import load_brand_prompt, BrandPolicy
from .bot_map import BotMap

logger = logging.getLogger(__name__)


class BrandResolver:
    """
    Class để resolve brand info từ bot_id, với caching để tối ưu performance.
    
    Sử dụng BotMap để ánh xạ bot_id -> (brand_id, prompt_path), 
    sau đó load brand prompt và policy từ file.
    """
    
    def __init__(self, bot_map_path: str = "config/bot_map.yaml"):
        """
        Initialize BrandResolver với bot mapping config.
        
        Args:
            bot_map_path: Đường dẫn tới file bot_map.yaml
        """
        self._map = BotMap(bot_map_path)
        self._cache: Dict[str, Tuple[str, BrandPolicy]] = {}
        
        # Log mapped bots for debugging
        mapped_bots = self._map.get_all_mapped_bots()
        logger.info(f"BrandResolver initialized with {len(mapped_bots)} mapped bots: {mapped_bots}")

    def resolve_by_bot_id(self, bot_id: Optional[str]) -> Tuple[str, BrandPolicy]:
        """
        Resolve brand prompt text và policy từ bot_id.
        
        Args:
            bot_id: Bot ID để resolve, có thể là None
            
        Returns:
            Tuple[str, BrandPolicy]: (brand_prompt_text, brand_policy)
            
        Raises:
            ValueError: Khi không thể resolve được hoặc load brand prompt failed
        """
        try:
            brand_id, prompt_path = self._map.resolve(bot_id)
            
            # Check cache trước
            if prompt_path not in self._cache:
                # Load brand prompt và cache kết quả
                brand_prompt_text, brand_policy = load_brand_prompt(prompt_path)
                self._cache[prompt_path] = (brand_prompt_text, brand_policy)
                logger.debug(f"Loaded and cached brand: {brand_id} from {prompt_path}")
            
            brand_prompt_text, brand_policy = self._cache[prompt_path]
            
            # Log resolution cho debugging (chỉ khi bot_id thay đổi)
            if bot_id:
                logger.debug(f"Resolved bot_id={bot_id} -> brand_id={brand_id}")
            else:
                logger.debug(f"Used fallback brand: {brand_id}")
            
            return brand_prompt_text, brand_policy
            
        except Exception as e:
            logger.error(f"Failed to resolve brand for bot_id={bot_id}: {e}")
            raise
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Trả về thống kê cache cho monitoring.
        
        Returns:
            Dict với cache_size và mapped_bots_count
        """
        return {
            "cache_size": len(self._cache),
            "mapped_bots_count": len(self._map.get_all_mapped_bots())
        }
