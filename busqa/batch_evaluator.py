import asyncio
import time
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import logging
import time
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

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
    max_concurrency: int = 3  
    adaptive_batching: bool = True
    initial_batch_size: int = 8
    progressive_multiplier: float = 1.5
    max_batch_size: int = 20
    llm_timeout: float = 60.0
    memory_cleanup_interval: int = 8
    progress_callback: Optional[callable] = None
    stream_callback: Optional[callable] = None
    use_high_performance_api: bool = True
    redis_url: Optional[str] = None
    api_rate_limit: int = 100

class HighSpeedBatchEvaluator:
    """Batch evaluator tối ưu cho conversations song song với multi-brand support"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.system_prompt_cache = {}
        self.processed_count = 0
        self.brand_stats = {}
        self.api_client = None
        
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
        """Main entry point"""
        
        self.processed_count = 0
        self.brand_stats = {}
        start_time = time.time()
        total_count = len(conversation_ids)
        
        perf_monitor = get_performance_monitor()
        await perf_monitor.start_monitoring()
        
        is_multi_brand = brand_resolver is not None
        mode_str = "multi-brand" if is_multi_brand else "single-brand"
        
        memory_pressure = get_memory_pressure()
        if memory_pressure in ["high", "critical"]:
            original_concurrency = self.config.max_concurrency
            self.config.max_concurrency = max(5, self.config.max_concurrency // 2)
        
        if not is_multi_brand:
            system_prompt_key = self._get_system_prompt_key(brand_policy, brand_prompt_text)
            if system_prompt_key not in self.system_prompt_cache:
                self.system_prompt_cache[system_prompt_key] = build_system_prompt_unified(
                    rubrics_cfg, brand_policy, brand_prompt_text
                )
        
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
        
        
        try:
            if self.api_client:
                async with self.api_client:
                    all_results = await self._process_all_conversations_async(
                        conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                        llm_api_key, llm_model, temperature, llm_base_url,
                        apply_diagnostics, diagnostics_cfg, brand_resolver
                    )
            else:
                all_results = await self._process_all_conversations_async(
                    conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                    llm_api_key, llm_model, temperature, llm_base_url,
                    apply_diagnostics, diagnostics_cfg, brand_resolver
                )
        finally:
            pass
        
        elapsed = time.time() - start_time
        success_count = len([r for r in all_results if "error" not in r])
        
        perf_monitor.stop_monitoring()
        perf_summary = perf_monitor.get_performance_summary()
        
        
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
        """Progressive batching"""
        
        total_count = len(conversation_ids)
        all_results = []
        
        if self.config.adaptive_batching and total_count > 15:
            return await self._process_progressive_batches(
                conversation_ids, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
        else:
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
        """Progressive batching"""
        
        all_results = []
        remaining_ids = conversation_ids.copy()
        current_batch_size = self.config.initial_batch_size
        batch_num = 1
        
        
        while remaining_ids:
            batch_ids = remaining_ids[:current_batch_size]
            remaining_ids = remaining_ids[current_batch_size:]
            
            batch_start_time = time.time()
            
            semaphore = asyncio.Semaphore(min(len(batch_ids), self.config.max_concurrency))
            batch_results = await self._process_batch_with_semaphore(
                batch_ids, semaphore, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
            
            batch_elapsed = time.time() - batch_start_time
            batch_throughput = len(batch_ids) / batch_elapsed if batch_elapsed > 0 else 0
            successful_in_batch = len([r for r in batch_results if "error" not in r])
            
            
            all_results.extend(batch_results)
            
            if remaining_ids:
                if batch_throughput > 1.0 and current_batch_size < self.config.max_batch_size:
                    new_batch_size = min(
                        int(current_batch_size * self.config.progressive_multiplier),
                        self.config.max_batch_size,
                        len(remaining_ids)
                    )
                    if new_batch_size > current_batch_size:
                        current_batch_size = new_batch_size
                elif batch_throughput < 0.5 and current_batch_size > self.config.initial_batch_size:
                    new_batch_size = max(
                        int(current_batch_size / self.config.progressive_multiplier),
                        self.config.initial_batch_size
                    )
                    current_batch_size = new_batch_size
                
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
        """Process a single batch with semaphore"""
        
        total_count = getattr(self, 'total_conversations', len(batch_ids))

        async def process_single(conv_id: str) -> Dict[str, Any]:
            async with semaphore:
                
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
                    
                    self.processed_count += 1
                    
                    perf_monitor = get_performance_monitor()
                    perf_monitor.update_processed_count(self.processed_count)
                    
                    if self.config.progress_callback:
                        progress = self.processed_count / getattr(self, 'total_conversations', len(batch_ids))
                        self.config.progress_callback(progress, self.processed_count, getattr(self, 'total_conversations', len(batch_ids)))
                    
                    # streaming result
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    
                    return result
                    
                except asyncio.TimeoutError:
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
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
        
        # process batch conversations
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
        
        # global semaphore for all conversations
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        total_count = len(conversation_ids)
        self.total_conversations = total_count  # Store for progress calculation

        async def process_single(conv_id: str) -> Dict[str, Any]:
            async with semaphore:
                # process conversation 
                
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
                    
                    # update progress
                    self.processed_count += 1
                    
                    # update performance monitor
                    perf_monitor = get_performance_monitor()
                    perf_monitor.update_processed_count(self.processed_count)
                    
                    if self.config.progress_callback:
                        progress = self.processed_count / total_count
                        self.config.progress_callback(progress, self.processed_count, total_count)
                    
                    # streaming result
                    if self.config.stream_callback:
                        self.config.stream_callback(result)

                    # log concurrent activity every 10 conversations
                    # Cleanup memory định kỳ và adaptive concurrency
                    if self.processed_count % self.config.memory_cleanup_interval == 0:
                        collected = cleanup_memory()
                        mem_info = monitor_memory_usage()
                        
                        # adaptive concurrency based on system pressure
                        perf_monitor = get_performance_monitor()
                        if perf_monitor.should_reduce_concurrency():
                            # Dynamic adjustment would require more complex implementation
                            pass
                    
                    return result
                    
                except asyncio.TimeoutError:
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
                    self.processed_count += 1
                    result = {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    if self.config.stream_callback:
                        self.config.stream_callback(result)
                    return result
        
        # Execute all conversations concurrently
        tasks = [process_single(conv_id) for conv_id in conversation_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)
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
                    # Re-raise để báo lỗi cho conversation này
                    raise ValueError(f"Brand resolution failed: {e}")
            
            messages = normalize_messages(raw_data)
            
            if not messages:
                raise ValueError("Không có messages")
            
            # Build transcript và metrics song song
            transcript, metrics = await asyncio.to_thread(
                self._compute_metrics_and_transcript, messages, brand_policy, brand_prompt_text
            )
            
            # Diagnostics nếu cần
            if apply_diagnostics and diagnostics_cfg:
                # These are now internally threaded, but we run them in a thread from asyncio's perspective
                # to avoid blocking the event loop at all.
                or_hits, rc_hits = await asyncio.gather(
                    asyncio.to_thread(detect_operational_readiness, messages, brand_policy, brand_prompt_text),
                    asyncio.to_thread(detect_risk_compliance, messages, brand_policy)
                )
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
            
            # Run final CPU-bound coercion in a thread
            result = await asyncio.to_thread(
                coerce_llm_json_unified,
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
            return {
                "conversation_id": conversation_id,
                "error": error_msg,
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def _compute_metrics_and_transcript(self, messages, brand_policy, brand_prompt_text):
        """Helper function to run synchronous metric computations in a thread."""
        transcript = build_transcript(messages)
        metrics = {}
        
        latency_metrics = compute_latency_metrics(messages)
        additional_metrics = compute_additional_metrics(messages, brand_policy, brand_prompt_text)
        policy_violations = compute_policy_violations_count(messages, brand_policy)
        
        metrics.update(latency_metrics)
        metrics.update(additional_metrics)
        metrics["policy_violations"] = policy_violations
        
        return transcript, metrics

    def _get_system_prompt_key(self, brand_policy: BrandPolicy, brand_prompt_text: str) -> str:
        """Tạo cache key cho system prompt - sử dụng abs() để tránh số âm"""
        policy_hash = abs(hash(str(brand_policy.__dict__))) if brand_policy else 0
        text_hash = abs(hash(brand_prompt_text)) if brand_prompt_text else 0
        return f"prompt_{policy_hash}_{text_hash}"

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
    max_concurrency: int = 30,  
    progress_callback: callable = None,
    stream_callback: callable = None,   
    brand_resolver: BrandResolver = None,
    use_high_performance_api: bool = True,  
    redis_url: str = None,  
    api_rate_limit: int = 200,  
    use_progressive_batching: bool = True  
) -> List[Dict[str, Any]]:
    """High-level API cho batch evaluation nhanh"""
    
    config = BatchConfig(
        max_concurrency=max_concurrency,
        adaptive_batching=use_progressive_batching,  
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


