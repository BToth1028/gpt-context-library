#!/usr/bin/env python3
"""
Test script for cursor-mcp-utils
Verifies all utilities work correctly
"""

import sys
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cursor_mcp_utils import (
    hash_content,
    norm_text,
    hash_sha256,
    iso_utc,
    unix_timestamp,
    date_str,
    time_str,
    generate_uuid5,
    generate_upsert_id,
    generate_chat_id,
    get_runtime_versions,
    get_git_info,
    get_env_context,
)


def test_hashing():
    print("\n" + "=" * 60)
    print("TESTING: Hashing Module (VMS S03_VECT.py)")
    print("=" * 60)
    
    # Test normalization
    text = "Some   text with    extra    spaces"
    normalized = norm_text(text)
    print(f"Original:   '{text}'")
    print(f"Normalized: '{normalized}'")
    assert normalized == "Some text with extra spaces", "Normalization failed"
    print("✅ Normalization works")
    
    # Test content hashing
    hash1 = hash_content("test")
    hash2 = hash_content("test")
    hash3 = hash_content("different")
    print(f"\nHash('test'): {hash1}")
    print(f"Hash('test'): {hash2}")
    print(f"Hash('different'): {hash3}")
    assert hash1 == hash2, "Same input should produce same hash"
    assert hash1 != hash3, "Different input should produce different hash"
    assert len(hash1) == 64, "SHA256 should be 64 hex chars"
    print("✅ Content hashing works (deterministic)")
    
    # Test raw bytes hashing
    hash4 = hash_sha256(b"binary data")
    print(f"Hash(bytes): {hash4}")
    assert len(hash4) == 64, "SHA256 should be 64 hex chars"
    print("✅ Byte hashing works")


def test_timestamps():
    print("\n" + "=" * 60)
    print("TESTING: Timestamps Module (VMS S03_VECT.py Enhanced)")
    print("=" * 60)
    
    # Test ISO UTC
    ts = iso_utc()
    print(f"ISO UTC: {ts}")
    assert "T" in ts and "Z" in ts, "Should be ISO8601 with timezone"
    print("✅ ISO UTC works")
    
    # Test Unix timestamp
    unix = unix_timestamp()
    print(f"Unix timestamp: {unix}")
    assert unix > 1700000000, "Should be recent timestamp"
    print("✅ Unix timestamp works")
    
    # Test date/time strings
    date = date_str()
    time = time_str()
    print(f"Date: {date}")
    print(f"Time: {time}")
    assert len(date) == 10 and date.count('-') == 2, "Should be YYYY-MM-DD"
    assert len(time) == 8 and time.count(':') == 2, "Should be HH:MM:SS"
    print("✅ Date/time formatting works")


def test_deterministic_ids():
    print("\n" + "=" * 60)
    print("TESTING: Deterministic IDs (NEW Phase 1)")
    print("=" * 60)
    
    # Test deterministic upsert IDs
    id1 = generate_upsert_id("chat-123", 5)
    id2 = generate_upsert_id("chat-123", 5)
    id3 = generate_upsert_id("chat-123", 6)
    print(f"Upsert ID (chat-123, 5): {id1}")
    print(f"Upsert ID (chat-123, 5): {id2}")
    print(f"Upsert ID (chat-123, 6): {id3}")
    assert id1 == id2, "Same input should produce same ID"
    assert id1 != id3, "Different turn should produce different ID"
    print("✅ Deterministic upsert IDs work (idempotent)")
    
    # Test random chat IDs
    chat1 = generate_chat_id()
    chat2 = generate_chat_id()
    print(f"\nRandom chat ID 1: {chat1}")
    print(f"Random chat ID 2: {chat2}")
    assert chat1 != chat2, "Random IDs should be different"
    print("✅ Random chat IDs work")


def test_runtime():
    print("\n" + "=" * 60)
    print("TESTING: Runtime Context (NEW Phase 1)")
    print("=" * 60)
    
    # Test runtime versions
    runtime = get_runtime_versions()
    print("\nRuntime Versions:")
    print(json.dumps(runtime, indent=2))
    assert "os" in runtime, "Should have OS"
    assert "python" in runtime, "Should have Python version"
    assert "shell" in runtime, "Should have shell"
    print("✅ Runtime versions captured")
    
    # Test git info
    git = get_git_info(Path("C:\\DEV"))
    if git:
        print("\nGit Info:")
        print(json.dumps(git, indent=2))
        assert "branch" in git, "Should have branch"
        assert "commit" in git, "Should have commit"
        print("✅ Git info captured")
    else:
        print("⚠️  Not a git repository (skipped)")
    
    # Test environment context
    env = get_env_context()
    print("\nEnvironment Context:")
    print(json.dumps(env, indent=2))
    assert "working_dir" in env, "Should have working directory"
    assert "os" in env, "Should have OS"
    print("✅ Environment context captured")


def test_integration():
    print("\n" + "=" * 60)
    print("TESTING: Full Integration")
    print("=" * 60)
    
    # Simulate complete metadata capture
    message_text = "Test message for integration"
    chat_id = generate_chat_id()
    turn_id = 1
    
    metadata = {
        # Content hashing (VMS pattern)
        "content_sha256": hash_content(message_text),
        "upsert_id": generate_upsert_id(chat_id, turn_id),
        
        # Timestamps
        "ts": iso_utc(),
        "unix_timestamp": unix_timestamp(),
        "date": date_str(),
        "time": time_str(),
        
        # Runtime context (Phase 1)
        "runtime": get_runtime_versions(),
        
        # Environment
        "environment": get_env_context(),
        
        # Git (if available)
        "git": get_git_info(Path("C:\\DEV")),
        
        # Session
        "chat_id": chat_id,
        "turn_id": turn_id,
    }
    
    print("\nComplete Metadata:")
    print(json.dumps(metadata, indent=2, default=str))
    
    # Verify idempotence
    metadata2 = {
        "content_sha256": hash_content(message_text),
        "upsert_id": generate_upsert_id(chat_id, turn_id),
    }
    
    assert metadata["content_sha256"] == metadata2["content_sha256"], "Content hash should match"
    assert metadata["upsert_id"] == metadata2["upsert_id"], "Upsert ID should match (idempotent)"
    print("\n✅ Integration test passed - idempotent upserts work!")


def main():
    print("\n" + "=" * 60)
    print("CURSOR MCP UTILS - TEST SUITE")
    print("=" * 60)
    
    try:
        test_hashing()
        test_timestamps()
        test_deterministic_ids()
        test_runtime()
        test_integration()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nUtilities are ready for production use!")
        print("Reuses VMS patterns + Phase 1 enhancements")
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

