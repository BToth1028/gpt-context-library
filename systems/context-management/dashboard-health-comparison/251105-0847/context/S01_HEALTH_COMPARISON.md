# S01 - Health Section Comparison

## Original MVM_DASH.py (lines 586-787)

### Key Features:

**1. Log-Based Timestamp Tracking**
- Reads health check logs (`health_CURRENT.ndjson`)
- Tracks last health check timestamp
- Tracks restart attempts for Qdrant/Ollama

**2. Live Probes (Real-Time)**
```python
q_probe = probe_qdrant(collection_hint=collection_hint)
o_probe = probe_ollama()
procs = find_procs()
```

**3. Contradiction Detection**
- Compares stale health check data vs current probe results
- TRUSTS CURRENT PROBE over old log data
- Shows when service is UP NOW even if old logs said it was down

**4. Recent Vectorization Activity Tracking**
- Reads vectorization logs to find recent Qdrant errors
- Filters errors if current probe shows service is OK
- Tracks last Qdrant activity timestamp

**5. Grace Period Handling**
- Restart grace: 60 seconds
- Shows "restarting..." status during grace period
- Prevents false alarms during service restarts

**6. Stale Error Filtering**
- Removes old `qdrant_unreachable` errors if service UP NOW
- Removes old `ollama_unreachable` errors if service UP NOW
- Uses 120-second window for "stale error" filtering

**7. Collection Hint Discovery**
- Searches vectorization logs for `qdrant_initialized` event
- Extracts collection name dynamically
- Passes to probe for specific collection checks

**8. Comprehensive Debug Output**
```python
debug = {
    "log_file": str(hfile) if hfile else None,
    "event_count": len(h_evs),
    "last_health_check": ts_health,
    "has_health_data": has_health_data,
    "service_details": last_complete if last_complete else {},
    "restart_attempts": {
        "qdrant_last": ts_qdrant_restart,
        "ollama_last": ts_ollama_restart
    },
    "probes": {
        "qdrant": q_probe,
        "ollama": o_probe,
        "procs": procs
    },
    "current_status": {
        "qdrant_ok": q_probe_ok,
        "ollama_ok": o_probe_ok,
        "note": "Current probe results (overrides stale health data)"
    },
    "contradictions": contradictions,
    "vector_recent": {
        "errors_5m": len(recent_qdrant_errors),
        "success_5m": len(recent_qdrant_success),
        "last_activity_ts": qdrant_activity_ts
    },
    "qdrant_from_vecto": {...},
    "ollama_model_from_vecto": {...},
    "last_errors": all_errors[:5]
}
```

---

## New dashboard_comprehensive.py (lines 374-449)

### Key Features:

**1. Live Probes (Real-Time)**
```python
q_probe = probe_qdrant()
o_probe = probe_ollama()
procs = find_procs()
db_stats = get_db_stats()
```

**2. Validation Functions**
- `validate_qdrant_working()`: Checks if Qdrant actually works
- `validate_ollama_working()`: Checks if Ollama has required model
- Cross-checks database vs Qdrant vector counts

**3. Database Stats Integration**
- Reads directly from SQLite (no log files)
- Shows total records, processed count, pending count
- Validates that processed records have corresponding vectors

**4. Contradiction Detection**
```python
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
```

**5. Simplified Debug Output**
```python
debug = {
    "probes": {"qdrant": q_probe, "ollama": o_probe},
    "processes": procs,
    "validation": {
        "qdrant_working": q_working,
        "qdrant_reason": q_reason,
        "ollama_working": o_working,
        "ollama_reason": o_reason
    },
    "contradictions": contradictions,
    "database": db_stats
}
```

---

## What's MISSING in the New Dashboard

### ❌ 1. Log-Based Health Check Tracking
**Missing:**
- No reading of `health_CURRENT.ndjson`
- No last health check timestamp
- No health check event history

**Impact:** Can't show when last health check ran

---

