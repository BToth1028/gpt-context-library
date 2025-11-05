#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MVM_DASH.py - Vector Management Dashboard (fixed syntax/indent only)
- No features changed: same endpoints, layout, watch mode logic, and parsing as your current V3 build.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, jsonify, render_template_string, request, g
import json, os, subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import glob
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from collections import deque
import socket
import http.client

try:
    import psutil
except Exception:
    psutil = None

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "40_RUNTIME" / "00_CONTROL" / "00_CODE" / "00_CORE"))
try:
    import queue_db
    import process_guard
except ImportError as e:
    print(f"Warning: Could not import queue system modules: {e}")
    queue_db = None
    process_guard = None

# ---------- CONFIG ----------


@dataclass
class LogSource:
    prefixes: Tuple[str, ...]


@dataclass
class EventMap:
    init_start: Tuple[str, ...] = ("control_start", "control_init")
    initialized: Tuple[str, ...] = ("health_invoked", "control_ready", "control_initialized")
    watch_extract: Tuple[str, ...] = ("watch_extract",)
    watch_vector: Tuple[str, ...] = ("watch_vector", "watch_vector_skipped")
    extraction_events: Tuple[str, ...] = ("extract_invoked", "watch_extract", "extract_complete")
    vectorization_events: Tuple[str, ...] = (
        "vector_invoked",
        "watch_vector",
        "watch_vector_skipped",
        "bulk_batch_progress",
        "vectorization_complete",
    )
    health_check: Tuple[str, ...] = ("services_and_db_complete", "normal_exit")
    qdrant_restart: Tuple[str, ...] = ("qdrant_forced_restart", "qdrant_restart_attempted")
    ollama_restart: Tuple[str, ...] = ("ollama_forced_restart", "ollama_restart_attempted")
    extract_complete: Tuple[str, ...] = ("extract_complete",)
    extract_stats: Tuple[str, ...] = ("filtering_complete", "dedupe_complete", "state_write_complete")
    vector_complete: Tuple[str, ...] = ("vectorization_complete",)
    vector_stats: Tuple[str, ...] = ("batch_complete", "qdrant_write_complete", "mvm_write_complete")


@dataclass
class SectionConfig:
    key: str
    title: str
    control: LogSource
    extraction: Optional[LogSource] = None
    vector: Optional[LogSource] = None
    events: EventMap = field(default_factory=EventMap)


# Root folder with env override
ROOT = Path(os.environ.get("MVM_ROOT", Path(__file__).resolve().parents[5]))
PORT = int(os.environ.get("MVM_PORT", "5000"))
TZ = ZoneInfo(os.environ.get("MVM_TZ", "America/New_York"))
TIMESTAMP_FMT = "%m/%d %H:%M"
MAX_TAIL = 8000

# Centralized freshness thresholds (seconds)
FRESHNESS_THRESHOLDS = {
    "default": 60,
    "watch_sub": 90,
    "extract": 120,
    "vector": 120,
    "idle": 300,
    "restart_grace": 60,
    "stale_error_window": 120,
}

CONFIG: List[SectionConfig] = [
    SectionConfig(
        key="S00",
        title="S00 - Coordinator",
        control=LogSource(prefixes=("control_",)),
        extraction=LogSource(prefixes=("extraction_",)),
        vector=LogSource(prefixes=("vectorization_", "vectorize_")),
    ),
    SectionConfig(
        key="S01",
        title="S01 - Health",
        control=LogSource(prefixes=("health_",)),
    ),
    SectionConfig(
        key="S02",
        title="S02 - Extractor",
        control=LogSource(prefixes=("extraction_",)),
    ),
    SectionConfig(
        key="S03",
        title="S03 - Vectorization",
        control=LogSource(prefixes=("vectorization_", "vectorize_")),
    ),
]

# ---------- LOGGING ----------

LOGFILE = Path(__file__).with_suffix(".log")
LOGFILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("vector_dash")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

fh = RotatingFileHandler(LOGFILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
fh.setFormatter(fmt)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(fmt)

if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)

logger.info("=== Vector Management starting (pid=%s, cwd=%s) ===", os.getpid(), os.getcwd())

# ---------- BOARD CACHE ----------

import threading

BOARD_CACHE = {"json": {"title": "Vector Management", "sections": [], "refresh_ms": 5000}, "ts": 0.0, "err": None}


def _build_board_json():
    t0 = time.time()
    logger.info("board: build start")
    try:
        sections = [build_section(s) for s in CONFIG]
        return {"title": "Vector Management", "sections": sections, "refresh_ms": 5000}
    finally:
        logger.info("board: build done in %.1f ms", (time.time() - t0) * 1000)


def _board_refresher(interval=5):
    while True:
        t0 = time.time()
        try:
            data = _build_board_json()
            BOARD_CACHE.update({"json": data, "ts": t0, "err": None})
        except Exception as e:
            BOARD_CACHE.update({"err": str(e)})
            logger.exception("board: refresh error")
        delay = max(1.0, interval - (time.time() - t0))
        time.sleep(delay)


# Background thread will start AFTER all functions are defined (see bottom of file)

# ---------- UTIL ----------


def latest_file_recursive(root: Path, prefixes: Tuple[str, ...]) -> Optional[Path]:
    """Find the newest *.ndjson matching any prefix anywhere under root."""
    paths: List[str] = []
    for px in prefixes:
        glob_pat = str(root / "**" / f"{px}*.ndjson")
        paths += glob.glob(glob_pat, recursive=True)
    if not paths:
        return None
    paths_p = [Path(p) for p in paths]
    return max(paths_p, key=lambda p: p.stat().st_mtime)


def get_current_log(root: Path, component: str) -> Optional[Path]:
    """Get CURRENT symlink for a component's log file."""
    log_map = {
        "control": root / "00_CONTROL/01_OUTPUT/control_CURRENT.ndjson",
        "extraction": root / "02_EXTRACT/01_OUTPUT/extraction_CURRENT.ndjson",
        "vectorization": root / "03_VECTOR/01_OUTPUT/vectorization_CURRENT.ndjson",
        "health": root / "01_HEALTH/01_OUTPUT/health_CURRENT.ndjson",
    }
    log_path = log_map.get(component)
    if log_path and (log_path.exists() or log_path.is_symlink()):
        return log_path
    return None


def tail_ndjson(path: Optional[Path], n=MAX_TAIL) -> List[Dict[str, Any]]:
    """Tail an NDJSON file using deque for better performance."""
    if path is None or not path.exists():
        return []
    dq = deque(maxlen=n)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    dq.append(json.loads(s))
                except Exception:
                    continue
    except Exception:
        return []
    return list(dq)


def last_event_ts(events: List[Dict[str, Any]], names: Tuple[str, ...]) -> Optional[str]:
    """Return ts/ timestamp of the last event whose name is in names (unchanged)."""
    for x in reversed(events):
        if x.get("event") in names:
            ts = x.get("ts") or x.get("timestamp")
            if ts:
                return ts
    return None


def fmt_est(ts_str: Optional[str]) -> str:
    """Format ts string into local TZ label (unchanged)."""
    if not ts_str:
        return ""
    fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S")
    for f in fmts:
        try:
            dt = datetime.strptime(ts_str, f)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(TZ).strftime(TIMESTAMP_FMT)
        except Exception:
            pass
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(TZ).strftime(TIMESTAMP_FMT)
    except Exception:
        return ts_str


def aggregate_ok(items: List[Dict[str, Any]]) -> Tuple[Optional[bool], str]:
    """Aggregate section status from items/subitems with clearer no-data handling."""
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


# ---------- LIVE PROBES ----------


def tcp_ping(host: str, port: int, timeout: float = 0.8) -> Tuple[bool, float, Optional[str]]:
    """TCP connection probe with latency measurement."""
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
        except Exception:
            pass
        return False, (time.time() - t0) * 1000.0, str(e)


def http_get(
    host: str, port: int, path: str, timeout: float = 1.2, secure: bool = False
) -> Tuple[int, Dict[str, str], str, float, Optional[str]]:
    """HTTP GET probe with latency and response capture."""
    t0 = time.time()
    conn = (http.client.HTTPSConnection if secure else http.client.HTTPConnection)(host, port, timeout=timeout)
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
        except Exception:
            pass


def find_procs(names=("qdrant", "ollama")) -> Dict[str, List[int]]:
    """Find running processes by name."""
    out = {n: [] for n in names}
    if not psutil:
        return out
    try:
        for p in psutil.process_iter(["name", "exe", "pid", "cmdline"]):
            n = (p.info.get("name") or "").lower()
            for target in names:
                if target in n or any(target in (c or "").lower() for c in p.info.get("cmdline") or []):
                    out[target].append(p.info["pid"])
    except Exception:
        pass
    return out


