"""
Shared utilities for Cursor MCP + Vector Management System
Reuses production-tested code from VMS
"""

from .hashing import hash_content, hash_sha256, norm_text
from .timestamps import iso_utc, unix_timestamp, date_str, time_str
from .deterministic_ids import generate_uuid5, generate_upsert_id
from .runtime import get_runtime_versions, get_git_info, get_env_context

__all__ = [
    # Hashing (from S03_VECT.py)
    'hash_content',
    'hash_sha256',
    'norm_text',
    
    # Timestamps (from S03_VECT.py + enhancements)
    'iso_utc',
    'unix_timestamp',
    'date_str',
    'time_str',
    
    # Deterministic IDs (new - Phase 1)
    'generate_uuid5',
    'generate_upsert_id',
    
    # Runtime context (new - Phase 1)
    'get_runtime_versions',
    'get_git_info',
    'get_env_context',
]

