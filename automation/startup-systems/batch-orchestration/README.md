# Batch Orchestration (Tier 3)

**Parent Subcategory**: Automation > Startup Systems
**Category Type**: Specific Topic (Tier 3)
**Created**: 2025-11-04
**Status**: Active

## Topic Overview

Windows batch file orchestration for starting the Project Context OS - a 4-portal engineering workspace consisting of MkDocs, Backstage, Sourcegraph, and Structurizr. Includes automated Docker Desktop startup, prerequisite checking, service cleanup, health monitoring, and browser automation.

## Context

The Project Context OS requires coordinating 4 different services:
- **MkDocs** (Python + venv) - Documentation portal
- **Sourcegraph** (Docker Compose) - Code search engine
- **Structurizr** (Docker container) - Architecture diagrams
- **Backstage** (Node + Yarn 4) - Service catalog

Challenges include:
- Docker Desktop cold start (20-30 seconds)
- Service startup timing variability
- Port conflicts on restart
- Windows batch file limitations
- Terminal window management
- Browser automation

## Version History

| Version | Date | Time | Status | Summary |
|---------|------|------|--------|---------|
| [V01](251104-1131_V01/) | 2025-11-04 | 11:31 | ✅ Working | Complete startup automation with 15 iterations |

## Key Points

- Single-click startup for 4 services
- Automatic Docker Desktop launch with polling
- All service terminals run minimized
- Aggregate monitor window for debugging
- Automatic browser opening after delay
- Service cleanup before restart
- Data persistence (Sourcegraph volumes preserved)

## Known Issues

- ⚠️ Backstage guest mode (no persistent auth)
- ⚠️ Occasional cleanup hanging
- ⚠️ Fixed delay for browser opening (not health-based)

## Suggested Improvements

1. Rewrite in PowerShell for better error handling
2. Add health check polling instead of fixed delays
3. Implement PostgreSQL backend for Backstage auth
4. Add automatic service restart on crash
5. Containerize all services for unified Docker Compose management

## Related Topics

- **Project Context OS Architecture**: `../systems/context-management/project-context-os/`
- **Windows Integration**: `../operations/windows-integration/`
- **Docker Orchestration**: Future topic

---

**Last Updated**: 2025-11-04

