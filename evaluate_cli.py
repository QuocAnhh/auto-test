#!/usr/bin/env python3
"""
CLI script for evaluating conversations using Unified Rubric System
Supports batch evaluation up to 50 conversations with high performance
"""
import argparse
import json
import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from busqa.api_client import fetch_messages
from busqa.normalize import normalize_messages, build_transcript
from busqa.metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
from busqa.prompt_loader import load_unified_rubrics
from busqa.brand_specs import load_brand_prompt
from busqa.prompting import build_system_prompt_unified, build_user_instruction
from busqa.llm_client import call_llm
from busqa.evaluator import coerce_llm_json_unified
from busqa.aggregate import make_summary, generate_insights
from busqa.utils import cleanup_memory, chunk_conversations, estimate_batch_time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def evaluate_conversation(
    conversation_id: str,
    base_url: str,
    brand_prompt_path: str,
    rubrics_cfg: dict,
    brand_prompt_text: str,
    brand_policy,
    llm_api_key: str,
    llm_model: str,
    temperature: float,
    llm_base_url: str = None,
    apply_diagnostics: bool = True,
    diagnostics_cfg: dict = None
) -> Dict[str, Any]:
    """Chấm điểm 1 conversation, tối ưu cho batch processing"""
    try:
        # Fetch + normalize nhanh
        raw_data = fetch_messages(base_url, conversation_id)
        messages = normalize_messages(raw_data)
        
        if not messages:
            raise ValueError("No messages found")
        
        # Compute metrics song song
        transcript = build_transcript(messages)
        metrics = compute_latency_metrics(messages)
        additional_metrics = compute_additional_metrics(messages)
        policy_violations_count = compute_policy_violations_count(messages, brand_policy)
        
        additional_metrics["policy_violations"] = policy_violations_count
        metrics.update(additional_metrics)
        metrics_for_llm = filter_non_null_metrics(metrics)
        
        # Build prompts (cached được nếu cần)
        system_prompt = build_system_prompt_unified(rubrics_cfg, brand_policy, brand_prompt_text)
        user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
        
        # Call LLM
        llm_response = call_llm(
            api_key=llm_api_key,
            model=llm_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=llm_base_url,
            temperature=temperature
        )
        
        # Process kết quả
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
        
        return {
            "conversation_id": conversation_id,
            "brand_prompt_path": brand_prompt_path,
            "rubric_version": rubrics_cfg["version"],
            "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
            "result": result.model_dump(),
            "metrics": metrics,
            "transcript_preview": transcript[:500] + "..." if len(transcript) > 500 else transcript  # Giảm preview
        }
        
    except Exception as e:
        logger.error(f"Error evaluating {conversation_id}: {e}")
        return {
            "conversation_id": conversation_id,
            "error": str(e),
            "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
        }

async def evaluate_conversations_batch(
    conversation_ids: List[str],
    base_url: str,
    brand_prompt_path: str,
    rubrics_cfg: dict,
    brand_prompt_text: str,
    brand_policy,
    llm_api_key: str,
    llm_model: str,
    temperature: float,
    llm_base_url: str = None,
    apply_diagnostics: bool = True,
    diagnostics_cfg: dict = None,
    max_concurrency: int = 15
) -> List[Dict[str, Any]]:
    """Chấm điểm nhiều conversations song song, tối ưu cho 50 conv"""
    
    # Tăng semaphore cho 50 conv
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def evaluate_with_semaphore(conv_id: str):
        async with semaphore:
            return await asyncio.to_thread(
                evaluate_conversation,
                conv_id, base_url, brand_prompt_path, rubrics_cfg,
                brand_prompt_text, brand_policy, llm_api_key, llm_model,
                temperature, llm_base_url, apply_diagnostics, diagnostics_cfg
            )
    
    # Tạo tasks cho tất cả conversations
    print(f"🔥 Starting batch evaluation: {len(conversation_ids)} conversations, concurrency={max_concurrency}")
    tasks = [evaluate_with_semaphore(conv_id) for conv_id in conversation_ids]
    
    # Chạy tất cả cùng lúc với progress tracking
    start_time = datetime.now()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Process exceptions thành error dicts
    processed_results = []
    success_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "conversation_id": conversation_ids[i],
                "error": str(result),
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
            })
        else:
            processed_results.append(result)
            success_count += 1
    
    print(f"✅ Batch completed: {success_count}/{len(conversation_ids)} success in {elapsed:.1f}s")
    return processed_results

