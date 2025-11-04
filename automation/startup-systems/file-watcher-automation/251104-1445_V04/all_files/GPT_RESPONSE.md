Target path: C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1445_V04\response

## What I reviewed
- gpt-response-watcher.ps1
- prepare-gpt-zip.ps1
- Briefing not present in zip, so Target path taken from your instruction above.

## What works
- Clear separation of watcher and packager.
- PowerShell fits Windows 11 environment.
- Basic file processing flow is understandable.

## What does not work / risks
- Event handling: missing or limited FileSystemWatcher usage; reliance on Start-Sleep; risk of missed or duplicate processing.
- No file stability check before moving. Writes can be mid-stream.
- Moves without retry/backoff; sharing violations will fail sporadically.
- Logs via Write-Host. No structured JSON logs or rotation.
- No metrics or health heartbeat for your dashboard probes.
- No env/.env configuration. Paths are hard-coded.
- Zipper lacks excludes for runtime/build dirs and uses fixed naming.

## Fixes provided
- Event-driven watcher using FileSystemWatcher with a periodic scan fallback every 10 s.
- Wait-FileStable size check before handling.
- Staged moves with exponential backoff and bounded retries.
- JSONL logging to 40_runtime/logs with date-named files.
- Simple metrics counters in 40_runtime/metrics/watcher.prom.
- Health heartbeat file 40_runtime/health/watcher.ok.
- .env-driven configuration and .env.example provided.
- Zipper rewritten with excludes, env config, and timestamped artifacts.

## Implementation
### Replace scripts with these fixed versions
- [gpt-response-watcher.fixed.ps1](sandbox:/mnt/data/response_pkg/gpt-response-watcher.fixed.ps1)
- [prepare-gpt-zip.fixed.ps1](sandbox:/mnt/data/response_pkg/prepare-gpt-zip.fixed.ps1)
- [.env.example](sandbox:/mnt/data/response_pkg/.env.example)

### Patch diffs
- [gpt-response-watcher.diff.patch](sandbox:/mnt/data/response_pkg/gpt-response-watcher.diff.patch)
- [prepare-gpt-zip.diff.patch](sandbox:/mnt/data/response_pkg/prepare-gpt-zip.diff.patch)

### PowerShell commands
```
# from 251104-1445_V04 directory
mkdir .\40_runtime\inbox,.\40_runtime\staging,.\40_runtime\processed,.\40_runtime\logs,.\40_runtime\metrics,.\40_runtime\health,.\40_runtime\artifacts -Force

# copy fixed scripts
Copy-Item "C:\path\to\download\gpt-response-watcher.fixed.ps1" .\code\gpt-response-watcher.ps1 -Force
Copy-Item "C:\path\to\download\prepare-gpt-zip.fixed.ps1" .\code\prepare-gpt-zip.ps1 -Force

# optional: seed .env
Copy-Item "C:\path\to\download\.env.example" .\50_config\.env -Force

# run watcher
pwsh -NoProfile -ExecutionPolicy Bypass -File .\code\gpt-response-watcher.ps1

# create zip artifact
pwsh -NoProfile -ExecutionPolicy Bypass -File .\code\prepare-gpt-zip.ps1
```

### Tests (Pester)
- Add tests under `code\tests` based on the examples in this response if you want CI checks.

## Suggested improvements
- Expose a tiny HTTP health endpoint via `Start-HttpListener` on localhost for richer probes. Keep default off. 
- Add a dedupe guard: compute hash of staged file and keep a small index to skip repeats.
- Emit Windows Event Log entries for WARN/ERROR to integrate with OS logging.
- Optional: publish metrics to a named pipe for your dashboard to read without file polling.

## Decision Note
**Title:** Harden file watcher and zipper for V04  
**Date:** 2025-11-04  
**Source:** Attached zip review  
**Context:** Provide fixes and production-ready scripts with env, logging, metrics, and health.  
**Original Prompt:** Review and fix V04 watcher/zip; include Target path line.  
**Key Takeaways:** Move to event-driven design with stability checks, retries, JSON logs, metrics, and env config. Zip script gains excludes and timestamped naming.  
**Implementation Guide:** Copy fixed scripts, create runtime dirs, set .env, run tests, and launch.  
**Related:** Prior V02/V03 iterations; dashboard health probes.
