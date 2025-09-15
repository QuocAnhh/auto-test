#!/usr/bin/env python3
"""
Script để test batch evaluation với nhiều conversations
Tạo fake conversation IDs để test performance
"""
import random
import string
from pathlib import Path

def generate_fake_conversation_ids(count: int) -> list:
    """Tạo fake conversation IDs để test"""
    fake_ids = []
    for i in range(count):
        # Format: conv_yyyymmdd_randomstring
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        fake_id = f"conv_20240916_{random_str}"
        fake_ids.append(fake_id)
    return fake_ids

def create_test_conversations_file(count: int, filename: str = "test_50_conversations.txt"):
    """Tạo file chứa conversation IDs để test"""
    fake_ids = generate_fake_conversation_ids(count)
    
    with open(filename, 'w') as f:
        for conv_id in fake_ids:
            f.write(f"{conv_id}\n")
    
    print(f"✅ Created {filename} with {count} conversation IDs")
    print(f"📂 File path: {Path(filename).absolute()}")
    return filename

def print_sample_command(conversations_file: str, count: int):
    """In ra sample command để chạy batch evaluation"""
    print(f"\n🚀 Sample command to test {count} conversations:")
    print("export GEMINI_API_KEY=your_api_key_here")
    print(f"python evaluate_cli.py \\")
    print(f"  --conversations-file {conversations_file} \\")
    print(f"  --brand-prompt-path brands/son_hai/prompt.md \\")
    print(f"  --max-concurrency 20 \\")
    print(f"  --output batch_50_results.json \\")
    print(f"  --verbose")
    
    print(f"\n💡 Hoặc test với conversation IDs trực tiếp:")
    print(f"python evaluate_cli.py \\")
    print(f"  --conversation-ids conv1,conv2,conv3 \\")
    print(f"  --brand-prompt-path brands/son_hai/prompt.md \\")
    print(f"  --max-concurrency 15")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test conversation IDs for batch evaluation")
    parser.add_argument("--count", type=int, default=50, help="Number of conversation IDs to generate")
    parser.add_argument("--output", default="test_conversations.txt", help="Output file name")
    
    args = parser.parse_args()
    
    print(f"🎯 Generating {args.count} fake conversation IDs...")
    
    # Tạo file test conversations
    conversations_file = create_test_conversations_file(args.count, args.output)
    
    # In sample commands
    print_sample_command(conversations_file, args.count)
    
    print(f"\n⚠️  Lưu ý: Đây là fake IDs để test performance.")
    print(f"   Để test thật, thay bằng conversation IDs thật từ hệ thống.")