def probe_qdrant(host="127.0.0.1", port=6333, collection_hint=None) -> Dict[str, Any]:
    """Comprehensive Qdrant health probe."""
    tcp_ok, tcp_ms, tcp_err = tcp_ping(host, port)
    health_code, health_hdr, health_body, health_ms, health_err = http_get(host, port, "/healthz")
    ver_code, ver_hdr, ver_body, ver_ms, ver_err = http_get(host, port, "/")
    coll_code, coll_hdr, coll_body, coll_ms, coll_err = http_get(host, port, "/collections")

    info = {
        "tcp": {"ok": tcp_ok, "ms": round(tcp_ms, 1), "err": tcp_err},
        "healthz": {"code": health_code, "ms": round(health_ms, 1), "err": health_err, "body": health_body[:512]},
        "version": {"code": ver_code, "ms": round(ver_ms, 1), "err": ver_err, "body": ver_body[:512]},
        "collections": {"code": coll_code, "ms": round(coll_ms, 1), "err": coll_err, "body": coll_body[:512]},
    }

    try:
        data = json.loads(coll_body) if coll_code == 200 else {}
        info["collections"]["parsed_count"] = len((data or {}).get("result", {}).get("collections", []))
    except Exception:
        info["collections"]["parsed_count"] = None

    if collection_hint and info["collections"].get("parsed_count"):
        cpath = f"/collections/{collection_hint}"
        c_code, _, c_body, c_ms, c_err = http_get(host, port, cpath)
        info["collection"] = {
            "name": collection_hint,
            "code": c_code,
            "ms": round(c_ms, 1),
            "err": c_err,
            "body": c_body[:512],
        }

    return info


def probe_ollama(host="127.0.0.1", port=11434) -> Dict[str, Any]:
    """Comprehensive Ollama health probe."""
    tcp_ok, tcp_ms, tcp_err = tcp_ping(host, port)
    ver_code, ver_hdr, ver_body, ver_ms, ver_err = http_get(host, port, "/api/version")
    tags_code, tags_hdr, tags_body, tags_ms, tags_err = http_get(host, port, "/api/tags")

    info = {
        "tcp": {"ok": tcp_ok, "ms": round(tcp_ms, 1), "err": tcp_err},
        "version": {"code": ver_code, "ms": round(ver_ms, 1), "err": ver_err, "body": ver_body[:512]},
        "tags": {"code": tags_code, "ms": round(tags_ms, 1), "err": tags_err, "body": tags_body[:512]},
    }

    try:
        tags = json.loads(tags_body) if tags_code == 200 else {}
        models = [m.get("name") for m in (tags.get("models") or [])]
        info["models"] = models[:12]
        info["model_count"] = len(models)
    except Exception:
        info["models"] = None
        info["model_count"] = None

    return info


# ---------- SECTION BUILDERS ----------


def is_timestamp_fresh(ts_str: Optional[str], max_age_seconds: int = 60) -> bool:
    """Check if timestamp is recent enough to indicate active process (unchanged logic)."""
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
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        age = datetime.now(ZoneInfo("UTC")) - dt
        return age.total_seconds() <= max_age_seconds
    except Exception:
        return False


def freshness_band(ts_str: Optional[str], fresh: int, aging: int) -> str:
    """
    Classify timestamp into freshness bands for gradual status transitions.

    Returns:
        'fresh' : age <= fresh (green)
        'aging' : fresh < age <= aging (yellow soft warning)
        'stale' : age > aging (red error)
    """
    if not ts_str:
        return "stale"
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
            return "stale"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        age = (datetime.now(ZoneInfo("UTC")) - dt).total_seconds()
        if age <= fresh:
            return "fresh"
        if age <= aging:
            return "aging"
        return "stale"
    except Exception:
        return "stale"


def build_s00(sec: SectionConfig) -> Dict[str, Any]:
    """Build S00 Coordinator section with comprehensive debug."""
    cfile = get_current_log(ROOT, "control")
    efile = get_current_log(ROOT, "extraction")
    vfile = get_current_log(ROOT, "vectorization")

    c_evs = tail_ndjson(cfile)
    e_evs = tail_ndjson(efile)
    v_evs = tail_ndjson(vfile)

    em = sec.events
    ts_init_start = last_event_ts(c_evs, em.init_start)
    ts_initialized = last_event_ts(c_evs, em.initialized)
    ts_watch_extract = last_event_ts(c_evs, em.watch_extract)
    ts_watch_vector = last_event_ts(c_evs, em.watch_vector)

    ts_extract = last_event_ts(e_evs, em.extraction_events)
    ts_vector = last_event_ts(v_evs, em.vectorization_events)

    all_timestamps = [
        ts for ts in [ts_init_start, ts_initialized, ts_watch_extract, ts_watch_vector, ts_extract, ts_vector] if ts
    ]
    most_recent_ts = max(all_timestamps, default=None, key=lambda t: t)

    is_running = is_timestamp_fresh(most_recent_ts, max_age_seconds=60)

    items: List[Dict[str, Any]] = []

    has_watch = ts_watch_extract or ts_watch_vector or ts_extract or ts_vector
    fallback_ts = ts_extract or ts_vector or ts_watch_extract or ts_watch_vector

    # Single "Initialized" tile (removed redundant "Initializing")
    if has_watch and is_running:
        items.append({"label": "Initialized", "ok": True, "note": fmt_est(fallback_ts)})
    elif ts_initialized and is_running:
        items.append({"label": "Initialized", "ok": True, "note": fmt_est(ts_initialized)})
    elif ts_init_start and is_running:
        items.append({"label": "Initialized", "ok": True, "note": fmt_est(ts_init_start)})
    else:
        items.append({"label": "Initialized", "ok": False, "note": "not running"})

    if has_watch and is_running:
        sub: List[Dict[str, Any]] = []

        # Extraction subitem with freshness bands + idle detection
        if ts_extract:
            band = freshness_band(ts_extract, FRESHNESS_THRESHOLDS["watch_sub"], FRESHNESS_THRESHOLDS["idle"])
            if band == "fresh":
                sub.append({"label": "Extraction", "ok": True, "note": fmt_est(ts_extract)})
            elif band == "aging":
                sub.append({"label": "Extraction", "ok": None, "note": fmt_est(ts_extract)})
            else:
                if not is_timestamp_fresh(ts_extract, FRESHNESS_THRESHOLDS["idle"]):
                    sub.append({"label": "Extraction", "ok": None, "status": "idle", "note": fmt_est(ts_extract)})
                else:
                    sub.append({"label": "Extraction", "ok": False, "note": fmt_est(ts_extract)})

        # Vectorization subitem with freshness bands + idle detection
        ts_vector_final = max([t for t in [ts_vector, ts_watch_vector] if t], default=None, key=lambda x: x)
        if ts_vector_final:
            band = freshness_band(ts_vector_final, FRESHNESS_THRESHOLDS["watch_sub"], FRESHNESS_THRESHOLDS["idle"])
            if band == "fresh":
                sub.append({"label": "Vectorization", "ok": True, "note": fmt_est(ts_vector_final)})
            elif band == "aging":
                sub.append({"label": "Vectorization", "ok": None, "note": fmt_est(ts_vector_final)})
            else:
                if not is_timestamp_fresh(ts_vector_final, FRESHNESS_THRESHOLDS["idle"]):
                    sub.append(
                        {"label": "Vectorization", "ok": None, "status": "idle", "note": fmt_est(ts_vector_final)}
                    )
                else:
                    sub.append({"label": "Vectorization", "ok": False, "note": fmt_est(ts_vector_final)})

        watch_mode_ts = ts_extract or ts_vector_final or fallback_ts
        items.append({"label": "Watch Mode", "ok": True, "note": fmt_est(watch_mode_ts), "subitems": sub})
    elif has_watch:
        items.append({"label": "Watch Mode", "ok": False, "note": "stopped", "subitems": []})

    queue_stats = None
    if queue_db:
        try:
            s = queue_db.stats()  # returns {'extract': {...}, 'vectorize': {...}}
            queue_stats = {
                "extraction": {
                    "queued": s.get("extract", {}).get("queued", 0),
                    "running": s.get("extract", {}).get("running", 0),
                    "failed": s.get("extract", {}).get("failed", 0),
                },
                "vectorization": {
                    "queued": s.get("vectorize", {}).get("queued", 0),
                    "running": s.get("vectorize", {}).get("running", 0),
                    "failed": s.get("vectorize", {}).get("failed", 0),
                },
            }
        except Exception:
            queue_stats = None

    # COMPREHENSIVE DEBUG
    debug = {
        "log_files": {
            "control": str(cfile) if cfile else None,
            "extraction": str(efile) if efile else None,
            "vectorization": str(vfile) if vfile else None,
        },
        "event_counts": {
            "control_events": len(c_evs),
            "extraction_events": len(e_evs),
            "vectorization_events": len(v_evs),
        },
        "timestamps": {
            "init_start": ts_init_start,
            "initialized": ts_initialized,
            "watch_extract": ts_watch_extract,
            "watch_vector": ts_watch_vector,
            "extract": ts_extract,
            "vector": ts_vector,
            "most_recent": most_recent_ts,
        },
        "watch_iterations": {
            "extract": max([e.get("iteration", 0) for e in c_evs if e.get("event") == "watch_extract"], default=0),
            "vector": max(
                [e.get("iteration", 0) for e in c_evs if e.get("event") in ("watch_vector", "watch_vector_skipped")],
                default=0,
            ),
        },
        "interval_config": next((e.get("interval_sec") for e in reversed(c_evs) if "interval_sec" in e), None),
        "last_errors": [e for e in reversed(c_evs) if e.get("level") in ("ERROR", "WARN")][:5],
        "is_running": is_running,
        "has_watch_mode": has_watch,
        "queue": queue_stats,
    }

    ok, status = aggregate_ok(items)
    return {"key": sec.key, "title": sec.title, "ok": ok, "status": status, "items": items, "debug": debug}


