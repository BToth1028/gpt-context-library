# GPT Summary Template - Usage Guide

## Quick Start

When creating a new GPT summary request:

1. **Check existing tiers** - Does the topic fit in an existing category?
2. **Create/reuse tier structure** as needed
3. **Copy VERSION_TEMPLATE/** folder
4. **Rename** to `YYMMDD-HHMM` (timestamp = version, newer = later)
5. **Populate** the subfolders with content
6. **Create BRIEFING.zip** (flatten all files from all subfolders)
7. **Open appropriate folder** for user to drag files to ChatGPT

## Template Structure

```
_TEMPLATE/
├── README_TIER1.md              # Copy when creating new Tier 1
├── README_TIER2.md              # Copy when creating new Tier 2
├── README_TIER3.md              # Copy when creating new Tier 3
├── USAGE.md                     # This file
│
└── VERSION_TEMPLATE/            # Copy for each new version request
    ├── request/
    │   └── BRIEFING.txt         # Main summary (edit metadata + fill in)
    ├── code/                    # Source files
    ├── config/                  # Configuration
    ├── logs/                    # Error output
    ├── docs/                    # Screenshots
    ├── tests/                   # Test files
    ├── data/                    # Sample data
    ├── diagrams/                # Visuals
    ├── references/              # Related docs
    ├── context/                 # Chat history
    └── zip/                     # Flattened for GPT
        └── README.txt
```

## Version Naming

**Format**: `YYMMDD-HHMM` (timestamp only, no version suffix)

**Examples**:
- `251104-1530` - Request on Nov 4, 2025 at 3:30 PM
- `251104-1645` - Another request same day at 4:45 PM (later time = newer)
- `251105-0900` - Request next day at 9:00 AM

**Note**: Timestamp serves as natural version - newer timestamps = newer versions

## Workflow Example

### Scenario: Startup script hanging issue

1. **Check tiers**:
   - Tier 1: `automation/` exists ✅
   - Tier 2: `automation/startup-systems/` exists ✅
   - Tier 3: `automation/startup-systems/startup-cleanup-hanging/` - NEW ❌

2. **Create Tier 3**:
   ```powershell
   mkdir "gpt/automation/startup-systems/startup-cleanup-hanging"
   cp _TEMPLATE/README_TIER3.md "gpt/automation/startup-systems/startup-cleanup-hanging/README.md"
   # Edit README.md with topic details
   ```

3. **Create Version**:
   ```powershell
   cp -Recurse _TEMPLATE/VERSION_TEMPLATE "gpt/automation/startup-systems/startup-cleanup-hanging/251104-1530"
   ```

4. **Populate folders**:
   - Edit `request/BRIEFING.txt` with full details (update Target path!)
   - **CRITICAL:** Ensure GPT Instructions link is line 2 (template includes it)
   - Copy `start-all.bat` to `code/`
   - Copy error logs to `logs/`
   - Copy screenshots to `docs/`

5. **Create BRIEFING.zip**:
   ```powershell
   # Flatten all files into zip, then compress
   cp request/BRIEFING.txt zip/
   cp code/* zip/
   cp logs/* zip/
   # etc. for all populated folders
   Compress-Archive -Path 'VERSION/zip/*' -DestinationPath 'VERSION/BRIEFING.zip' -Force
   # Delete intermediate zip/ folder
   rm -r zip/
   ```

6. **Send to GPT**:
   - If < 10 files: Open BRIEFING.zip, drag individual files
   - If ≥ 10 files: Open parent folder, drag BRIEFING.zip

## README Template Guidelines

### Tier 1 (High-level)
- Very general category (e.g., "automation", "architecture", "infrastructure")
- 1-2 sentence overview
- Lists Tier 2 subcategories

### Tier 2 (Subcategory)
- More specific than Tier 1, still broad (e.g., "startup-systems", "deployment-scripts")
- 2-3 sentence description
- Lists Tier 3 topics

### Tier 3 (Specific Topic)
- Specific problem/feature (e.g., "startup-cleanup-hanging", "database-migration-failure")
- Includes version history table
- Links to related topics/ADRs

## When to Create New Tiers

**Create new Tier 1** when:
- Completely new high-level category
- Doesn't fit existing Tier 1s
- Represents major system area

**Create new Tier 2** when:
- Topic is related to Tier 1 but new subcategory
- Multiple Tier 3s would fall under it

**Create new Tier 3** when:
- Specific topic doesn't exist
- Different enough from existing Tier 3s

**Add new timestamped folder** when:
- Same topic, new attempt/iteration
- Follow-up on previous GPT consultation
- Simply create new folder with current timestamp (no version suffix needed)

## Tips

- **Delete empty folders** - If you don't need `tests/` or `diagrams/`, remove them
- **Keep organized** - Use the structured folders for human navigation
- **Target path critical** - MUST be line 1 in BRIEFING.txt, exact path match required
- **Instructions link** - MUST be line 2 in BRIEFING.txt (template has it, don't remove!)
- **BRIEFING.zip only** - Create one zip with all files flattened, no intermediate folders
- **Timestamps are versions** - Newer timestamp = newer version, no V01/V02 needed
- **GPT response format** - Instructions link ensures ChatGPT formats correctly for watcher

## Maintenance

Update this template structure when:
- New folder types are needed
- BRIEFING.txt format changes
- README structure improves
- Additional metadata required
