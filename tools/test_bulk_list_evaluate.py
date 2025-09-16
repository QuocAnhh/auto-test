#!/usr/bin/env python3
"""
Test script for bulk_list_evaluate.py
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.bulk_list_evaluate import select_conversations, make_summary_enhanced

def test_select_conversations():
    """Test conversation selection logic"""
    print("Testing select_conversations...")
    
    # Mock conversations data
    conversations = [
        {
            "conversation_id": "conv1",
            "messages": ["msg1", "msg2"],
            "created_at": "2024-01-01T10:00:00Z"
        },
        {
            "conversation_id": "conv2", 
            "messages": ["msg1", "msg2", "msg3"],
            "created_at": "2024-01-02T10:00:00Z"
        },
        {
            "conversation_id": "conv3",
            "messages": ["msg1"],
            "created_at": "2024-01-03T10:00:00Z"
        },
        {
            "conversation_id": "conv4",
            "messages": ["msg1", "msg2", "msg3", "msg4"],
            "created_at": "2024-01-04T10:00:00Z"
        }
    ]
    
    # Test head strategy
    selected = select_conversations(conversations, take=2, strategy="head")
    assert len(selected) == 2
    print(f"✓ Head strategy: {[c['conversation_id'] for c in selected]}")
    
    # Test newest strategy
    selected = select_conversations(conversations, take=2, strategy="newest")
    assert len(selected) == 2
    assert selected[0]["conversation_id"] == "conv4" # Most recent first
    print(f"✓ Newest strategy: {[c['conversation_id'] for c in selected]}")
    
    # Test length sorting
    selected = select_conversations(conversations, take=2, sort_by="length", order="desc")
    assert len(selected) == 2
    assert len(selected[0]["messages"]) >= len(selected[1]["messages"])
    print(f"✓ Length sort desc: {[(c['conversation_id'], len(c['messages'])) for c in selected]}")
    
    # Test minimum turns filter
    selected = select_conversations(conversations, take=10, min_turns=3)
    assert len(selected) == 2  # Only conv2 and conv4 have >= 3 messages
    print(f"✓ Min turns filter: {[c['conversation_id'] for c in selected]}")
    
    print("select_conversations tests passed!\n")

def test_make_summary():
    """Test summary creation"""
    print("Testing make_summary_enhanced...")
    
    # Mock evaluation results
    results = [
        {
            "conversation_id": "conv1",
            "brand_id": "son_hai",
            "result": {
                "total_score": 85,
                "flow_type": "informational"
            },
            "metrics": {
                "policy_violations": 0,
                "diagnostics": {
                    "operational_readiness": {"greeting": 1, "escalation": 0},
                    "risk_compliance": {"privacy": 0}
                }
            }
        },
        {
            "conversation_id": "conv2",
            "brand_id": "son_hai", 
            "result": {
                "total_score": 92,
                "flow_type": "transactional"
            },
            "metrics": {
                "policy_violations": 1,
                "diagnostics": {
                    "operational_readiness": {"greeting": 1, "escalation": 1},
                    "risk_compliance": {"privacy": 1}
                }
            }
        },
        {
            "conversation_id": "conv3",
            "error": "Some error occurred"
        }
    ]
    
    summary = make_summary_enhanced(results)
    
    # Check basic structure
    assert "count" in summary
    assert "brand_distribution" in summary
    assert "top_diagnostics_detailed" in summary
    assert summary["count"] == 3
    assert summary["brand_distribution"]["son_hai"] == 2
    
    print(f"✓ Summary created with {summary['count']} results")
    print(f"✓ Brand distribution: {summary['brand_distribution']}")
    print(f"✓ Top diagnostics: {list(summary['top_diagnostics_detailed'].keys())}")
    
    print("make_summary_enhanced tests passed!\n")

if __name__ == "__main__":
    print("Running bulk_list_evaluate.py tests\n")
    test_select_conversations()
    test_make_summary()
    print("All tests passed! ✅")
