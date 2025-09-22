"""
System Performance Monitor for high-throughput batch processing
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_rss_mb: float = 0.0
    memory_available_mb: float = 0.0
    active_threads: int = 0
    open_files: int = 0
    network_connections: int = 0
    throughput_per_second: float = 0.0

class SystemPerformanceMonitor:
    """Real-time system performance monitoring cho batch processing"""
    
    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.metrics_history: List[PerformanceMetrics] = []
        self.is_monitoring = False
        self.processed_items = 0
        self.start_time = None
        
    async def start_monitoring(self):
        """Start continuous performance monitoring"""
        if not PSUTIL_AVAILABLE:
            return
            
        self.is_monitoring = True
        self.start_time = time.time()
        
        async def monitor_loop():
            while self.is_monitoring:
                try:
                    metrics = self._collect_metrics()
                    self.metrics_history.append(metrics)
                    
                    # Keep only last 100 samples to prevent memory leak
                    if len(self.metrics_history) > 100:
                        self.metrics_history = self.metrics_history[-100:]
                    
                    await asyncio.sleep(self.sample_interval)
                except Exception as e:
                    await asyncio.sleep(self.sample_interval)
        
        # Start monitoring in background
        asyncio.create_task(monitor_loop())
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.is_monitoring = False
    
    def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        if not PSUTIL_AVAILABLE:
            return PerformanceMetrics()
        
        try:
            process = psutil.Process()
            system_memory = psutil.virtual_memory()
            
            # Calculate throughput
            elapsed = time.time() - self.start_time if self.start_time else 1
            throughput = self.processed_items / elapsed if elapsed > 0 else 0
            
            return PerformanceMetrics(
                cpu_percent=process.cpu_percent(),
                memory_percent=process.memory_percent(),
                memory_rss_mb=process.memory_info().rss / 1024 / 1024,
                memory_available_mb=system_memory.available / 1024 / 1024,
                active_threads=process.num_threads(),
                open_files=process.num_fds() if hasattr(process, 'num_fds') else 0,
                network_connections=len(process.connections()),
                throughput_per_second=throughput
            )
        except Exception as e:
            return PerformanceMetrics()
    
    def update_processed_count(self, count: int):
        """Update processed items count for throughput calculation"""
        self.processed_items = count
    
    
    def get_performance_summary(self) -> Dict[str, float]:
        """Get performance summary statistics"""
        if not self.metrics_history:
            return {}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 samples
        
        return {
            "avg_cpu_percent": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            "avg_memory_percent": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            "avg_memory_rss_mb": sum(m.memory_rss_mb for m in recent_metrics) / len(recent_metrics),
            "current_throughput": recent_metrics[-1].throughput_per_second if recent_metrics else 0,
            "peak_memory_mb": max(m.memory_rss_mb for m in self.metrics_history),
            "avg_threads": sum(m.active_threads for m in recent_metrics) / len(recent_metrics)
        }
    
    
    def should_reduce_concurrency(self) -> bool:
        """Determine if concurrency should be reduced"""
        if not self.metrics_history or len(self.metrics_history) < 3:
            return False
        
        # Check last 3 samples for sustained high load
        recent = self.metrics_history[-3:]
        high_load_count = sum(1 for m in recent if m.cpu_percent > 75 or m.memory_percent > 80)
        
        return high_load_count >= 2

# Global performance monitor instance
_performance_monitor = None

# Alias for backward compatibility
PerformanceMonitor = SystemPerformanceMonitor

def get_performance_monitor() -> SystemPerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = SystemPerformanceMonitor()
    return _performance_monitor
