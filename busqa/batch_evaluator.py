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

logger = logging.getLogger(__name__)

@dataclass
class BatchConfig:
    """Config cho batch evaluation tối ưu 50 conv"""
    max_concurrency: int = 25  # Tăng từ 15 lên 25 cho 50 conv
    chunk_size: int = 10       # Chia nhỏ để control memory
    llm_timeout: float = 30.0  # Timeout cho mỗi LLM call
    memory_cleanup_interval: int = 15  # Cleanup sau 15 conv
    progress_callback: Optional[callable] = None

class HighSpeedBatchEvaluator:
    """Batch evaluator tối ưu cho 50 conversations song song"""
    
    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.system_prompt_cache = {}  # Cache system prompts
        self.processed_count = 0
        
    async def evaluate_batch(
        self, 
        conversation_ids: List[str],
        base_url: str,
        rubrics_cfg: dict,
        brand_policy: BrandPolicy,
        brand_prompt_text: str,
        llm_api_key: str,
        llm_model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        llm_base_url: str = None,
        apply_diagnostics: bool = True,
        diagnostics_cfg: dict = None
    ) -> List[Dict[str, Any]]:
        """Main entry point - chấm điểm batch với tốc độ cao"""
        
        start_time = time.time()
        total_count = len(conversation_ids)
        
        logger.info(f"🚀 Bắt đầu chấm {total_count} conv với concurrency={self.config.max_concurrency}")
        
        # Pre-build system prompt để cache
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
                apply_diagnostics, diagnostics_cfg
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
        diagnostics_cfg: dict
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
                            temperature, llm_base_url, apply_diagnostics, diagnostics_cfg
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
        diagnostics_cfg: dict
    ) -> Dict[str, Any]:
        """Evaluate single conversation - tối ưu tốc độ"""
        
        try:
            # Fetch data nhanh
            raw_data = fetch_messages(base_url, conversation_id)
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
            system_prompt = self.system_prompt_cache[system_prompt_key]
            
            # Build user prompt
            user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
            
            # Call LLM với timeout
            llm_response = call_llm(
                api_key=llm_api_key,
                model=llm_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                base_url=llm_base_url,
                temperature=temperature
            )
            
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
            
            # Return minimal result để tiết kiệm memory
            return {
                "conversation_id": conversation_id,
                "result": result.model_dump(),
                "metrics": metrics,
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
                # Bỏ transcript_preview để tiết kiệm memory
            }
            
        except Exception as e:
            logger.error(f"Error evaluating {conversation_id}: {e}")
            return {
                "conversation_id": conversation_id,
                "error": str(e),
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def _get_system_prompt_key(self, brand_policy: BrandPolicy, brand_prompt_text: str) -> str:
        """Tạo cache key cho system prompt"""
        policy_hash = hash(str(brand_policy.__dict__)) if brand_policy else 0
        text_hash = hash(brand_prompt_text)
        return f"{policy_hash}_{text_hash}"

# Convenience function cho CLI
async def evaluate_conversations_high_speed(
    conversation_ids: List[str],
    base_url: str,
    rubrics_cfg: dict,
    brand_policy: BrandPolicy,
    brand_prompt_text: str,
    llm_api_key: str,
    llm_model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    llm_base_url: str = None,
    apply_diagnostics: bool = True,
    diagnostics_cfg: dict = None,
    max_concurrency: int = 25,
    progress_callback: callable = None
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
        llm_base_url, apply_diagnostics, diagnostics_cfg
    )
