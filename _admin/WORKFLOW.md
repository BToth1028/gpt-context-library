# GPT Briefing Workflow

**Last Updated:** 2025-11-04

## Primary Workflow: ZIP File Method

**Use this method for all GPT briefings.** It's instant, reliable, and simple.

### Steps

1. **Create briefing folders** (or I'll do this automatically):
   ```
   docs/gpt/[tier1]/[tier2]/[tier3]/YYMMDD-HHMM_VXX/
     ├── request/      (BRIEFING.txt goes here)
     ├── code/         (relevant code files)
     ├── response/     (GPT_RESPONSE.md auto-moved here)
     └── logs/         (optional)
   ```

2. **Run the prepare script:**
   ```powershell
   cd C:\DEV
   powershell -ExecutionPolicy Bypass -File C:\DEV\scripts\prepare-gpt-briefing.ps1
   ```

3. **What happens automatically:**
   - ✓ Finds latest version folder
   - ✓ Creates `zip.zip` with all relevant files
   - ✓ Opens Explorer with zip.zip selected
   - ✓ Copies GPT prompt to clipboard
   - ✓ Starts response watcher (one-shot mode)
   - ✓ Shows PID for tracking

4. **Send to ChatGPT:**
   - Upload the `zip.zip` file
   - Press `Ctrl+V` to paste the prompt (already copied!)
   - Send

5. **Save response:**
   - ChatGPT provides response (and optionally additional files)
   - Save/download main response as `GPT_RESPONSE.md` in your Downloads folder
   - **Must be named exactly:** `GPT_RESPONSE.md`
   - **Must include:** `Target path: [path]` as first line
   - **Optional:** If ChatGPT creates additional files, it lists them on line 2: `Files: file1.ps1, file2.json`
   - Save all additional files to Downloads with exact names listed

6. **Watcher auto-moves files:**
   - Checks Downloads every 2 seconds
   - Detects `GPT_RESPONSE.md`
   - Reads target path and files list from content
   - Moves `GPT_RESPONSE.md` + all additional files to response folder
   - Shows Windows notification with count
   - Logs warnings if any listed files not found
   - Exits automatically

### Timing
- **Total workflow:** ~30 seconds
- **No waiting** for caches or GitHub

### Troubleshooting

**Watcher not moving file:**
- Check watcher is running: `Get-Process | Where-Object { (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*gpt-response-watcher*" }`
- Verify file is named exactly `GPT_RESPONSE.md`
- Check file has `**Target path:**` as first line
- Manual kill: `Stop-Process -Id [PID] -Force`

**Manual file move if needed:**
```powershell
Move-Item "$env:USERPROFILE\Downloads\GPT_RESPONSE.md" "C:\DEV\docs\gpt\[path]\response\GPT_RESPONSE.md" -Force
```

## Backup Workflow: GitHub Sync

**Use occasionally** to backup the GPT library to GitHub. Not for real-time ChatGPT work.

### When to use:
- End of day backup
- Weekly documentation updates
- Building public reference library

### Command:
```powershell
cd C:\DEV
powershell -ExecutionPolicy Bypass -File C:\DEV\scripts\sync-gpt-repo.ps1 -Message "Backup: [description]"
```

### What it does:
- Commits all changes in `docs/gpt/`
- Pushes to GitHub (public repo: `BToth1028/gpt-context-library`)
- **Does NOT create zip files** (removed for speed)
- Generates commit-pinned permalinks (for reference)

### Why not use for ChatGPT:
- **15-minute cache delay** - ChatGPT's GitHub connector needs time to see new commits
- Slower than ZIP workflow
- Unnecessary waiting

## Script Locations

| Script | Path | Purpose |
|--------|------|---------|
| prepare-gpt-briefing.ps1 | `C:\DEV\scripts\` | Prepare briefing + start watcher (PRIMARY) |
| gpt-response-watcher.ps1 | `C:\DEV\scripts\` | Auto-move GPT responses |
| sync-gpt-repo.ps1 | `C:\DEV\scripts\` | Backup to GitHub (OCCASIONAL) |
| start-gpt-watcher.bat | `C:\DEV\scripts\` | Manual watcher start (if needed) |

## Watcher Details

### How it works:
- Polls Downloads folder every 2 seconds
- Pattern: `GPT_RESPONSE.md` (exact name)
- Reads target path from file content using regex: `\*\*Target path:\*\*\s*(.+?)`
- Creates target directory if needed
- Moves file (cuts, not copies)
- Exits after successful move (one-shot mode)

### PID Management:
- PID saved to: `C:\DEV\.watcher.pid`
- Automatically killed when running new watcher
- Manual kill: Read PID from file, `Stop-Process -Id [PID]`

### Timeout:
- Max wait: 1 hour
- Heartbeat message: Every 5 minutes
- Auto-exits if timeout reached

## Version Numbering

Format: `YYMMDD-HHMM_VXX`

Examples:
- `251104-1445_V01` - First version on Nov 4, 2025 at 14:45
- `251104-1445_V02` - Second version (iteration)
- `251104-1500_V01` - New topic at 15:00

**Increment V when:**
- Iterating on same topic
- GPT provides another revision
- Refining the same problem

**New timestamp when:**
- Different topic entirely
- New problem/feature
- Different tier-3 folder

## ChatGPT Prompt Format

The auto-copied prompt includes:
```
Please review the attached zip file containing a GPT briefing.

Tasks:
1. Review all documentation (note the Target path in the briefing)
2. Summarize what works and what does not work
3. Provide complete code fixes for all apparent issues
4. Suggest improvements and additional features
5. Include implementation code for all suggestions

Please be thorough and provide production-ready code with explanations.

IMPORTANT: When creating your response document:
- Name it: GPT_RESPONSE.md
- Include this as the FIRST LINE: **Target path:** [path from briefing]
```

This ensures:
- Consistent format
- Target path is included
- Watcher can auto-route response

## Best Practices

1. **One briefing at a time** - Don't run multiple watchers simultaneously
2. **Clear names** - Use descriptive tier-3 folder names
3. **Version intentionally** - Don't spam versions, iterate meaningfully
4. **Check watcher started** - Look for PID confirmation
5. **Wait for file to move** - Don't manually move while watcher is running
6. **Kill stale watchers** - If process hangs, kill via PID file

## Future Improvements

Potential enhancements (not implemented yet):
- Stability check for file before moving (wait for size to stabilize)
- Better error logging
- Email/notification when file moved
- Automatic GitHub sync after X versions
- Web UI for browsing briefings
