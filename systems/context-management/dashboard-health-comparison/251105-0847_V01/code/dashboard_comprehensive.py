#!/usr/bin/env python3
"""
Comprehensive Dashboard for Vector Management
Full port from original MVM_DASH.py with all applicable features
"""
import os
import sys
import json
import time
import socket
import sqlite3
import threading
import http.client
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from flask import Flask, jsonify, render_template_string, request, g

try:
    import psutil
except ImportError:
    psutil = None

# ========== CONFIG ==========

DB_PATH = Path(__file__).resolve().parents[3] / "data/vector-mgmt/cursor_chats.db"
CACHE_DB = Path(__file__).resolve().parents[3] / "data/vector-mgmt/embeddings_cache.db"
PORT = 5555
REFRESH_MS = 2000

# Freshness thresholds (seconds)
FRESHNESS = {
    "default": 60,
    "extract": 120,
    "vector": 120,
    "idle": 300,
    "stale_error": 120
}

# Board cache
BOARD_CACHE = {
    "json": {"title": "Vector Management", "sections": [], "refresh_ms": REFRESH_MS},
    "ts": 0.0,
    "err": None
}


# ========== UTILITY FUNCTIONS ==========

def get_current_log(component: str) -> Optional[Path]:
	"""Get CURRENT log file for a component."""
	log_map = {
		"control": DB_PATH.parent / "control_CURRENT.ndjson",
		"extraction": DB_PATH.parent / "extraction_CURRENT.ndjson",
		"vectorization": DB_PATH.parent / "vectorization_CURRENT.ndjson",
		"health": DB_PATH.parent / "health_CURRENT.ndjson",
	}
	log_path = log_map.get(component)
	if log_path and (log_path.exists() or log_path.is_symlink()):
		return log_path
	return None


def tail_ndjson(path: Optional[Path], n: int = 8000) -> List[Dict[str, Any]]:
	"""Tail an NDJSON file."""
	if path is None or not path.exists():
		return []
	from collections import deque
	dq = deque(maxlen=n)
	try:
		with path.open("r", encoding="utf-8", errors="ignore") as f:
			for line in f:
				s = line.strip()
				if not s:
					continue
				try:
					dq.append(json.loads(s))
				except:
					continue
	except:
		return []
	return list(dq)


def last_event_ts(events: List[Dict[str, Any]], names: Tuple[str, ...]) -> Optional[str]:
	"""Return timestamp of the last event whose name is in names."""
	for x in reversed(events):
		if x.get("event") in names:
			ts = x.get("ts") or x.get("timestamp")
			if ts:
				return ts
	return None


def is_timestamp_fresh(ts_str: Optional[str], max_age_seconds: int = 60) -> bool:
	"""Check if timestamp is recent enough."""
	if not ts_str:
		return False
	try:
		fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S")
		dt = None
		for f in fmts:
			try:
				dt = datetime.strptime(ts_str, f)
				break
			except ValueError:
				continue
		if dt is None:
			try:
				dt = datetime.fromisoformat(ts_str)
			except:
				return False
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=timezone.utc)
		age = datetime.now(timezone.utc) - dt
		return age.total_seconds() <= max_age_seconds
	except:
		return False


def tcp_ping(host: str, port: int, timeout: float = 0.8) -> Tuple[bool, float, Optional[str]]:
    """TCP connection probe with latency measurement"""
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True, (time.time() - t0) * 1000.0, None
    except Exception as e:
        try:
            s.close()
        except:
            pass
        return False, (time.time() - t0) * 1000.0, str(e)


def http_get(host: str, port: int, path: str, timeout: float = 1.2) -> Tuple[int, Dict, str, float, Optional[str]]:
    """HTTP GET probe with latency"""
    t0 = time.time()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        resp = conn.getresponse()
        body = resp.read(4096).decode("utf-8", errors="ignore")
        headers = {k.lower(): v for k, v in resp.getheaders()}
        return resp.status, headers, body, (time.time() - t0) * 1000.0, None
    except Exception as e:
        return 0, {}, "", (time.time() - t0) * 1000.0, str(e)
    finally:
        try:
            conn.close()
        except:
            pass


def probe_qdrant(host="127.0.0.1", port=6333, collection_hint: Optional[str] = None) -> Dict[str, Any]:
	"""Comprehensive Qdrant health probe"""
	collection = collection_hint or "cursor-chats"
	tcp_ok, tcp_ms, tcp_err = tcp_ping(host, port)
	health_code, _, health_body, health_ms, health_err = http_get(host, port, "/healthz")
	coll_code, _, coll_body, coll_ms, coll_err = http_get(host, port, f"/collections/{collection}")
	colls_code, _, colls_body, colls_ms, colls_err = http_get(host, port, "/collections")

    info = {
        "tcp": {"ok": tcp_ok, "ms": round(tcp_ms, 1), "err": tcp_err},
        "healthz": {"code": health_code, "ms": round(health_ms, 1), "err": health_err},
        "collection": {"code": coll_code, "ms": round(coll_ms, 1), "err": coll_err},
        "collections": {"code": colls_code, "ms": round(colls_ms, 1), "err": colls_err}
    }

    if coll_code == 200:
        try:
            data = json.loads(coll_body)
            result = data.get("result", {})
            info["collection"]["vectors_count"] = result.get("vectors_count", 0)
            info["collection"]["points_count"] = result.get("points_count", 0)
            info["collection"]["status"] = result.get("status", "unknown")
        except:
            pass

    if colls_code == 200:
        try:
            data = json.loads(colls_body)
            colls = data.get("result", {}).get("collections", [])
            info["collections"]["count"] = len(colls)
        except:
            pass

    return info


