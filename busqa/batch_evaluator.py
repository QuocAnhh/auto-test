import asyncio
import time
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import logging
import time
from datetime import datetime

# Setup detailed performance logging
logger = logging.getLogger(__name__)

# Create performance logger specifically for bottleneck analysis
perf_logger = logging.getLogger('performance_debug')
perf_handler = logging.StreamHandler()
perf_formatter = logging.Formatter('🔍 [PERF] %(asctime)s - %(message)s')
perf_handler.setFormatter(perf_formatter)
perf_logger.addHandler(perf_handler)
perf_logger.setLevel(logging.INFO)

from .api_client import fetch_messages
from .high_performance_api import HighPerformanceAPIClient, APIClientConfig
from .normalize import normalize_messages, build_transcript
from .metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
from .brand_specs import BrandPolicy
from .prompting import build_system_prompt_unified, build_user_instruction
from .llm_client import call_llm, call_llm_async
from .evaluator import coerce_llm_json_unified
from .utils import cleanup_memory, monitor_memory_usage, get_memory_pressure
from .performance_monitor import get_performance_monitor
from .diagnostics import detect_operational_readiness, detect_risk_compliance
from .parsers import extract_bot_id
from .brand_resolver import BrandResolver

logger = logging.getLogger(__name__)



@dataclass
class BatchConfig:
    """Config cho batch evaluation tối ưu với progressive batching"""
    max_concurrency: int = 30  # Giảm xuống để tránh convoy effect
    adaptive_batching: bool = True  # Enable adaptive progressive batching
    initial_batch_size: int = 8    # Start với batch nhỏ để test latency
    progressive_multiplier: float = 1.5  # Tăng batch size dần dần
    max_batch_size: int = 20       # Max batch size để control memory
    llm_timeout: float = 35.0      # Giảm timeout để fail fast
    memory_cleanup_interval: int = 8   # Cleanup thường xuyên hơn
    progress_callback: Optional[callable] = None
    stream_callback: Optional[callable] = None  # Callback để stream kết quả
    use_high_performance_api: bool = True  # Enable connection pooling
    redis_url: Optional[str] = None  # Redis URL for caching
    api_rate_limit: int = 100  # API calls per second

