# Cursor MCP Memory - Complete Metadata Schema

**Last Updated**: November 5, 2025  
**Collection**: cursor-chats  
**Purpose**: Full attribution and context for every AI conversation

---

## Schema Overview

Every stored conversation in Cursor captures **maximum context** including:
- AI model attribution
- Precise timestamps
- Project and file context
- Git repository state
- Environment details
- Classification and tags

## Complete Schema

```json
{
  "ai_model": "string",
  "ai_provider": "string",
  "cursor_mode": "string",
  
  "ts": "string (ISO8601)",
  "unix_timestamp": "number",
  "date": "string (YYYY-MM-DD)",
  "time": "string (HH:MM:SS)",
  
  "project": {
    "root": "string",
    "name": "string",
    "subproject": "string (optional)",
    "workspace": "string (optional)"
  },
  
  "git": {
    "branch": "string",
    "commit": "string (short SHA)",
    "commit_full": "string (full SHA)",
    "repo_url": "string",
    "dirty": "boolean",
    "remote": "string"
  },
  
  "file": {
    "path": "string (absolute)",
    "relative_path": "string",
    "line": "number (optional)",
    "line_range": {"start": "number", "end": "number"},
    "language": "string",
    "size_bytes": "number",
    "last_modified": "string (timestamp)"
  },
  
  "code": {
    "symbol": "string",
    "type": "string",
    "scope": "string",
    "context": "string",
    "imports": ["array of strings"]
  },
  
  "environment": {
    "working_dir": "string",
    "shell": "string",
    "os": "string",
    "open_files": ["array of strings"],
    "open_file_count": "number",
    "env_vars": {
      "key": "value"
    }
  },
  
  "topic": "string",
  "category": "string",
  "priority": "string",
  "tags": ["array of strings"],
  
  "role": "string",
  "chat_id": "string (UUID)",
  "turn_id": "number",
  "conversation_length": "number"
}
```

---

## Field Reference

### AI Attribution

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ai_model` | string | ✅ | Model name (e.g., "claude-sonnet-4.5") |
| `ai_provider` | string | ✅ | Provider ("anthropic", "openai", etc.) |
| `cursor_mode` | string | ✅ | "chat" or "composer" |

**Example:**
```json
{
  "ai_model": "claude-sonnet-4.5",
  "ai_provider": "anthropic",
  "cursor_mode": "chat"
}
```

---

### Timestamps

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | string | ✅ | ISO8601 with timezone |
| `unix_timestamp` | number | ✅ | Unix epoch for sorting |
| `date` | string | ✅ | YYYY-MM-DD format |
| `time` | string | ✅ | HH:MM:SS format |

**Example:**
```json
{
  "ts": "2025-11-05T16:45:30Z",
  "unix_timestamp": 1730826330,
  "date": "2025-11-05",
  "time": "16:45:30"
}
```

---

### Project Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project.root` | string | ✅ | Project root directory |
| `project.name` | string | ✅ | Detected project name |
| `project.subproject` | string | ❌ | Nested project if applicable |
| `project.workspace` | string | ❌ | Workspace file name |

**Detection Logic:**
```
C:\DEV\                          → "engineering-home"
C:\DEV\backstage\                → "backstage"
C:\DEV\services\api\             → "services" (subproject: "api")
C:\DEV\tools\context-builder\    → "tools" (subproject: "context-builder")
```

**Example:**
```json
{
  "project": {
    "root": "C:\\DEV",
    "name": "backstage",
    "workspace": "engineering-home.code-workspace"
  }
}
```

---

### Git Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `git.branch` | string | ❌ | Current branch name |
| `git.commit` | string | ❌ | Short SHA (7 chars) |
| `git.commit_full` | string | ❌ | Full commit SHA |
| `git.repo_url` | string | ❌ | Repository URL |
| `git.dirty` | boolean | ❌ | Has uncommitted changes |
| `git.remote` | string | ❌ | Remote origin URL |