def probe_ollama(host="127.0.0.1", port=11434) -> Dict[str, Any]:
    """Comprehensive Ollama health probe"""
    tcp_ok, tcp_ms, tcp_err = tcp_ping(host, port)
    ver_code, _, ver_body, ver_ms, ver_err = http_get(host, port, "/api/version")
    tags_code, _, tags_body, tags_ms, tags_err = http_get(host, port, "/api/tags")

    info = {
        "tcp": {"ok": tcp_ok, "ms": round(tcp_ms, 1), "err": tcp_err},
        "version": {"code": ver_code, "ms": round(ver_ms, 1), "err": ver_err},
        "tags": {"code": tags_code, "ms": round(tags_ms, 1), "err": tags_err}
    }

    if tags_code == 200:
        try:
            tags = json.loads(tags_body)
            models = [m.get("name") for m in tags.get("models", [])]
            info["models"] = models[:12]
            info["model_count"] = len(models)
            # Check for required model
            info["has_nomic"] = any("nomic-embed-text" in m for m in models)
        except:
            pass

    return info


def find_procs(names=("qdrant", "ollama")) -> Dict[str, List[int]]:
    """Find running processes by name"""
    out = {n: [] for n in names}
    if not psutil:
        return out
    try:
        for p in psutil.process_iter(["name", "exe", "pid", "cmdline"]):
            n = (p.info.get("name") or "").lower()
            for target in names:
                if target in n or any(target in (c or "").lower() for c in p.info.get("cmdline") or []):
                    out[target].append(p.info["pid"])
    except:
        pass
    return out


def aggregate_ok(items: List[Dict[str, Any]]) -> Tuple[Optional[bool], str]:
    """Aggregate section status from items with proper 3-state logic"""
    if not items:
        return None, "no_data"

    any_err = any(i.get("ok") is False for i in items) or any(
        any(si.get("ok") is False for si in i.get("subitems", [])) for i in items
    )
    any_warn = any((i.get("ok") is None or i.get("status") == "warning") for i in items) or any(
        (si.get("ok") is None or si.get("status") == "warning") for i in items for si in i.get("subitems", [])
    )

    if any_err:
        return False, "error"
    if any_warn:
        return None, "warning"
    return True, "ok"


def get_db_stats() -> Dict[str, Any]:
    """Get comprehensive database stats"""
    try:
        if not DB_PATH.exists():
            return {"error": "database not found", "exists": False}

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM chat_data")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM chat_data WHERE processed = 1")
        processed = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM chat_data WHERE text IS NULL OR TRIM(text) = ""')
        empty = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM chat_data WHERE text IS NOT NULL AND TRIM(text) != "" AND processed = 0')
        pending_text = cur.fetchone()[0]

        # Get last processed timestamp
        cur.execute('SELECT MAX(extracted_at) FROM chat_data WHERE processed = 1')
        last_processed = cur.fetchone()[0]

        # Get filtering stats
        cur.execute('SELECT COUNT(*) FROM chat_data WHERE value_score >= 3')
        with_metadata = cur.fetchone()[0]

        conn.close()

        return {
            "exists": True,
            "total": total,
            "processed": processed,
            "unprocessed": total - processed,
            "empty": empty,
            "pending_text": pending_text,
            "with_metadata": with_metadata,
            "progress_pct": round((processed / total * 100) if total > 0 else 0, 1),
            "last_processed": last_processed
        }
    except Exception as e:
        return {"error": str(e), "exists": False, "total": 0, "processed": 0}


def get_cache_stats() -> Dict[str, Any]:
    """Get comprehensive embedding cache and DLQ stats with full diagnostics"""
    try:
        if not CACHE_DB.exists():
            return {
                "cached": 0,
                "dlq": 0,
                "dlq_errors": [],
                "cache_exists": False,
                "error": "cache db not found"
            }

        conn = sqlite3.connect(str(CACHE_DB))
        cur = conn.cursor()

        # Cache stats
        cur.execute("SELECT COUNT(*) FROM embed_cache")
        cached = cur.fetchone()[0]

        # Get cache sample for verification
        cur.execute("""
            SELECT model, dims, created_at
            FROM embed_cache
            ORDER BY created_at DESC
            LIMIT 3
        """)
        cache_samples = [
            {"model": r[0], "dims": r[1], "created_at": r[2]}
            for r in cur.fetchall()
        ]

        # DLQ stats with FULL error details
        try:
            cur.execute("SELECT COUNT(*) FROM embed_dlq")
            dlq = cur.fetchone()[0]

            # Get ALL DLQ errors with complete details
            cur.execute("""
                SELECT key, text, last_error, attempts, last_attempt_at, created_at
                FROM embed_dlq
                ORDER BY last_attempt_at DESC
                LIMIT 10
            """)
            dlq_errors = [
                {
                    "key": r[0][:50],
                    "text_preview": r[1][:200] if r[1] else "",
                    "text_length": len(r[1]) if r[1] else 0,
                    "error": r[2],
                    "attempts": r[3],
                    "last_attempt": r[4],
                    "created_at": r[5]
                }
                for r in cur.fetchall()
            ]

            # Parse error types
            error_types = {}
            for err in dlq_errors:
                error_msg = err["error"] or "unknown"
                if "500" in error_msg:
                    error_types["ollama_500_errors"] = error_types.get("ollama_500_errors", 0) + 1
                elif "timeout" in error_msg.lower():
                    error_types["timeout_errors"] = error_types.get("timeout_errors", 0) + 1
                elif "connection" in error_msg.lower():
                    error_types["connection_errors"] = error_types.get("connection_errors", 0) + 1
                else:
                    error_types["other_errors"] = error_types.get("other_errors", 0) + 1

        except Exception as e:
            dlq = 0
            dlq_errors = []
            error_types = {"error": str(e)}

        conn.close()

        return {
            "cached": cached,
            "dlq": dlq,
            "dlq_errors": dlq_errors,
            "error_types": error_types,
            "cache_samples": cache_samples,
            "cache_exists": True
        }
    except Exception as e:
        return {
            "cached": 0,
            "dlq": 0,
            "dlq_errors": [],
            "cache_exists": False,
            "error": str(e)
        }


