"""
Deterministic ID generation for idempotent upserts
NEW - Phase 1 enhancement based on ChatGPT feedback
"""

import uuid
import hashlib
from typing import Optional


# Namespace UUID for this project (generated once, fixed)
PROJECT_NAMESPACE = uuid.UUID('8f7e6d5c-4b3a-2918-1a0b-fedcba987654')


def generate_uuid5(namespace: uuid.UUID, name: str) -> str:
    """
    Generate UUIDv5 (deterministic) from namespace + name
    Based on ChatGPT feedback for idempotent upserts
    
    Args:
        namespace: Namespace UUID
        name: Name to hash
        
    Returns:
        UUID string
    """
    return str(uuid.uuid5(namespace, name))


def generate_upsert_id(chat_id: str, turn_id: int) -> str:
    """
    Generate deterministic upsert ID for Qdrant points
    Same (chat_id, turn_id) always produces same ID
    
    Args:
        chat_id: Chat session ID
        turn_id: Turn number in conversation
        
    Returns:
        Deterministic UUID string
    """
    name = f"{chat_id}|{turn_id}"
    return generate_uuid5(PROJECT_NAMESPACE, name)


def generate_chat_id() -> str:
    """
    Generate new random chat session ID
    
    Returns:
        UUIDv4 string
    """
    return str(uuid.uuid4())


def generate_content_id(content: str) -> str:
    """
    Generate deterministic ID from content hash
    
    Args:
        content: Text content
        
    Returns:
        UUID based on content SHA256
    """
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
    # Use first 32 hex chars to make a valid UUID
    uuid_str = f"{content_hash[:8]}-{content_hash[8:12]}-{content_hash[12:16]}-{content_hash[16:20]}-{content_hash[20:32]}"
    return uuid_str