def build_s01(sec: SectionConfig) -> Dict[str, Any]:
    """Build S01 Health section with LIVE PROBES."""
    hfile = get_current_log(ROOT, "health")
    h_evs = tail_ndjson(hfile)

    em = sec.events
    ts_health = last_event_ts(h_evs, em.health_check)
    ts_qdrant_restart = last_event_ts(h_evs, em.qdrant_restart)
    ts_ollama_restart = last_event_ts(h_evs, em.ollama_restart)

    last_complete = None
    for x in reversed(h_evs):
        if x.get("event") == "services_and_db_complete":
            last_complete = x
            break
    has_health_data = last_complete is not None

    # === LIVE PROBES ===
    vfile_for_health = get_current_log(ROOT, "vectorization")
    v_evs_for_health = tail_ndjson(vfile_for_health)
    collection_hint = next(
        (
            e.get("collection")
            for e in reversed(v_evs_for_health)
            if e.get("event") == "qdrant_initialized" and e.get("collection")
        ),
        None,
    )

    q_probe = probe_qdrant(collection_hint=collection_hint)
    o_probe = probe_ollama()
    procs = find_procs()

    # Recent vectorization activity
    recent_qdrant_errors = [
        e
        for e in v_evs_for_health
        if e.get("event") == "qdrant_init_failed" and is_timestamp_fresh(e.get("ts"), max_age_seconds=300)
    ]
    recent_qdrant_success = [
        e
        for e in v_evs_for_health
        if e.get("event") in ("qdrant_initialized", "qdrant_write_complete")
        and is_timestamp_fresh(e.get("ts"), max_age_seconds=300)
    ]
    qdrant_activity_ts = None
    if recent_qdrant_success or recent_qdrant_errors:
        all_q = recent_qdrant_success + recent_qdrant_errors
        qdrant_activity_ts = max([e.get("ts") for e in all_q if e.get("ts")], default=None)

    items: List[Dict[str, Any]] = []

    # Qdrant tile — TRUST CURRENT PROBE over stale health data
    qdrant_restarting = ts_qdrant_restart and is_timestamp_fresh(
        ts_qdrant_restart, FRESHNESS_THRESHOLDS["restart_grace"]
    )

    # Current probe status (live TCP + HTTP checks)
    q_probe_ok = q_probe["tcp"]["ok"] and q_probe["healthz"]["code"] == 200 and q_probe["collections"]["code"] == 200

    if not has_health_data:
        items.append({"label": "Qdrant", "ok": None, "note": "checking..."})
    elif "qdrant" in last_complete:
        # If current probe is OK, ignore stale errors from health check
        if q_probe_ok:
            qdrant_ok = True
            note = fmt_est(qdrant_activity_ts) if qdrant_activity_ts else fmt_est(ts_health)
        else:
            # Probe failed — trust that over old health data
            qdrant_ok = False
            if q_probe["tcp"]["ok"] is False:
                note = "port closed"
            elif q_probe["healthz"]["code"] != 200:
                note = f"HTTP {q_probe['healthz']['code']}"
            else:
                note = fmt_est(ts_health) if ts_health else "---"

        if qdrant_restarting and not qdrant_ok:
            note = "restarting..."
        items.append({"label": "Qdrant", "ok": qdrant_ok if not qdrant_restarting else None, "note": note})
    else:
        items.append({"label": "Qdrant", "ok": None, "note": "---"})

    # Ollama tile — TRUST CURRENT PROBE over stale health data
    ollama_restarting = ts_ollama_restart and is_timestamp_fresh(
        ts_ollama_restart, FRESHNESS_THRESHOLDS["restart_grace"]
    )

    # Current probe status
    o_probe_ok = (
        o_probe["tcp"]["ok"]
        and o_probe["version"]["code"] == 200
        and o_probe["tags"]["code"] == 200
        and (o_probe.get("model_count") or 0) > 0
    )

    if not has_health_data:
        items.append({"label": "Ollama", "ok": None, "note": "checking..."})
    elif "ollama" in last_complete:
        # If current probe is OK, ignore stale errors
        if o_probe_ok:
            ollama_ok = True
            note = fmt_est(ts_health) if ts_health else "ready"
        else:
            # Probe failed
            ollama_ok = False
            if o_probe["tcp"]["ok"] is False:
                note = "port closed"
            elif o_probe["version"]["code"] != 200:
                note = f"HTTP {o_probe['version']['code']}"
            elif (o_probe.get("model_count") or 0) == 0:
                note = "no models"
            else:
                note = fmt_est(ts_health) if ts_health else "---"

        if ollama_restarting and not ollama_ok:
            note = "restarting..."
        items.append({"label": "Ollama", "ok": ollama_ok if not ollama_restarting else None, "note": note})
    else:
        items.append({"label": "Ollama", "ok": None, "note": "---"})

    # Database tile
    if not has_health_data:
        items.append({"label": "Database", "ok": None, "note": "checking..."})
    elif "state_db" in last_complete:
        state_db = last_complete["state_db"]
        db_ok = state_db.get("exists", False) and state_db.get("integrity") == "ok"
        items.append({"label": "Database", "ok": db_ok, "note": fmt_est(ts_health) if ts_health else ""})
    else:
        items.append({"label": "Database", "ok": None, "note": "---"})

    # === COMPREHENSIVE DEBUG with PROBES and CONTRADICTIONS ===
    contradictions = {
        "qdrant": (
            (last_complete and "qdrant" in last_complete and last_complete["qdrant"].get("running", False))
            and (not q_probe["tcp"]["ok"] or q_probe["healthz"]["code"] != 200)
        ),
        "ollama": (
            (last_complete and "ollama" in last_complete and last_complete["ollama"].get("running", False))
            and (not o_probe["tcp"]["ok"] or o_probe["version"]["code"] != 200)
        ),
    }

    # Filter out stale errors if current probe is OK (don't confuse user)
    all_errors = [e for e in reversed(h_evs) if e.get("level") in ("ERROR", "WARN")][:10]
    if q_probe_ok:
        # Remove old qdrant_unreachable errors if service is UP NOW
        all_errors = [
            e
            for e in all_errors
            if e.get("event") != "qdrant_unreachable"
            or is_timestamp_fresh(e.get("ts", ""), FRESHNESS_THRESHOLDS["stale_error_window"])
        ]
    if o_probe_ok:
        # Remove old ollama errors if service is UP NOW
        all_errors = [
            e
            for e in all_errors
            if e.get("event") not in ("ollama_unreachable", "ollama_not_responding")
            or is_timestamp_fresh(e.get("ts", ""), FRESHNESS_THRESHOLDS["stale_error_window"])
        ]

    debug = {
        "log_file": str(hfile) if hfile else None,
        "event_count": len(h_evs),
        "last_health_check": ts_health,
        "has_health_data": has_health_data,
        "service_details": last_complete if last_complete else {},
        "restart_attempts": {"qdrant_last": ts_qdrant_restart, "ollama_last": ts_ollama_restart},
        "probes": {
            "qdrant": q_probe,
            "ollama": o_probe,
            "procs": procs,
        },
        "current_status": {
            "qdrant_ok": q_probe_ok,
            "ollama_ok": o_probe_ok,
            "note": "Current probe results (overrides stale health data)",
        },
        "contradictions": contradictions,
        "vector_recent": {
            "errors_5m": len(recent_qdrant_errors),
            "success_5m": len(recent_qdrant_success),
            "last_activity_ts": qdrant_activity_ts,
        },
        "qdrant_from_vecto": next(
            (
                {"host": e.get("host"), "port": e.get("port"), "collection": e.get("collection")}
                for e in reversed(v_evs_for_health)
                if e.get("event") == "qdrant_initialized"
            ),
            None,
        ),
        "ollama_model_from_vecto": next(
            (e.get("model") for e in reversed(v_evs_for_health) if e.get("event") == "ollama_initialized"),
            None,
        ),
        "last_errors": all_errors[:5],
    }

    ok, status = aggregate_ok(items)
    return {"key": sec.key, "title": sec.title, "ok": ok, "status": status, "items": items, "debug": debug}


