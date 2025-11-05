"""
Content hashing utilities
Reused from S03_VECT.py with enhancements
"""

import hashlib
from typing import Optional


def norm_text(s: str, max_chars: int = 8000) -> str:
    """
    Normalize text: collapse whitespace and truncate
    SOURCE: S03_VECT.py line 83-88
    """
    if not s:
        return ""
    s = " ".join(s.strip().split())
    return s[:max_chars]


def hash_content(s: str) -> str:
    """
    Generate SHA256 content hash for deduplication
    SOURCE: S03_VECT.py line 91-93 (_hash_key)
    
    Args:
        s: Text to hash
        
    Returns:
        64-character hex string (SHA256)
    """
    return hashlib.sha256(norm_text(s).encode("utf-8")).hexdigest()


def hash_sha256(data: bytes) -> str:
    """
    Generate SHA256 hash of raw bytes
    
    Args:
        data: Raw bytes to hash
        
    Returns:
        64-character hex string (SHA256)
    """
    return hashlib.sha256(data).hexdigest()


def hash_text_sha256(text: str, normalize: bool = True) -> str:
    """
    Generate SHA256 hash of text
    
    Args:
        text: Text to hash
        normalize: Whether to normalize whitespace first
        
    Returns:
        64-character hex string (SHA256)
    """
    if normalize:
        text = norm_text(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