### ❌ 2. Restart Detection & Grace Periods
**Missing:**
- No tracking of `qdrant_restart_attempted`
- No tracking of `ollama_restart_attempted`
- No grace period logic
- No "restarting..." status

**Impact:** False errors shown during service restarts

---

### ❌ 3. Stale Error Filtering
**Missing:**
- No error log reading
- No filtering of old errors when service is UP NOW
- No 120-second stale error window

**Impact:** Old errors might confuse users

---

### ❌ 4. Recent Vectorization Activity Tracking
**Missing:**
- No reading of vectorization logs
- No tracking of recent Qdrant errors
- No tracking of recent Qdrant successes
- No last activity timestamp

**Impact:** Can't show recent vector operations status

---

### ❌ 5. Dynamic Collection Discovery
**Missing:**
- No search for `qdrant_initialized` event
- Hardcoded collection name in config
- Can't adapt if collection name changes

**Impact:** Won't work if collection name changes

---

### ❌ 6. Service Detail from Health Checks
**Missing:**
- No `state_db` integrity checks from logs
- No detailed service info from last health check
- No Docker container status from health logs

**Impact:** Less detailed service status

---

### ❌ 7. Model Discovery from Vectorization Logs
**Missing:**
- No reading of vectorization logs to find which model is being used
- No tracking of embedding dimensions

**Impact:** Can't show which model is active

---

## What's BETTER in the New Dashboard

### ✅ 1. Direct Database Access
**Better:** Reads DB directly instead of parsing logs
**Benefit:** Real-time record counts, faster

### ✅ 2. Validation Functions
**Better:** Explicit validation logic with clear reasons
**Benefit:** Easier to understand why something failed

### ✅ 3. Vector Count Display
**Better:** Shows `"10,234 vectors"` instead of just OK/ERROR
**Benefit:** More informative at a glance

### ✅ 4. Database Cross-Check
**Better:** Validates processed records have vectors in Qdrant
**Benefit:** Catches silent failures

### ✅ 5. Specific Model Check
**Better:** Explicitly checks for `nomic-embed-text` model
**Benefit:** Catches wrong model loaded

---

## Recommendation: What to Add Back

### Priority 1 (Critical for Production)
1. **Restart grace periods** - Prevent false alarms
2. **Stale error filtering** - Show only recent errors
3. **Collection discovery** - Dynamic collection name

### Priority 2 (Nice to Have)
4. Health check timestamp tracking
5. Recent vectorization activity
6. Model discovery from logs

### Priority 3 (Optional)
7. Full health check log integration
8. Docker container status
9. Detailed service info from logs

---

## Quick Fix: Add Missing Features

```python
def build_s01_health() -> Dict[str, Any]:
    # EXISTING: Live probes
    q_probe = probe_qdrant()
    o_probe = probe_ollama()
    procs = find_procs()
    db_stats = get_db_stats()

    # ADD: Read logs for context
    health_log = get_current_log(ROOT, "health")
    vector_log = get_current_log(ROOT, "vectorization")
    h_evs = tail_ndjson(health_log) if health_log else []
    v_evs = tail_ndjson(vector_log) if vector_log else []

    # ADD: Track restart attempts
    ts_qdrant_restart = last_event_ts(h_evs, ("qdrant_restart_attempted",))
    ts_ollama_restart = last_event_ts(h_evs, ("ollama_restart_attempted",))

    qdrant_restarting = ts_qdrant_restart and is_timestamp_fresh(ts_qdrant_restart, 60)
    ollama_restarting = ts_ollama_restart and is_timestamp_fresh(ts_ollama_restart, 60)

    # ADD: Recent vectorization activity
    recent_qdrant_errors = [
        e for e in v_evs
        if e.get("event") == "qdrant_init_failed" and is_timestamp_fresh(e.get("ts"), 300)
    ]

    # ADD: Dynamic collection discovery
    collection_hint = next(
        (e.get("collection") for e in reversed(v_evs)
         if e.get("event") == "qdrant_initialized" and e.get("collection")),
        None
    )

    # ... rest of function
```