def build_s02(sec: SectionConfig) -> Dict[str, Any]:
    """Build S02 Extractor section."""
    efile = get_current_log(ROOT, "extraction")
    e_evs = tail_ndjson(efile)

    em = sec.events
    ts_extract = last_event_ts(e_evs, em.extract_complete)

    # Get last complete extraction for stats
    last_extract = None
    last_filter = None
    last_dedupe = None
    last_write = None

    for x in reversed(e_evs):
        if not last_extract and x.get("event") == "extract_complete":
            last_extract = x
        if not last_filter and x.get("event") == "filtering_complete":
            last_filter = x
        if not last_dedupe and x.get("event") == "dedupe_complete":
            last_dedupe = x
        if not last_write and x.get("event") == "state_write_complete":
            last_write = x
        if last_extract and last_filter and last_dedupe and last_write:
            break

    has_data = last_extract is not None
    is_running = is_timestamp_fresh(ts_extract, FRESHNESS_THRESHOLDS["extract"])

    items: List[Dict[str, Any]] = []

    # Extraction status with freshness bands + idle detection
    if not has_data:
        items.append({"label": "Extraction", "ok": None, "note": "checking..."})
    else:
        band = freshness_band(ts_extract, FRESHNESS_THRESHOLDS["extract"], FRESHNESS_THRESHOLDS["idle"])
        if band == "fresh":
            items.append({"label": "Extraction", "ok": True, "note": fmt_est(ts_extract)})
        elif band == "aging":
            items.append({"label": "Extraction", "ok": None, "note": fmt_est(ts_extract)})
        else:
            if not is_timestamp_fresh(ts_extract, FRESHNESS_THRESHOLDS["idle"]):
                items.append({"label": "Extraction", "ok": None, "status": "idle", "note": fmt_est(ts_extract)})
            else:
                items.append({"label": "Extraction", "ok": False, "note": fmt_est(ts_extract) if ts_extract else "---"})

    # Records extracted
    if last_write:
        count = last_write.get("inserted", 0)
        items.append({"label": "Records Extracted", "ok": True if count > 0 else None, "note": str(count)})
    elif has_data:
        items.append({"label": "Records Extracted", "ok": None, "note": "---"})

    # Deduplication
    if last_dedupe:
        dupes = last_dedupe.get("duplicates_removed", 0)
        items.append({"label": "Duplicates Removed", "ok": True, "note": str(dupes)})
    elif has_data:
        items.append({"label": "Duplicates Removed", "ok": None, "note": "---"})

    # COMPREHENSIVE DEBUG
    debug = {
        "log_file": str(efile) if efile else None,
        "event_count": len(e_evs),
        "last_extraction": ts_extract,
        "has_data": has_data,
        "is_running": is_running,
        "extraction_stats": {
            "total_bubbles": (
                last_filter.get("kept", 0)
                + last_filter.get("discarded_empty", 0)
                + last_filter.get("discarded_borderline", 0)
                if last_filter
                else 0
            ),
            "kept": last_filter.get("kept", 0) if last_filter else 0,
            "discarded_empty": last_filter.get("discarded_empty", 0) if last_filter else 0,
            "discarded_borderline": last_filter.get("discarded_borderline", 0) if last_filter else 0,
            "kept_borderline": last_filter.get("kept_borderline", 0) if last_filter else 0,
        },
        "deduplication": {
            "before": last_dedupe.get("before", 0) if last_dedupe else 0,
            "after": last_dedupe.get("after", 0) if last_dedupe else 0,
            "duplicates_removed": last_dedupe.get("duplicates_removed", 0) if last_dedupe else 0,
            "existing_sources": last_dedupe.get("existing_sources", 0) if last_dedupe else 0,
        },
        "database_writes": {
            "proc_db_inserted": last_write.get("inserted", 0) if last_write else 0,
            "state_db_inserted": last_write.get("inserted", 0) if last_write else 0,
        },
        "baseline": next((e for e in reversed(e_evs) if e.get("event") == "baseline_saved"), None),
        "last_errors": [e for e in reversed(e_evs) if e.get("level") in ("ERROR", "WARN")][:5],
    }

    ok, status = aggregate_ok(items)
    return {"key": sec.key, "title": sec.title, "ok": ok, "status": status, "items": items, "debug": debug}


def build_s03(sec: SectionConfig) -> Dict[str, Any]:
    """Build S03 Vectorization section."""
    vfile = get_current_log(ROOT, "vectorization")
    v_evs = tail_ndjson(vfile)

    em = sec.events
    ts_vector = last_event_ts(v_evs, em.vector_complete)

    # Get last complete vectorization for stats
    last_vector = None
    last_batch = None
    last_qdrant_write = None
    last_mvm_write = None

    for x in reversed(v_evs):
        if not last_vector and x.get("event") == "vectorization_complete":
            last_vector = x
        if not last_batch and x.get("event") == "batch_complete":
            last_batch = x
        if not last_qdrant_write and x.get("event") == "qdrant_write_complete":
            last_qdrant_write = x
        if not last_mvm_write and x.get("event") == "mvm_write_complete":
            last_mvm_write = x
        if last_vector and last_batch and last_qdrant_write and last_mvm_write:
            break

    has_data = last_vector is not None
    is_running = is_timestamp_fresh(ts_vector, FRESHNESS_THRESHOLDS["vector"])

    # Check if CURRENTLY experiencing failures (last event was a failure, not a success)
    actively_failing = False
    if v_evs:
        # Get most recent embedding-related events
        embedding_events = [
            e
            for e in reversed(v_evs)
            if e.get("event")
            in ("embedding_failed", "vectorization_complete", "batch_complete", "qdrant_write_complete")
        ]
        if embedding_events:
            last_event_type = embedding_events[0].get("event")
            last_embed_ts = embedding_events[0].get("ts")

            # If last event was a failure, check if it's recent
            if last_event_type == "embedding_failed":
                if is_timestamp_fresh(last_embed_ts, FRESHNESS_THRESHOLDS["vector"]):
                    actively_failing = True

    items: List[Dict[str, Any]] = []

    # Vectorization status with freshness bands + idle detection + active failure overlay
    if not has_data:
        items.append({"label": "Vectorization", "ok": None, "note": "checking..."})
    else:
        band = freshness_band(ts_vector, FRESHNESS_THRESHOLDS["vector"], FRESHNESS_THRESHOLDS["idle"])
        if band == "stale":
            if not is_timestamp_fresh(ts_vector, FRESHNESS_THRESHOLDS["idle"]):
                items.append({"label": "Vectorization", "ok": None, "status": "idle", "note": fmt_est(ts_vector)})
            else:
                items.append(
                    {"label": "Vectorization", "ok": False, "note": fmt_est(ts_vector) if ts_vector else "---"}
                )
        elif band == "aging":
            # Yellow "aging" — but if actively failing, mark as 'warning' for gear icon
            if actively_failing:
                items.append({"label": "Vectorization", "ok": None, "status": "warning", "note": fmt_est(ts_vector)})
            else:
                items.append({"label": "Vectorization", "ok": None, "note": fmt_est(ts_vector)})
        else:  # fresh
            if actively_failing:
                items.append({"label": "Vectorization", "ok": None, "status": "warning", "note": fmt_est(ts_vector)})
            else:
                items.append({"label": "Vectorization", "ok": True, "note": fmt_est(ts_vector)})

    # Records vectorized
    if last_batch:
        count = last_batch.get("processed", 0)
        items.append({"label": "Records Processed", "ok": True if count > 0 else None, "note": str(count)})
    elif has_data:
        items.append({"label": "Records Processed", "ok": None, "note": "---"})

    # Qdrant writes
    if last_qdrant_write:
        count = last_qdrant_write.get("count", 0)
        items.append({"label": "Qdrant Writes", "ok": True if count > 0 else None, "note": str(count)})
    elif has_data:
        items.append({"label": "Qdrant Writes", "ok": None, "note": "---"})

    # COMPREHENSIVE DEBUG
    debug = {
        "log_file": str(vfile) if vfile else None,
        "event_count": len(v_evs),
        "last_vectorization": ts_vector,
        "has_data": has_data,
        "is_running": is_running,
        "batch_stats": {
            "last_batch_size": last_batch.get("processed", 0) if last_batch else 0,
            "queue_size": next((e.get("queue_size", 0) for e in reversed(v_evs) if "queue_size" in e), 0),
        },
        "writes": {
            "qdrant_count": last_qdrant_write.get("count", 0) if last_qdrant_write else 0,
            "mvm_count": last_mvm_write.get("count", 0) if last_mvm_write else 0,
        },
        "model_info": next(
            (
                {"model": e.get("model"), "dimensions": e.get("dimensions")}
                for e in reversed(v_evs)
                if e.get("event") == "ollama_initialized"
            ),
            None,
        ),
        "qdrant_info": next(
            (
                {"host": e.get("host"), "port": e.get("port"), "collection": e.get("collection")}
                for e in reversed(v_evs)
                if e.get("event") == "qdrant_initialized"
            ),
            None,
        ),
        "mode": next(
            (e.get("event") for e in reversed(v_evs) if e.get("event") in ("mode_instant", "mode_batch")), None
        ),
        "last_errors": [e for e in reversed(v_evs) if e.get("level") in ("ERROR", "WARN")][:5],
        "embedding_failures": len([e for e in v_evs if e.get("event") == "embedding_failed"]),
    }

    ok, status = aggregate_ok(items)
    return {"key": sec.key, "title": sec.title, "ok": ok, "status": status, "items": items, "debug": debug}


