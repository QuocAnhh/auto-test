import json
import gc
from typing import List, Dict, Any





def monitor_memory_usage() -> Dict[str, float]:
    """Enhanced memory monitoring cho batch processing"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # System memory info
        system_memory = psutil.virtual_memory()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "system_memory_available_mb": system_memory.available / 1024 / 1024,
            "system_memory_percent": system_memory.percent,
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, 'num_fds') else 0
        }
    except ImportError:
        return {"rss_mb": 0, "vms_mb": 0, "cpu_percent": 0, "memory_percent": 0}

def cleanup_memory():
    """Enhanced memory cleanup"""
    # Force garbage collection for all generations
    collected = gc.collect()
    
    # Additional cleanup for specific objects
    import sys
    if hasattr(sys, '_clear_type_cache'):
        sys._clear_type_cache()
    
    return collected

def get_memory_pressure() -> str:
    """Detect memory pressure level"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return "critical"
        elif memory.percent > 75:
            return "high"
        elif memory.percent > 60:
            return "medium"
        else:
            return "low"
    except ImportError:
        return "unknown"


def estimate_batch_time(num_conversations: int, concurrency: int) -> float:
    """Ước tính thời gian batch processing"""
    # Tối ưu theo size batch: avg time giảm với batch lớn do caching
    if num_conversations >= 50:
        avg_time_per_conv = 2.5  # Fast batch mode với caching
    elif num_conversations >= 20:
        avg_time_per_conv = 3.0  # Medium batch
    else:
        avg_time_per_conv = 4.0  # Small batch
    return (num_conversations * avg_time_per_conv) / concurrency

def get_optimal_concurrency(num_conversations: int) -> int:
    """Gợi ý concurrency tối ưu theo số lượng conv"""
    if num_conversations >= 100:
        return 30  # Rất cao cho batch rất lớn
    elif num_conversations >= 50:
        return 25  # Cao cho batch lớn
    elif num_conversations >= 20:
        return 20
    elif num_conversations >= 10:
        return 15
    else:
        return 10