def validate_qdrant_working(q_probe: Dict, db_stats: Dict) -> Tuple[bool, str]:
    """
    Validate Qdrant is actually working, not just responding to pings
    Returns (is_working, reason)
    """
    # Check if Qdrant is reachable
    if not q_probe["tcp"]["ok"]:
        return False, "port_closed"

    if q_probe["healthz"]["code"] != 200:
        return False, f"healthz_{q_probe['healthz']['code']}"

    if q_probe["collections"]["code"] != 200:
        return False, f"collections_api_{q_probe['collections']['code']}"

    # Check if collection exists and is accessible
    if q_probe["collection"]["code"] != 200:
        return False, f"collection_{q_probe['collection']['code']}"

    # If we've processed records, check if vectors actually made it
    if db_stats.get("processed", 0) > 0:
        points = q_probe["collection"].get("points_count", 0)
        if points == 0:
            return False, "no_vectors_stored"  # Critical: processed but no vectors!

    return True, "validated"


def validate_ollama_working(o_probe: Dict) -> Tuple[bool, str]:
    """
    Validate Ollama is actually working
    Returns (is_working, reason)
    """
    if not o_probe["tcp"]["ok"]:
        return False, "port_closed"

    if o_probe["version"]["code"] != 200:
        return False, f"version_{o_probe['version']['code']}"

    if o_probe["tags"]["code"] != 200:
        return False, f"tags_{o_probe['tags']['code']}"

    if not o_probe.get("has_nomic"):
        return False, "missing_nomic_model"

    return True, "validated"


# ========== SECTION BUILDERS ==========

