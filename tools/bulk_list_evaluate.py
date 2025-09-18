#!/usr/bin/env python3
"""
Bulk List & Evaluate Tool - Unified Rubric System
Fetches conversations list from API, selects N conversations by strategy, evaluates with single-brand approach.
Maintains backward compatibility with existing per-conversation result format.
"""
import argparse
import json
import sys
import os
import asyncio
import random
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import requests
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from busqa.normalize import normalize_messages, build_transcript
from busqa.metrics import (
    compute_latency_metrics, compute_additional_metrics, 
    compute_policy_violations_count, filter_non_null_metrics
)
from busqa.prompt_loader import load_unified_rubrics
from busqa.brand_specs import load_brand_prompt
from busqa.prompting import build_system_prompt_unified, build_user_instruction
from busqa.llm_client import call_llm
from busqa.batch_evaluator import evaluate_conversations_high_speed
from busqa.evaluator import coerce_llm_json_unified
from busqa.aggregate import make_summary
from busqa.diagnostics import detect_operational_readiness, detect_risk_compliance

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FetchConfig:
    """Configuration for fetching conversations"""
    base_url: str
    bot_id: str
    bearer_token: str
    page_size: int = 100
    max_pages: int = 20
    retry_count: int = 3
    backoff_delay: float = 1.0
    timeout: int = 30

