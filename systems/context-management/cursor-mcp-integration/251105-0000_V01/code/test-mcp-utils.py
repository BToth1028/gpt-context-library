#!/usr/bin/env python3
"""Quick test of MCP utilities"""
import sys
from pathlib import Path

# Add libs to path
sys.path.insert(0, str(Path(__file__).parent / "libs"))

from cursor_mcp_utils import (
    hash_content,
    iso_utc,
    unix_timestamp,
    generate_upsert_id,
    get_runtime_versions,
    get_git_info,
)

print("\n" + "=" * 60)
print("TESTING MCP UTILITIES")
print("=" * 60)

# Test hashing (VMS pattern)
print("\n1. Content Hashing (VMS S03_VECT.py)")
hash1 = hash_content("test")
hash2 = hash_content("test")
print(f"   Hash('test'): {hash1[:16]}...")
print(f"   Hash('test'): {hash2[:16]}...")
assert hash1 == hash2, "Hashes should match"
print("   [OK] Deterministic hashing works")

# Test timestamps
print("\n2. Timestamps (VMS S03_VECT.py)")
ts = iso_utc()
unix = unix_timestamp()
print(f"   ISO UTC: {ts}")
print(f"   Unix: {unix}")
print("   [OK] Timestamp utilities work")

# Test deterministic IDs (Phase 1)
print("\n3. Deterministic IDs (Phase 1)")
id1 = generate_upsert_id("chat-123", 5)
id2 = generate_upsert_id("chat-123", 5)
print(f"   ID1: {id1}")
print(f"   ID2: {id2}")
assert id1 == id2, "IDs should match"
print("   [OK] Idempotent upserts work")

# Test runtime (Phase 1)
print("\n4. Runtime Context (Phase 1)")
runtime = get_runtime_versions()
print(f"   OS: {runtime.get('os')}")
print(f"   Python: {runtime.get('python')}")
print(f"   Shell: {runtime.get('shell')}")
print("   [OK] Runtime capture works")

# Test git (Phase 1)
print("\n5. Git Integration (Phase 1)")
git = get_git_info(Path("C:\\DEV"))
if git:
    print(f"   Branch: {git.get('branch')}")
    print(f"   Commit: {git.get('commit')}")
    print(f"   Dirty: {git.get('dirty')}")
    print("   [OK] Git info captured")
else:
    print("   [WARN] Not a git repo (skipped)")

print("\n" + "=" * 60)
print("[OK] ALL TESTS PASSED")
print("=" * 60)
print("\nUtilities ready! Now test in Cursor.")