def build_s01_health() -> Dict[str, Any]:
    """Build S01 Health section with VALIDATION (not just probes)"""

    # PRIORITY 2: Read logs for context
    health_log = get_current_log("health")
    vector_log = get_current_log("vectorization")
    h_evs = tail_ndjson(health_log) if health_log else []
    v_evs = tail_ndjson(vector_log) if vector_log else []

    # PRIORITY 2: Health check timestamp
    ts_health = last_event_ts(h_evs, ("services_and_db_complete", "normal_exit"))

    # PRIORITY 1: Track restart attempts (grace period)
    ts_qdrant_restart = last_event_ts(h_evs, ("qdrant_forced_restart", "qdrant_restart_attempted"))
    ts_ollama_restart = last_event_ts(h_evs, ("ollama_forced_restart", "ollama_restart_attempted"))

    qdrant_restarting = ts_qdrant_restart and is_timestamp_fresh(ts_qdrant_restart, 60)
    ollama_restarting = ts_ollama_restart and is_timestamp_fresh(ts_ollama_restart, 60)

    # PRIORITY 2: Recent vectorization activity
    recent_qdrant_errors = [
        e for e in v_evs
        if e.get("event") == "qdrant_init_failed" and is_timestamp_fresh(e.get("ts"), 300)
    ]
    recent_qdrant_success = [
        e for e in v_evs
        if e.get("event") in ("qdrant_initialized", "qdrant_write_complete")
        and is_timestamp_fresh(e.get("ts"), 300)
    ]
    qdrant_activity_ts = None
    if recent_qdrant_success or recent_qdrant_errors:
        all_q = recent_qdrant_success + recent_qdrant_errors
        qdrant_activity_ts = max([e.get("ts") for e in all_q if e.get("ts")], default=None)

    # PRIORITY 1: Dynamic collection discovery
    collection_hint = next(
        (e.get("collection") for e in reversed(v_evs)
         if e.get("event") == "qdrant_initialized" and e.get("collection")),
        None
    )

    # Live probes with dynamic collection
    q_probe = probe_qdrant(collection_hint=collection_hint)
    o_probe = probe_ollama()
    procs = find_procs()
    db_stats = get_db_stats()

    # Current probe status
    q_probe_ok = q_probe["tcp"]["ok"] and q_probe["healthz"]["code"] == 200 and q_probe["collections"]["code"] == 200
    o_probe_ok = o_probe["tcp"]["ok"] and o_probe["version"]["code"] == 200 and o_probe["tags"]["code"] == 200 and (o_probe.get("model_count") or 0) > 0

    items = []

    # Qdrant - with VALIDATION and GRACE PERIOD
    q_working, q_reason = validate_qdrant_working(q_probe, db_stats)

    if not q_probe["tcp"]["ok"]:
        items.append({"label": "Qdrant", "ok": False, "note": "port closed"})
    elif qdrant_restarting and not q_working:
        # PRIORITY 1: Grace period during restart
        items.append({"label": "Qdrant", "ok": None, "note": "restarting..."})
    elif q_reason == "no_vectors_stored":
        items.append({
            "label": "Qdrant",
            "ok": False,
            "status": "error",
            "note": f"0 vectors (expected {db_stats.get('processed', 0)})"
        })
    elif not q_working:
        items.append({"label": "Qdrant", "ok": False, "note": q_reason})
    else:
        points = q_probe["collection"].get("points_count", 0)
        note = f"{points:,} vectors"
        if qdrant_activity_ts and is_timestamp_fresh(qdrant_activity_ts, 300):
            note += " (active)"
        items.append({"label": "Qdrant", "ok": True, "note": note})

    # Ollama - with VALIDATION and GRACE PERIOD
    o_working, o_reason = validate_ollama_working(o_probe)

    if not o_probe["tcp"]["ok"]:
        items.append({"label": "Ollama", "ok": False, "note": "port closed"})
    elif ollama_restarting and not o_working:
        # PRIORITY 1: Grace period during restart
        items.append({"label": "Ollama", "ok": None, "note": "restarting..."})
    elif not o_working:
        items.append({"label": "Ollama", "ok": False, "note": o_reason})
    else:
        models = o_probe.get("model_count", 0)
        items.append({"label": "Ollama", "ok": True, "note": f"{models} models"})

    # Database
    if not db_stats.get("exists"):
        items.append({"label": "Database", "ok": False, "note": db_stats.get("error", "not found")})
    else:
        items.append({"label": "Database", "ok": True, "note": f"{db_stats['total']:,} records"})

    # Build comprehensive debug
    contradictions = {
        "qdrant_responding_but_broken": (
            q_probe["tcp"]["ok"] and q_probe["healthz"]["code"] == 200
            and not q_working
        ),
        "processed_but_no_vectors": (
            db_stats.get("processed", 0) > 0
            and q_probe["collection"].get("points_count", 0) == 0
        ),
        "ollama_responding_but_broken": (
            o_probe["tcp"]["ok"] and o_probe["version"]["code"] == 200
            and not o_working
        )
    }

    # PRIORITY 1: Stale error filtering
    all_errors = [e for e in reversed(h_evs) if e.get("level") in ("ERROR", "WARN")][:10]
    if q_probe_ok:
        all_errors = [
            e for e in all_errors
            if e.get("event") != "qdrant_unreachable"
            or is_timestamp_fresh(e.get("ts", ""), FRESHNESS["stale_error"])
        ]
    if o_probe_ok:
        all_errors = [
            e for e in all_errors
            if e.get("event") not in ("ollama_unreachable", "ollama_not_responding")
            or is_timestamp_fresh(e.get("ts", ""), FRESHNESS["stale_error"])
        ]

    debug = {
        "log_files": {
            "health": str(health_log) if health_log else None,
            "vectorization": str(vector_log) if vector_log else None
        },
        "event_counts": {
            "health_events": len(h_evs),
            "vector_events": len(v_evs)
        },
        "last_health_check": ts_health,
        "restart_attempts": {
            "qdrant_last": ts_qdrant_restart,
            "qdrant_restarting": qdrant_restarting,
            "ollama_last": ts_ollama_restart,
            "ollama_restarting": ollama_restarting
        },
        "collection_discovery": {
            "hint": collection_hint,
            "used_default": collection_hint is None
        },
        "probes": {"qdrant": q_probe, "ollama": o_probe},
        "processes": procs,
        "current_status": {
            "qdrant_ok": q_probe_ok,
            "ollama_ok": o_probe_ok,
            "note": "Current probe results (overrides stale health data)"
        },
        "validation": {
            "qdrant_working": q_working,
            "qdrant_reason": q_reason,
            "ollama_working": o_working,
            "ollama_reason": o_reason
        },
        "vector_recent": {
            "errors_5m": len(recent_qdrant_errors),
            "success_5m": len(recent_qdrant_success),
            "last_activity_ts": qdrant_activity_ts
        },
        "contradictions": contradictions,
        "database": db_stats,
        "last_errors": all_errors[:5]
    }

    ok, status = aggregate_ok(items)
    return {"key": "S01", "title": "S01 - Health", "ok": ok, "status": status, "items": items, "debug": debug}


def build_s02_extraction() -> Dict[str, Any]:
    """Build S02 Extraction section"""
    db_stats = get_db_stats()

    if not db_stats.get("exists"):
        return {
            "key": "S02",
            "title": "S02 - Extraction",
            "ok": False,
            "status": "error",
            "items": [{"label": "Database", "ok": False, "note": "not found"}],
            "debug": {"error": db_stats.get("error")}
        }

    items = []

    # Total extracted
    total = db_stats["total"]
    if total > 0:
        items.append({"label": "Total Extracted", "ok": True, "note": f"{total:,} bubbles"})
    else:
        items.append({"label": "Total Extracted", "ok": None, "note": "0"})

    # Filtering stats
    kept = db_stats["total"] - db_stats["empty"]
    if kept > 0:
        items.append({"label": "Kept (Filtered)", "ok": True, "note": f"{kept:,}"})

    discarded = db_stats["empty"]
    if discarded > 0:
        items.append({"label": "Discarded Empty", "ok": True, "note": f"{discarded:,}"})

    # Last extraction time
    if db_stats.get("last_processed"):
        items.append({"label": "Last Extraction", "ok": True, "note": db_stats["last_processed"][:16]})

    debug = {
        "database": db_stats,
        "filtering": {
            "total_bubbles": total,
            "kept": kept,
            "discarded_empty": discarded,
            "with_metadata": db_stats.get("with_metadata", 0)
        }
    }

    ok, status = aggregate_ok(items)
    return {"key": "S02", "title": "S02 - Extraction", "ok": ok, "status": status, "items": items, "debug": debug}