def test_bearer_token(base_url: str, bearer_token: str, timeout: int = 10) -> bool:
    """
    Test if bearer token is valid by making a simple API call.
    
    Args:
        base_url: API base URL
        bearer_token: Bearer token to test
        timeout: Request timeout
        
    Returns:
        True if token is valid, False otherwise
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        
        # Try a simple endpoint first (like getting bot info or health check)
        test_url = f"{base_url.rstrip('/')}/api/conversations"
        
        response = requests.get(
            test_url,
            headers=headers,
            params={"page": 1, "page_size": 1},  # Minimal request
            timeout=timeout
        )
        
        return response.status_code not in [401, 403]
        
    except Exception as e:
        return False

def fetch_conversations_with_messages(config: FetchConfig) -> List[Dict[str, Any]]:
    """
    Fetch all conversations with messages from API with retry/backoff for 429/5xx errors.
    
    Args:
        config: FetchConfig object with API parameters
        
    Returns:
        List of conversation dictionaries with conversation_id, messages, created_at, etc.
    """
    all_conversations = []
    headers = {
        "Authorization": f"Bearer {config.bearer_token}",
        "Content-Type": "application/json"
    }
    
    for page in range(1, config.max_pages + 1):
        url = f"{config.base_url.rstrip('/')}/api/conversations"
        params = {
            "bot_id": config.bot_id,
            "page": page,
            "page_size": config.page_size
        }
        
        for attempt in range(config.retry_count):
            try:
                logger.info(f"Fetching page {page}/{config.max_pages} (attempt {attempt + 1}/{config.retry_count})")
                
                response = requests.get(
                    url, 
                    headers=headers, 
                    params=params, 
                    timeout=config.timeout
                )
                
                # Request completed
                
                if response.status_code == 401:
                    # Authentication error - don't retry, fail immediately
                    logger.error(f"Authentication failed (401). Check bearer token.")
                    logger.error(f"Token preview: {config.bearer_token[:20]}...")
                    logger.error(f"Response: {response.text[:200]}")
                    raise requests.exceptions.HTTPError(f"401 Client Error: Unauthorized. Invalid or expired bearer token.")
                elif response.status_code == 403:
                    # Forbidden - don't retry
                    logger.error(f"Access forbidden (403). Check bot_id permissions.")
                    logger.error(f"Bot ID: {config.bot_id}")
                    logger.error(f"Response: {response.text[:200]}")
                    raise requests.exceptions.HTTPError(f"403 Forbidden: Access denied to bot_id {config.bot_id}")
                elif response.status_code == 429:
                    # Rate limited - backoff and retry
                    backoff_time = config.backoff_delay * (2 ** attempt)
                    logger.warning(f"Rate limited (429). Backing off for {backoff_time:.1f}s")
                    time.sleep(backoff_time)
                    continue
                elif response.status_code >= 500:
                    # Server error - backoff and retry
                    backoff_time = config.backoff_delay * (2 ** attempt)
                    logger.warning(f"Server error ({response.status_code}). Backing off for {backoff_time:.1f}s")
                    time.sleep(backoff_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                conversations = data.get("conversations", [])
                if not conversations:
                    logger.info(f"No more conversations on page {page}. Stopping.")
                    break
                
                all_conversations.extend(conversations)
                logger.info(f"Page {page}: Got {len(conversations)} conversations (total: {len(all_conversations)})")
                
                # Check if there are more pages
                if len(conversations) < config.page_size:
                    logger.info("Last page reached (fewer than page_size conversations)")
                    break
                
                break  # Success, no need to retry
                
            except requests.exceptions.RequestException as e:
                if attempt == config.retry_count - 1:
                    logger.error(f"Failed to fetch page {page} after {config.retry_count} attempts: {e}")
                    raise
                else:
                    backoff_time = config.backoff_delay * (2 ** attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}): {e}. Retrying in {backoff_time:.1f}s")
                    time.sleep(backoff_time)
        else:
            # All attempts failed for this page
            break
    
    logger.info(f"Total conversations fetched: {len(all_conversations)}")
    return all_conversations

def select_conversations(
    conversations: List[Dict[str, Any]], 
    take: int = 10, 
    skip: int = 0, 
    strategy: str = "head",
    sort_by: str = "created_at",
    order: str = "desc",
    min_turns: int = 0
) -> List[Dict[str, Any]]:
    """
    Select N conversations based on strategy after filtering and sorting.
    
    Args:
        conversations: List of conversation dictionaries
        take: Number of conversations to select
        skip: Number of conversations to skip
        strategy: Selection strategy (head|tail|random|newest|oldest)
        sort_by: Sort field (created_at|length)
        order: Sort order (asc|desc)
        min_turns: Minimum number of turns (messages) required
        
    Returns:
        Selected conversations list
    """
    if not conversations:
        return []
    
    # Filter by minimum turns
    if min_turns > 0:
        filtered_convs = []
        for conv in conversations:
            messages = conv.get("messages", [])
            if len(messages) >= min_turns:
                filtered_convs.append(conv)
        conversations = filtered_convs
        logger.info(f"Filtered to {len(conversations)} conversations with >= {min_turns} turns")
    
    # Sort conversations
    if sort_by == "created_at":
        # Parse created_at to datetime for proper sorting
        def parse_created_at(conv):
            try:
                created_at = conv.get("created_at", "")
                if created_at:
                    # Handle different datetime formats
                    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            return datetime.strptime(created_at, fmt)
                        except ValueError:
                            continue
                return datetime.min
            except:
                return datetime.min
        
        conversations.sort(key=parse_created_at, reverse=(order == "desc"))
        
    elif sort_by == "length":
        conversations.sort(
            key=lambda conv: len(conv.get("messages", [])), 
            reverse=(order == "desc")
        )
    
    # Apply strategy
    if strategy == "newest":
        # Sort by created_at desc regardless of current sort
        def parse_created_at(conv):
            try:
                created_at = conv.get("created_at", "")
                if created_at:
                    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            return datetime.strptime(created_at, fmt)
                        except ValueError:
                            continue
                return datetime.min
            except:
                return datetime.min
        conversations.sort(key=parse_created_at, reverse=True)
        
    elif strategy == "oldest":
        # Sort by created_at asc regardless of current sort
        def parse_created_at(conv):
            try:
                created_at = conv.get("created_at", "")
                if created_at:
                    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            return datetime.strptime(created_at, fmt)
                        except ValueError:
                            continue
                return datetime.min
            except:
                return datetime.min
        conversations.sort(key=parse_created_at, reverse=False)
        
    elif strategy == "random":
        random.shuffle(conversations)
        
    elif strategy == "tail":
        # Take from the end (after current sorting)
        conversations = conversations[-(take + skip):] if len(conversations) > (take + skip) else conversations
        
    # elif strategy == "head" is the default - no additional processing needed
    
    # Apply skip and take
    selected = conversations[skip:skip + take]
    
    # Conversations selected
    return selected

def evaluate_conversation_from_raw(
    raw_conv: Dict[str, Any],
    brand_prompt_path: str,
    rubrics: str = "config/rubrics_unified.yaml",
    model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    apply_diagnostics: bool = True,
    llm_api_key: str = None,
    llm_base_url: str = None
) -> Dict[str, Any]:
    """
    Evaluate a single conversation using the existing pipeline.
    
    Args:
        raw_conv: Raw conversation dict with conversation_id, messages, etc.
        brand_prompt_path: Path to brand prompt file
        rubrics: Path to rubrics config file
        model: LLM model name
        temperature: LLM temperature
        apply_diagnostics: Whether to apply diagnostics
        llm_api_key: LLM API key
        llm_base_url: LLM base URL
        
    Returns:
        Per-conversation result dict (same format as evaluate_cli.py)
    """
    conversation_id = raw_conv.get("conversation_id")
    if not conversation_id:
        raise ValueError("Missing conversation_id in raw conversation data")
    
    try:
        # Load configurations
        rubrics_cfg = load_unified_rubrics(rubrics)
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        
        # Get diagnostics config if needed
        diagnostics_cfg = None
        if apply_diagnostics:
            diagnostics_path = "config/diagnostics.yaml"
            if os.path.exists(diagnostics_path):
                import yaml
                with open(diagnostics_path, 'r', encoding='utf-8') as f:
                    diagnostics_cfg = yaml.safe_load(f)
        
        # Normalize messages (raw_conv already has "messages" key)
        messages = normalize_messages(raw_conv)
        
        if not messages:
            raise ValueError("No messages found after normalization")
        
        # Build transcript and compute metrics
        transcript = build_transcript(messages)
        metrics = compute_latency_metrics(messages)
        additional_metrics = compute_additional_metrics(messages, brand_policy, brand_prompt_text)
        policy_violations_count = compute_policy_violations_count(messages, brand_policy)
        
        additional_metrics["policy_violations"] = policy_violations_count
        metrics.update(additional_metrics)
        
        # Add diagnostics if enabled
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
        
        # Build prompts
        system_prompt = build_system_prompt_unified(rubrics_cfg, brand_policy, brand_prompt_text)
        user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
        
        # Call LLM
        llm_response = call_llm(
            api_key=llm_api_key,
            model=model,
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
        
        # Extract brand_id from brand_prompt_path
        brand_id = "unknown"
        if brand_prompt_path:
            brand_parts = brand_prompt_path.split(os.sep)
            if "brands" in brand_parts:
                try:
                    brand_idx = brand_parts.index("brands")
                    if brand_idx + 1 < len(brand_parts):
                        brand_id = brand_parts[brand_idx + 1]
                except:
                    pass
        
        # Return same format as evaluate_cli.py
        return {
            "conversation_id": conversation_id,
            "brand_id": brand_id,
            "brand_prompt_path": brand_prompt_path,
            "rubric_version": rubrics_cfg["version"],
            "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
            "result": result.model_dump(),
            "metrics": metrics,
            "transcript_preview": transcript[:500] + "..." if len(transcript) > 500 else transcript
        }
        
    except Exception as e:
        logger.error(f"Error evaluating conversation {conversation_id}: {e}")
        return {
            "conversation_id": conversation_id,
            "error": str(e),
            "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
        }

async def evaluate_many_raw_conversations(
    raw_conversations: List[Dict[str, Any]],
    brand_prompt_path: str,
    rubrics: str = "config/rubrics_unified.yaml",
    model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    apply_diagnostics: bool = True,
    llm_api_key: str = None,
    llm_base_url: str = None,
    max_concurrency: int = 5,
    stream_callback: Optional[callable] = None
) -> List[Dict[str, Any]]:
    """
    Evaluate multiple conversations concurrently with error handling.
    
    Args:
        raw_conversations: List of raw conversation dicts
        brand_prompt_path: Path to brand prompt file
        rubrics: Path to rubrics config file
        model: LLM model name
        temperature: LLM temperature
        apply_diagnostics: Whether to apply diagnostics
        llm_api_key: LLM API key
        llm_base_url: LLM base URL
        max_concurrency: Maximum concurrent evaluations
        
    Returns:
        List of evaluation results (errors included, processing continues)
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def evaluate_single(raw_conv: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            conversation_id = raw_conv.get("conversation_id", "unknown")
            try:
                logger.info(f"Starting evaluation: {conversation_id}")
                
                # Run in thread to avoid blocking
                result = await asyncio.to_thread(
                    evaluate_conversation_from_raw,
                    raw_conv,
                    brand_prompt_path,
                    rubrics,
                    model,
                    temperature,
                    apply_diagnostics,
                    llm_api_key,
                    llm_base_url
                )
                
                if "error" not in result:
                    logger.info(f"Completed evaluation: {conversation_id}")
                else:
                    logger.error(f"Failed evaluation: {conversation_id} - {result['error']}")
                
                # Emit per-item streaming callback if provided
                if stream_callback:
                    try:
                        if asyncio.iscoroutinefunction(stream_callback):
                            await stream_callback(result)
                        else:
                            # Offload sync callback to thread to avoid blocking event loop
                            await asyncio.to_thread(stream_callback, result)
                    except Exception:
                        pass

                return result
                
            except Exception as e:
                logger.error(f"Exception evaluating {conversation_id}: {e}")
                return {
                    "conversation_id": conversation_id,
                    "error": str(e),
                    "evaluation_timestamp": datetime.utcnow().isoformat() + "Z"
                }
    
    # Run all evaluations concurrently
    tasks = [evaluate_single(conv) for conv in raw_conversations]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    return results

def make_summary_enhanced(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create enhanced summary with additional statistics.
    
    Args:
        results: List of evaluation results
        
    Returns:
        Enhanced summary dictionary
    """
    # Use the existing make_summary function
    summary = make_summary(results)
    
    # Add additional statistics
    successful_results = [r for r in results if "error" not in r]
    
    if successful_results:
        # Count by brand_id
        brand_counts = {}
        for result in successful_results:
            brand_id = result.get("brand_id", "unknown")
            brand_counts[brand_id] = brand_counts.get(brand_id, 0) + 1
        summary["brand_distribution"] = brand_counts
        
        # Flow distribution
        flow_counts = {}
        for result in successful_results:
            try:
                flow_type = result.get("result", {}).get("flow_type", "unknown")
                flow_counts[flow_type] = flow_counts.get(flow_type, 0) + 1
            except:
                pass
        summary["flow_distribution_detailed"] = flow_counts
        
        # Policy violation rate
        violation_count = 0
        for result in successful_results:
            try:
                violations = result.get("metrics", {}).get("policy_violations", 0)
                if violations > 0:
                    violation_count += 1
            except:
                pass
        summary["policy_violation_conversations"] = violation_count
        
        # Top diagnostics
        diagnostic_counts = {}
        for result in successful_results:
            try:
                diagnostics = result.get("metrics", {}).get("diagnostics", {})
                for category, hits in diagnostics.items():
                    if isinstance(hits, dict):
                        for diagnostic, count in hits.items():
                            if count > 0:
                                key = f"{category}.{diagnostic}"
                                diagnostic_counts[key] = diagnostic_counts.get(key, 0) + count
            except:
                pass
        
        # Sort and take top 10
        top_diagnostics = sorted(diagnostic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        summary["top_diagnostics_detailed"] = dict(top_diagnostics)
    
    return summary

def main():
    parser = argparse.ArgumentParser(
        description="Bulk List & Evaluate Tool - Fetch conversations from API and evaluate with Unified Rubric System"
    )
    
    # Required parameters
    parser.add_argument("--bot-id", required=True, help="Bot ID to fetch conversations for")
    parser.add_argument("--brand-prompt-path", help="Path to brand prompt file (e.g., brands/son_hai/prompt.md)")
    parser.add_argument("--brand", help="Brand name to map to prompt path (alternative to --brand-prompt-path)")
    
    # API parameters
    parser.add_argument("--list-base-url", default="https://live-demo.agenticai.pro.vn", 
                       help="Base URL for listing conversations API")
    parser.add_argument("--bearer", help="Bearer token for API authentication")
    parser.add_argument("--page-size", type=int, default=100, help="Page size for API requests")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages to fetch")
    
    # Selection parameters
    parser.add_argument("--take", type=int, default=10, help="Number of conversations to select")
    parser.add_argument("--skip", type=int, default=0, help="Number of conversations to skip")
    parser.add_argument("--strategy", choices=["head", "tail", "random", "newest", "oldest"], 
                       default="head", help="Selection strategy")
    parser.add_argument("--sort-by", choices=["created_at", "length"], default="created_at", 
                       help="Sort field")
    parser.add_argument("--order", choices=["asc", "desc"], default="desc", help="Sort order")
    parser.add_argument("--min-turns", type=int, default=0, help="Minimum number of turns required")
    
    # Evaluation parameters
    parser.add_argument("--rubrics", default="config/rubrics_unified.yaml", help="Path to rubrics config")
    parser.add_argument("--llm-model", default="gemini-2.5-flash", help="LLM model to use")
    parser.add_argument("--temperature", type=float, default=0.2, help="LLM temperature")
    parser.add_argument("--llm-base-url", help="LLM base URL (optional)")
    parser.add_argument("--max-concurrency", type=int, default=5, help="Maximum concurrent evaluations")
    parser.add_argument("--apply-diagnostics", action="store_true", default=True, 
                       help="Apply diagnostics analysis")
    parser.add_argument("--no-diagnostics", dest="apply_diagnostics", action="store_false",
                       help="Disable diagnostics analysis")
    
    # Output parameters
    parser.add_argument("--output-json", help="Output JSON file path (e.g., results.json)")
    parser.add_argument("--output-summary", help="Output summary JSON file path (e.g., summary.json)")
    parser.add_argument("--output-csv", help="Output CSV file path (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Only show selected conversation IDs")
    
    args = parser.parse_args()
    
    # Validate required parameters
    if not args.brand_prompt_path and not args.brand:
        parser.error("Either --brand-prompt-path or --brand must be specified")
    
    # Get bearer token
    bearer_token = args.bearer or os.getenv("BEARER_TOKEN")
    if not bearer_token:
        parser.error("Bearer token is required. Use --bearer or set BEARER_TOKEN environment variable")
    
    # Get LLM API key
    llm_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not llm_api_key:
        parser.error("LLM API key is required. Set OPENAI_API_KEY or GEMINI_API_KEY environment variable")
    
    # Resolve brand prompt path
    brand_prompt_path = args.brand_prompt_path
    if args.brand and not brand_prompt_path:
        brand_prompt_path = f"brands/{args.brand}/prompt.md"
    
    if not os.path.exists(brand_prompt_path):
        parser.error(f"Brand prompt file not found: {brand_prompt_path}")
    
    # Create fetch config
    fetch_config = FetchConfig(
        base_url=args.list_base_url,
        bot_id=args.bot_id,
        bearer_token=bearer_token,
        page_size=args.page_size,
        max_pages=args.max_pages
    )
    
    try:
        # Step 1: Fetch conversations
        logger.info(f"Fetching conversations for bot_id={args.bot_id}")
        conversations = fetch_conversations_with_messages(fetch_config)
        
        if not conversations:
            logger.error("No conversations found")
            return 1
        
        # Step 2: Select conversations
        logger.info(f"Selecting conversations (take={args.take}, skip={args.skip}, strategy={args.strategy})")
        selected_conversations = select_conversations(
            conversations,
            take=args.take,
            skip=args.skip,
            strategy=args.strategy,
            sort_by=args.sort_by,
            order=args.order,
            min_turns=args.min_turns
        )
        
        if not selected_conversations:
            logger.error("No conversations selected after filtering")
            return 1
        
        # Dry run - just show selected IDs
        if args.dry_run:
            selected_ids = [conv.get("conversation_id") for conv in selected_conversations]
            print("Selected conversation IDs:")
            for conv_id in selected_ids:
                print(f"  {conv_id}")
            return 0
        
        # Step 3: Evaluate conversations using HighSpeedBatchEvaluator
        logger.info(f"Evaluating {len(selected_conversations)} conversations (high-speed path)")
        # Preload configs once
        rubrics_cfg = load_unified_rubrics(args.rubrics)
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        diagnostics_cfg = None
        if args.apply_diagnostics:
            diagnostics_path = "config/diagnostics.yaml"
            if os.path.exists(diagnostics_path):
                import yaml
                with open(diagnostics_path, 'r', encoding='utf-8') as f:
                    diagnostics_cfg = yaml.safe_load(f)

        # Extract conversation_ids
        conversation_ids = [conv.get("conversation_id") for conv in selected_conversations if conv.get("conversation_id")]
        # Build base_url for HighSpeed API client from list-base-url
        base_url = args.list_base_url

        results = asyncio.run(evaluate_conversations_high_speed(
            conversation_ids=conversation_ids,
            base_url=base_url,
            rubrics_cfg=rubrics_cfg,
            brand_policy=brand_policy,
            brand_prompt_text=brand_prompt_text,
            llm_api_key=llm_api_key,
            llm_model=args.llm_model,
            temperature=args.temperature,
            llm_base_url=args.llm_base_url,
            apply_diagnostics=args.apply_diagnostics,
            diagnostics_cfg=diagnostics_cfg,
            max_concurrency=args.max_concurrency,
            use_high_performance_api=True,
            use_progressive_batching=True
        ))
        
        # Step 4: Create summary
        summary = make_summary_enhanced(results)
        
        # Step 5: Output results
        # Print to STDOUT as JSON array
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
        # Write to files if specified
        if args.output_json:
            with open(args.output_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            pass  # Results written
        
        if args.output_summary:
            with open(args.output_summary, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            pass  # Summary written
        
        if args.output_csv:
            # Simple CSV output
            import csv
            with open(args.output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow([
                    'conversation_id', 'brand_id', 'total_score', 'flow_type', 
                    'policy_violations', 'error', 'evaluation_timestamp'
                ])
                # Data
                for result in results:
                    if "error" in result:
                        writer.writerow([
                            result.get('conversation_id', ''),
                            result.get('brand_id', ''),
                            '',
                            '',
                            '',
                            result.get('error', ''),
                            result.get('evaluation_timestamp', '')
                        ])
                    else:
                        evaluation_result = result.get('result', {})
                        writer.writerow([
                            result.get('conversation_id', ''),
                            result.get('brand_id', ''),
                            evaluation_result.get('total_score', ''),
                            evaluation_result.get('flow_type', ''),
                            result.get('metrics', {}).get('policy_violations', ''),
                            '',
                            result.get('evaluation_timestamp', '')
                        ])
            pass  # CSV written
        
        # Log final stats
        success_count = len([r for r in results if "error" not in r])
        error_count = len(results) - success_count
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