def parse_conversation_ids(args) -> List[str]:
    """Parse conversation IDs from command line arguments."""
    conversation_ids = []
    
    # From --conversation-id (single, for backward compatibility)
    if hasattr(args, 'conversation_id') and args.conversation_id:
        conversation_ids.append(args.conversation_id.strip())
    
    # From --conversation-ids (comma-separated)
    if hasattr(args, 'conversation_ids') and args.conversation_ids:
        ids = [id.strip() for id in args.conversation_ids.split(',')]
        conversation_ids.extend([id for id in ids if id])
    
    # From --conversations-file (one per line)
    if hasattr(args, 'conversations_file') and args.conversations_file:
        try:
            with open(args.conversations_file, 'r', encoding='utf-8') as f:
                file_ids = [line.strip() for line in f.readlines()]
                conversation_ids.extend([id for id in file_ids if id])
        except Exception as e:
            logger.error(f"Error reading conversations file: {e}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_ids = []
    for id in conversation_ids:
        if id not in seen:
            seen.add(id)
            unique_ids.append(id)
    
    # Cap at 50 conversations
    if len(unique_ids) > 50:
        logger.warning(f"Too many conversation IDs ({len(unique_ids)}). Limiting to first 50.")
        unique_ids = unique_ids[:50]
    
    return unique_ids

def main():
    parser = argparse.ArgumentParser(description="Evaluate bus QA conversations using Unified Rubric System")
    
    # Single conversation (backward compatibility)
    parser.add_argument("--conversation-id", help="Single conversation ID to evaluate")
    
    # Batch conversations (new)
    parser.add_argument("--conversation-ids", help="Comma-separated conversation IDs (e.g., 'id1,id2,id3')")
    parser.add_argument("--conversations-file", help="Path to file with conversation IDs (one per line)")
    
    # Configuration
    parser.add_argument("--base-url", default="http://103.141.140.243:14496", help="API base URL")
    parser.add_argument("--brand-prompt-path", required=True, help="Path to brand prompt file (e.g., brands/son_hai/prompt.md)")
    parser.add_argument("--rubrics", default="config/rubrics_unified.yaml", help="Path to unified rubrics config")
    
    # LLM settings
    parser.add_argument("--llm-model", default="gemini-2.5-flash", help="LLM model to use")
    parser.add_argument("--llm-base-url", help="LLM base URL (optional)")
    parser.add_argument("--temperature", type=float, default=0.2, help="LLM temperature")
    
    # Concurrency and output
    parser.add_argument("--max-concurrency", type=int, default=15, help="Maximum concurrent evaluations (default: 15)")
    parser.add_argument("--output", help="Output JSON file path")
    
    # Diagnostics
    parser.add_argument("--apply-diagnostics", action="store_true", default=True, help="Apply diagnostic penalties (default: True)")
    parser.add_argument("--no-diagnostics", action="store_true", help="Disable diagnostic penalties")
    
    # Debug
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Parse conversation IDs
    conversation_ids = parse_conversation_ids(args)
    if not conversation_ids:
        print("✗ No conversation IDs provided. Use --conversation-id, --conversation-ids, or --conversations-file")
        sys.exit(1)
    
    print(f"📝 Found {len(conversation_ids)} conversation(s) to evaluate:")
    for i, conv_id in enumerate(conversation_ids, 1):
        print(f"  {i}. {conv_id}")
    
    # Handle diagnostics flags
    apply_diagnostics = args.apply_diagnostics and not args.no_diagnostics
    
    # Load configurations
    try:
        rubrics_cfg = load_unified_rubrics(args.rubrics)
        if args.verbose:
            print(f"✓ Loaded unified rubrics v{rubrics_cfg['version']}")
            print(f"  Criteria: {list(rubrics_cfg['criteria'].keys())}")
    except Exception as e:
        print(f"✗ Error loading rubrics: {e}")
        sys.exit(1)
    
    # Load diagnostics config
    diagnostics_cfg = None
    if apply_diagnostics:
        try:
            from busqa.prompt_loader import load_diagnostics_config
            diagnostics_cfg = load_diagnostics_config()
            if args.verbose:
                or_count = len(diagnostics_cfg.get('operational_readiness', []))
                rc_count = len(diagnostics_cfg.get('risk_compliance', []))
                print(f"✓ Loaded diagnostics config: {or_count} OR + {rc_count} RC rules")
        except Exception as e:
            print(f"✗ Error loading diagnostics config: {e}")
            apply_diagnostics = False
    
    try:
        brand_prompt_text, brand_policy = load_brand_prompt(args.brand_prompt_path)
        if args.verbose:
            print(f"✓ Loaded brand prompt: {args.brand_prompt_path}")
            print(f"  Policy flags: phone_collect={not brand_policy.forbid_phone_collect}, "
                  f"fixed_greeting={brand_policy.require_fixed_greeting}, "
                  f"money_words={brand_policy.read_money_in_words}")
    except Exception as e:
        print(f"✗ Error loading brand prompt: {e}")
        sys.exit(1)
    
    # Get API key
    llm_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_api_key:
        print("✗ Missing LLM API key. Set GEMINI_API_KEY or OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    # Auto-adjust concurrency cho tối ưu
    from busqa.utils import get_optimal_concurrency
    if args.max_concurrency == 15:  # Default value
        optimal_concurrency = get_optimal_concurrency(len(conversation_ids))
        args.max_concurrency = optimal_concurrency
        print(f"🎯 Auto-adjusted concurrency to {optimal_concurrency} for {len(conversation_ids)} conversations")
    
    # Ước tính thời gian và bắt đầu evaluation
    if len(conversation_ids) > 1:
        estimated_time = estimate_batch_time(len(conversation_ids), args.max_concurrency)
        print(f"⏱️  Estimated time: {estimated_time:.1f}s for {len(conversation_ids)} conversations")
    
    print(f"\n🚀 Starting evaluation with concurrency={args.max_concurrency}...")
    
    if len(conversation_ids) == 1:
        # Single conversation - backward compatibility
        start_time = datetime.now()
        result = evaluate_conversation(
            conversation_ids[0], args.base_url, args.brand_prompt_path,
            rubrics_cfg, brand_prompt_text, brand_policy, llm_api_key,
            args.llm_model, args.temperature, args.llm_base_url,
            apply_diagnostics, diagnostics_cfg
        )
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Save single result
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✓ Result saved to {args.output} ({elapsed:.1f}s)")
        
        if "error" not in result:
            print_single_summary(result, rubrics_cfg, apply_diagnostics)
        else:
            print(f"✗ Evaluation failed: {result['error']}")
    
    else:
        # Batch evaluation - sử dụng high-speed evaluator cho 50 conv
        try:
            from busqa.batch_evaluator import evaluate_conversations_high_speed
            
            def progress_callback(progress, current, total):
                print(f"Progress: {current}/{total} ({progress:.1%})", end='\r', flush=True)
            
            results = asyncio.run(evaluate_conversations_high_speed(
                conversation_ids, args.base_url, rubrics_cfg, brand_policy,
                brand_prompt_text, llm_api_key, args.llm_model, args.temperature,
                args.llm_base_url, apply_diagnostics, diagnostics_cfg,
                args.max_concurrency, progress_callback
            ))
            
            # Save batch results
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"✓ Batch results saved to {args.output}")
            
            # Clean up memory sau khi save
            cleanup_memory()
            
            # Tạo summary nhanh
            summary = make_summary(results)
            insights = generate_insights(summary)
            
            summary_data = {
                "summary": summary,
                "insights": insights,
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            summary_file = args.output.replace('.json', '_summary.json') if args.output else 'batch_summary.json'
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            print(f"✓ Summary saved to {summary_file}")
            
            # Print batch summary
            print_batch_summary(summary, insights)
            
        except Exception as e:
            print(f"✗ Error running batch evaluation: {e}")
            sys.exit(1)

def print_single_summary(result: Dict[str, Any], rubrics_cfg: dict, apply_diagnostics: bool):
    """Print summary for single conversation evaluation."""
    eval_result = result["result"]
    metrics = result["metrics"]
    
    print(f"\n📊 EVALUATION SUMMARY")
    print(f"Flow: {eval_result['detected_flow']}")
    print(f"Score: {eval_result['total_score']:.1f}/100 ({eval_result['label']})")
    print(f"Confidence: {eval_result['confidence']:.1%}")
    
    if eval_result.get('tags'):
        print(f"Tags: {', '.join(eval_result['tags'])}")
    
    if eval_result.get('risks'):
        print("⚠ Risks identified:")
        for risk in eval_result['risks']:
            print(f"  • {risk}")
    
    print("💡 Suggestions:")
    if eval_result.get('suggestions'):
        for suggestion in eval_result['suggestions']:
            print(f"  • {suggestion}")
    else:
        if eval_result['total_score'] >= 80:
            print("  (No suggestions needed - score >= 80)")
        else:
            print("  (No suggestions provided by LLM)")
    
    # Print diagnostics summary
    diagnostics_hits = metrics.get("diagnostics", {})
    if apply_diagnostics and diagnostics_hits:
        or_hits = diagnostics_hits.get("operational_readiness", [])
        rc_hits = diagnostics_hits.get("risk_compliance", [])
        
        if or_hits or rc_hits:
            print(f"\n🔍 DIAGNOSTIC HITS")
            
            if or_hits:
                print("Operational Readiness:")
                for hit in or_hits:
                    print(f"  • {hit['key']}")
                    if hit.get('evidence'):
                        print(f"    Evidence: {hit['evidence'][0][:80]}...")
            
            if rc_hits:
                print("Risk Compliance:")
                for hit in rc_hits:
                    print(f"  • {hit['key']}")
                    if hit.get('evidence'):
                        print(f"    Evidence: {hit['evidence'][0][:80]}...")
            
            penalty_status = "Applied" if apply_diagnostics else "Display only"
            print(f"  Status: {penalty_status}")
        else:
            print(f"\n🎉 No diagnostic issues detected!")
    elif not apply_diagnostics:
        print(f"\nℹ️ Diagnostic penalties disabled")
    
    print(f"\n🎯 CRITERIA BREAKDOWN")
    for criterion, details in eval_result['criteria'].items():
        score = details["score"]
        weight = rubrics_cfg["criteria"][criterion]
        weighted_contribution = score * weight
        print(f"  {criterion}: {score:.0f}/100 (weight: {weight:.1%}, contributes: {weighted_contribution:.1f})")
        if details["note"] and details["note"] != "missing":
            print(f"    Note: {details['note']}")

def print_batch_summary(summary: Dict[str, Any], insights: List[str]):
    """Print summary for batch evaluation."""
    print(f"\n📊 BATCH EVALUATION SUMMARY")
    print(f"Total conversations: {summary['count']}")
    print(f"Successful: {summary['successful_count']}")
    print(f"Errors: {summary['error_count']}")
    
    if summary['successful_count'] > 0:
        print(f"\nOverall Performance:")
        print(f"  Average score: {summary['avg_total_score']:.1f}/100")
        print(f"  Median score: {summary['median_total_score']:.1f}/100")
        print(f"  Standard deviation: {summary['std_total_score']:.1f}")
        
        print(f"\nCriteria Performance:")
        for criterion, avg_score in summary['criteria_avg'].items():
            print(f"  {criterion}: {avg_score:.1f}/100")
        
        print(f"\nFlow Distribution:")
        for flow, count in summary['flow_distribution'].items():
            print(f"  {flow}: {count} conversations")
        
        if summary['diagnostics_top']:
            print(f"\nTop Diagnostic Issues:")
            for issue, count in summary['diagnostics_top'][:3]:
                print(f"  {issue}: {count} occurrences")
        
        print(f"\nPolicy Violation Rate: {summary['policy_violation_rate']:.1%}")
    
    if insights:
        print(f"\n💡 INSIGHTS:")
        for insight in insights:
            print(f"  • {insight}")
    
    if summary['error_count'] > 0:
        print(f"\n❌ ERRORS:")
        for error in summary['errors']:
            print(f"  • {error['conversation_id']}: {error['error']}")

if __name__ == "__main__":
    main()
