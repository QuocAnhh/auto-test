import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from .api_client import fetch_messages
from .normalize import normalize_messages, build_transcript
from .metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
from .brand_specs import BrandPolicy
from .prompting import build_system_prompt_unified, build_user_instruction
from .llm_client import call_llm
from .evaluator import coerce_llm_json_unified
from .utils import cleanup_memory, monitor_memory_usage
from .diagnostics import detect_operational_readiness, detect_risk_compliance
from .parsers import extract_bot_id
from .brand_resolver import BrandResolver

logger = logging.getLogger(__name__)

@dataclass
class BatchConfig:
    """Config cho batch evaluation tối ưu 50 conv"""
    max_concurrency: int = 15  # Giảm xuống 15 để ổn định hơn
    chunk_size: int = 10       # Chia nhỏ để control memory
    llm_timeout: float = 60.0  # Tăng timeout lên 60s
    memory_cleanup_interval: int = 15  # Cleanup sau 15 conv
    progress_callback: Optional[callable] = None

class HighSpeedBatchEvaluator:
    """Batch evaluator tối ưu cho 50 conversations song song với multi-brand support"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.system_prompt_cache = {}  # Cache system prompts theo brand
        self.processed_count = 0
        self.brand_stats = {}  # Thống kê theo brand
        
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
        
        start_time = time.time()
        total_count = len(conversation_ids)
        
        # Determine mode
        is_multi_brand = brand_resolver is not None
        mode_str = "multi-brand" if is_multi_brand else "single-brand"
        
        logger.info(f"🚀 Bắt đầu chấm {total_count} conv ({mode_str}) với concurrency={self.config.max_concurrency}")
        
        # Pre-build system prompt để cache (chỉ cho single-brand mode)
        if not is_multi_brand:
            system_prompt_key = self._get_system_prompt_key(brand_policy, brand_prompt_text)
            if system_prompt_key not in self.system_prompt_cache:
                self.system_prompt_cache[system_prompt_key] = build_system_prompt_unified(
                    rubrics_cfg, brand_policy, brand_prompt_text
                )
        
        # Chia nhỏ conversations thành chunks để tránh overload
        chunks = [conversation_ids[i:i + self.config.chunk_size] 
                 for i in range(0, len(conversation_ids), self.config.chunk_size)]
        
        all_results = []
        
        # Process từng chunk
        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} conv)")
            
            chunk_results = await self._process_chunk_async(
                chunk, base_url, rubrics_cfg, brand_policy, brand_prompt_text,
                llm_api_key, llm_model, temperature, llm_base_url,
                apply_diagnostics, diagnostics_cfg, brand_resolver
            )
            
            all_results.extend(chunk_results)
            self.processed_count += len(chunk)
            
            # Progress callback
            if self.config.progress_callback:
                progress = self.processed_count / total_count
                self.config.progress_callback(progress, self.processed_count, total_count)
            
            # Cleanup memory định kỳ
            if self.processed_count % self.config.memory_cleanup_interval == 0:
                cleanup_memory()
                mem_info = monitor_memory_usage()
                logger.info(f"Memory: {mem_info['rss_mb']:.1f}MB RSS")
        
        elapsed = time.time() - start_time
        success_count = len([r for r in all_results if "error" not in r])
        
        logger.info(f"✅ Hoàn thành {success_count}/{total_count} trong {elapsed:.1f}s")
        logger.info(f"Tốc độ: {success_count/elapsed:.1f} conv/s")
        
        # Log brand usage stats cho multi-brand mode
        if is_multi_brand and self.brand_stats:
            brand_summary = ", ".join([f"{brand}={count}" for brand, count in self.brand_stats.items()])
            logger.info(f"Brand usage: {brand_summary}")
        
        return all_results
    
    async def _process_chunk_async(
        self,
        chunk: List[str],
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
        """Process một chunk conversations song song"""
        
        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        
        async def process_single(conv_id: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await asyncio.wait_for(
                        asyncio.to_thread(
                            self._evaluate_single_fast,
                            conv_id, base_url, rubrics_cfg, brand_policy,
                            brand_prompt_text, llm_api_key, llm_model,
                            temperature, llm_base_url, apply_diagnostics, diagnostics_cfg,
                            brand_resolver
                        ),
                        timeout=self.config.llm_timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Timeout cho conv {conv_id}")
                    return {
                        "conversation_id": conv_id,
                        "error": "Timeout after 30s",
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                except Exception as e:
                    logger.error(f"Error processing {conv_id}: {e}")
                    return {
                        "conversation_id": conv_id,
                        "error": str(e),
                        "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                    }
        
        # Chạy tất cả trong chunk cùng lúc
        tasks = [process_single(conv_id) for conv_id in chunk]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return results
    
    def _evaluate_single_fast(
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
        """Evaluate single conversation - tối ưu tốc độ với multi-brand support"""
        
        try:
            # Timing debug
            start_time = time.time()
            
            # Fetch data nhanh
            raw_data = fetch_messages(base_url, conversation_id)
            fetch_time = time.time() - start_time
            
            # Resolve brand nếu có brand_resolver
            if brand_resolver:
                bot_id = extract_bot_id(raw_data)
                try:
                    brand_prompt_text, brand_policy = brand_resolver.resolve_by_bot_id(bot_id)
                    
                    # Track brand stats
                    # Lấy brand_id từ resolution để stats
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
            
            # Call LLM với timeout
            llm_start = time.time()
            llm_response = call_llm(
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
            import traceback
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
    max_concurrency: int = 15,  # Giảm default xuống 15 cho stability
    progress_callback: callable = None,
    brand_resolver: BrandResolver = None
) -> List[Dict[str, Any]]:
    """High-level API cho batch evaluation nhanh"""
    
    config = BatchConfig(
        max_concurrency=max_concurrency,
        progress_callback=progress_callback
    )
    
    evaluator = HighSpeedBatchEvaluator(config)
    
    return await evaluator.evaluate_batch(
        conversation_ids, base_url, rubrics_cfg, brand_policy,
        brand_prompt_text, llm_api_key, llm_model, temperature,
        llm_base_url, apply_diagnostics, diagnostics_cfg, brand_resolver
    )
