# Qdrant MCP for Cursor - Quick Start

**Status**: ✅ Production Ready
**Last Updated**: November 5, 2025

---

## What Is This?

Qdrant MCP gives Cursor AI **working memory** - it can remember conversations and retrieve context automatically using your local Qdrant instance.

---

## Quick Links

📖 **Documentation**:
- [Full Setup Guide](docs/guides/cursor-mcp-setup.md) - Step-by-step installation
- [Metadata Schema](docs/architecture/integration/cursor-mcp-metadata-schema.md) - What gets stored
- [Integration Guide](docs/architecture/integration/qdrant-mcp-cursor-integration.md) - Complete technical guide
- [Implementation Status](docs/status/mcp-implementation.md) - Current progress

🔧 **Tools**:
- [Shared Utils Library](libs/cursor-mcp-utils/README.md) - Reusable code
- [Setup Script](scripts/setup-qdrant-mcp.ps1) - Automated installation
- [Memory Viewer](scripts/view-cursor-memory.ps1) - Explore stored chats
- [Unified Search](scripts/search-all-chats.py) - Search all conversations

---

## 5-Minute Setup

### 1. Start Services
```powershell
cd C:\DEV
.\start-all.bat
# Qdrant + Ollama start automatically
```

### 2. Add MCP to Cursor

File: `.cursor/mcp.json` (already created)

```json
{
  "mcpServers": {
    "qdrant-cursor-chats": {
      "command": "uvx",
      "args": ["mcp-server-qdrant"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "COLLECTION_NAME": "cursor-chats",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }
}
```

### 3. Restart Cursor

Close and reopen Cursor completely.

### 4. Verify

Check: **Settings → Features → MCP**

Should show:
- ✅ Server: `qdrant-cursor-chats`
- ✅ Status: Connected (green dot)
- ✅ Tools: 2 tools enabled

### 5. Test

In Cursor chat:
```
Store this: "MCP is working! Testing memory storage."
```

Then:
```
Search for: "MCP working memory"
```

---

## How It Works

```
Cursor Chat → AI decides to store → MCP tool → Qdrant
                                                  ↓
Later... → AI needs context → Search → Retrieves stored memory
```

**The AI automatically stores important information:**
- Configuration details
- Decisions made
- Solutions found
- Commands that worked

**Just talk naturally:**
- "Remember that we use port 5000 for the dashboard"
- "Note: The main config file is app-config.yaml"
- "Important: We decided to use tabs not spaces"

---

## What Gets Stored

Every conversation captures:
- ✅ AI model (claude-sonnet-4.5, etc.)
- ✅ Exact timestamp
- ✅ Project context (which project, file, line)
- ✅ Git state (branch, commit, dirty flag)
- ✅ Runtime versions (Python, Node, Docker)
- ✅ Environment (working dir, shell)
- ✅ Content hash (deduplication)
- ✅ Deterministic ID (idempotent storage)

**See**: [Metadata Schema](docs/architecture/integration/cursor-mcp-metadata-schema.md)

---

## View Stored Memories

```powershell
# View all memories
.\scripts\view-cursor-memory.ps1

# Filter by project
.\scripts\view-cursor-memory.ps1 -Project "backstage"

# Statistics
.\scripts\view-cursor-memory.ps1 -Stats

# Export JSON
.\scripts\view-cursor-memory.ps1 -Json > memories.json
```

---

## Search Across Everything

```powershell
# Search both Cursor chats + iMessage history
python .\scripts\search-all-chats.py "Ollama configuration"
```

---

## Current Status

✅ **Phase 1 Complete**:
- MCP server installed and configured
- Auto-ingestion rule active
- Content hashing (reuses VMS code)
- Deterministic IDs (idempotent upserts)
- Runtime context capture
- Git integration
- Full attribution metadata

**What's Working**:
- Qdrant (localhost:6333)
- Ollama (localhost:11434)
- MCP tools: `qdrant-store`, `qdrant-find`
- Auto-storage on important conversations
- Cross-collection search

**See**: [Implementation Status](docs/status/mcp-implementation.md)

---

## Troubleshooting

### MCP not showing in Cursor
- Check: Settings → Features → MCP → Server status
- Restart Cursor completely
- Check logs: Settings → Output → MCP

### No results from search
```powershell
# Verify collection exists
Invoke-RestMethod http://localhost:6333/collections/cursor-chats | ConvertTo-Json
```

### Services not running
```powershell
docker ps --filter "name=cursor_"
# Should show cursor_qdrant and cursor_ollama
```

### Reset and retry
```powershell
.\scripts\setup-qdrant-mcp.ps1
```

---

## What's Next

**Phase 2** (Planned):
- Recent hour context (AI pulls last hour of chat automatically)
- Tool latency tracking
- Enhanced intent classification
- Nightly deduplication/compaction

**Vector Management System Migration**:
- Move existing VMS from `C:\AI_Coding\...` to `C:\DEV\tools\vector-management\`
- Unified dashboard showing both systems
- Shared infrastructure (same Qdrant/Ollama)

**See**: [Implementation Status](docs/status/mcp-implementation.md)

---

## Architecture

```
┌─────────────────────────────────────┐
│  CURSOR IDE                         │
│  MCP: qdrant-store / qdrant-find   │
└──────────┬──────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│  mcp-server-qdrant (stdio)          │
│  FastEmbed (384 dims)                │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│  Qdrant (localhost:6333)             │
│  ├─ cursor-chats (Cursor IDE)       │
│  └─ chat_vectors (iMessage VMS)     │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│  Ollama (localhost:11434)            │
│  Model: nomic-embed-text (768 dims)  │
└──────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `.cursor/mcp.json` | MCP server configuration |
| `.cursor/rules/_cursor_mcp_memory.mdc` | Auto-ingestion rule |
| `libs/cursor-mcp-utils/` | Shared utilities (reuses VMS code) |
| `scripts/setup-qdrant-mcp.ps1` | Setup automation |
| `scripts/view-cursor-memory.ps1` | Memory viewer |
| `scripts/search-all-chats.py` | Unified search |

---

**Ready to use!** Just talk to the AI naturally and it will remember important information.

For detailed documentation, see the [Full Integration Guide](docs/architecture/integration/qdrant-mcp-cursor-integration.md).