def build_s03_vectorization() -> Dict[str, Any]:
    """Build S03 Vectorization section with COMPREHENSIVE DIAGNOSTICS"""
    db_stats = get_db_stats()
    cache_stats = get_cache_stats()
    q_probe = probe_qdrant()

    items = []

    # Check for critical mismatch
    db_processed = db_stats.get("processed", 0)
    qdrant_points = q_probe["collection"].get("points_count", 0)

    has_critical_mismatch = db_processed > 0 and qdrant_points == 0

    # Get detailed processing history from DB
    processing_history = {}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()

        # Get last 10 processed records
        cur.execute("""
            SELECT bubble_id, text, processed, extracted_at
            FROM chat_data
            WHERE processed = 1
            ORDER BY extracted_at DESC
            LIMIT 10
        """)
        last_processed = [
            {
                "bubble_id": r[0][:20],
                "text_preview": r[1][:50] if r[1] else "",
                "processed_at": r[3]
            }
            for r in cur.fetchall()
        ]

        # Check if any processed records have text
        cur.execute("""
            SELECT COUNT(*)
            FROM chat_data
            WHERE processed = 1 AND (text IS NULL OR TRIM(text) = "")
        """)
        processed_empty = cur.fetchone()[0]

        # Get processing rate info
        cur.execute("""
            SELECT MIN(extracted_at), MAX(extracted_at), COUNT(*)
            FROM chat_data
            WHERE processed = 1
        """)
        first_proc, last_proc, total_proc = cur.fetchone()

        processing_history = {
            "last_processed": last_processed,
            "processed_empty_records": processed_empty,
            "first_processed_at": first_proc,
            "last_processed_at": last_proc,
            "total_processed": total_proc
        }

        conn.close()
    except Exception as e:
        processing_history = {"error": str(e)}

    # Analyze failure patterns
    failure_analysis = {
        "total_failures": cache_stats.get("dlq", 0),
        "error_types": cache_stats.get("error_types", {}),
        "has_ollama_500_errors": cache_stats.get("error_types", {}).get("ollama_500_errors", 0) > 0,
        "has_timeout_errors": cache_stats.get("error_types", {}).get("timeout_errors", 0) > 0,
        "suspected_cause": None
    }

    # Diagnose suspected cause
    if has_critical_mismatch:
        failure_analysis["suspected_cause"] = "qdrant_write_failure"
        failure_analysis["diagnosis"] = "Records marked processed in DB but not written to Qdrant. Likely Qdrant client error or silent write failure."
    elif cache_stats.get("error_types", {}).get("ollama_500_errors", 0) > 0:
        failure_analysis["suspected_cause"] = "ollama_embedding_failure"
        failure_analysis["diagnosis"] = "Ollama returning 500 errors. Likely: message too long, invalid content, or Ollama internal error."
    elif cache_stats.get("error_types", {}).get("timeout_errors", 0) > 0:
        failure_analysis["suspected_cause"] = "timeout"
        failure_analysis["diagnosis"] = "Operations timing out. Check network, Ollama load, or Qdrant performance."

    # Vectorization progress
    if has_critical_mismatch:
        items.append({
            "label": "Vectorization",
            "ok": False,
            "status": "error",
            "note": f"DB: {db_processed}, Qdrant: 0"
        })
    elif db_processed > 0:
        items.append({
            "label": "Processed",
            "ok": True,
            "note": f"{db_processed:,} / {db_stats['total']:,}"
        })
    else:
        items.append({"label": "Processed", "ok": None, "note": "0"})

    # Pending work
    pending = db_stats.get("pending_text", 0)
    if pending > 0:
        items.append({
            "label": "Pending",
            "ok": None,
            "status": "warning",
            "note": f"{pending:,} messages"
        })
    elif db_processed > 0 and not has_critical_mismatch:
        items.append({"label": "Complete", "ok": True, "note": f"{db_stats['progress_pct']}%"})

    # Qdrant writes
    if qdrant_points > 0:
        items.append({"label": "Qdrant Vectors", "ok": True, "note": f"{qdrant_points:,}"})
    elif db_processed > 0:
        items.append({"label": "Qdrant Vectors", "ok": False, "note": "0 (FAILED)"})

    # Cache
    if cache_stats["cached"] > 0:
        items.append({"label": "Cache Hits", "ok": True, "note": f"{cache_stats['cached']:,}"})

    # DLQ - ACTIVE FAILURES with breakdown
    if cache_stats["dlq"] > 0:
        error_summary = ", ".join([f"{k}: {v}" for k, v in cache_stats.get("error_types", {}).items()])
        items.append({
            "label": "Failed (DLQ)",
            "ok": False,
            "status": "error",
            "note": f"{cache_stats['dlq']} ({error_summary})"
        })

    # Build COMPREHENSIVE debug
    debug = {
        "database": db_stats,
        "cache": cache_stats,
        "qdrant": {
            "points_count": qdrant_points,
            "status": q_probe["collection"].get("status"),
            "collection_ok": q_probe["collection"]["code"] == 200,
            "collection_response_ms": q_probe["collection"].get("ms")
        },
        "processing_history": processing_history,
        "failure_analysis": failure_analysis,
        "critical_issues": {
            "db_qdrant_mismatch": has_critical_mismatch,
            "db_processed": db_processed,
            "qdrant_points": qdrant_points,
            "dlq_count": cache_stats["dlq"],
            "processed_empty_records": processing_history.get("processed_empty_records", 0)
        },
        "recent_dlq_errors_full": cache_stats.get("dlq_errors", [])[:5],
        "recommended_action": get_recommended_action(has_critical_mismatch, cache_stats, failure_analysis)
    }

    # Status logic: Error if critical mismatch or DLQ failures
    if has_critical_mismatch or cache_stats["dlq"] > 0:
        ok, status = False, "error"
    elif pending > 0:
        ok, status = None, "warning"
    elif db_processed > 0:
        ok, status = True, "ok"
    else:
        ok, status = None, "warning"

    return {"key": "S03", "title": "S03 - Vectorization", "ok": ok, "status": status, "items": items, "debug": debug}