**Note:** Omit entire `git` object if not in a git repository.

**Example:**
```json
{
  "git": {
    "branch": "main",
    "commit": "abc123d",
    "commit_full": "abc123def456789abcdef...",
    "repo_url": "github.com/user/engineering-home",
    "dirty": false,
    "remote": "https://github.com/user/engineering-home.git"
  }
}
```

---

### File Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file.path` | string | ❌ | Absolute file path |
| `file.relative_path` | string | ❌ | Path relative to project root |
| `file.line` | number | ❌ | Specific line number |
| `file.line_range` | object | ❌ | Range of lines |
| `file.language` | string | ❌ | Programming language |
| `file.size_bytes` | number | ❌ | File size |
| `file.last_modified` | string | ❌ | Last modified timestamp |

**Note:** Only include when discussing a specific file.

**Example:**
```json
{
  "file": {
    "path": "C:\\DEV\\backstage\\app-config.yaml",
    "relative_path": "backstage/app-config.yaml",
    "line": 23,
    "language": "yaml",
    "size_bytes": 4521,
    "last_modified": "2025-11-05T15:30:00Z"
  }
}
```

---

### Code Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code.symbol` | string | ❌ | Function/class/variable name |
| `code.type` | string | ❌ | Symbol type |
| `code.scope` | string | ❌ | Scope (global/local/module) |
| `code.context` | string | ❌ | Brief description |
| `code.imports` | array | ❌ | Relevant imports |

**Valid types:** "function", "class", "variable", "component", "interface"

**Note:** Only include when discussing specific code.

**Example:**
```json
{
  "code": {
    "symbol": "startAllServices",
    "type": "function",
    "scope": "global",
    "context": "Main startup function in start-all.bat",
    "imports": []
  }
}
```

---

### Environment Context

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `environment.working_dir` | string | ✅ | Current terminal directory |
| `environment.shell` | string | ✅ | Shell type |
| `environment.os` | string | ✅ | Operating system |
| `environment.open_files` | array | ✅ | Currently open files |
| `environment.open_file_count` | number | ✅ | Number of open files |
| `environment.env_vars` | object | ❌ | Relevant environment variables |

**Valid shells:** "powershell", "bash", "cmd", "zsh"  
**Valid OS:** "windows", "linux", "macos"

**Example:**
```json
{
  "environment": {
    "working_dir": "C:\\DEV\\backstage",
    "shell": "powershell",
    "os": "windows",
    "open_files": [
      "backstage/app-config.yaml",
      "start-all.bat",
      "docs/README.md"
    ],
    "open_file_count": 3,
    "env_vars": {
      "NODE_ENV": "development"
    }
  }
}
```

---

### Content Classification

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | ✅ | One-line summary (max 100 chars) |
| `category` | string | ✅ | Primary category |
| `priority` | string | ✅ | Importance level |
| `tags` | array | ✅ | Searchable keywords (3-7) |

**Valid categories:** "config", "code", "bug", "decision", "architecture", "docs", "command", "question"

**Valid priorities:** "high", "medium", "low"

**Example:**
```json
{
  "topic": "Backstage PostgreSQL configuration",
  "category": "config",
  "priority": "high",
  "tags": ["backstage", "postgres", "database", "config"]
}
```

---

### Session Info

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | string | ✅ | "user" or "assistant" |
| `chat_id` | string | ✅ | UUID per chat session |
| `turn_id` | number | ✅ | Increment per turn |
| `conversation_length` | number | ✅ | Total turns in conversation |

**Example:**
```json
{
  "role": "assistant",
  "chat_id": "session-xyz-789",
  "turn_id": 3,
  "conversation_length": 6
}
```

---

## Complete Example

