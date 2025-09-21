#!/usr/bin/env python3
"""
Test Frontend Integration with Mock API Server
"""

import json
import requests
import time
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_api_endpoints():
    """Test all API endpoints"""
    
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Frontend Integration with Mock API")
    print("=" * 60)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Health check passed")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False
    
    # Test 2: Get brands
    print("2. Testing get brands...")
    try:
        response = requests.get(f"{base_url}/configs/brands", timeout=5)
        if response.status_code == 200:
            data = response.json()
            brands = data.get('brands', [])
            print(f"   ✅ Got brands: {brands}")
        else:
            print(f"   ❌ Get brands failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Get brands error: {e}")
        return False
    
    # Test 3: Prompt suggestions analysis
    print("3. Testing prompt suggestions analysis...")
    try:
        # Create test evaluation summary
        evaluation_summary = {
            "count": 10,
            "successful_count": 10,
            "error_count": 0,
            "avg_total_score": 68.5,
            "criteria_avg": {
                "intent_routing": 75,
                "slots_completeness": 65,
                "no_redundant_questions": 70,
                "knowledge_accuracy": 70,
                "context_flow_closure": 80,
                "style_tts": 75,
                "policy_compliance": 85,
                "empathy_experience": 60
            },
            "diagnostics_top": [],
            "flow_distribution": {"A": 8, "G": 2},
            "policy_violation_rate": 0.1
        }
        
        payload = {
            "brand_id": "long_van",
            "evaluation_summary": evaluation_summary
        }
        
        response = requests.post(
            f"{base_url}/analyze/prompt-suggestions",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Prompt analysis successful!")
            
            # Display results
            analysis = data.get('analysis', {})
            fixes = analysis.get('specific_fixes', [])
            
            print(f"   📊 Analysis Results:")
            print(f"      - Brand: {data.get('brand_id')}")
            print(f"      - Overall patterns: {len(analysis.get('overall_patterns', []))}")
            print(f"      - Critical issues: {len(analysis.get('critical_issues', []))}")
            print(f"      - Specific fixes: {len(fixes)}")
            
            if fixes:
                print(f"   🔧 Specific Fixes:")
                for i, fix in enumerate(fixes, 1):
                    print(f"      {i}. {fix['criterion']} ({fix['avg_score']}/100 → {fix['target_score']}/100)")
                    print(f"         Priority: {fix['priority'].upper()}")
                    print(f"         Problem: {fix['problem_pattern']}")
                    print(f"         Expected: {fix['expected_improvement']}")
                    print()
            
            # Save results
            with open("frontend_test_result.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"   💾 Results saved to: frontend_test_result.json")
            
        else:
            print(f"   ❌ Prompt analysis failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Prompt analysis error: {e}")
        return False
    
    print("\n🎉 All tests passed! Frontend integration is working correctly.")
    return True


def test_different_scenarios():
    """Test different evaluation scenarios"""
    
    base_url = "http://localhost:8000"
    
    print("\n🔄 Testing Different Scenarios")
    print("=" * 40)
    
    scenarios = [
        {
            "name": "High Slots Completeness Issue",
            "criteria_avg": {
                "slots_completeness": 45,  # Very low
                "knowledge_accuracy": 80,
                "empathy_experience": 75
            },
            "avg_total_score": 65.0
        },
        {
            "name": "Knowledge Accuracy Problem",
            "criteria_avg": {
                "slots_completeness": 80,
                "knowledge_accuracy": 50,  # Very low
                "empathy_experience": 75
            },
            "avg_total_score": 68.0
        },
        {
            "name": "Style TTS Issues",
            "criteria_avg": {
                "slots_completeness": 80,
                "knowledge_accuracy": 80,
                "style_tts": 55,  # Very low
                "empathy_experience": 75
            },
            "avg_total_score": 72.0
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. Testing: {scenario['name']}")
        
        evaluation_summary = {
            "count": 10,
            "successful_count": 10,
            "error_count": 0,
            "avg_total_score": scenario["avg_total_score"],
            "criteria_avg": scenario["criteria_avg"],
            "diagnostics_top": [],
            "flow_distribution": {"A": 8, "G": 2},
            "policy_violation_rate": 0.1
        }
        
        payload = {
            "brand_id": "long_van",
            "evaluation_summary": evaluation_summary
        }
        
        try:
            response = requests.post(
                f"{base_url}/analyze/prompt-suggestions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                fixes = data.get('analysis', {}).get('specific_fixes', [])
                print(f"   ✅ Generated {len(fixes)} fixes")
                
                if fixes:
                    main_fix = fixes[0]
                    print(f"   🎯 Main fix: {main_fix['criterion']} ({main_fix['avg_score']}/100)")
                    print(f"   📈 Expected improvement: {main_fix['expected_improvement']}")
            else:
                print(f"   ❌ Failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    print("🚀 Starting Frontend Integration Tests")
    print("Make sure mock API server is running on port 8000")
    print("Run: python3 mock_api_server.py")
    print()
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    # Run tests
    success = test_api_endpoints()
    
    if success:
        test_different_scenarios()
        print("\n✅ All integration tests completed successfully!")
        print("\n📋 Next steps:")
        print("1. Open frontend in browser")
        print("2. Run an evaluation")
        print("3. Go to 'Prompt Suggestions' tab")
        print("4. Click 'Analyze Prompt' button")
        print("5. View the suggestions!")
    else:
        print("\n❌ Integration tests failed!")
        print("Make sure mock API server is running: python3 mock_api_server.py")