def get_recommended_action(has_mismatch, cache_stats, failure_analysis):
    """Generate recommended action based on failure patterns"""
    if has_mismatch:
        return "CRITICAL: Check vectorization.py _write_to_qdrant() method. Records marked processed but not written. Add error logging to Qdrant write operations."

    if failure_analysis.get("suspected_cause") == "ollama_embedding_failure":
        dlq_errors = cache_stats.get("dlq_errors", [])
        if dlq_errors:
            first_error = dlq_errors[0]
            if first_error.get("text_length", 0) > 5000:
                return f"Ollama 500 error on long text ({first_error['text_length']} chars). Add text truncation or chunking before embedding."
            else:
                return f"Ollama 500 error. Check Ollama logs, verify model loaded, test embedding API directly with sample text."

    if failure_analysis.get("suspected_cause") == "timeout":
        return "Timeout errors detected. Check: 1) Network connectivity, 2) Ollama responsiveness, 3) Qdrant performance, 4) Increase timeout values."

    return "Check debug panel for detailed error information and DLQ entries."


def build_board_json() -> Dict[str, Any]:
    """Build complete board with all sections"""
    sections = [
        build_s01_health(),
        build_s02_extraction(),
        build_s03_vectorization()
    ]
    return {"title": "Vector Management", "sections": sections, "refresh_ms": REFRESH_MS}


def board_refresher(interval=2):
    """Background thread to refresh board data"""
    while True:
        t0 = time.time()
        try:
            data = build_board_json()
            BOARD_CACHE.update({"json": data, "ts": t0, "err": None})
        except Exception as e:
            BOARD_CACHE.update({"err": str(e)})
        delay = max(0.5, interval - (time.time() - t0))
        time.sleep(delay)


# ========== FLASK APP ==========

app = Flask(__name__)


@app.get("/")
def index():
    return render_template_string(HTML, PORT=PORT)


@app.get("/api/board")
def api_board():
    payload = dict(BOARD_CACHE["json"])
    payload["generated_ts"] = BOARD_CACHE["ts"]
    if BOARD_CACHE["err"]:
        payload["server_note"] = f"Error: {BOARD_CACHE['err']}"
    return jsonify(payload)


@app.get("/api/probe/services")
def api_probe_services():
    """Live probe endpoint"""
    return jsonify({
        "ts": time.time(),
        "qdrant": probe_qdrant(),
        "ollama": probe_ollama(),
        "procs": find_procs()
    })


# ========== HTML WITH ALL ICONS ==========

