#!/usr/bin/env python3
"""
CLI script for evaluating conversations using Unified Rubric System
"""
import argparse
import json
import sys
import os
from pathlib import Path

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

def main():
    parser = argparse.ArgumentParser(description="Evaluate bus QA conversations using Unified Rubric System")
    parser.add_argument("--conversation-id", required=True, help="Conversation ID to evaluate")
    parser.add_argument("--base-url", default="http://103.141.140.243:14496", help="API base URL")
    parser.add_argument("--brand-prompt-path", required=True, help="Path to brand prompt file (e.g., brands/son_hai/prompt.md)")
    parser.add_argument("--rubrics", default="config/rubrics_unified.yaml", help="Path to unified rubrics config")
    parser.add_argument("--llm-model", default="gemini-2.5-flash", help="LLM model to use")
    parser.add_argument("--temperature", type=float, default=0.2, help="LLM temperature")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--apply-diagnostics", action="store_true", default=True, help="Apply diagnostic penalties (default: True)")
    parser.add_argument("--no-diagnostics", action="store_true", help="Disable diagnostic penalties")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
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
    
    # Fetch conversation data
    try:
        if args.verbose:
            print(f"Fetching conversation {args.conversation_id}...")
        raw_data = fetch_messages(args.base_url, args.conversation_id)
        messages = normalize_messages(raw_data)
        if not messages:
            print("✗ No messages found in conversation")
            sys.exit(1)
        if args.verbose:
            print(f"✓ Loaded {len(messages)} messages")
    except Exception as e:
        print(f"✗ Error fetching conversation: {e}")
        sys.exit(1)
    
    # Build transcript and compute metrics
    transcript = build_transcript(messages)
    metrics = compute_latency_metrics(messages)
    additional_metrics = compute_additional_metrics(messages)
    
    # Compute policy violations
    policy_violations_count = compute_policy_violations_count(messages, brand_policy)
    additional_metrics["policy_violations"] = policy_violations_count
    
    metrics.update(additional_metrics)
    metrics_for_llm = filter_non_null_metrics(metrics)
    
    if args.verbose:
        print(f"✓ Computed metrics: {len(metrics)} total")
        if policy_violations_count > 0:
            print(f"  ⚠ Policy violations detected: {policy_violations_count}")
    
    # Build prompts
    system_prompt = build_system_prompt_unified(rubrics_cfg, brand_policy, brand_prompt_text)
    user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
    
    if args.verbose:
        print("✓ Built unified prompts")
        print(f"  System prompt length: {len(system_prompt)} chars")
        print(f"  User prompt length: {len(user_prompt)} chars")
    
    # Call LLM
    try:
        if args.verbose:
            print(f"Calling {args.llm_model}...")
        llm_response = call_llm(
            api_key=llm_api_key,
            model=args.llm_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=args.temperature
        )
        if args.verbose:
            print("✓ Got LLM response")
            # Debug: check if LLM returned suggestions
            if isinstance(llm_response, dict):
                llm_suggestions = llm_response.get("suggestions", [])
                llm_total_score = llm_response.get("total_score", 0)
                print(f"  LLM total_score: {llm_total_score}")
                print(f"  LLM suggestions: {len(llm_suggestions)} items")
                if llm_suggestions:
                    for i, sugg in enumerate(llm_suggestions[:2]):
                        print(f"    {i+1}. {sugg[:60]}...")
    except Exception as e:
        print(f"✗ Error calling LLM: {e}")
        sys.exit(1)
    
    # Process results
    try:
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
        if args.verbose:
            print("✓ Processed and validated results")
            print(f"  Final total_score: {result.total_score}")
            print(f"  Final suggestions: {len(result.suggestions)} items")
            if result.suggestions:
                for i, sugg in enumerate(result.suggestions[:2]):
                    print(f"    {i+1}. {sugg[:60]}...")
    except Exception as e:
        print(f"✗ Error processing results: {e}")
        sys.exit(1)
    
    # Prepare output
    output_data = {
        "conversation_id": args.conversation_id,
        "brand_prompt_path": args.brand_prompt_path,
        "rubric_version": rubrics_cfg["version"],
        "evaluation_timestamp": "2025-09-13T12:00:00Z",  # Mock timestamp
        "result": result.model_dump(),
        "metrics": metrics,
        "transcript_preview": transcript[:1000] + "..." if len(transcript) > 1000 else transcript
    }
    
    # Output results
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"✓ Results saved to {args.output}")
    else:
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    
    # Summary
    print(f"\n📊 EVALUATION SUMMARY")
    print(f"Flow: {result.detected_flow}")
    print(f"Score: {result.total_score:.1f}/100 ({result.label})")
    print(f"Confidence: {result.confidence:.1%}")
    
    if result.tags:
        print(f"Tags: {', '.join(result.tags)}")
    
    if result.risks:
        print("⚠ Risks identified:")
        for risk in result.risks:
            print(f"  • {risk}")
    
    print("💡 Suggestions:")
    if result.suggestions:
        for suggestion in result.suggestions:
            print(f"  • {suggestion}")
    else:
        if result.total_score >= 80:
            print("  (No suggestions needed - score >= 80)")
        else:
            print("  (No suggestions provided by LLM)")
    
    # Print diagnostics summary
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
    for criterion, details in result.criteria.items():
        score = details["score"]
        weight = rubrics_cfg["criteria"][criterion]
        weighted_contribution = score * weight
        print(f"  {criterion}: {score:.0f}/100 (weight: {weight:.1%}, contributes: {weighted_contribution:.1f})")
        if details["note"] and details["note"] != "missing":
            print(f"    Note: {details['note']}")

if __name__ == "__main__":
    main()
