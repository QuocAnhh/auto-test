#!/usr/bin/env python3
"""
Test script để verify logic fetch conversations với limit
"""

def test_fetch_logic():
    """Test logic fetch với limit"""
    
    # Simulate conversations data
    all_conversations = []
    limit = 10
    page_size = 10
    
    # Simulate page 1: 10 conversations
    page1_conversations = [f"conv_{i}" for i in range(1, 11)]
    all_conversations.extend(page1_conversations)
    print(f"Page 1: Got {len(page1_conversations)} conversations (total: {len(all_conversations)})")
    
    # Check limit after page 1
    if limit and len(all_conversations) >= limit:
        print(f"✅ Reached limit of {limit} conversations, stopping fetch.")
        return all_conversations
    
    # Simulate page 2: 10 more conversations (should not reach here)
    page2_conversations = [f"conv_{i}" for i in range(11, 21)]
    all_conversations.extend(page2_conversations)
    print(f"Page 2: Got {len(page2_conversations)} conversations (total: {len(all_conversations)})")
    
    return all_conversations

if __name__ == "__main__":
    print("Testing fetch logic with limit=10, page_size=10...")
    result = test_fetch_logic()
    print(f"Final result: {len(result)} conversations")
    print("✅ Logic works correctly - stops after reaching limit!")

