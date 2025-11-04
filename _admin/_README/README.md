# GPT Summary System

**Purpose**: Organized storage for GPT/ChatGPT consultation requests with complete context, code, and analysis.

---

## System Overview

This directory uses a **3-tier folder structure** with **versioned summaries**:

```
gpt/
├── _admin/                       # Admin files (templates, README)
│   ├── _README/                  # This overview document
│   └── template/                 # Template system (see USAGE.md)
│
├── [tier1]/                      # High-level category
│   ├── README.md                 # Category overview
│   │
│   └── [tier2]/                  # Subcategory
│       ├── README.md             # Subcategory overview
│       │
│       └── [tier3]/              # Specific topic
│           ├── README.md         # Topic overview + version history
│           │
│           └── YYMMDD-HHMM_VXX/  # Timestamped version
│               ├── request/
│               │   └── BRIEFING.txt       # Full summary
│               ├── code/                   # Source files
│               ├── config/                 # Configs
│               ├── logs/                   # Error logs
│               ├── docs/                   # Screenshots
│               ├── tests/                  # Test files
│               ├── data/                   # Sample data
│               ├── diagrams/               # Visuals
│               ├── references/             # ADRs/links
│               ├── context/                # Chat history
│               └── zip/                    # Flattened for GPT
```

---

## Quick Start

**For detailed step-by-step instructions, see [WORKFLOW.md](../_admin/WORKFLOW.md)**

### TL;DR

### When Cursor Creates a Summary:

1. **Say**: "Give me a GPT summary"
2. **Cursor will**:
   - Check existing tiers (reuse if possible)
   - Create new version folder: `YYMMDD-HHMM_VXX`
   - Generate complete BRIEFING.txt
   - Copy all relevant code/configs/logs
   - Flatten everything to `zip/` folder
3. **You**:
   - Copy contents of `zip/` folder
   - Paste to ChatGPT
   - Get solution
   - Update Tier 3 README with results

### Creating Summaries Manually:

1. Copy `_admin/template/VERSION_TEMPLATE/`
2. Rename to `YYMMDD-HHMM_V01`
3. Fill in `request/BRIEFING.txt`
4. Add files to appropriate folders
5. Copy everything to `zip/` (flattened)

---

## Tier Guidelines

### Tier 1 (High-Level Categories)

**Examples**:
- `systems/` - System architecture, design patterns
- `operations/` - DevOps, deployment, infrastructure
- `automation/` - Scripts, workflows, tooling

**When to Create**:
- New major area that doesn't fit existing categories
- Would contain multiple subcategories

### Tier 2 (Subcategories)

**Examples**:
- `systems/context-management/`
- `operations/windows-integration/`
- `automation/startup-systems/`

**When to Create**:
- Related to Tier 1 but needs subdivision
- Multiple specific topics would fall under it

### Tier 3 (Specific Topics)

**Examples**:
- `systems/context-management/project-context-os/`
- `operations/windows-integration/sandboxie/`
- `automation/startup-systems/startup-cleanup-hanging/`

**When to Create**:
- Specific problem/feature/implementation
- Needs GPT consultation

---

## Version Naming

**Format**: `YYMMDD-HHMM_VXX`

**Rules**:
- Same topic → increment version (V01 → V02 → V03)
- New topic → new Tier 3, start at V01
- Include date and time for chronological tracking

**Examples**:
- `251104-1530_V01` - First request Nov 4, 2025 at 3:30 PM
- `251104-1645_V02` - Second request same day
- `251105-0900_V03` - Third request next day

---

## Current Categories

### Systems (Tier 1)
- **context-management/** - Context systems, documentation, knowledge bases
  - **project-context-os/** - The 4-portal engineering workspace

### Operations (Tier 1)
- **windows-integration/** - Windows-specific tooling and integration
  - **sandboxie/** - Sandboxie research and implementation

---

## Legacy Files

Files in flat structure (pre-Nov 2025) are being migrated to new 3-tier system:

- `architecture/` → Moving to `systems/context-management/project-context-os/`
- `devops/` → Moving to `operations/windows-integration/`
- `coding-patterns/` → Will be reorganized as needed

---

## Special Folders

### `_admin/`
Administrative files including:
- **template/** - Complete template system with README templates for each tier, VERSION_TEMPLATE folder structure, and USAGE.md guide
- **_README/** - This overview document
- **DO NOT MODIFY templates** - Copy from here

---

## Best Practices

1. **Always check existing tiers first** - Reuse structure when possible
2. **Update Tier 3 README** - Track version history
3. **Use zip/ folder** - Makes sending to GPT effortless
4. **Keep READMEs general** - Save details for version folders
5. **Delete empty subfolders** - Only keep what's needed for each request
6. **Sanitize sensitive data** - This folder syncs to public GitHub repo
   - Remove passwords, API keys, tokens
   - Use placeholder values for internal IPs/domains
   - Keep code examples generic when possible

---

## See Also

- **Template Usage**: `_admin/template/USAGE.md`
- **BRIEFING Format**: `_admin/template/VERSION_TEMPLATE/request/BRIEFING.txt`
- **Cursor Rules**: `.cursor/rules/project-standards.mdc` (lines 235-280)
- **Public Repository**: This folder is synced to a separate public GitHub repo
- **Sync Scripts**: `../../scripts/init-gpt-repo.ps1` and `../../scripts/sync-gpt-repo.ps1`
