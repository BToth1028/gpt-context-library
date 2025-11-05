import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "libs"))

from cursor_mcp_utils import (
    hash_content,
    iso_utc,
    unix_timestamp,
    generate_upsert_id,
)
from .redact import redact_sensitive
from .qdrant_payload import build_payload

try:
    from qdrant_client import QdrantClient

    QDRANT_CLIENT_AVAILABLE = True
except ImportError:
    QDRANT_CLIENT_AVAILABLE = False

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "cursor-chats")
MCP_HISTORY_LIMIT = int(os.getenv("MCP_HISTORY_LIMIT", "200"))
MCP_RECENT_SECONDS = int(os.getenv("MCP_RECENT_SECONDS", "3600"))


def history_list(since_ts: Optional[datetime] = None, limit: int = None) -> List[Dict[str, Any]]:
    if since_ts is None:
        since_ts = datetime.now(timezone.utc) - timedelta(seconds=MCP_RECENT_SECONDS)

    if limit is None:
        limit = MCP_HISTORY_LIMIT

    if not QDRANT_CLIENT_AVAILABLE:
        return []

    try:
        client = QdrantClient(url=QDRANT_URL)
        result = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter={"must": [{"key": "unix_timestamp", "range": {"gte": int(since_ts.timestamp())}}]},
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return result[0] if result else []
    except Exception as e:
        print(f"[ERROR] history_list failed: {e}")
        return []


def qdrant_store(
    text: str,
    metadata: Dict[str, Any],
    chat_id: str = None,
    turn_id: int = None,
) -> Optional[str]:
    if not QDRANT_CLIENT_AVAILABLE:
        print("[ERROR] qdrant-client not installed. Run: pip install qdrant-client fastembed")
        return None

    text_clean, was_redacted = redact_sensitive(text)

    if chat_id and turn_id:
        point_id = generate_upsert_id(chat_id, turn_id)
    else:
        import uuid

        point_id = str(uuid.uuid4())

    payload = build_payload(
        text=text_clean,
        metadata=metadata,
        content_hash=hash_content(text),
        was_redacted=was_redacted,
    )

    try:
        from fastembed import TextEmbedding

        client = QdrantClient(url=QDRANT_URL)
        embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        embeddings = list(embedding_model.embed([text_clean]))

        from qdrant_client.models import PointStruct

        point = PointStruct(
            id=point_id, vector=embeddings[0].tolist(), payload=payload["metadata"]
        )

        client.upsert(collection_name=QDRANT_COLLECTION, points=[point])
        return point_id
    except Exception as e:
        print(f"[ERROR] qdrant_store failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def qdrant_find(
    query: str,
    k: int = 5,
    filter_: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    if not QDRANT_CLIENT_AVAILABLE:
        return []

    try:
        from fastembed import TextEmbedding

        client = QdrantClient(url=QDRANT_URL)
        embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = list(embedding_model.embed([query]))[0].tolist()

        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_embedding,
            limit=k,
            query_filter=filter_,
        )
        return results
    except Exception as e:
        print(f"[ERROR] qdrant_find failed: {e}")
        return []