def build_section(sec: SectionConfig) -> Dict[str, Any]:
    if sec.key == "S01":
        return build_s01(sec)
    elif sec.key == "S02":
        return build_s02(sec)
    elif sec.key == "S03":
        return build_s03(sec)
    return build_s00(sec)


# ---------- APP ----------

app = Flask(__name__)


@app.before_request
def _dbg_start():
    g._t0 = time.time()
    if request.path.startswith("/api/"):
        logger.info(
            "→ API %s %s from %s origin=%s ua=%s",
            request.method,
            request.path,
            request.remote_addr,
            request.headers.get("Origin"),
            request.headers.get("User-Agent"),
        )


@app.after_request
def no_store(resp):
    try:
        dur = (time.time() - g.get("_t0", time.time())) * 1000.0
        if request.path.startswith("/api/"):
            logger.info("← API %s %s -> %s in %.1f ms", request.method, request.path, resp.status_code, dur)
    except Exception:
        pass

    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"

    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin") or "null"
        allowed = {"null", f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
        resp.headers["Access-Control-Allow-Origin"] = origin if origin in allowed else f"http://127.0.0.1:{PORT}"
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/<path:_>", methods=["OPTIONS"])
def _api_preflight(_):
    return ("", 204)


@app.errorhandler(Exception)
def _dbg_ex(e):
    logger.exception("!! Unhandled exception on %s %s", request.method, request.path)
    return jsonify(error=str(e)), 500


@app.get("/")
def index():
    return render_template_string(HTML.replace("{{{PORT}}}", str(PORT)), app_title="Vector Management", PORT=PORT)


@app.get("/api/ping")
def api_ping():
    return jsonify(status="ok", ts=time.time())


@app.get("/api/diag")
def api_diag():
    info = {
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "ts": time.time(),
        "env_PORT": os.environ.get("MVM_PORT"),
        "client_ip": request.remote_addr,
        "origin": request.headers.get("Origin"),
        "user_agent": request.headers.get("User-Agent"),
    }
    return jsonify(info)


@app.post("/api/client-log")
def api_client_log():
    data = request.get_json(silent=True) or {}
    try:
        logger.warning("CLIENT %s", json.dumps(data, ensure_ascii=False))
    except Exception:
        logger.warning("CLIENT %r", data)
    return jsonify(ok=True)


@app.route("/api/board", methods=["GET", "OPTIONS"])
def api_board():
    if request.method == "OPTIONS":
        return "", 204
    payload = dict(BOARD_CACHE["json"])
    payload["generated_ts"] = BOARD_CACHE["ts"]
    if BOARD_CACHE["err"]:
        payload["server_note"] = f"Last refresh had an error: {BOARD_CACHE['err']}"
    return jsonify(payload)


@app.route("/api/restart", methods=["POST", "OPTIONS"])
def api_restart():
    """Safe in-place dashboard restart."""
    if request.method == "OPTIONS":
        return "", 204

    try:
        script_path = Path(__file__).resolve()

        if os.name == "nt":
            if process_guard:
                env = os.environ.copy()
                pid = process_guard.spawn_python(script_path, env=env, quiet=True)
                logger.info(f"Spawned replacement dashboard PID={pid}, exiting current")
            else:
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    creationflags=0x08000000,
                    cwd=str(script_path.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            def shutdown():
                time.sleep(1)
                os._exit(0)

            from threading import Thread

            Thread(target=shutdown, daemon=True).start()
            return jsonify({"status": "restarting"})
        else:
            os.execv(sys.executable, [sys.executable, str(script_path)])
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.get("/api/probe/services")
def api_probe_services():
    """Live probe of all services (Qdrant, Ollama, processes)."""
    vh = get_current_log(ROOT, "vectorization")
    hint = None
    if vh:
        for e in reversed(tail_ndjson(vh, 1000)):
            if e.get("event") == "qdrant_initialized" and e.get("collection"):
                hint = e.get("collection")
                break

    procs = find_procs()
    q = probe_qdrant(collection_hint=hint)
    o = probe_ollama()
    out = {"ts": time.time(), "procs": procs, "qdrant": q, "ollama": o}
    logger.info(
        "probe: services %s",
        {k: {"ok": v.get("tcp", {}).get("ok")} for k, v in [("qdrant", q), ("ollama", o)]},
    )
    return jsonify(out)


@app.get("/api/probe/qdrant")
def api_probe_qdrant():
    """Live probe of Qdrant only."""
    return jsonify(probe_qdrant())


@app.get("/api/probe/ollama")
def api_probe_ollama():
    """Live probe of Ollama only."""
    return jsonify(probe_ollama())


# ---------- FRONTEND (unchanged layout/logic) ----------

HTML = r"""
<!doctype html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ app_title }}</title>
<style>
:root{
  --bg:#0b1220; --panel:#0f172a; --panel2:#0b1426; --text:#e7ecf3; --muted:#94a3b8;
  --ok:#21c074; --warn:#f2b84c; --err:#ef5959; --loop:#4da6ff; --rule:#1e293b;
}
body{margin:0;background:var(--bg);color:var(--text);font:12px/1.4 Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto;display:flex;flex-direction:column;min-height:100vh}
.top-bar{display:none}
.wrap{flex:1;display:flex;align-items:center;padding:8px}
.card{width:100%;background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid #0a1a33;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.35)}
.header{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--rule);font-weight:700;font-size:14px}
.header .dot{margin-right:4px}
.header-title{flex:1}
.header-btn{padding:3px 6px;font-size:12px;font-weight:600;background:#1e3a5f;color:var(--text);border:1px solid #2d5a8f;border-radius:3px;cursor:pointer;transition:all .2s}
.header-btn:hover{background:#2d5a8f;border-color:#3d6a9f}
.master-debug-btn{display:none}
.master-debug-btn.visible{display:inline-block}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px rgba(33,192,116,0.14)}
.dot.warn{background:var(--warn);box-shadow:0 0 0 3px rgba(242,184,76,0.16)}
.dot.err{background:var(--err);box-shadow:0 0 0 3px rgba(239,89,89,0.18)}
.section{border-top:1px solid var(--rule)}
.sect-head{display:grid;grid-template-columns:12px 1fr 40px;align-items:center;gap:8px;padding:10px 12px}
.sect-title{font-size:13px;font-weight:700}
.details-btn{display:none;padding:2px 4px;font-size:11px;font-weight:400;background:#1e3a5f;color:var(--text);border:1px solid #2d5a8f;border-radius:3px;cursor:pointer;transition:all .2s;opacity:0.8}
.details-btn.visible{display:block}
.details-btn:hover{background:#2d5a8f;border-color:#3d6a9f;opacity:1}
.items{display:none;margin:0 8px 8px 8px;border:1px solid #162746;border-radius:6px;background:#0a1324}
.items.open{display:block}
.table{display:grid;grid-template-columns:1fr 80px;border-bottom:1px solid var(--rule);padding:4px 8px 4px 28px;color:var(--muted);font-weight:600;font-size:10px;letter-spacing:.1px}
ul.board{list-style:none;margin:0;padding:0}
li.row{display:grid;grid-template-columns:16px 1fr 80px;gap:6px;align-items:center;padding:6px 8px;border-bottom:1px solid var(--rule);font-size:11px;font-variant-numeric:tabular-nums}
li.row:last-child{border-bottom:0}
.label{font-weight:600;font-variant-numeric:tabular-nums}
.note{justify-self:end;color:var(--muted);font-variant-numeric:tabular-nums;font-size:10px}
.table{font-variant-numeric:tabular-nums}
.check{display:inline-flex;width:14px;height:14px;align-items:center;justify-content:center;color:var(--ok)}
.check.warn{color:var(--warn)} .check.err{color:var(--err)}
/* sub-rows render as full rows, same 3 columns as main rows */
li.row.sub{display:grid;grid-template-columns:16px 1fr 80px;gap:6px;align-items:center;padding:4px 8px 4px 48px;border-bottom:1px dashed #1b2940;font-size:10px;position:relative}
li.row.sub::before{content:"";position:absolute;left:24px;top:0;bottom:0;width:1px;background:#1f2f4a}
li.row.sub .note{justify-self:end}
.kbd-focus{outline:2px solid #2d5a8f; outline-offset:2px; border-radius:4px}
.debug-panel{display:none;margin:0 8px 8px 8px;padding:12px;border:1px solid #2d5a8f;border-radius:6px;background:#0a1324;font-family:ui-monospace,monospace;font-size:10px;max-height:400px;overflow:auto}
.debug-panel.open{display:block}
.debug-panel pre{margin:0;white-space:pre-wrap;color:var(--muted);line-height:1.5}
</style>
</head><body>
<div class="top-bar"><span id="refreshTime"></span></div>
<div class="wrap"><div class="card">
  <div class="header"><span id="topdot" class="dot"></span><span class="header-title">{{ app_title }}</span><button class="header-btn master-debug-btn" id="masterDebug" onclick="copyAllDebug()" title="Copy all debug info">🐛</button><button class="header-btn" onclick="restartDash()" title="Restart dashboard">⟳</button></div>
  <div id="content"></div>
</div></div>

<script>
try { window.resizeTo(560, 420); } catch(_) {}

const PORT = {{ PORT }};
const ORIGIN = (location.origin === 'null' || location.protocol === 'file:')
  ? `http://127.0.0.1:${PORT}`
  : location.origin;

const DEBUG = false;
let dbgEl;

function ts(){
  const d = new Date();
  return d.toLocaleTimeString() + '.' + String(d.getMilliseconds()).padStart(3,'0');
}

function dlog(...args){
  const msg = args.map(x => (typeof x === 'object' ? JSON.stringify(x) : String(x))).join(' ');
  console.log('[VM]', ...args);
  try{
    if (dbgEl) {
      const line = document.createElement('div');
      line.style.whiteSpace = 'pre-wrap';
      line.style.fontFamily = 'ui-monospace, monospace';
      line.style.fontSize = '11px';
      line.style.opacity = .8;
      line.textContent = `[${ts()}] ${msg}`;
      dbgEl.appendChild(line);
      if (dbgEl.childElementCount > 200) dbgEl.removeChild(dbgEl.firstChild);
    }
    fetch(`${ORIGIN}/api/client-log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ t: Date.now(), msg, loc: location.href })
    }).catch(()=>{});
  }catch(e){}
}

window.addEventListener('error', e => dlog('window.onerror:', e.message, e.filename, e.lineno+':'+e.colno));
window.addEventListener('unhandledrejection', e => dlog('unhandledrejection:', (e.reason && (e.reason.stack || e.reason.message)) || String(e.reason)));

document.addEventListener('DOMContentLoaded', () => {
  const panel = document.createElement('div');
  panel.id = 'debug-panel';
  panel.style.position = 'fixed';
  panel.style.bottom = '0';
  panel.style.left = '0';
  panel.style.right = '0';
  panel.style.padding = '8px';
  panel.style.background = 'rgba(0,0,0,0.9)';
  panel.style.maxHeight = '200px';
  panel.style.overflow = 'auto';
  panel.style.borderTop = '1px solid #333';
  panel.style.fontSize = '10px';
  panel.style.zIndex = '9999';
  panel.style.display = DEBUG ? 'block' : 'none';
  document.body.appendChild(panel);
  dbgEl = panel;

  dlog('Page loaded. origin=', location.origin, 'ORIGIN=', ORIGIN,
       'navigator.onLine=', navigator.onLine, 'visibility=', document.visibilityState);

  myFetch(`${ORIGIN}/api/ping`).then(r => r.json()).then(j => dlog('/api/ping ok', j))
      .catch(e => dlog('/api/ping ERR', String(e)));
  myFetch(`${ORIGIN}/api/diag`).then(r => r.json()).then(j => dlog('/api/diag', j))
      .catch(e => dlog('/api/diag ERR', String(e)));

  const ro = new ResizeObserver(() => scheduleFit());
  const card = document.querySelector('.card');
  if (card) ro.observe(card);

  const mo = new MutationObserver(() => scheduleFit());
  mo.observe(document.getElementById('content'), { childList:true, subtree:true, characterData:true });

  setTimeout(scheduleFit, 50);
});

async function myFetch(url, options){
  const t0 = performance.now();
  dlog('fetch →', url, options ? JSON.stringify(options) : '');
  try{
    const r = await fetch(url, { cache:'no-store', ...options });
    const headers = {};
    try { r.headers.forEach((v,k)=>headers[k]=v); } catch(_){}
    dlog('fetch ←', url, `${r.status} ${r.statusText}`, headers, `in ${(performance.now()-t0).toFixed(1)}ms`);
    return r;
  }catch(e){
    dlog('fetch ✖', url, (e && e.message) || String(e), `after ${(performance.now()-t0).toFixed(1)}ms`);
    throw e;
  }
}

const expandState={sections:{}};
const sectionStatus={};
const debugPanelOpen={};
let masterDebugNeeded = false;  // Sticky flag: stays true until user clicks
let accumulatedDebug = {};  // Accumulates debug info from problem sections (persists until user clicks master debug)

async function restartDash(){
  if(!confirm('Restart dashboard?')) return;
  try{
    await myFetch(`${ORIGIN}/api/restart`, {method:'POST'});
    document.getElementById('content').innerHTML='<div style="padding:40px;text-align:center;color:var(--muted)">Restarting dashboard...<br>Refresh page in 3 seconds</div>';
    setTimeout(()=>location.reload(), 3000);
  }catch(e){
    dlog('restartDash error:', e && e.message || e);
    alert('Restart failed: '+e);
  }
}

async function copyAllDebug(){
  try{
    const btn = document.getElementById('masterDebug');

    // Use accumulated debug data (includes all historical issues, not just current)
    const debugText = JSON.stringify(accumulatedDebug, null, 2);
    await navigator.clipboard.writeText(debugText);

    const orig = btn.textContent;
    btn.textContent = '✓';
    setTimeout(()=>{ btn.textContent = orig; }, 1500);

    // Clear accumulated debug data and reset sticky flag - user has acknowledged the issues
    accumulatedDebug = {};
    masterDebugNeeded = false;

    // Hide button after user copies
    setTimeout(()=>{
      btn.classList.remove('visible');
    }, 1600);
  }catch(err){
    console.error('Master debug copy failed:', err);
    alert('Failed to copy debug info: ' + err.message);
  }
}

function svg(name){
  const m={
    check:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>',
    x:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M18.3 5.7 12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7 4.3 4.3l6.3 6.3 6.3-6.3z"/></svg>',
    hourglass:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M6 2h12v4a6 6 0 0 1-3 5.2V13a6 6 0 0 1 3 5.2V22H6v-3.8A6 6 0 0 1 9 13v-1.8A6 6 0 0 1 6 6.1z"/></svg>',
    loop:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 4V1L8 5l4 4V6c3.3 0 6 2.7 6 6s-2.7 6-6 6-6-2.7-6-6H4c0 4.4 3.6 8 8 8s8-3.6 8-8-3.6-8-8-8z"/></svg>',
    gear:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M12 15.5c-1.9 0-3.5-1.6-3.5-3.5s1.6-3.5 3.5-3.5 3.5 1.6 3.5 3.5-1.6 3.5-3.5 3.5zm7.4-4.8l-1.6-.5c-.2-.5-.4-1-.7-1.4l.8-1.5c.2-.3.1-.7-.2-.9l-1.4-1.4c-.3-.3-.6-.3-.9-.2l-1.5.8c-.5-.3-.9-.5-1.4-.7l-.5-1.6c-.1-.3-.4-.5-.7-.5h-2c-.3 0-.6.2-.7.5l-.5 1.6c-.5.2-1 .4-1.4.7l-1.5-.8c-.3-.2-.7-.1-.9.2L3.4 6.3c-.3.3-.3.6-.2.9l.8 1.5c-.3.5-.5.9-.7 1.4l-1.6.5c-.3.1-.5.4-.5.7v2c0 .3.2.6.5.7l1.6.5c.2.5.4 1 .7 1.4l-.8 1.5c-.2.3-.1.7.2.9l1.4 1.4c.3.3.6.3.9.2l1.5-.8c.5.3.9.5 1.4.7l.5 1.6c.1.3.4.5.7.5h2c.3 0 .6-.2.7-.5l.5-1.6c.5-.2 1-.4 1.4-.7l1.5.8c.3.2.7.1.9-.2l1.4-1.4c.3-.3.3-.6.2-.9l-.8-1.5c.3-.5.5-.9.7-1.4l1.6-.5c.3-.1.5-.4.5-.7v-2c0-.3-.2-.6-.5-.7z"/></svg>',
    sleep:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M22 7h-3l2-3h-3l-2 3h-2L16 4h-3l-2 3h-1c-1.7 0-3 1.3-3 3v1h16V8c0-.6-.4-1-1-1zM4 20c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-9H4v9zm4-6h8v2H8v-2z"/></svg>'
  };
  return m[name]||'';
}
function liIcon(ok,status,label){
  if(label && label==='Watch Mode') return svg('loop');
  // Sleep icon for idle status (no activity for a while)
  if(status==='idle') return svg('sleep');
  // Gear icon for Vectorization warnings (running but struggling)
  if(status==='warning' && label==='Vectorization') return svg('gear');
  // Hourglass for other warnings (checking/initializing)
  if(status==='warning' || ok===null || ok===undefined) return svg('hourglass');
  return ok?svg('check'):svg('x');
}
function liColor(ok,status,label){
  if(label && label==='Watch Mode') return 'var(--loop)'; // default blue for Watch Mode
  if(status==='idle') return 'var(--muted)'; // gray for idle/sleeping
  if(status==='warning' || ok===null || ok===undefined) return 'var(--warn)';
  return ok?'var(--ok)':'var(--err)';
}
function dotClass(ok,status){
  if(ok===false || status==='error') return 'dot err';
  if(ok===true) return 'dot';
  return 'dot warn';
}

async function refresh(tries=0){
  try{
    const r = await myFetch(`${ORIGIN}/api/board?ts=${Date.now()}`);
    if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  const b = await r.json();
    dlog('board json bytes:', (JSON.stringify(b)||'').length);
  render(b);
    setTimeout(refresh, (b.refresh_ms||5000));
  }catch(e){
    const delay = tries < 3 ? 800 * Math.pow(2, tries) : 5000;
    const box = document.getElementById('content');
    box.innerHTML = `
      <div style="padding:16px">
        <div style="font-weight:600">Connecting to dashboard…</div>
        <div style="margin-top:8px;opacity:.8">
          Error: ${String(e)}<br>
          Origin: ${ORIGIN}<br>
          Target: ${ORIGIN}/api/board<br>
          Retry: ${tries+1}
        </div>
      </div>`;
    dlog('refresh retry in', delay, 'ms due to', String(e));
    setTimeout(()=>refresh(Math.min(tries+1,10)), delay);
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

  // Update top dot
  const anyErr = b.sections.some(s => s.ok===false || s.status==='error');
  const anyWarn = b.sections.some(s => (s.ok===null || s.status==='warning') && s.ok!==false);
  const topdot = document.getElementById('topdot');
  topdot.className = anyErr ? 'dot err' : (anyWarn ? 'dot warn' : 'dot');

  // First render: build everything
  if(content.children.length === 0){
    buildAll(content, b);
  }else{
    // Subsequent renders: update in place
    updateAll(content, b);
  }

  // Show master debug button if any section has issues (do this AFTER build/update)
  // STICKY BEHAVIOR: Once shown, stays visible until user clicks it
  const masterDebug = document.getElementById('masterDebug');
  const anyIssues = b.sections.some(s => s.ok !== true);
  if(masterDebug){
    // Always store latest section data
    masterDebug.dataset.sections = JSON.stringify(b.sections);

    // ACCUMULATE debug data from problem sections
    b.sections.forEach(sec => {
      if(sec.ok !== true && sec.debug){
        // Add timestamp to track when this issue was first seen
        if(!accumulatedDebug[sec.title]){
          accumulatedDebug[sec.title] = {
            first_seen: new Date().toISOString(),
            debug_snapshots: []
          };
        }
        // Add latest debug snapshot (avoid duplicates by checking last entry)
        const snapshots = accumulatedDebug[sec.title].debug_snapshots;
        const lastSnapshot = snapshots[snapshots.length - 1];
        const currentDebugStr = JSON.stringify(sec.debug);
        if(!lastSnapshot || JSON.stringify(lastSnapshot.data) !== currentDebugStr){
          snapshots.push({
            timestamp: new Date().toISOString(),
            status: sec.status,
            ok: sec.ok,
            data: sec.debug
          });
          // Keep only last 5 snapshots per section
          if(snapshots.length > 5){
            snapshots.shift();
          }
        }
      }
    });

    if(anyIssues){
      // Set sticky flag when issues appear
      masterDebugNeeded = true;
      masterDebug.classList.add('visible');
    }else if(masterDebugNeeded){
      // Keep button visible even if everything is green now (user hasn't clicked yet)
      masterDebug.classList.add('visible');
    }else{
      // No issues and user has acknowledged previous issues - hide button
      masterDebug.classList.remove('visible');
    }
  }

  scheduleFit();
}

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

  // Use scroll* to include overflow content as sections expand
  const r = card.getBoundingClientRect();
  const sw = Math.ceil(Math.max(r.width,  card.scrollWidth  || r.width));
  const sh = Math.ceil(Math.max(r.height, card.scrollHeight || r.height));

  const { dW, dH } = chromeDelta();

  // wrap padding (centered flex with ~8px margins)
  const targetW = Math.min(maxW, Math.max(minW, sw + dW + padW));
  const targetH = Math.min(maxH, Math.max(minH, sh + dH + padH));

  const needW = Math.abs(window.outerWidth  - targetW) > 2;
  const needH = Math.abs(window.outerHeight - targetH) > 2;
  if (needW || needH) {
    try {
      // Calculate position to keep right edge fixed
      const currentX = window.screenX;
      const currentRight = currentX + window.outerWidth;
      const newX = currentRight - targetW;

      // Move to new position and resize
      window.moveTo(newX, window.screenY);
      window.resizeTo(targetW, targetH);
    } catch(_) {}
  }
}

function scheduleFit(){
  if (_fitRAF) return;
  _fitRAF = requestAnimationFrame(()=>{ _fitRAF = 0; fitWindowExact(); });
}

function buildAll(content, b){
  content.innerHTML='';
  b.sections.forEach(sec => {
    const container=document.createElement('div'); container.className='section';

    const head=document.createElement('div'); head.className='sect-head';
    const lamp=document.createElement('span'); lamp.className=dotClass(sec.ok, sec.status);
    const title=document.createElement('div'); title.className='sect-title'; title.textContent=sec.title;
    const detailsBtn=document.createElement('button'); detailsBtn.className='details-btn'; detailsBtn.textContent='🐛'; detailsBtn.type='button'; detailsBtn.title='Debug info';
    // For S03, only show debug button on error, not warning
    if(sec.title === 'S03 - Vectorization' && sec.status === 'warning'){
      // Don't show debug for S03 warnings
    }else if(sec.ok !== true){
      detailsBtn.classList.add('visible');
    }
    head.appendChild(lamp); head.appendChild(title); head.appendChild(detailsBtn);

    const items=document.createElement('div'); items.className='items';
    const hdr=document.createElement('div'); hdr.className='table'; hdr.innerHTML='<div>Status</div><div style="text-align:right">Timestamp</div>';
    const ul=document.createElement('ul'); ul.className='board';

    (sec.items||[]).forEach(it=>{
      const li=document.createElement('li'); li.className='row';
      li.dataset.key = `${sec.title}|${it.label}`;
      const ck=document.createElement('span'); ck.className='check'; ck.innerHTML=liIcon(it.ok,it.status,it.label); ck.style.color=liColor(it.ok,it.status,it.label);
      const lab=document.createElement('div'); lab.className='label'; lab.textContent=it.label;
      const ts=document.createElement('div'); ts.className='note'; ts.textContent=it.note||'';
      li.appendChild(ck); li.appendChild(lab); li.appendChild(ts);
      ul.appendChild(li);

      if(it.subitems && it.subitems.length){
        it.subitems.forEach(si=>{
          const sub=document.createElement('li'); sub.className='row sub';
          sub.dataset.key = `${sec.title}|${it.label}|${si.label}`;
          const sck=document.createElement('span'); sck.className='check'; sck.innerHTML=liIcon(si.ok,si.status,si.label); sck.style.color=liColor(si.ok,si.status,si.label);
          const slab=document.createElement('div'); slab.className='label'; slab.textContent=si.label;
          const sts=document.createElement('div'); sts.className='note'; sts.textContent=si.note||'';
          sub.appendChild(sck); sub.appendChild(slab); sub.appendChild(sts);
          ul.appendChild(sub);
        });
      }
    });

    items.appendChild(hdr); items.appendChild(ul);

    // Debug panel
    const debugPanel=document.createElement('div'); debugPanel.className='debug-panel';
    const debugPre=document.createElement('pre');
    debugPre.textContent = JSON.stringify(sec.debug || {}, null, 2);
    debugPanel.appendChild(debugPre);

    container.appendChild(head); container.appendChild(items); container.appendChild(debugPanel);
    content.appendChild(container);

    // Auto-expand based on status only (no manual control)
    // For S03 (Vectorization), only expand on error, not warning
    if(sec.title === 'S03 - Vectorization' && sec.status === 'warning'){
      items.classList.remove('open');
    }else if(sec.ok !== true){
      items.classList.add('open');
    }else{
      items.classList.remove('open');
    }

    detailsBtn.addEventListener('click', async (e)=>{
      e.stopPropagation();
      const wasOpen = debugPanel.classList.contains('open');
      debugPanel.classList.toggle('open');
      debugPanelOpen[sec.title] = !wasOpen;

      if(!wasOpen && sec.ok === true){
        detailsBtn.classList.add('visible');
      }else if(wasOpen && sec.ok === true){
        detailsBtn.classList.remove('visible');
      }

      scheduleFit();
      try{
        const debugText = JSON.stringify(sec.debug || {}, null, 2);
        await navigator.clipboard.writeText(debugText);
        const orig = detailsBtn.textContent;
        detailsBtn.textContent = '✓';
        setTimeout(()=>{ detailsBtn.textContent = orig; }, 1500);
      }catch(err){
        console.error('Clipboard copy failed:', err);
      }
    });
  });
}

function updateAll(content, b){
  b.sections.forEach((sec, secIdx) => {
    const container = content.children[secIdx];
    if(!container) return;

    // lamp
    const lamp = container.querySelector('.sect-head .dot');
    if(lamp) lamp.className = dotClass(sec.ok, sec.status);

    // Auto-expand/collapse based on status
    const items = container.querySelector('.items');
    if(items){
      // For S03 (Vectorization), only expand on error, not warning
      if(sec.title === 'S03 - Vectorization' && sec.status === 'warning'){
        items.classList.remove('open');
      }else if(sec.ok !== true){
        items.classList.add('open');
      }else{
        items.classList.remove('open');
      }
    }

    const prevStatus = sectionStatus[sec.title];
    if(prevStatus !== sec.ok){
      sectionStatus[sec.title] = sec.ok;
    }

    // details button visibility (keep visible if debug panel is open OR section has issues)
    const detailsBtn = container.querySelector('.details-btn');
    const debugPanel = container.querySelector('.debug-panel');
    const isPanelOpen = debugPanel && debugPanel.classList.contains('open');

    if(detailsBtn){
      // For S03, only show debug button on error, not warning
      if(sec.title === 'S03 - Vectorization' && sec.status === 'warning' && !isPanelOpen){
        detailsBtn.classList.remove('visible');
      }else if(sec.ok !== true || isPanelOpen){
        detailsBtn.classList.add('visible');
      }else{
        detailsBtn.classList.remove('visible');
      }
    }

    // update debug panel content
    if(debugPanel && sec.debug){
      const debugPre = debugPanel.querySelector('pre');
      if(debugPre){
        debugPre.textContent = JSON.stringify(sec.debug, null, 2);
      }
    }

    // items
    const ul = container.querySelector('.board');
    if(!ul) return;

    (sec.items||[]).forEach(it => {
      // update main row by key
      const key = `${sec.title}|${it.label}`;
      const row = ul.querySelector(`li.row[data-key="${CSS.escape(key)}"]`);
      if(row){
      const ck = row.querySelector('.check');
      if(ck){
        ck.innerHTML = liIcon(it.ok, it.status, it.label);
        ck.style.color = liColor(it.ok, it.status, it.label);
      }
      const ts = row.querySelector('.note');
        if(ts) ts.textContent = it.note||'';
      }

      // update sub-rows by key
      (it.subitems||[]).forEach(si => {
          const skey = `${sec.title}|${it.label}|${si.label}`;
        const srow = ul.querySelector(`li.row.sub[data-key="${CSS.escape(skey)}"]`);
        if(srow){
          const sck = srow.querySelector('.check');
          if(sck){
            sck.innerHTML = liIcon(si.ok, si.status, si.label);
            sck.style.color = liColor(si.ok, si.status, si.label);
          }
          const sts = srow.querySelector('.note');
          if(sts) sts.textContent = si.note||'';
        }
      });
    });
  });
}

// Keyboard shortcuts: J/K/O/R
let focusIdx = 0;
function getSections(){ return Array.from(document.querySelectorAll('.section')); }
function focusSection(idx){
  const sections = getSections();
  if(!sections.length) return;
  focusIdx = (idx + sections.length) % sections.length;
  const sec = sections[focusIdx];
  sec.scrollIntoView({behavior:'smooth', block:'center'});
  sec.classList.add('kbd-focus');
  setTimeout(()=>sec.classList.remove('kbd-focus'), 500);
}
document.addEventListener('keydown', (e)=>{
  if(['INPUT','TEXTAREA'].includes(e.target.tagName||'')) return;
  if(e.key==='j'){ e.preventDefault(); focusSection(focusIdx+1); }
  if(e.key==='k'){ e.preventDefault(); focusSection(focusIdx-1); }
  if(e.key==='r'){ e.preventDefault(); location.reload(); }
});

refresh();
</script>
</body></html>
"""

# ---------- PROCESS CONTROL (unchanged approach) ----------


def kill_existing_dashboard():
    """Kill any process using the dashboard port."""
    try:
        result = subprocess.run(
            f"netstat -ano | findstr :{PORT} | findstr LISTENING",
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            pid = result.stdout.strip().split()[-1]
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True, check=False)
            print(f"[MVM_DASH] Killed existing process on port {PORT} (PID {pid})")
            import time

            time.sleep(1)
    except Exception as e:
        print(f"[MVM_DASH] Error killing existing process: {e}")


def _port_guard_or_exit():
    """Check if port is available, kill existing if needed."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORT))
        sock.close()
    except OSError:
        kill_existing_dashboard()
        time.sleep(1)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", PORT))
            sock.close()
        except OSError:
            print(f"[MVM_DASH] ERROR: Port {PORT} still in use after cleanup")
            sys.exit(1)


def run_dashboard():
    """Run the dashboard with auto-restart on crash (matching working version)."""
    kill_existing_dashboard()
    print(f"[MVM_DASH] Starting on http://127.0.0.1:{PORT}")
    print("[MVM_DASH] Keys: J/K = navigate, R = reload")

    while True:
        try:
            app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
            break
        except Exception as e:
            print(f"[MVM_DASH] Crashed: {e}")
            print("[MVM_DASH] Restarting in 2 seconds...")
            import time

            time.sleep(2)
            kill_existing_dashboard()


# Start background board refresher (after all functions are defined)
if not globals().get("_board_thread_started"):
    threading.Thread(target=_board_refresher, args=(5,), daemon=True).start()
    globals()["_board_thread_started"] = True
    logger.info("board: background refresher started")


if __name__ == "__main__":
    run_dashboard()
