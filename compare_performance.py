#!/usr/bin/env python3
"""
Script để so sánh performance giữa batch evaluator cũ và mới
"""
import time
from busqa.utils import estimate_batch_time, get_optimal_concurrency

def compare_performance():
    """So sánh performance estimates"""
    
    print("🏁 Performance Comparison: Old vs New Batch Evaluator")
    print("=" * 60)
    
    test_cases = [10, 20, 50, 100]
    
    for num_conv in test_cases:
        print(f"\n📊 {num_conv} conversations:")
        
        # Old method
        old_concurrency = 15  # Fixed concurrency
        old_time = estimate_batch_time(num_conv, old_concurrency)
        
        # New method
        new_concurrency = get_optimal_concurrency(num_conv)
        new_time = estimate_batch_time(num_conv, new_concurrency)
        
        improvement = ((old_time - new_time) / old_time) * 100
        
        print(f"  Old: {old_time:.1f}s (concurrency={old_concurrency})")
        print(f"  New: {new_time:.1f}s (concurrency={new_concurrency})")
        print(f"  🚀 Improvement: {improvement:.1f}% faster")
        
        # Tính số conv/s
        old_rate = num_conv / old_time
        new_rate = num_conv / new_time
        print(f"  📈 Rate: {old_rate:.1f} → {new_rate:.1f} conv/s")

if __name__ == "__main__":
    compare_performance()
