from typing import Tuple, Optional, Dict, Any
import os
import yaml


class BotMap:
    """Class để map bot_id thành (brand_id, prompt_path) từ file cấu hình YAML"""
    
    def __init__(self, path: str = "config/bot_map.yaml"):
        """
        Load bot mapping configuration từ YAML file.
        
        Args:
            path: Đường dẫn tới file bot_map.yaml
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        self._bots: Dict[str, Dict[str, Any]] = data.get("bots", {})
        self._defaults = data.get("defaults", {})
        self._brands_dir = self._defaults.get("brands_dir", "brands")
        self._fallback_brand = self._defaults.get("fallback_brand")

    def resolve(self, bot_id: Optional[str]) -> Tuple[str, str]:
        """
        Trả về (brand_id, prompt_path) cho bot_id.
        
        Logic:
        - Nếu bot_id có trong map: dùng entry đó.
        - Nếu không có prompt_path: dùng brands_dir/<brand_id>/prompt.md
        - Nếu bot_id không có trong map: dùng fallback_brand (nếu có).
        - Nếu vẫn không có: raise ValueError.
        
        Args:
            bot_id: Bot ID để resolve, có thể là None
            
        Returns:
            Tuple[str, str]: (brand_id, prompt_path)
            
        Raises:
            ValueError: Khi không thể resolve được brand cho bot_id
        """
        # thử resolve từ mapping trước
        if bot_id and bot_id in self._bots:
            entry = self._bots[bot_id] or {}
            brand_id = entry.get("brand_id")
            prompt_path = entry.get("prompt_path")
            
            # Nếu không có prompt_path, tự động tạo từ brands_dir
            if brand_id and not prompt_path:
                prompt_path = os.path.join(self._brands_dir, brand_id, "prompt.md")
            
            if brand_id and prompt_path:
                return brand_id, prompt_path

        # fallback
        if self._fallback_brand:
            brand_id = self._fallback_brand
            prompt_path = os.path.join(self._brands_dir, brand_id, "prompt.md")
            return brand_id, prompt_path

        raise ValueError(f"Cannot resolve brand for bot_id={bot_id!r} and no fallback_brand configured")
    
    def get_all_mapped_bots(self) -> Dict[str, str]:
        """
        Trả về dict mapping tất cả bot_id -> brand_id có trong config.
        Hữu ích cho logging và debugging.
        """
        result = {}
        for bot_id, entry in self._bots.items():
            brand_id = entry.get("brand_id")
            if brand_id:
                result[bot_id] = brand_id
        return result
