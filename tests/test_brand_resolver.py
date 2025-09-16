import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, mock_open

from busqa.brand_resolver import BrandResolver
from busqa.bot_map import BotMap


class TestBrandResolver:
    """Test cases cho BrandResolver class"""
    
    def test_bot_map_basic_resolve(self):
        """Test basic bot_id resolution từ mapping"""
        # Tạo temp config
        config_data = {
            "defaults": {
                "fallback_brand": "son_hai",
                "brands_dir": "brands"
            },
            "bots": {
                "4496": {
                    "brand_id": "son_hai",
                    "prompt_path": "brands/son_hai/prompt.md"
                },
                "9999": {
                    "brand_id": "phuong_trang",
                    "prompt_path": "brands/phuong_trang/prompt.md"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            bot_map = BotMap(config_path)
            
            # Test mapped bot
            brand_id, prompt_path = bot_map.resolve("4496")
            assert brand_id == "son_hai"
            assert prompt_path == "brands/son_hai/prompt.md"
            
            # Test fallback
            brand_id, prompt_path = bot_map.resolve("unknown_bot")
            assert brand_id == "son_hai"
            assert prompt_path == "brands/son_hai/prompt.md"
            
            # Test None bot_id
            brand_id, prompt_path = bot_map.resolve(None)
            assert brand_id == "son_hai"
            
        finally:
            os.unlink(config_path)
    
    def test_bot_map_no_fallback_error(self):
        """Test error khi không có fallback brand"""
        config_data = {
            "bots": {
                "4496": {
                    "brand_id": "son_hai",
                    "prompt_path": "brands/son_hai/prompt.md"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            bot_map = BotMap(config_path)
            
            # Should work for mapped bot
            brand_id, _ = bot_map.resolve("4496")
            assert brand_id == "son_hai"
            
            # Should error for unmapped bot
            with pytest.raises(ValueError, match="Cannot resolve brand"):
                bot_map.resolve("unknown_bot")
                
        finally:
            os.unlink(config_path)
    
    def test_bot_map_auto_prompt_path(self):
        """Test tự động tạo prompt_path từ brands_dir"""
        config_data = {
            "defaults": {
                "brands_dir": "custom_brands"
            },
            "bots": {
                "4496": {
                    "brand_id": "test_brand"
                    # Không có prompt_path
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            bot_map = BotMap(config_path)
            brand_id, prompt_path = bot_map.resolve("4496")
            assert brand_id == "test_brand"
            assert prompt_path == "custom_brands/test_brand/prompt.md"
            
        finally:
            os.unlink(config_path)
    
    @patch('busqa.brand_specs.load_brand_prompt')
    def test_brand_resolver_caching(self, mock_load_brand_prompt):
        """Test caching mechanism của BrandResolver"""
        # Setup mock
        mock_brand_policy = object()  # Mock object
        mock_load_brand_prompt.return_value = ("mock_text", mock_brand_policy)
        
        config_data = {
            "defaults": {"fallback_brand": "son_hai"},
            "bots": {
                "4496": {
                    "brand_id": "son_hai",
                    "prompt_path": "brands/son_hai/prompt.md"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            resolver = BrandResolver(config_path)
            
            # First call - should load from file
            text1, policy1 = resolver.resolve_by_bot_id("4496")
            assert text1 == "mock_text"
            assert policy1 is mock_brand_policy
            mock_load_brand_prompt.assert_called_once_with("brands/son_hai/prompt.md")
            
            # Second call - should use cache
            text2, policy2 = resolver.resolve_by_bot_id("4496")
            assert text2 == "mock_text"
            assert policy2 is mock_brand_policy
            # Still only called once
            mock_load_brand_prompt.assert_called_once()
            
            # Check cache stats
            stats = resolver.get_cache_stats()
            assert stats["cache_size"] == 1
            assert stats["mapped_bots_count"] == 1
            
        finally:
            os.unlink(config_path)
    
    @patch('busqa.brand_specs.load_brand_prompt')
    def test_brand_resolver_fallback_logging(self, mock_load_brand_prompt):
        """Test fallback behavior và logging"""
        mock_load_brand_prompt.return_value = ("fallback_text", object())
        
        config_data = {
            "defaults": {"fallback_brand": "default_brand"},
            "bots": {}  # Empty bots
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            resolver = BrandResolver(config_path)
            
            # Should use fallback for unknown bot
            text, policy = resolver.resolve_by_bot_id("unknown_bot_123")
            assert text == "fallback_text"
            mock_load_brand_prompt.assert_called_once_with("brands/default_brand/prompt.md")
            
        finally:
            os.unlink(config_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