HTML = r"""
<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vector Management</title>
<style>
:root{
  --bg:#0b1220; --panel:#0f172a; --text:#e7ecf3; --muted:#94a3b8;
  --ok:#21c074; --warn:#f2b84c; --err:#ef5959; --rule:#1e293b;
}
body{margin:0;background:var(--bg);color:var(--text);font:12px/1.4 Inter,ui-sans-serif,system-ui;display:flex;flex-direction:column;min-height:100vh}
.wrap{flex:1;display:flex;align-items:center;padding:8px}
.card{width:100%;background:linear-gradient(180deg,var(--panel),#0b1426);border:1px solid #0a1a33;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.35)}
.header{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--rule);font-weight:700;font-size:14px}
.refresh-time{font-size:9px;font-weight:400;color:var(--muted);margin-left:auto;font-variant-numeric:tabular-nums}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px rgba(33,192,116,0.14)}
.dot.warn{background:var(--warn);box-shadow:0 0 0 3px rgba(242,184,76,0.16)}
.dot.err{background:var(--err);box-shadow:0 0 0 3px rgba(239,89,89,0.18)}
.section{border-top:1px solid var(--rule)}
.sect-head{display:grid;grid-template-columns:12px 1fr 40px;align-items:center;gap:8px;padding:10px 12px}
.sect-title{font-size:13px;font-weight:700}
.details-btn{padding:2px 4px;font-size:11px;background:#1e3a5f;color:var(--text);border:1px solid #2d5a8f;border-radius:3px;cursor:pointer;opacity:0.8}
.details-btn:hover{background:#2d5a8f;opacity:1}
.details-btn.visible{display:block}
.items{display:none;margin:0 8px 8px 8px;border:1px solid #162746;border-radius:6px;background:#0a1324}
.items.open{display:block}
.table{display:grid;grid-template-columns:1fr 120px;border-bottom:1px solid var(--rule);padding:4px 8px 4px 28px;color:var(--muted);font-weight:600;font-size:10px}
ul.board{list-style:none;margin:0;padding:0}
li.row{display:grid;grid-template-columns:16px 1fr 120px;gap:6px;align-items:center;padding:6px 8px;border-bottom:1px solid var(--rule);font-size:11px}
li.row:last-child{border-bottom:0}
.label{font-weight:600}
.note{justify-self:end;color:var(--muted);font-size:10px}
.check{display:inline-flex;width:14px;height:14px;color:var(--ok)}
.check.warn{color:var(--warn)} .check.err{color:var(--err)}
.debug-panel{display:none;margin:0 8px 8px 8px;padding:12px;border:1px solid #2d5a8f;border-radius:6px;background:#0a1324;font-family:monospace;font-size:10px;max-height:400px;overflow:auto}
.debug-panel.open{display:block}
.debug-panel pre{margin:0;white-space:pre-wrap;color:var(--muted)}
</style>
</head><body>
<div class="wrap"><div class="card">
  <div class="header"><span id="topdot" class="dot"></span> Vector Management <span id="refreshTime" class="refresh-time"></span></div>
  <div id="content"></div>
</div></div>

<script>
// Position window on Monitor 3 (X=-400, Y=100)
try {
  window.moveTo(-400, 100);
  window.resizeTo(560, 420);
} catch(_) {}

const PORT = {{ PORT }};

let _fitRAF = 0;

function chromeDelta(){
  return {
    dW: Math.max(0, window.outerWidth  - window.innerWidth),
    dH: Math.max(0, window.outerHeight - window.innerHeight),
  };
}

function fitWindowExact(opts){
  const { minW=460, maxW=820, minH=160, maxH=1600, padW=16, padH=20 } = (opts||{});
  const card = document.querySelector('.card');
  if(!card) return;

  const r = card.getBoundingClientRect();
  const sw = Math.ceil(Math.max(r.width,  card.scrollWidth  || r.width));
  const sh = Math.ceil(Math.max(r.height, card.scrollHeight || r.height));

  const { dW, dH } = chromeDelta();

  const targetW = Math.min(maxW, Math.max(minW, sw + dW + padW));
  const targetH = Math.min(maxH, Math.max(minH, sh + dH + padH));

  const needW = Math.abs(window.outerWidth  - targetW) > 2;
  const needH = Math.abs(window.outerHeight - targetH) > 2;
  if (needW || needH) {
    try {
      // Keep X position fixed (don't reposition), only resize
      window.resizeTo(targetW, targetH);
    } catch(_) {}
  }
}

function scheduleFit(){
  if (_fitRAF) return;
  _fitRAF = requestAnimationFrame(()=>{ _fitRAF = 0; fitWindowExact(); });
}

function svg(n){
  const m={
    check:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>',
    x:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M18.3 5.7 12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7 4.3 4.3l6.3 6.3 6.3-6.3z"/></svg>',
    hourglass:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M6 2h12v4a6 6 0 0 1-3 5.2V13a6 6 0 0 1 3 5.2V22H6v-3.8A6 6 0 0 1 9 13v-1.8A6 6 0 0 1 6 6.1z"/></svg>',
    gear:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 15.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5zm7.4-4.8l-1.6-.5c-.2-.5-.4-1-.7-1.4l.8-1.5c.2-.3.1-.7-.2-.9l-1.4-1.4c-.3-.3-.6-.3-.9-.2l-1.5.8c-.5-.3-.9-.5-1.4-.7l-.5-1.6c-.1-.3-.4-.5-.7-.5h-2c-.3 0-.6.2-.7.5l-.5 1.6c-.5.2-1 .4-1.4.7l-1.5-.8c-.3-.2-.7-.1-.9.2L3.4 6.3c-.3.3-.3.6-.2.9l.8 1.5c-.3.5-.5.9-.7 1.4l-1.6.5c-.3.1-.5.4-.5.7v2c0 .3.2.6.5.7l1.6.5c.2.5.4 1 .7 1.4l-.8 1.5c-.2.3-.1.7.2.9l1.4 1.4c.3.3.6.3.9.2l1.5-.8c.5.3.9.5 1.4.7l.5 1.6c.1.3.4.5.7.5h2c.3 0 .6-.2.7-.5l.5-1.6c.5-.2 1-.4 1.4-.7l1.5.8c.3.2.7.1.9-.2l1.4-1.4c.3-.3.3-.6.2-.9l-.8-1.5c.3-.5.5-.9.7-1.4l1.6-.5c.3-.1.5-.4.5-.7v-2c0-.3-.2-.6-.5-.7z"/></svg>',
    sleep:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M22 7h-3l2-3h-3l-2 3h-2L16 4h-3l-2 3h-1c-1.7 0-3 1.3-3 3v1h16V8c0-.6-.4-1-1-1zM4 20c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-9H4v9zm4-6h8v2H8v-2z"/></svg>'
  };
  return m[n]||'';
}

function liIcon(ok,status,label){
  if(status==='idle') return svg('sleep');
  if(status==='warning' && label && (label.includes('Vectorization') || label.includes('Pending'))) return svg('gear');
  if(status==='warning' || ok===null || ok===undefined) return svg('hourglass');
  return ok?svg('check'):svg('x');
}

function liColor(ok,status,label){
  if(status==='idle') return 'var(--muted)';
  if(status==='warning' || ok===null || ok===undefined) return 'var(--warn)';
  return ok?'var(--ok)':'var(--err)';
}

function dotClass(ok,status){
  if(ok===false || status==='error') return 'dot err';
  if(ok===true) return 'dot';
  return 'dot warn';
}

async function refresh(){
  try{
    const b = await fetch('/api/board').then(r=>r.json());
    render(b);
    setTimeout(refresh, b.refresh_ms||2000);
  }catch(e){
    setTimeout(refresh, 3000);
  }
}

function render(b){
  const content = document.getElementById('content');

  // Update refresh timestamp
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  const timeStr = `${month}/${day} ${hours}:${minutes}:${seconds}`;
  document.title = `Vector Management [Refreshed: ${timeStr}]`;
  document.getElementById('refreshTime').textContent = timeStr;

  const topdot = document.getElementById('topdot');
  const anyErr = b.sections.some(s=>s.ok===false||s.status==='error');
  const anyWarn = b.sections.some(s=>(s.ok===null||s.status==='warning')&&s.ok!==false);
  topdot.className = anyErr?'dot err':(anyWarn?'dot warn':'dot');

  if(content.children.length===0){
    buildAll(content, b);
  }else{
    updateAll(content, b);
  }

  scheduleFit();
}

function buildAll(content, b){
  content.innerHTML='';
  b.sections.forEach(sec=>{
    const container=document.createElement('div'); container.className='section';
    const head=document.createElement('div'); head.className='sect-head';
    const lamp=document.createElement('span'); lamp.className=dotClass(sec.ok,sec.status);
    const title=document.createElement('div'); title.className='sect-title'; title.textContent=sec.title;
    const btn=document.createElement('button'); btn.className='details-btn'; btn.textContent='🐛';
    if(sec.ok!==true) btn.classList.add('visible');
    head.appendChild(lamp); head.appendChild(title); head.appendChild(btn);

    const items=document.createElement('div'); items.className='items';
    const hdr=document.createElement('div'); hdr.className='table';
    hdr.innerHTML='<div>Status</div><div style="text-align:right">Info</div>';
    const ul=document.createElement('ul'); ul.className='board';

    (sec.items||[]).forEach(it=>{
      const li=document.createElement('li'); li.className='row';
      const ck=document.createElement('span'); ck.className='check';
      ck.innerHTML=liIcon(it.ok,it.status,it.label); ck.style.color=liColor(it.ok,it.status,it.label);
      const lab=document.createElement('div'); lab.className='label'; lab.textContent=it.label;
      const note=document.createElement('div'); note.className='note'; note.textContent=it.note||'';
      li.appendChild(ck); li.appendChild(lab); li.appendChild(note);
      ul.appendChild(li);
    });

    items.appendChild(hdr); items.appendChild(ul);

    const debugPanel=document.createElement('div'); debugPanel.className='debug-panel';
    const debugPre=document.createElement('pre');
    debugPre.textContent = JSON.stringify(sec.debug||{}, null, 2);
    debugPanel.appendChild(debugPre);

    container.appendChild(head); container.appendChild(items); container.appendChild(debugPanel);
    content.appendChild(container);

    if(sec.ok!==true) items.classList.add('open');

    btn.addEventListener('click', async(e)=>{
      e.stopPropagation();
      debugPanel.classList.toggle('open');
      scheduleFit();
      try{
        await navigator.clipboard.writeText(JSON.stringify(sec.debug||{},null,2));
        const orig=btn.textContent; btn.textContent='✓';
        setTimeout(()=>btn.textContent=orig, 1500);
      }catch(err){}
    });
  });
}

document.addEventListener('DOMContentLoaded', ()=>{
  const ro = new ResizeObserver(() => scheduleFit());
  const card = document.querySelector('.card');
  if (card) ro.observe(card);

  const mo = new MutationObserver(() => scheduleFit());
  mo.observe(document.getElementById('content'), { childList:true, subtree:true, characterData:true });

  setTimeout(scheduleFit, 50);
});

function updateAll(content, b){
  b.sections.forEach((sec,idx)=>{
    const container = content.children[idx];
    if(!container) return;

    const lamp = container.querySelector('.dot');
    if(lamp) lamp.className = dotClass(sec.ok, sec.status);

    const items = container.querySelector('.items');
    if(items){
      if(sec.ok!==true) items.classList.add('open');
      else items.classList.remove('open');
    }

    const btn = container.querySelector('.details-btn');
    if(btn){
      if(sec.ok!==true) btn.classList.add('visible');
      else btn.classList.remove('visible');
    }

    const debugPanel = container.querySelector('.debug-panel');
    if(debugPanel && sec.debug){
      const debugPre = debugPanel.querySelector('pre');
      if(debugPre) debugPre.textContent = JSON.stringify(sec.debug, null, 2);
    }

    const ul = container.querySelector('.board');
    if(!ul) return;

    (sec.items||[]).forEach((it,i)=>{
      const li = ul.children[i];
      if(!li) return;
      const ck = li.querySelector('.check');
      if(ck){
        ck.innerHTML=liIcon(it.ok,it.status,it.label);
        ck.style.color=liColor(it.ok,it.status,it.label);
      }
      const note = li.querySelector('.note');
      if(note) note.textContent = it.note||'';
    });
  });
}

refresh();
</script>
</body></html>
"""

# ========== MAIN ==========

if __name__ == "__main__":
    # Start background refresher
    threading.Thread(target=board_refresher, args=(2,), daemon=True).start()

    print("=" * 80)
    print("VECTOR MANAGEMENT DASHBOARD (COMPREHENSIVE)")
    print("=" * 80)
    print(f"\nOpen in browser: http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    print("=" * 80 + "\n")

    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