class HighSpeedBatchEvaluator:
    """Batch evaluator tối ưu cho conversations song song với multi-brand support"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.system_prompt_cache = {}  # Cache system prompts theo brand
        self.processed_count = 0
        self.brand_stats = {}  # Thống kê theo brand
        self.api_client = None  # High-performance API client
        
    async def evaluate_batch(
        self, 
        conversation_ids: List[str],
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy = None,
        brand_prompt_text: str = None,
        llm_api_key: str = None,
        llm_model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        llm_base_url: str = None,
        apply_diagnostics: bool = True,
        diagnostics_cfg: dict = None,
        brand_resolver: BrandResolver = None
    ) -> List[Dict[str, Any]]:
        """Main entry point - chấm điểm batch với tốc độ cao, hỗ trợ multi-brand"""
        
        self.processed_count = 0
        self.brand_stats = {}
        start_time = time.time()
        total_count = len(conversation_ids)
        
        # Start performance monitoring
        perf_monitor = get_performance_monitor()
        await perf_monitor.start_monitoring()
        
        # Determine mode
        is_multi_brand = brand_resolver is not None
        mode_str = "multi-brand" if is_multi_brand else "single-brand"
        
        logger.info(f"🚀 Bắt đầu chấm {total_count} conv ({mode_str}) với concurrency={self.config.max_concurrency}")
        
        # Adaptive concurrency based on system resources
        memory_pressure = get_memory_pressure()
        if memory_pressure in ["high", "critical"]:
            original_concurrency = self.config.max_concurrency
            self.config.max_concurrency = max(5, self.config.max_concurrency // 2)
            logger.warning(f"⚠️ Giảm concurrency từ {original_concurrency} xuống {self.config.max_concurrency} do memory pressure: {memory_pressure}")
        
        # Pre-build system prompt để cache (chỉ cho single-brand mode)
        if not is_multi_brand:
            system_prompt_key = self._get_system_prompt_key(brand_policy, brand_prompt_text)
            if system_prompt_key not in self.system_prompt_cache:
                self.system_prompt_cache[system_prompt_key] = build_system_prompt_unified(
                    rubrics_cfg, brand_policy, brand_prompt_text
                )
        
        # Initialize high-performance API client if enabled
        if self.config.use_high_performance_api:
            api_config = APIClientConfig(
                max_connections=min(self.config.max_concurrency * 2, 200),
                rate_limit_per_second=self.config.api_rate_limit,
                enable_caching=self.config.redis_url is not None
            )
            self.api_client = HighPerformanceAPIClient(
                base_url=base_url,
                config=api_config,
                redis_url=self.config.redis_url
            )
        
        # Process tất cả conversations song song với global concurrency control
        logger.info(f"Processing {total_count} conversations với max_concurrency={self.config.max_concurrency}")
        if self.config.use_high_performance_api:
            logger.info("🚀 Using high-performance API client with connection pooling")
        
        try:
            all_results = await self._process_all_conversations_async(
                conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
        finally:
            # Cleanup API client
            if self.api_client:
                await self.api_client.__aexit__(None, None, None)
        
        elapsed = time.time() - start_time
        success_count = len([r for r in all_results if "error" not in r])
        
        # Stop performance monitoring and get summary
        perf_monitor.stop_monitoring()
        perf_summary = perf_monitor.get_performance_summary()
        
        logger.info(f"✅ Hoàn thành {success_count}/{total_count} trong {elapsed:.1f}s")
        logger.info(f"Tốc độ: {success_count/elapsed:.1f} conv/s")
        
        # Log performance summary
        if perf_summary:
            logger.info(f"📊 Performance: CPU={perf_summary.get('avg_cpu_percent', 0):.1f}%, "
                       f"Memory={perf_summary.get('avg_memory_rss_mb', 0):.1f}MB, "
                       f"Peak Memory={perf_summary.get('peak_memory_mb', 0):.1f}MB, "
                       f"Avg Threads={perf_summary.get('avg_threads', 0):.0f}")
        
        # Log brand usage stats cho multi-brand mode
        if is_multi_brand and self.brand_stats:
            brand_summary = ", ".join([f"{brand}={count}" for brand, count in self.brand_stats.items()])
            logger.info(f"Brand usage: {brand_summary}")
        
        return all_results
    
    async def _process_all_conversations_async(
        self,
        conversation_ids: List[str],
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str,
        temperature: float,
        llm_base_url: str,
        apply_diagnostics: bool,
        diagnostics_cfg: dict,
        brand_resolver: BrandResolver = None
    ) -> List[Dict[str, Any]]:
        """Progressive batching để tránh convoy effect và resource starvation"""
        
        total_count = len(conversation_ids)
        all_results = []
        
        if self.config.adaptive_batching and total_count > 15:
            # Use progressive batching for large batches
            logger.info(f"🔄 Using PROGRESSIVE BATCHING for {total_count} conversations")
            return await self._process_progressive_batches(
                conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
        else:
            # Fallback to original method for small batches
            logger.info(f"🔄 Using STANDARD BATCHING for {total_count} conversations")
            return await self._process_standard_batch(
                conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
    
    async def _process_progressive_batches(
        self,
        conversation_ids: List[str],
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str,
        temperature: float,
        llm_base_url: str,
        apply_diagnostics: bool,
        diagnostics_cfg: dict,
        brand_resolver: BrandResolver = None
    ) -> List[Dict[str, Any]]:
        """Progressive batching: Start nhỏ, tăng dần based on performance"""
        
        all_results = []
        remaining_ids = conversation_ids.copy()
        current_batch_size = self.config.initial_batch_size
        batch_num = 1
        
        perf_logger.info(f"🚀 Starting progressive batching: initial_size={current_batch_size}, max_size={self.config.max_batch_size}")
        
        while remaining_ids:
            # Get next batch
            batch_ids = remaining_ids[:current_batch_size]
            remaining_ids = remaining_ids[current_batch_size:]
            
            batch_start_time = time.time()
            perf_logger.info(f"📦 Batch {batch_num}: processing {len(batch_ids)} conversations (batch_size={current_batch_size})")
            
            # Process batch with controlled concurrency
            semaphore = asyncio.Semaphore(min(len(batch_ids), self.config.max_concurrency))
            batch_results = await self._process_batch_with_semaphore(
                batch_ids, semaphore, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
            
            batch_elapsed = time.time() - batch_start_time
            batch_throughput = len(batch_ids) / batch_elapsed if batch_elapsed > 0 else 0
            successful_in_batch = len([r for r in batch_results if "error" not in r])
            
            perf_logger.info(f"✅ Batch {batch_num} completed: {successful_in_batch}/{len(batch_ids)} successful in {batch_elapsed:.1f}s (throughput: {batch_throughput:.1f} conv/s)")
            
            all_results.extend(batch_results)
            
            # Adaptive batch size adjustment based on performance
            if remaining_ids:  # Only adjust if more batches to come
                if batch_throughput > 1.0 and current_batch_size < self.config.max_batch_size:
                    # Performance is good, increase batch size
                    new_batch_size = min(
                        int(current_batch_size * self.config.progressive_multiplier),
                        self.config.max_batch_size,
                        len(remaining_ids)  # Don't exceed remaining
                    )
                    if new_batch_size > current_batch_size:
                        perf_logger.info(f"📈 Increasing batch size: {current_batch_size} → {new_batch_size} (good performance)")
                        current_batch_size = new_batch_size
                elif batch_throughput < 0.5 and current_batch_size > self.config.initial_batch_size:
                    # Performance is poor, decrease batch size
                    new_batch_size = max(
                        int(current_batch_size / self.config.progressive_multiplier),
                        self.config.initial_batch_size
                    )
                    perf_logger.info(f"📉 Decreasing batch size: {current_batch_size} → {new_batch_size} (poor performance)")
                    current_batch_size = new_batch_size
                
                # Small delay between batches to prevent resource exhaustion
                if len(remaining_ids) > 0:
                    await asyncio.sleep(0.5)
            
            batch_num += 1
        
        return all_results
    
    async def _process_batch_with_semaphore(
        self,
        batch_ids: List[str],
        semaphore: asyncio.Semaphore,
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str,
        temperature: float,
        llm_base_url: str,
        apply_diagnostics: bool,
        diagnostics_cfg: dict,
        brand_resolver: BrandResolver = None
    ) -> List[Dict[str, Any]]:
        """Process a single batch with semaphore control"""
        
        total_count = len(self.processed_count) if hasattr(self, 'total_conversations') else len(batch_ids)

        async def process_single(conv_id: str) -> Dict[str, Any]:
            async with semaphore:
                # Log concurrency info
                active_tasks = semaphore._bound_value - semaphore._value
                logger.debug(f"Conv {conv_id}: active_tasks={active_tasks}/{semaphore._bound_value}")
                
                try:
                    start_time = time.time()
                    result = await asyncio.wait_for(
                        self._evaluate_single_fast_async(
                            conv_id, base_url, rubrics_cfg, brand_policy,
                            brand_prompt_text, llm_api_key, llm_model,
                            temperature, llm_base_url, apply_diagnostics, diagnostics_cfg,
                            brand_resolver
                        ),
                        timeout=self.config.llm_timeout
                    )
                    elapsed = time.time() - start_time
                    logger.debug(f"Conv {conv_id}: completed in {elapsed:.1f}s")
                    
                    # Update progress
                    self.processed_count += 1
                    
                    # Update performance monitor
                    perf_monitor = get_performance_monitor()
                    perf_monitor.update_processed_count(self.processed_count)
                    
                    if self.config.progress_callback:
                        progress = self.processed_count / getattr(self, 'total_conversations', len(batch_ids))
                        self.config.progress_callback(progress, self.processed_count, getattr(self, 'total_conversations', len(batch_ids)))
                    
                    # STREAMING: Gọi callback ngay khi có kết quả
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error(f"Timeout cho conv {conv_id}")
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": f"Timeout after {self.config.llm_timeout}s",
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
                except Exception as e:
                    logger.error(f"Error processing {conv_id}: {e}")
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
        
        # Process batch conversations
        tasks = [process_single(conv_id) for conv_id in batch_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return results
    
    async def _process_standard_batch(
        self,
        conversation_ids: List[str],
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str,
        temperature: float,
        llm_base_url: str,
        apply_diagnostics: bool,
        diagnostics_cfg: dict,
        brand_resolver: BrandResolver = None
    ) -> List[Dict[str, Any]]:
        """Fallback standard batch processing for small batches"""
        
        # Global semaphore cho tất cả conversations
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        total_count = len(conversation_ids)
        self.total_conversations = total_count  # Store for progress calculation

        async def process_single(conv_id: str) -> Dict[str, Any]:
            async with semaphore:
                # Log concurrency info
                active_tasks = self.config.max_concurrency - semaphore._value
                logger.debug(f"Conv {conv_id}: active_tasks={active_tasks}/{self.config.max_concurrency}")
                
                try:
                    start_time = time.time()
                    result = await asyncio.wait_for(
                        self._evaluate_single_fast_async(
                            conv_id, base_url, rubrics_cfg, brand_policy,
                            brand_prompt_text, llm_api_key, llm_model,
                            temperature, llm_base_url, apply_diagnostics, diagnostics_cfg,
                            brand_resolver
                        ),
                        timeout=self.config.llm_timeout
                    )
                    elapsed = time.time() - start_time
                    logger.debug(f"Conv {conv_id}: completed in {elapsed:.1f}s")
                    
                    # Update progress
                    self.processed_count += 1
                    
                    # Update performance monitor
                    perf_monitor = get_performance_monitor()
                    perf_monitor.update_processed_count(self.processed_count)
                    
                    if self.config.progress_callback:
                        progress = self.processed_count / total_count
                        self.config.progress_callback(progress, self.processed_count, total_count)
                    
                    # STREAMING: Gọi callback ngay khi có kết quả
                    if self.config.stream_callback:
                        self.config.stream_callback(result)

                    # Log concurrent activity mỗi 10 conversations
                    if self.processed_count % 10 == 0:
                        active_tasks = self.config.max_concurrency - semaphore._value
                        logger.info(f"⚡ Processed: {self.processed_count}/{total_count}, active_concurrent_tasks: {active_tasks}/{self.config.max_concurrency}")
                    
                    # Cleanup memory định kỳ và adaptive concurrency
                    if self.processed_count % self.config.memory_cleanup_interval == 0:
                        collected = cleanup_memory()
                        mem_info = monitor_memory_usage()
                        
                        # Log memory info
                        logger.info(f"🧹 Memory: {mem_info['rss_mb']:.1f}MB RSS, "
                                  f"System: {mem_info.get('system_memory_percent', 0):.1f}%, "
                                  f"GC collected: {collected}, processed: {self.processed_count}/{total_count}")
                        
                        # Adaptive concurrency based on system pressure
                        perf_monitor = get_performance_monitor()
                        if perf_monitor.should_reduce_concurrency():
                            # Dynamic adjustment would require more complex implementation
                            logger.warning("⚠️ System under pressure - consider reducing concurrency for next batch")
                    
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error(f"Timeout cho conv {conv_id}")
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": f"Timeout after {self.config.llm_timeout}s",
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
                except Exception as e:
                    logger.error(f"Error processing {conv_id}: {e}")
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
        
        # Chạy TẤT CẢ conversations cùng lúc với concurrency control
        logger.info(f"🚀 Starting {total_count} conversations với RÉALLY max_concurrency={self.config.max_concurrency}")
        logger.info(f"📊 Semaphore limit: {self.config.max_concurrency}, chunk_size bị loại bỏ!")
        
        tasks = [process_single(conv_id) for conv_id in conversation_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        logger.info(f"✅ Completed processing {len(results)} conversations")
        return results
    
    async def _evaluate_single_fast_async(
        self,
        conversation_id: str,
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str,
        temperature: float,
        llm_base_url: str,
        apply_diagnostics: bool,
        diagnostics_cfg: dict,
        brand_resolver: BrandResolver = None
    ) -> Dict[str, Any]:
        """Async version of evaluate single conversation - TRUE concurrent LLM calls"""
        
        try:
            # Timing debug
            start_time = time.time()
            
            # Fetch data với high-performance client nếu có
            if self.api_client:
                # Use high-performance API client
                api_results = await self.api_client.fetch_conversation_batch([conversation_id])
                api_result = api_results[0]
                if api_result.get("status") == "success":
                    raw_data = api_result["data"]
                else:
                    raise ValueError(f"API fetch failed: {api_result.get('error', 'Unknown error')}")
            else:
                # Fallback to original method
                raw_data = await asyncio.to_thread(fetch_messages, base_url, conversation_id)
            
            fetch_time = time.time() - start_time
            
            # Resolve brand nếu có brand_resolver
            if brand_resolver:
                bot_id = extract_bot_id(raw_data)
                try:
                    brand_prompt_text, brand_policy = brand_resolver.resolve_by_bot_id(bot_id)
                    
                    # Track brand stats
                    try:
                        resolved_brand_id, _ = brand_resolver._map.resolve(bot_id)
                        self.brand_stats[resolved_brand_id] = self.brand_stats.get(resolved_brand_id, 0) + 1
                    except:
                        pass  # Không để stats làm crash
                        
                except Exception as e:
                    logger.warning(f"Failed to resolve brand for conv {conversation_id} (bot_id={bot_id}): {e}")
                    # Re-raise để báo lỗi cho conversation này
                    raise ValueError(f"Brand resolution failed: {e}")
            
            messages = normalize_messages(raw_data)
            
            if not messages:
                raise ValueError("Không có messages")
            
            # Build transcript và metrics song song
            transcript = build_transcript(messages)
            metrics = {}
            
            # Compute metrics đồng thời (không block)
            latency_metrics = compute_latency_metrics(messages)
            additional_metrics = compute_additional_metrics(messages, brand_policy, brand_prompt_text)
            policy_violations = compute_policy_violations_count(messages, brand_policy)
            
            metrics.update(latency_metrics)
            metrics.update(additional_metrics)
            metrics["policy_violations"] = policy_violations
            
            # Diagnostics nếu cần
            if apply_diagnostics and diagnostics_cfg:
                or_hits = detect_operational_readiness(messages, brand_policy, brand_prompt_text)
                rc_hits = detect_risk_compliance(messages, brand_policy)
                diagnostics_hits = {
                    "operational_readiness": or_hits,
                    "risk_compliance": rc_hits
                }
                metrics["diagnostics"] = diagnostics_hits
            
            # Filter metrics for LLM
            metrics_for_llm = filter_non_null_metrics(metrics)
            
            # Get cached system prompt
            system_prompt_key = self._get_system_prompt_key(brand_policy, brand_prompt_text)
            if system_prompt_key not in self.system_prompt_cache:
                # Build system prompt if not cached
                self.system_prompt_cache[system_prompt_key] = build_system_prompt_unified(
                    rubrics_cfg, brand_policy, brand_prompt_text
                )
            system_prompt = self.system_prompt_cache[system_prompt_key]
            
            # Build user prompt
            user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
            
            # Call LLM với ASYNC - THIS IS THE KEY FIX!
            llm_start = time.time()
            llm_response = await call_llm_async(
                api_key=llm_api_key,
                model=llm_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                base_url=llm_base_url,
                temperature=temperature
            )
            llm_time = time.time() - llm_start
            
            # Process result
            diagnostics_hits = metrics.get("diagnostics", {}) if apply_diagnostics else {}
            
            result = coerce_llm_json_unified(
                llm_response,
                rubrics_cfg=rubrics_cfg,
                brand_policy=brand_policy,
                messages=messages,
                transcript=transcript,
                metrics=metrics,
                diagnostics_cfg=diagnostics_cfg if apply_diagnostics else None,
                diagnostics_hits=diagnostics_hits
            )
            
            total_time = time.time() - start_time
            logger.debug(f"Conv {conversation_id}: fetch={fetch_time:.1f}s, llm={llm_time:.1f}s, total={total_time:.1f}s")
            
            # Extract brand_id for reporting
            brand_id = "unknown"
            if brand_resolver:
                try:
                    bot_id = extract_bot_id(raw_data)
                    resolved_brand_id, _ = brand_resolver._map.resolve(bot_id)
                    brand_id = resolved_brand_id
                except:
                    pass  # Keep default "unknown"
            
            # Return minimal result để tiết kiệm memory
            return {
                "conversation_id": conversation_id,
                "brand_id": brand_id,  # Add brand_id for PDF/CSV reporting
                "result": result.model_dump(),
                "metrics": metrics,
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
                # Bỏ transcript_preview để tiết kiệm memory
            }
            
        except Exception as e:
            # Better error logging with traceback
            error_msg = f"{str(e)}"
            logger.error(f"Error evaluating {conversation_id}: {error_msg}")
            logger.debug(f"Full traceback for {conversation_id}: {traceback.format_exc()}")
            return {
                "conversation_id": conversation_id,
                "error": error_msg,
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def _get_system_prompt_key(self, brand_policy: BrandPolicy, brand_prompt_text: str) -> str:
        """Tạo cache key cho system prompt - sử dụng abs() để tránh số âm"""
        policy_hash = abs(hash(str(brand_policy.__dict__))) if brand_policy else 0
        text_hash = abs(hash(brand_prompt_text)) if brand_prompt_text else 0
        return f"prompt_{policy_hash}_{text_hash}"

# Convenience function cho CLI
async def evaluate_conversations_high_speed(
    conversation_ids: List[str],
    base_url: str,
    rubrics_cfg: dict,
    brand_policy: BrandPolicy = None,
    brand_prompt_text: str = None,
    llm_api_key: str = None,
    llm_model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    llm_base_url: str = None,
    apply_diagnostics: bool = True,
    diagnostics_cfg: dict = None,
    max_concurrency: int = 30,  # Giảm xuống 30 để work with progressive batching
    progress_callback: callable = None,
    stream_callback: callable = None, # Thêm stream_callback
    brand_resolver: BrandResolver = None,
    use_high_performance_api: bool = True,  # Enable connection pooling by default
    redis_url: str = None,  # Redis URL for caching
    api_rate_limit: int = 200,  # API rate limit
    use_progressive_batching: bool = True  # Enable progressive batching to fix convoy effect
) -> List[Dict[str, Any]]:
    """High-level API cho batch evaluation nhanh"""
    
    config = BatchConfig(
        max_concurrency=max_concurrency,
        adaptive_batching=use_progressive_batching,  # Use parameter to control progressive batching
        progress_callback=progress_callback,
        stream_callback=stream_callback,
        use_high_performance_api=use_high_performance_api,
        redis_url=redis_url,
        api_rate_limit=api_rate_limit
    )
    
    evaluator = HighSpeedBatchEvaluator(config)
    
    return await evaluator.evaluate_batch(
        conversation_ids, base_url, rubrics_cfg, brand_policy,
        brand_prompt_text, llm_api_key, llm_model, temperature,
        llm_base_url, apply_diagnostics, diagnostics_cfg, brand_resolver
    )


