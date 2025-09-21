#!/usr/bin/env python3
"""
Test script for Prompt Suggestions functionality
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from busqa.prompt_doctor import analyze_prompt_suggestions
from busqa.brand_specs import load_brand_prompt, get_available_brands


async def test_prompt_suggestions():
    """Test the prompt suggestions functionality"""
    
    print("🧪 Testing Prompt Suggestions Functionality")
    print("=" * 50)
    
    # Get available brands
    brands = get_available_brands()
    print(f"Available brands: {brands}")
    
    if not brands:
        print("❌ No brands available for testing")
        return
    
    # Use first available brand
    brand_id = brands[0]
    print(f"Testing with brand: {brand_id}")
    
    # Load brand prompt
    try:
        brand_prompt_path = f"brands/{brand_id}/prompt.md"
        with open(brand_prompt_path, 'r', encoding='utf-8') as f:
            brand_prompt = f.read()
        print(f"✅ Loaded brand prompt from {brand_prompt_path} ({len(brand_prompt)} characters)")
    except Exception as e:
        print(f"❌ Failed to load brand prompt: {e}")
        return
    
    # Create mock evaluation summary
    evaluation_summary = {
        'count': 10,
        'successful_count': 10,
        'error_count': 0,
        'avg_total_score': 68.5,
        'criteria_avg': {
            'intent_routing': 75,
            'slots_completeness': 65,  # Low score
            'no_redundant_questions': 70,
            'knowledge_accuracy': 70,  # Low score
            'context_flow_closure': 80,
            'style_tts': 75,
            'policy_compliance': 85,
            'empathy_experience': 60   # Low score
        },
        'diagnostics_top': [],
        'flow_distribution': {'A': 8, 'G': 2},
        'policy_violation_rate': 0.1
    }
    
    print(f"📊 Evaluation Summary:")
    print(f"  - Total conversations: {evaluation_summary['count']}")
    print(f"  - Average score: {evaluation_summary['avg_total_score']}/100")
    print(f"  - Lowest criteria: {min(evaluation_summary['criteria_avg'].items(), key=lambda x: x[1])}")
    
    # Test prompt analysis
    print(f"\n🔍 Analyzing prompt suggestions...")
    try:
        result = await analyze_prompt_suggestions(
            evaluation_summary=evaluation_summary,
            current_prompt=brand_prompt,
            brand_policy=""
        )
        
        print("✅ Analysis completed successfully!")
        
        # Display results
        print(f"\n📋 Analysis Results:")
        print(f"  - Overall patterns: {len(result.get('analysis', {}).get('overall_patterns', []))}")
        print(f"  - Critical issues: {len(result.get('analysis', {}).get('critical_issues', []))}")
        print(f"  - Specific fixes: {len(result.get('specific_fixes', []))}")
        
        # Show specific fixes
        fixes = result.get('specific_fixes', [])
        if fixes:
            print(f"\n🔧 Specific Fixes:")
            for i, fix in enumerate(fixes, 1):
                print(f"  {i}. {fix['criterion']} ({fix['avg_score']}/100 → {fix['target_score']}/100)")
                print(f"     Priority: {fix['priority'].upper()}")
                print(f"     Problem: {fix['problem_pattern']}")
                print(f"     Section: {fix['prompt_section']} (Lines {fix['line_range'][0]}-{fix['line_range'][1]})")
                print(f"     Expected: {fix['expected_improvement']}")
                print()
        
        # Show summary
        summary = result.get('summary', '')
        if summary:
            print(f"📝 Summary: {summary}")
        
        # Save results to file
        output_file = "prompt_suggestions_test_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Results saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_prompt_suggestions())
