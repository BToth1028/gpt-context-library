Target path: C:\DEV\docs\gpt\automation\startup-systems\batch-orchestration\251104-1549_V01\response
Files: code/start-all.ps1, code/monitor-all.ps1, code/start-backstage.ps1, infra/backstage/docker-compose.yml, app-config.local.yaml

# Batch Orchestration System — Review and Harden

## Summary
Converted brittle batch startup into PowerShell-first orchestration with structured logs, health heartbeats, and backoff readiness. Added persistent Postgres for Backstage. Provided a monitor script and a clean rollout path.

## What works
- Separation of start and monitor scripts.
- Service list and ports are sensible.
- Docker volumes prevent data loss when using `stop`.

## Issues fixed
- Replaced fixed sleeps with readiness checks and bounded backoff.
- Centralized JSON logging in `40_runtime\logs`.
- Health heartbeats in `40_runtime\health`.
- Disabled duplicate browser auto-open.
- Added Backstage Postgres config and compose file.

## Implementation
### PowerShell
```powershell
# create runtime dirs
mkdir .\40_runtime\logs,.\40_runtime\health -Force

# optional: start local Postgres for Backstage
cd .\infra\backstage
docker compose up -d
cd ..\..

# start services
pwsh -NoProfile -ExecutionPolicy Bypass -File .\code\start-all.ps1

# monitor
pwsh -NoProfile -ExecutionPolicy Bypass -File .\code\monitor-all.ps1
```

## Risks
- Ports or paths that differ in your workspace will need edits in `start-all.ps1`.
- Sourcegraph single-node can be sensitive; keep `docker compose logs` handy.

## Decision Note
**Title:** Batch orchestration → PowerShell hardening  
**Date:** 2025-11-04  
**Source:** Uploaded batch scripts and briefing  
**Context:** Reliability and UX on Windows 11  
**Original Prompt:** Follow instruction format; save files individually; include `Files:` line  
**Key Takeaways:** Orchestrate with PowerShell, add logs and health, add Backstage Postgres, and open browser only after readiness  
**Implementation Guide:** Use the files above, start Postgres, run orchestrator, and monitor  
**Related:** Backstage docs, Docker Desktop on Windows