```json
{
  "ai_model": "claude-sonnet-4.5",
  "ai_provider": "anthropic",
  "cursor_mode": "chat",
  
  "ts": "2025-11-05T16:45:30Z",
  "unix_timestamp": 1730826330,
  "date": "2025-11-05",
  "time": "16:45:30",
  
  "project": {
    "root": "C:\\DEV",
    "name": "backstage",
    "workspace": "engineering-home.code-workspace"
  },
  
  "git": {
    "branch": "main",
    "commit": "abc123d",
    "commit_full": "abc123def456789abcdef0123456789abcdef01",
    "repo_url": "github.com/user/engineering-home",
    "dirty": false,
    "remote": "https://github.com/user/engineering-home.git"
  },
  
  "file": {
    "path": "C:\\DEV\\backstage\\app-config.yaml",
    "relative_path": "backstage/app-config.yaml",
    "line": 23,
    "language": "yaml",
    "size_bytes": 4521,
    "last_modified": "2025-11-05T15:30:00Z"
  },
  
  "code": {
    "symbol": "databaseConfig",
    "type": "variable",
    "scope": "global",
    "context": "PostgreSQL connection configuration"
  },
  
  "environment": {
    "working_dir": "C:\\DEV\\backstage",
    "shell": "powershell",
    "os": "windows",
    "open_files": [
      "backstage/app-config.yaml",
      "start-all.bat",
      "docs/README.md"
    ],
    "open_file_count": 3,
    "env_vars": {
      "NODE_ENV": "development",
      "POSTGRES_HOST": "localhost"
    }
  },
  
  "topic": "Backstage PostgreSQL configuration on line 23",
  "category": "config",
  "priority": "high",
  "tags": ["backstage", "postgres", "database", "config", "yaml"],
  
  "role": "assistant",
  "chat_id": "session-xyz-789",
  "turn_id": 3,
  "conversation_length": 6
}
```

---

## Search Examples

### Search by Project
```
qdrant-find with filter: { "project.name": "backstage" }
```

### Search by Category
```
qdrant-find with filter: { "category": "config" }
```

### Search by Date
```
qdrant-find with filter: { "date": "2025-11-05" }
```

### Search by AI Model
```
qdrant-find with filter: { "ai_model": "claude-sonnet-4.5" }
```

### Search by Git Branch
```
qdrant-find with filter: { "git.branch": "main" }
```

### Combined Filters
```
qdrant-find with filter: {
  "project.name": "backstage",
  "category": "config",
  "priority": "high"
}
```

---

## View Stored Memories

### Using PowerShell Script
```powershell
# View all memories
.\scripts\view-cursor-memory.ps1

# View specific project
.\scripts\view-cursor-memory.ps1 -Project "backstage"

# View by category
.\scripts\view-cursor-memory.ps1 -Category "config"

# View statistics
.\scripts\view-cursor-memory.ps1 -Stats

# Export as JSON
.\scripts\view-cursor-memory.ps1 -Json > memories.json
```

### Using Qdrant API
```powershell
# Get all points
$body = '{"limit": 100, "with_payload": true, "with_vector": false}'
Invoke-RestMethod -Method POST `
    -Uri "http://localhost:6333/collections/cursor-chats/points/scroll" `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 10
```

---

## Benefits

This rich metadata enables:

✅ **Full attribution** - Know exactly which AI model said what  
✅ **Project tracking** - Filter by specific projects or subprojects  
✅ **Git awareness** - See what branch and commit context  
✅ **File context** - Know which file and line number  
✅ **Environment state** - See working directory and open files  
✅ **Timeline analysis** - Sort and filter by precise timestamps  
✅ **Cross-referencing** - Link conversations to code locations  
✅ **Audit trail** - Complete history of AI interactions  

---

## Related Files

- Rule file: `.cursor/rules/_cursor_mcp_memory.mdc`
- Viewer script: `scripts/view-cursor-memory.ps1`
- MCP config: `.cursor/mcp.json`
- Setup guide: `CURSOR_MCP_SETUP_COMPLETE.md`
- Integration guide: `docs/architecture/integration/qdrant-mcp-cursor-integration.md`

---

**Last Updated**: November 5, 2025

