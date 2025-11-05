# GPT Briefing Summary - Cursor MCP Metadata Issue

**Created**: 2025-11-05 00:00  
**Version**: 251105-0000_V01  
**Status**: Ready for ChatGPT  
**Watcher PID**: 41084

---

## Problem Statement

We successfully set up Qdrant MCP with Cursor and created rich metadata utilities reusing VMS code, but the AI is only storing minimal metadata in Qdrant. We designed comprehensive attribution but it's not being used.

**What works**: Basic MCP storage/retrieval, utilities tested  
**What's broken**: Rich metadata not being saved, recent hour context not implemented

---

## Files Included in Briefing

### Request
- `BRIEFING.txt` - Complete problem description, questions, constraints

### Code
- `_cursor_mcp_memory.mdc` - Cursor rule for auto-ingestion
- `mcp.json` - MCP server configuration
- `__init__.py` - Utilities package init
- `hashing.py` - Content hashing (VMS reused)
- `timestamps.py` - Timestamp utilities (VMS reused)
- `deterministic_ids.py` - UUID5 generation (Phase 1)
- `runtime.py` - Runtime context capture (Phase 1)
- `test_utils.py` - Unit tests (all passing)
- `test-mcp-utils.py` - Integration test

### Context
- `cursor-mcp-metadata-schema.md` - Designed rich schema
- `IMPLEMENTATION_COMPLETE.md` - What we thought was done
- `QUICK_START_MCP.md` - User-facing documentation
- `S03_VECT.py` - VMS source (reference for reused patterns)
- `ACTUAL_QDRANT_DATA.json` - What's really being stored

---

## Key Questions for ChatGPT

1. **Metadata Enforcement**: How to make AI use rich metadata?
   - Improve Cursor rule?
   - Create middleware/wrapper?
   - Other architecture?

2. **Recent Hour Context**: How to implement chat history summary?
   - Where does Cursor store chats?
   - How to read programmatically?
   - How to summarize efficiently?

3. **Idempotency**: How to ensure deterministic point IDs?

4. **Deduplication**: Best strategy for content hash checking?

5. **Architecture**: Best way to inject metadata into black-box MCP server?

---

## What We Need Back

1. Architecture recommendation
2. Complete working code
3. Updated Cursor rule (if needed)
4. Testing procedures
5. Honest assessment (did we over-engineer?)

---

## Next Steps

1. ✅ Upload `zip.zip` to ChatGPT
2. ⏳ Wait for response
3. ⏳ Save as `GPT_RESPONSE.md` in Downloads
4. ⏳ Watcher auto-moves to response folder
5. ⏳ Implement ChatGPT's solution

---

## File Locations

**Briefing**: `C:\DEV\docs\gpt\systems\context-management\cursor-mcp-integration\251105-0000_V01\`

**Zip**: `C:\DEV\docs\gpt\systems\context-management\cursor-mcp-integration\251105-0000_V01\zip\zip.zip`

**Response will go**: `C:\DEV\docs\gpt\systems\context-management\cursor-mcp-integration\251105-0000_V01\response\`

**Watcher PID**: 41084 (saved to C:\DEV\.watcher.pid)

---

## Utilities Test Results

All utilities tested successfully:

```
1. Content Hashing (VMS S03_VECT.py) - [OK]
2. Timestamps (VMS S03_VECT.py) - [OK]
3. Deterministic IDs (Phase 1) - [OK]
4. Runtime Context (Phase 1) - [OK]
5. Git Integration (Phase 1) - [OK]
```

Environment captured:
- OS: Windows 11
- Python: 3.12.4
- Shell: PowerShell
- Git: branch main, commit cfc6057, dirty True

---

## Current Qdrant Status

**Collection**: cursor-chats  
**Status**: green  
**Points**: 3  
**Vector**: fast-all-minilm-l6-v2 (384 dims)

**Problem**: Points only have minimal metadata like `{"project": "engineering-home"}` instead of the rich schema we designed.

---

**Briefing is complete and ready for ChatGPT review!**

