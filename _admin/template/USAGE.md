# GPT Summary Template - Usage Guide

## Quick Start

When creating a new GPT summary request:

1. **Check existing tiers** - Does the topic fit in an existing category?
2. **Create/reuse tier structure** as needed
3. **Copy VERSION_TEMPLATE/** folder
4. **Rename** to `YYMMDD-HHMM_VXX` (increment version if same topic)
5. **Populate** the subfolders with content
6. **Copy everything to zip/** folder (flattened)
7. **Update** the Tier 3 README with new version entry

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

**Format**: `YYMMDD-HHMM_VXX`

**Examples**:
- `251104-1530_V01` - First request on Nov 4, 2025 at 3:30 PM
- `251104-1645_V02` - Second request same day at 4:45 PM
- `251105-0900_V03` - Third request next day at 9:00 AM

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

3. **Create Version 1**:
   ```powershell
   cp -Recurse _TEMPLATE/VERSION_TEMPLATE "gpt/automation/startup-systems/startup-cleanup-hanging/251104-1530_V01"
   ```

4. **Populate folders**:
   - Edit `request/BRIEFING.txt` with full details
   - Copy `start-all.bat` to `code/`
   - Copy error logs to `logs/`
   - Copy screenshots to `docs/`

5. **Flatten to zip/**:
   ```powershell
   cp request/BRIEFING.txt zip/
   cp code/* zip/
   cp logs/* zip/
   # etc. for all populated folders
   ```

6. **Send to GPT**:
   - Copy everything from `zip/` folder
   - Paste to ChatGPT

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

**Add new Version** when:
- Same topic, new attempt/iteration
- Follow-up on previous GPT consultation

## Tips

- **Delete empty folders** - If you don't need `tests/` or `diagrams/`, remove them
- **Keep organized** - Use the structured folders for human navigation
- **Keep zip/ flat** - Everything goes directly in zip/, no subfolders
- **Update READMEs** - Keep tier READMEs current with new topics/versions
- **Version incrementally** - V01, V02, V03... don't skip numbers

## Maintenance

Update this template structure when:
- New folder types are needed
- BRIEFING.txt format changes
- README structure improves
- Additional metadata required
