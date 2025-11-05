#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S03_VECT.py (HARDENED VERSION - Fixed Ollama 500 Errors)
Production-Ready Vectorization Engine

IMPROVEMENTS:
- Token bucket rate limiting (adaptive, no busy-wait)
- Circuit breaker with exponential cooldown
- Content-hash deduplication cache (SQLite)
- Dead letter queue (DLQ) for failed embeddings
- Connection pooling (httpx)
- Only marks successful embeddings as processed
- Uses nomic-embed-text by default (lighter, faster)

USAGE:
    python S03_VECT.py                          # Auto-detect mode (instant/bulk)
    python S03_VECT.py --mode instant           # Process all unprocessed
    python S03_VECT.py --mode bulk --batches 5  # Process 5 batches only
    python S03_VECT.py --target qdrant          # Write to Qdrant only
    python S03_VECT.py --target mvm             # Write to MVM.db only
    python S03_VECT.py --target both            # Write to both (default)

Dependencies: httpx, qdrant-client (optional, only if --target qdrant/both)
"""

from __future__ import annotations
import os, sys, json, time, asyncio, random, sqlite3, argparse, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import defaultdict

UTC = timezone.utc

# =====================================================================================
# CONFIG DEFAULTS (aligned with S00_HEALTH and S01_EXTRACTOR)
# =====================================================================================
CONFIG_DEFAULTS = {
    "expected_embed_model": "nomic-embed-text",
    "expected_dims": 768,
    "ollama_url": "http://localhost:11434",
    "qdrant_url": "http://localhost:6333",
    "qdrant_collection": "chat_vectors",
    "qdrant_distance": "Cosine",
    "paths": {
        "data_link_rel": "30_DATA",
        "output_rel": "40_RUNTIME/03_VECTOR/01_OUTPUT",
        "config_rel": "50_CONFIG/HEALTH_CONFIG.json",
        "state_rel": "00_STATE/MVM_STATE.db",
        "proc_rel": "01_PROC/MVM_PROC.db",
        "mvm_rel": "02_VECT/MVM_VECT.db",
    },
    "file_prefix": "vectorization_",
    "file_ext": ".ndjson",
    "rate_limit": {
        "max_concurrent": 1,
        "min_interval_ms": 2000,
    },
    "retry_policy": {
        "attempts": 3,
        "base_ms": 1000,
        "max_ms": 5000,
    },
    "circuit_breaker": {
        "failure_threshold": 10,
        "pause_duration_s": 30,
    },
}


# =====================================================================================
# UTILITIES
# =====================================================================================
def _iso_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _day() -> str:
    return datetime.now().strftime("%Y%m%d")


def _norm_text(s: str, max_chars: int = 8000) -> str:
    """Normalize text: collapse whitespace and truncate"""
    if not s:
        return ""
    s = " ".join(s.strip().split())
    return s[:max_chars]


def _hash_key(s: str) -> str:
    """Generate content hash for deduplication"""
    return hashlib.sha256(_norm_text(s).encode("utf-8")).hexdigest()


# =====================================================================================
# NDJSON LOGGING
# =====================================================================================
_log_handle = None
_log_path: Optional[Path] = None


def init_logging(out_dir: Path, file_prefix: str, file_ext: str):
    """Initialize NDJSON log file with CURRENT symlink"""
    out_dir.mkdir(parents=True, exist_ok=True)
    global _log_path, _log_handle
    _log_path = out_dir / f"{file_prefix}_{_day()}{file_ext}"
    if not _log_path.exists():
        with open(_log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"_meta": "created", "ts": _iso_utc(), "version": "2.1"}) + "\n")
    _log_handle = open(_log_path, "a", encoding="utf-8")

    _symlink = out_dir / f"{file_prefix}_CURRENT{file_ext}"
    try:
        if _symlink.exists() or _symlink.is_symlink():
            _symlink.unlink()
        _symlink.symlink_to(_log_path.name)
    except Exception as e:
        log_event({"event": "symlink_failed", "level": "WARN", "error": str(e)})

    log_event({"event": "vectorization_start"})


def log_event(event: Dict[str, Any]):
    """Write event to NDJSON log"""
    payload = {"ts": _iso_utc(), "level": event.get("level", "INFO"), **event}
    if _log_handle:
        _log_handle.write(json.dumps(payload) + "\n")
        _log_handle.flush()


def close_logging():
    """Close NDJSON log file"""
    if _log_handle:
        try:
            log_event({"event": "vectorization_complete"})
            _log_handle.close()
        except:
            pass


# =====================================================================================
# VECTORIZATION ENGINE (HARDENED)
# =====================================================================================
class VectorizerEngine:
    def __init__(self, config: Dict[str, Any], proc_db: Path, mvm_db: Path, target: str = "both"):
        self.config = config
        self.proc_db = proc_db
        self.mvm_db = mvm_db
        self.target = target

        self.http_client = None
        self.qdrant_client = None
        self.embedding_dim = None
        self.model = config["expected_embed_model"]
        self.embed_url = f"{config['ollama_url']}/api/embeddings"

        # Token bucket rate limiting
        self.tokens = 2.0
        self.token_last = time.time()
        self.tokens_per_sec = 1000.0 / config["rate_limit"]["min_interval_ms"]
        self.bucket_size = 2.0

        # Circuit breaker
        self.cb_failures = 0
        self.cb_threshold = config.get("circuit_breaker", {}).get("failure_threshold", 10)
        self.cb_pause_s = config.get("circuit_breaker", {}).get("pause_duration_s", 30)

        # Stats
        self.stats = defaultdict(int)
        self.stats["cache_hits"] = 0
        self.stats["circuit_trips"] = 0

        # Cache initialization flag
        self._cache_initialized = False

    async def initialize(self) -> bool:
        """Initialize HTTP client for Ollama and optionally Qdrant"""
        print("\n" + "=" * 80)
        print("INITIALIZING VECTORIZER (HARDENED VERSION)")
        print("=" * 80 + "\n")

        try:
            # Initialize Ollama HTTP client with connection pooling
            import httpx

            self.http_client = httpx.AsyncClient(
                timeout=60,
                limits=httpx.Limits(max_keepalive_connections=1, max_connections=1, keepalive_expiry=30.0),
                transport=httpx.AsyncHTTPTransport(retries=0),
            )

            # Health check Ollama
            print(f"[CHECK] Testing Ollama at {self.embed_url}...")
            for attempt in range(3):
                try:
                    r = await self.http_client.post(self.embed_url, json={"model": self.model, "prompt": "test warmup"})
                    r.raise_for_status()
                    data = r.json()
                    emb = data.get("embedding")
                    if isinstance(emb, list) and len(emb) > 0:
                        self.embedding_dim = len(emb)
                        print(f"[OK] Ollama healthy")
                        print(f"  Model: {self.model}")
                        print(f"  Dimensions: {self.embedding_dim}")
                        log_event(
                            {"event": "ollama_initialized", "model": self.model, "dimensions": self.embedding_dim}
                        )
                        break
                except Exception as e:
                    if attempt < 2:
                        print(f"[WARN] Ollama check attempt {attempt + 1}/3 failed: {e}")
                        await asyncio.sleep(2**attempt)
                    else:
                        print(f"[ERROR] Ollama health check failed after 3 attempts")
                        log_event({"level": "ERROR", "event": "ollama_init_failed", "error": str(e)})
                        return False

            # Initialize Qdrant if needed
            if self.target in ["qdrant", "both"]:
                if not await self._init_qdrant():
                    if self.target == "qdrant":
                        print("[ERROR] Qdrant required but initialization failed")
                        return False
                    else:
                        print("[WARN] Qdrant init failed, falling back to MVM.db only")
                        self.target = "mvm"

            # Validate MVM.db and create tables
            if self.target in ["mvm", "both"]:
                if not self.mvm_db.exists():
                    print(f"[ERROR] MVM.db not found: {self.mvm_db}")
                    return False
                print(f"[OK] MVM.db found: {self.mvm_db}")

                # Ensure all required tables exist
                await self._ensure_cache_tables()
                print(f"[OK] All tables ready (vectors, embed_cache, embed_dlq)")

            print(f"\n[OK] Vectorizer initialized (target: {self.target})")
            print(f"  Rate limit: {self.tokens_per_sec:.2f} req/sec")
            print(f"  Circuit breaker: {self.cb_threshold} failures")
            return True

        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            log_event({"level": "ERROR", "event": "init_failed", "error": str(e)})
            return False

    async def _ensure_cache_tables(self):
        """Ensure cache and DLQ tables exist (idempotent)"""
        if self._cache_initialized:
            return

        conn = sqlite3.connect(self.mvm_db)

        # Vectors table (main storage)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                state_row_id INTEGER,
                bubble_id TEXT UNIQUE NOT NULL,
                composer_id TEXT,
                CHAT_TIMESTAMP_UTC TEXT,
                message_text TEXT,
                bubble_type_name TEXT,
                vector TEXT,
                vector_model TEXT,
                vector_dimensions INTEGER,
                vectorized_at TEXT
            )
        """
        )

        # Embedding cache (content-hash deduplication)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embed_cache (
                key TEXT PRIMARY KEY,
                vector TEXT NOT NULL,
                model TEXT,
                dims INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_embed_cache_dims ON embed_cache(dims)")

        # Dead letter queue (failed embeddings)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embed_dlq (
                key TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                last_error TEXT,
                attempts INTEGER DEFAULT 0,
                last_attempt_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        self._cache_initialized = True

    async def _init_qdrant(self) -> bool:
        """Initialize Qdrant client and collection"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            qdrant_url = self.config["qdrant_url"]
            if ":" in qdrant_url.split("//")[-1]:
                host, port = qdrant_url.split("//")[-1].split(":")
                port = int(port)
            else:
                host = qdrant_url.split("//")[-1]
                port = 6333

            print(f"[CHECK] Connecting to Qdrant at {host}:{port}...")
            self.qdrant_client = QdrantClient(host=host, port=port)

            health = self.qdrant_client.get_collections()
            print(f"[OK] Qdrant connected")

            collection_name = self.config["qdrant_collection"]
            collections = health.collections

            if not any(c.name == collection_name for c in collections):
                print(f"[INFO] Creating collection: {collection_name}")

                distance_map = {
                    "Cosine": Distance.COSINE,
                    "Euclidean": Distance.EUCLID,
                    "Dot": Distance.DOT,
                }
                distance = distance_map.get(self.config["qdrant_distance"], Distance.COSINE)

                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=self.embedding_dim, distance=distance),
                )
                print(f"[OK] Collection created")
                log_event({"event": "qdrant_collection_created", "collection": collection_name})
            else:
                print(f"[OK] Collection exists: {collection_name}")

            log_event({"event": "qdrant_initialized", "host": host, "port": port, "collection": collection_name})
            return True

        except ImportError:
            print("[WARN] qdrant-client not installed (pip install qdrant-client)")
            log_event({"level": "WARN", "event": "qdrant_import_failed"})
            return False
        except Exception as e:
            print(f"[WARN] Qdrant initialization failed: {e}")
            log_event({"level": "WARN", "event": "qdrant_init_failed", "error": str(e)})
            return False

    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    async def _take_token(self) -> bool:
        """Token bucket rate limiting (adaptive wait, no busy-loop)"""
        now = time.time()
        # Refill tokens based on elapsed time
        self.tokens = min(self.bucket_size, self.tokens + (now - self.token_last) * self.tokens_per_sec)
        self.token_last = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True

        # Calculate time until next token available (adaptive sleep)
        needed = 1.0 - self.tokens
        wait_time = needed / self.tokens_per_sec
        await asyncio.sleep(min(wait_time, 0.5))  # Cap at 0.5s
        return False

    async def _cool_if_cb_open(self):
        """Circuit breaker with exponential backoff for repeated trips"""
        if self.cb_failures >= self.cb_threshold:
            # Exponential backoff for repeated trips (bounded at 5x)
            pause_multiplier = min(self.stats.get("circuit_trips", 0) + 1, 5)
            pause_time = self.cb_pause_s * pause_multiplier

            log_event(
                {
                    "level": "ERROR",
                    "event": "circuit_open",
                    "consecutive_failures": self.cb_failures,
                    "pause_s": pause_time,
                    "trip_count": pause_multiplier,
                }
            )

            print(f"[CIRCUIT BREAKER] Open after {self.cb_failures} failures - cooling {pause_time}s...")
            await asyncio.sleep(pause_time)

            self.cb_failures = 0  # Half-open (try again)
            self.stats["circuit_trips"] += 1

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding with token bucket + circuit breaker + cache"""
        # Ensure cache tables exist
        await self._ensure_cache_tables()

        # Token bucket pacing (no busy-wait)
        while not await self._take_token():
            pass

        text = _norm_text(text)
        if not text:
            self.stats["empty_text"] += 1
            return []

        # Cache check
        k = _hash_key(text)
        try:
            conn = sqlite3.connect(self.mvm_db)
            cur = conn.cursor()
            row = cur.execute("SELECT vector, dims FROM embed_cache WHERE key=?", (k,)).fetchone()
            conn.close()
            if row:
                vec = json.loads(row[0])
                self.stats["cache_hits"] += 1
                log_event({"event": "cache_hit", "key": k[:16]})
                return vec
        except Exception as e:
            log_event({"level": "WARN", "event": "cache_read_failed", "error": str(e)})

        # Circuit breaker gate
        await self._cool_if_cb_open()

        # Retry with exponential backoff
        rp = self.config["retry_policy"]
        for attempt in range(rp["attempts"]):
            try:
                r = await self.http_client.post(self.embed_url, json={"model": self.model, "prompt": text})
                r.raise_for_status()
                data = r.json()
                emb = data.get("embedding")

                if not isinstance(emb, list) or not emb:
                    raise RuntimeError("invalid_embedding_payload")

                vec = [float(x) for x in emb]

                # Write to cache
                try:
                    conn = sqlite3.connect(self.mvm_db)
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR IGNORE INTO embed_cache(key, vector, model, dims) VALUES(?,?,?,?)",
                        (k, json.dumps(vec), self.model, len(vec)),
                    )
                    conn.commit()
                    conn.close()
                except Exception as e2:
                    log_event({"level": "WARN", "event": "cache_write_failed", "error": str(e2)})

                # Success - reset circuit breaker
                self.cb_failures = 0
                self.stats["embeddings_generated"] += 1
                return vec

            except Exception as e:
                self.stats["embedding_errors"] += 1
                self.cb_failures += 1

                if attempt < rp["attempts"] - 1:
                    delay_ms = min(rp["base_ms"] * (2**attempt), rp["max_ms"])
                    jitter = random.uniform(0, delay_ms * 0.1)
                    await asyncio.sleep((delay_ms + jitter) / 1000.0)
                    log_event({"level": "WARN", "event": "embedding_retry", "attempt": attempt + 1, "error": str(e)})
                else:
                    # Final failure - write to DLQ
                    try:
                        conn = sqlite3.connect(self.mvm_db)
                        cur = conn.cursor()
                        cur.execute(
                            """
                            INSERT INTO embed_dlq(key, text, last_error, attempts, last_attempt_at)
                            VALUES(?,?,?,1,datetime('now'))
                            ON CONFLICT(key) DO UPDATE SET
                                last_error=excluded.last_error,
                                attempts=embed_dlq.attempts+1,
                                last_attempt_at=datetime('now')
                        """,
                            (k, text, str(e)),
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e2:
                        log_event({"level": "ERROR", "event": "dlq_write_failed", "error": str(e2)})

                    log_event({"level": "ERROR", "event": "embedding_failed_final", "error": str(e), "key": k[:16]})
                    return None  # Return None (not zero vector)

        return None

    async def drain_dlq(self, max_items: int = 50):
        """Attempt to reprocess failed embeddings from DLQ"""
        try:
            conn = sqlite3.connect(self.mvm_db)
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT key, text FROM embed_dlq WHERE attempts < 10 ORDER BY last_attempt_at ASC LIMIT ?", (max_items,)
            ).fetchall()
            conn.close()

            if not rows:
                return

            print(f"[DLQ DRAIN] Retrying {len(rows)} failed embeddings...")
            log_event({"event": "dlq_drain_start", "count": len(rows)})

            recovered = 0
            for k, text in rows:
                v = await self.generate_embedding(text)
                if v is not None:
                    # Success - remove from DLQ
                    conn = sqlite3.connect(self.mvm_db)
                    cur = conn.cursor()
                    cur.execute("DELETE FROM embed_dlq WHERE key=?", (k,))
                    conn.commit()
                    conn.close()
                    recovered += 1
                    log_event({"event": "dlq_recovered", "key": k[:16]})

            print(f"[DLQ DRAIN] Recovered {recovered}/{len(rows)} embeddings")
            log_event({"event": "dlq_drain_complete", "recovered": recovered, "total": len(rows)})

        except Exception as e:
            log_event({"level": "WARN", "event": "dlq_drain_failed", "error": str(e)})

    def get_queue_size(self) -> int:
        """Get number of unprocessed messages in PROC.db"""
        try:
            conn = sqlite3.connect(self.proc_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chat_data WHERE processed = 0")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"[ERROR] Cannot read PROC queue: {e}")
            log_event({"level": "ERROR", "event": "queue_read_failed", "error": str(e)})
            return 0

    async def vectorize_batch(self, batch_size: int = 10) -> int:
        """Vectorize a batch of unprocessed messages (only mark successes)"""
        try:
            # Read batch from PROC.db
            conn = sqlite3.connect(self.proc_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT rowid, bubble_id, composer_id, created_at_utc, text, bubble_type_name
                FROM chat_data
                WHERE processed = 0
                LIMIT ?
            """,
                (batch_size,),
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return 0

            print(f"[BATCH] Processing {len(rows)} messages...")
            log_event({"event": "batch_start", "size": len(rows)})

            # Generate embeddings - track successes and failures
            vectors = []
            rowids_success = []
            failed = []

            for row in rows:
                rowid = row["rowid"]
                bubble_id = row["bubble_id"]
                composer_id = row["composer_id"]
                timestamp = row["created_at_utc"]
                text = row["text"] or ""
                bubble_type = row["bubble_type_name"]

                # Generate embedding
                vec = await self.generate_embedding(text)

                if vec is None:
                    # Failed - don't mark as processed, will retry later
                    failed.append({"rowid": rowid, "bubble_id": bubble_id})
                    continue

                vectors.append(
                    {
                        "rowid": rowid,
                        "bubble_id": bubble_id,
                        "composer_id": composer_id,
                        "timestamp": timestamp,
                        "text": text,
                        "bubble_type": bubble_type,
                        "vector": vec,
                    }
                )

                rowids_success.append(rowid)

            # Write successful vectors to target(s)
            if vectors:
                if self.target in ["mvm", "both"]:
                    await self._write_to_mvm(vectors)

                if self.target in ["qdrant", "both"]:
                    await self._write_to_qdrant(vectors)

            # Mark ONLY successes as processed
            if rowids_success:
                conn = sqlite3.connect(self.proc_db)
                cursor = conn.cursor()

                placeholders = ",".join("?" * len(rowids_success))
                cursor.execute(f"UPDATE chat_data SET processed = 1 WHERE rowid IN ({placeholders})", rowids_success)

                conn.commit()
                conn.close()

                print(f"[OK] Marked {len(rowids_success)} successful embeddings as processed")
                log_event({"event": "batch_complete", "processed": len(rowids_success), "failed": len(failed)})

            if failed:
                print(f"[WARN] {len(failed)} embeddings failed - will retry later")
                log_event({"level": "WARN", "event": "batch_partial_fail", "failed_count": len(failed)})

            return len(rowids_success)

        except Exception as e:
            print(f"[ERROR] Batch vectorization failed: {e}")
            log_event({"level": "ERROR", "event": "batch_failed", "error": str(e)})
            import traceback

            traceback.print_exc()
            return 0

    async def _write_to_mvm(self, vectors: List[Dict]):
        """Write vectors to MVM.db"""
        try:
            conn = sqlite3.connect(self.mvm_db)
            cursor = conn.cursor()

            for vec in vectors:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO vectors (
                        state_row_id, bubble_id, composer_id, CHAT_TIMESTAMP_UTC,
                        message_text, bubble_type_name, vector, vector_model,
                        vector_dimensions, vectorized_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        vec["rowid"],
                        vec["bubble_id"],
                        vec["composer_id"],
                        vec["timestamp"],
                        vec["text"][:500] if vec["text"] else "",
                        vec["bubble_type"],
                        json.dumps(vec["vector"]),
                        self.model,
                        len(vec["vector"]),
                        _iso_utc(),
                    ),
                )

            conn.commit()
            conn.close()

            print(f"[OK] Wrote {len(vectors)} vectors to MVM.db")
            log_event({"event": "mvm_write_complete", "count": len(vectors)})
            self.stats["mvm_writes"] += len(vectors)

        except Exception as e:
            print(f"[ERROR] MVM.db write failed: {e}")
            log_event({"level": "ERROR", "event": "mvm_write_failed", "error": str(e)})

    async def _write_to_qdrant(self, vectors: List[Dict]):
        """Write vectors to Qdrant"""
        try:
            from qdrant_client.models import PointStruct

            points = []
            for vec in vectors:
                points.append(
                    PointStruct(
                        id=vec["bubble_id"],
                        vector=vec["vector"],
                        payload={
                            "bubble_id": vec["bubble_id"],
                            "composer_id": vec["composer_id"],
                            "timestamp": str(vec["timestamp"]),
                            "text_preview": vec["text"][:500] if vec["text"] else "",
                            "bubble_type": vec["bubble_type"],
                            "vector_model": self.model,
                            "vector_dimensions": len(vec["vector"]),
                            "vectorized_at": _iso_utc(),
                        },
                    )
                )

            self.qdrant_client.upsert(collection_name=self.config["qdrant_collection"], points=points)

            print(f"[OK] Wrote {len(points)} vectors to Qdrant")
            log_event({"event": "qdrant_write_complete", "count": len(points)})
            self.stats["qdrant_writes"] += len(points)

        except Exception as e:
            print(f"[ERROR] Qdrant write failed: {e}")
            log_event({"level": "ERROR", "event": "qdrant_write_failed", "error": str(e)})

    async def run_instant_mode(self) -> int:
        """Instant mode: vectorize all unprocessed messages"""
        # Drain DLQ first
        await self.drain_dlq(max_items=25)

        queue_size = self.get_queue_size()

        if queue_size == 0:
            print("[INFO] No unprocessed messages in queue")
            return 0

        print(f"\n[MODE] INSTANT - Processing all {queue_size} unprocessed messages")
        log_event({"event": "mode_instant", "queue_size": queue_size})

        total = 0
        while self.get_queue_size() > 0:
            count = await self.vectorize_batch(batch_size=10)
            if count == 0:
                break
            total += count

        print(f"\n[OK] Instant mode complete - vectorized {total} messages")
        return total

    async def run_bulk_mode(self, max_batches: int = 10) -> int:
        """Bulk mode: vectorize in controlled batches"""
        # Drain DLQ first
        await self.drain_dlq(max_items=25)

        queue_size = self.get_queue_size()

        if queue_size == 0:
            print("[INFO] No unprocessed messages in queue")
            return 0

        print(f"\n[MODE] BULK - Processing up to {max_batches} batches")
        log_event({"event": "mode_bulk", "queue_size": queue_size, "max_batches": max_batches})

        total = 0
        for batch_num in range(max_batches):
            count = await self.vectorize_batch(batch_size=10)
            if count == 0:
                break
            total += count

            remaining = self.get_queue_size()
            completed = batch_num + 1
            progress_pct = (completed / max_batches) * 100
            print(f"[INFO] Batch {completed}/{max_batches} complete - {remaining} remaining")
            log_event(
                {
                    "event": "bulk_batch_progress",
                    "batch_num": completed,
                    "max_batches": max_batches,
                    "progress_pct": round(progress_pct, 1),
                    "remaining": remaining,
                    "vectorized_this_batch": count,
                }
            )

            # Small inter-batch delay for system stability
            await asyncio.sleep(2)

        remaining = self.get_queue_size()
        if remaining > 0:
            print(f"\n[INFO] Bulk mode paused - {remaining} messages remaining (will continue next run)")
        else:
            print(f"\n[OK] Bulk mode complete - all messages vectorized")

        return total


# =====================================================================================
# MAIN
# =====================================================================================
async def main_async(args):
    """Main async entry point"""
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent.parent

    # Load config with proper nested merge
    config_path = workspace_root / CONFIG_DEFAULTS["paths"]["config_rel"]
    config = CONFIG_DEFAULTS.copy()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # Deep merge
            for key, value in user_config.items():
                if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                    config[key] = {**config[key], **value}
                else:
                    config[key] = value
        except Exception as e:
            print(f"[WARN] Config load failed, using defaults: {e}")
            config = CONFIG_DEFAULTS.copy()

    data_link = workspace_root / config["paths"]["data_link_rel"]
    out_dir = workspace_root / config["paths"]["output_rel"]
    proc_db = data_link / config["paths"]["proc_rel"]
    mvm_db = data_link / config["paths"]["mvm_rel"]

    # Initialize logging
    init_logging(out_dir, config["file_prefix"], config["file_ext"])

    print("\n" + "=" * 80)
    print("S03_VECT - PRODUCTION VECTORIZATION ENGINE (HARDENED)")
    print("=" * 80)
    print(f"\nPaths:")
    print(f"  PROC.db: {proc_db}")
    print(f"  MVM.db: {mvm_db}")
    print(f"  Target: {args.target}")
    print(f"  Mode: {args.mode or 'auto'}")

    # Check PROC.db exists
    if not proc_db.exists():
        print(f"\n[ERROR] PROC.db not found - run S02_EXTR.py first")
        close_logging()
        return 1

    # Initialize vectorizer
    vectorizer = VectorizerEngine(config, proc_db, mvm_db, target=args.target)

    if not await vectorizer.initialize():
        print("\n[ERROR] Vectorizer initialization failed")
        close_logging()
        return 1

    # Determine mode
    queue_size = vectorizer.get_queue_size()

    if queue_size == 0:
        print("\n[INFO] No unprocessed messages to vectorize")
        await vectorizer.close()
        close_logging()
        return 0

    # Run vectorization
    if args.mode == "instant":
        total = await vectorizer.run_instant_mode()
    elif args.mode == "bulk":
        total = await vectorizer.run_bulk_mode(max_batches=args.batches)
    else:
        # Auto-detect: instant if < 100, bulk otherwise
        if queue_size < 100:
            total = await vectorizer.run_instant_mode()
        else:
            total = await vectorizer.run_bulk_mode(max_batches=10)

    await vectorizer.close()

    # Summary
    print("\n" + "=" * 80)
    print("VECTORIZATION COMPLETE")
    print("=" * 80)
    print(f"Total vectorized: {total}")
    print(f"Stats:")
    for k, v in vectorizer.stats.items():
        print(f"  {k}: {v}")

    # DLQ status
    try:
        conn = sqlite3.connect(mvm_db)
        cur = conn.cursor()
        dlq_count = cur.execute("SELECT COUNT(*) FROM embed_dlq").fetchone()[0]
        conn.close()
        if dlq_count > 0:
            print(f"  dlq_remaining: {dlq_count} (will retry next run)")
    except:
        pass

    print("=" * 80 + "\n")

    close_logging()
    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="S03_VECT - Production Vectorization Engine (Hardened)")
    parser.add_argument("--mode", choices=["instant", "bulk"], help="Vectorization mode (auto if not specified)")
    parser.add_argument("--batches", type=int, default=10, help="Max batches for bulk mode (default: 10)")
    parser.add_argument(
        "--target", choices=["mvm", "qdrant", "both"], default="both", help="Write target (default: both)"
    )

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(main_async(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
        close_logging()
        sys.exit(130)
    except Exception as e:
        print(f"[FATAL] {e}")
        log_event({"level": "FATAL", "event": "vectorizer_crashed", "error": str(e)})
        close_logging()
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
