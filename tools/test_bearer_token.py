#!/usr/bin/env python3
"""
Simple script to test Bearer token validity
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.bulk_list_evaluate import test_bearer_token
import requests

def main():
    # Get token from environment or prompt
    bearer_token = os.getenv("BEARER_TOKEN")
    if not bearer_token:
        bearer_token = input("Enter Bearer Token: ").strip()
    
    if not bearer_token:
        print("❌ No bearer token provided")
        return 1
    
    base_url = "https://live-demo.agenticai.pro.vn"
    
    print(f"🧪 Testing bearer token...")
    print(f"📍 Base URL: {base_url}")
    print(f"🔑 Token length: {len(bearer_token)} chars")
    print(f"🔑 Token preview: {bearer_token[:20]}...")
    print()
    
    try:
        # Test token
        is_valid = test_bearer_token(base_url, bearer_token)
        
        if is_valid:
            print("✅ Bearer token is VALID!")
            
            # Try to get some sample data
            print("\n🔍 Testing actual API call...")
            headers = {"Authorization": f"Bearer {bearer_token}"}
            response = requests.get(
                f"{base_url}/api/conversations",
                headers=headers,
                params={"page": 1, "page_size": 5},
                timeout=10
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                conv_count = len(data.get("conversations", []))
                print(f"✅ Successfully fetched {conv_count} conversations")
            else:
                print(f"⚠️ Response: {response.text[:200]}")
            
        else:
            print("❌ Bearer token is INVALID or EXPIRED")
            return 1
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
