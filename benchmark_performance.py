#!/usr/bin/env python3
"""
Performance benchmark tool cho Bus QA LLM Project
"""
import asyncio
import time
import sys
import os
from pathlib import Path
import argparse
import logging
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from busqa.batch_evaluator import HighSpeedBatchEvaluator, BatchConfig
from busqa.prompt_loader import load_unified_rubrics
from busqa.performance_monitor import get_performance_monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def benchmark_batch_processing(
    conversation_ids: List[str],
    base_url: str,
    llm_api_key: str,
    concurrency_levels: List[int] = [5, 10, 15, 20, 25, 30],
    redis_url: str = None
):
    """Benchmark batch processing với các mức concurrency khác nhau"""
    
    # Load rubrics
    rubrics_cfg = load_unified_rubrics()
    
    results = []
    
    for concurrency in concurrency_levels:
        logger.info(f"\n🚀 Testing concurrency level: {concurrency}")
        
        # Setup config
        config = BatchConfig(
            max_concurrency=concurrency,
            use_high_performance_api=True,
            redis_url=redis_url,
            api_rate_limit=concurrency * 5  # Scale API rate limit
        )
        
        evaluator = HighSpeedBatchEvaluator(config)
        
        start_time = time.time()
        
        try:
            batch_results = await evaluator.evaluate_batch(
                conversation_ids=conversation_ids,
                base_url=base_url,
                rubrics_cfg=rubrics_cfg,
                llm_api_key=llm_api_key,
                llm_model="gemini-2.5-flash",
                temperature=0.2
            )
            
            elapsed = time.time() - start_time
            success_count = len([r for r in batch_results if "error" not in r])
            throughput = success_count / elapsed
            
            # Get performance metrics
            perf_monitor = get_performance_monitor()
            perf_summary = perf_monitor.get_performance_summary()
            
            result = {
                "concurrency": concurrency,
                "total_conversations": len(conversation_ids),
                "successful_conversations": success_count,
                "elapsed_time": elapsed,
                "throughput_per_second": throughput,
                "avg_cpu_percent": perf_summary.get("avg_cpu_percent", 0),
                "peak_memory_mb": perf_summary.get("peak_memory_mb", 0),
                "avg_memory_mb": perf_summary.get("avg_memory_rss_mb", 0)
            }
            
            results.append(result)
            
            logger.info(f"✅ Concurrency {concurrency}: {throughput:.1f} conv/s, "
                       f"Memory: {result['peak_memory_mb']:.0f}MB peak, "
                       f"CPU: {result['avg_cpu_percent']:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error at concurrency {concurrency}: {e}")
            results.append({
                "concurrency": concurrency,
                "error": str(e)
            })
        
        # Cool down between tests
        await asyncio.sleep(2)
    
    return results

def print_benchmark_results(results: List[dict]):
    """Print formatted benchmark results"""
    print(f"\n{'='*80}")
    print("🎯 PERFORMANCE BENCHMARK RESULTS")
    print(f"{'='*80}")
    
    print(f"{'Concurrency':<12} {'Throughput':<12} {'Memory(MB)':<12} {'CPU(%)':<8} {'Status'}")
    print(f"{'-'*60}")
    
    best_throughput = 0
    best_config = None
    
    for result in results:
        if "error" in result:
            print(f"{result['concurrency']:<12} {'ERROR':<12} {'-':<12} {'-':<8} {result['error'][:20]}")
        else:
            throughput = result['throughput_per_second']
            memory = result['peak_memory_mb']
            cpu = result['avg_cpu_percent']
            
            print(f"{result['concurrency']:<12} {throughput:<12.1f} {memory:<12.0f} {cpu:<8.1f} {'✅' if throughput > 0 else '❌'}")
            
            if throughput > best_throughput:
                best_throughput = throughput
                best_config = result
    
    if best_config:
        print(f"\n🏆 OPTIMAL CONFIGURATION:")
        print(f"   Concurrency: {best_config['concurrency']}")
        print(f"   Throughput: {best_config['throughput_per_second']:.1f} conversations/second")
        print(f"   Peak Memory: {best_config['peak_memory_mb']:.0f} MB")
        print(f"   Avg CPU: {best_config['avg_cpu_percent']:.1f}%")

async def main():
    parser = argparse.ArgumentParser(description="Bus QA Performance Benchmark")
    parser.add_argument("--base-url", required=True, help="API base URL")
    parser.add_argument("--llm-api-key", required=True, help="LLM API key")
    parser.add_argument("--conversation-ids", required=True, help="Comma-separated conversation IDs")
    parser.add_argument("--redis-url", help="Redis URL for caching (optional)")
    parser.add_argument("--max-concurrency", type=int, default=30, help="Maximum concurrency to test")
    
    args = parser.parse_args()
    
    # Parse conversation IDs
    conversation_ids = [id.strip() for id in args.conversation_ids.split(",")]
    
    # Generate concurrency levels to test
    max_concurrency = min(args.max_concurrency, 50)  # Cap at 50
    concurrency_levels = [5, 10, 15, 20, 25]
    if max_concurrency > 25:
        concurrency_levels.extend(range(30, max_concurrency + 1, 5))
    
    logger.info(f"🎯 Starting benchmark với {len(conversation_ids)} conversations")
    logger.info(f"🎯 Testing concurrency levels: {concurrency_levels}")
    
    # Run benchmark
    results = await benchmark_batch_processing(
        conversation_ids=conversation_ids,
        base_url=args.base_url,
        llm_api_key=args.llm_api_key,
        concurrency_levels=concurrency_levels,
        redis_url=args.redis_url
    )
    
    # Print results
    print_benchmark_results(results)

if __name__ == "__main__":
    asyncio.run(main())
