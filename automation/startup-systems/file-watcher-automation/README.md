# File Watcher Automation

PowerShell FileSystemWatcher implementation for automated GPT response capture.

## Overview

This topic covers the development and troubleshooting of a one-shot file watcher that monitors the Downloads folder for GPT_RESPONSE.md files, automatically moves them to the correct versioned response folder based on a **Target path:** header in the file, and then exits.

## Problem Space

**Goal**: Eliminate manual file management when ChatGPT provides responses to GPT briefings.

**Requirements**:
- Monitor Downloads folder for specific files
- Parse target path from file content
- Move file to correct location
- Provide user feedback (notifications, logs)
- Automatically exit after completing task (one-shot mode)
- Handle file locks and retries
- Work reliably when started by orchestration scripts

**Challenges**:
- PowerShell FileSystemWatcher event reliability
- Event handler scope and function access
- Timing issues (file created before watcher ready)
- Different file operations trigger different events
- Graceful shutdown after task completion

## Version History

| Version | Date | Time | Status | Description |
|---------|------|------|--------|-------------|
| [V01](./251104-1230_V01/) | 2025-11-04 | 12:30 | 🔴 Broken | Initial implementation - watcher starts but doesn't detect files |

## Related Topics

- [Batch Orchestration](../batch-orchestration/) - Startup scripts that launch the watcher
- [Project Context OS](../../../systems/context-management/project-context-os/) - Overall system architecture

## Key Files

- `gpt-response-watcher.ps1` - Main watcher script
- `sync-gpt-repo.ps1` - Orchestration script that starts watcher
- `start-gpt-watcher.bat` - Manual start wrapper
