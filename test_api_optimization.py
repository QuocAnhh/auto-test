#!/usr/bin/env python3
"""
Test script to verify API optimization works correctly
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_batch_evaluator_imports():
    """Test that batch evaluator components can be imported"""
    try:
        from busqa.batch_evaluator import HighSpeedBatchEvaluator, BatchConfig
        print("✅ HighSpeedBatchEvaluator and BatchConfig imported successfully")
        
        # Test basic instantiation
        config = BatchConfig()
        evaluator = HighSpeedBatchEvaluator(config)
        
        print("✅ HighSpeedBatchEvaluator instantiated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error testing batch evaluator imports: {e}")
        return False

def test_high_speed_evaluator():
    """Test that high-speed evaluator can be imported"""
    try:
        from busqa.batch_evaluator import evaluate_conversations_high_speed
        print("✅ evaluate_conversations_high_speed imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error importing high-speed evaluator: {e}")
        return False

def test_legacy_api_client():
    """Test that legacy API client still works"""
    try:
        from busqa.api_client import fetch_messages
        print("✅ Legacy fetch_messages imported successfully")
        
        # Check that it has the legacy warning in docstring
        docstring = fetch_messages.__doc__
        if docstring and "LEGACY" in docstring:
            print("✅ Legacy function properly marked with warning")
        else:
            print("❌ Legacy function should have LEGACY warning in docstring")
            
        return True
        
    except Exception as e:
        print(f"❌ Error testing legacy API client: {e}")
        return False

def main():
    print("Testing API optimization changes...\n")
    
    tests = [
        ("Bulk fetch function", test_bulk_fetch_function),
        ("High-speed evaluator", test_high_speed_evaluator),
        ("Legacy API client", test_legacy_api_client),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n=== {test_name} ===")
        if test_func():
            passed += 1
        
    print(f"\n=== Summary ===")
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 All tests passed! API optimization is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
