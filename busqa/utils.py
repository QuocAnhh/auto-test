import json
import gc
from typing import List, Dict, Any


def safe_parse_headers(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        return {str(k): str(v) for k, v in d.items()}
    except Exception:
        return {}



def monitor_memory_usage() -> Dict[str, float]:
    """Monitor memory usage cho batch processing (simplified)"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "cpu_percent": process.cpu_percent()
        }
    except ImportError:
        return {"rss_mb": 0, "vms_mb": 0, "cpu_percent": 0}

def cleanup_memory():
    """Force garbage collection khi cần"""
    gc.collect()

def chunk_conversations(conv_ids: List[str], chunk_size: int = 10) -> List[List[str]]:
    """Chia conversations thành chunks nhỏ để xử lý"""
    return [conv_ids[i:i + chunk_size] for i in range(0, len(conv_ids), chunk_size)]

def estimate_batch_time(num_conversations: int, concurrency: int) -> float:
    """Ước tính thời gian batch processing"""
    # Tối ưu cho 50 conv: avg time giảm xuống 2.5-3s với caching
    if num_conversations >= 50:
        avg_time_per_conv = 2.8  # Fast batch mode
    else:
        avg_time_per_conv = 4.0  # Normal mode
    return (num_conversations * avg_time_per_conv) / concurrency

def get_optimal_concurrency(num_conversations: int) -> int:
    """Gợi ý concurrency tối ưu theo số lượng conv"""
    if num_conversations >= 50:
        return 25  # Cao cho batch lớn
    elif num_conversations >= 20:
        return 20
    elif num_conversations >= 10:
        return 15
    else:
        return 10