# GPT Workflow - Quick Reference

## 🎯 When User Says:
- "Give me a GPT summary"
- "Create briefing for GPT"
- "Send this to ChatGPT"

## ⚡ Cursor Does (Automatic):

### 1. Check Tiers
- `docs/gpt/[TIER1]/[TIER2]/[TIER3]/`
- Reuse existing tier3 if topic matches
- Increment version (V01→V02) if same topic

### 2. Create Version Folder
- `YYMMDD-HHMM_VXX/`
- Copy from `_admin/template/VERSION_TEMPLATE/`

### 3. Populate Folders
- `request/BRIEFING.txt` - Complete context
- `code/` - All source files
- `config/` - Configs
- `logs/` - Errors
- `response/` - (Empty, for ChatGPT's reply)
- Delete empty folders

### 4. Flatten Files
- **<10 files** → `all_files/` (no zip)
- **≥10 files** → `zip.zip` archive

### 5. Sanitize
- Remove: passwords, keys, IPs, tokens
- Replace with: `[REDACTED]`

### 6. Start Watcher
```powershell
# Kill old watcher
if (Test-Path ".watcher.pid") {
    Stop-Process -Id (Get-Content ".watcher.pid") -Force
}

# Start new (save PID)
$proc = Start-Process powershell -ArgumentList "..." -WindowStyle Minimized -PassThru
$proc.Id | Out-File ".watcher.pid"
```

### 7. Sync to GitHub
```powershell
cd C:\DEV\docs\gpt
git add .
git commit -m "Add: [topic] VXX"
git push
git log -1 --format=%H
```

### 8. Output Two Messages

**Message 1 (GitHub URLs):**
```
Please review these files for [topic]:

**Briefing:**
https://raw.githubusercontent.com/BToth1028/gpt-context-library/[HASH]/[path]/BRIEFING.txt

**Code Files:**
https://raw.githubusercontent.com/BToth1028/gpt-context-library/[HASH]/[path]/file1.ps1
https://raw.githubusercontent.com/BToth1028/gpt-context-library/[HASH]/[path]/file2.bat

Follow instructions at: https://raw.githubusercontent.com/.../GPT_INSTRUCTIONS.md
```

**Message 2 (User Instructions):**
```
Copy prompt above → Send to ChatGPT → Save response as GPT_RESPONSE.md
Watcher is running and will auto-move the file.
```

---

## 📋 BRIEFING.txt Header (Required)

```
═══════════════════════════════════════════════════════════════
GPT BRIEFING REQUEST
═══════════════════════════════════════════════════════════════
AI Model: Claude Sonnet 4.5 (Cursor IDE)
Topic: [Specific problem]
Date: YYYY-MM-DD
Time: HH:MM
Version: VXX
Status: [Issue/Enhancement/Review]
Category: [tier1]/[tier2]/[tier3]
═══════════════════════════════════════════════════════════════

Follow instructions at: https://raw.githubusercontent.com/.../GPT_INSTRUCTIONS.md

**Target path:** C:\DEV\docs\gpt\[tier1]\[tier2]\[tier3]\[VERSION]\response

## Summary
[Brief overview]

## What Works ✅
[List]

## What's Broken ❌
[List]

## What We're Trying to Do
[Goal]

## Context
[Architecture, constraints]

## Analysis
[Root causes]

## Suggested Fixes
[Recommendations]

## Code Listings
[Complete files]
```

---

## 🤖 ChatGPT Response Format (Required)

**File:** `GPT_RESPONSE.md`

**Line 1 (REQUIRED):**
```
**Target path:** C:\DEV\docs\gpt\[tier1]\[tier2]\[tier3]\[VERSION]\response
```

**Line 2 (if multiple files):**
```
**Files:** improved-script.ps1, config.json, test.ps1
```

---

## 🔍 Watcher Behavior (One-Shot)

1. Detects `GPT_RESPONSE.md` in Downloads
2. Reads line 1: `**Target path:**`
3. Reads line 2: `**Files:**` (if exists)
4. **Single file:** Move → Exit
5. **Multiple files:**
   - Poll every 3 seconds
   - Move each as it appears
   - Reset timer on new file
   - Exit when no files for 3 seconds

**Retry:** 5 attempts, backoff 50→100→200→400→800ms
**Error:** Creates dirs, logs missing files, exits cleanly

---

## 📊 When ChatGPT Responds

### Step 1: STOP - Don't Implement Yet
- Read full response (in `[VERSION]/response/`)
- ChatGPT only sees one commit
- Cursor has full project context

### Step 2: Analyze
Present to user:
- ✅ What makes sense
- ❌ What doesn't (context ChatGPT missed)
- ⚖️ Trade-offs
- 🔍 Missing context
- 📊 Honest assessment

### Step 3: Ask User
- **Option A: Implement** → Apply + test + report
- **Option B: Iterate** → New version (VXX+1)

### Step 4: Execute Choice
- **A:** Implement immediately
- **B:** Start GPT workflow again (increment version)

---

## 📁 Folder Structure (Quick View)

```
docs/gpt/
├── _admin/
│   ├── template/
│   │   ├── README_TIER1.md
│   │   ├── README_TIER2.md
│   │   ├── README_TIER3.md
│   │   └── VERSION_TEMPLATE/
│   └── GPT_INSTRUCTIONS.md
│
└── [TIER1]/                    # automation, systems, operations
    └── [TIER2]/                # startup-systems, file-watcher
        └── [TIER3]/            # batch-orchestration
            ├── README.md       # Version history
            └── YYMMDD-HHMM_VXX/
                ├── request/BRIEFING.txt
                ├── response/        # Auto-filled by watcher
                ├── code/
                ├── config/
                ├── logs/
                ├── all_files/       # <10 files
                └── zip.zip          # ≥10 files
```

---

## 🔑 Key Rules

### Version Increment:
- **Same topic + iteration** → V01→V02→V03
- **Different topic** → New Tier 3, V01

### File Count:
- **<10 files** → `all_files/` folder (no zip)
- **≥10 files** → `zip.zip` archive

### Watcher:
- **One-shot mode** - exits after moving files
- **PID tracked** - `.watcher.pid` at workspace root
- **Auto-starts** - when briefing created
- **Auto-kills old** - prevents duplicates

### GitHub:
- **Public repo** - sanitize sensitive data
- **Raw URLs only** - ChatGPT needs direct file access
- **Commit hash** - use in URLs for permanence

---

## 🚨 Common Mistakes to Avoid

❌ Creating zip when <10 files
❌ Not killing old watcher first
❌ Using regular GitHub URLs (not raw)
❌ Forgetting target path in briefing
❌ Not incrementing version for same topic
❌ Creating new tier when topic exists
❌ Implementing ChatGPT response immediately (review first!)
❌ Forgetting to sanitize before GitHub sync
❌ Not updating Tier 3 README with version
❌ Leaving empty folders in version

---

## 📍 Script Locations

**Watcher:**
- `C:\DEV\scripts\gpt-response-watcher.ps1`
- `C:\DEV\scripts\start-gpt-watcher.bat`
- `C:\DEV\.watcher.pid` (runtime)

**GitHub Sync:**
- `C:\DEV\scripts\sync-gpt-repo.ps1`

**Briefing Builder:**
- `C:\DEV\scripts\prepare-gpt-briefing.ps1`

**Templates:**
- `C:\DEV\docs\gpt\_admin\template\`

**Instructions:**
- `C:\DEV\docs\gpt\_admin\GPT_INSTRUCTIONS.md`

---

## 📞 Quick Commands

```powershell
# Manual watcher start (if needed)
.\scripts\start-gpt-watcher.bat

# Kill stuck watcher
Stop-Process -Id (Get-Content ".watcher.pid") -Force

# Manual GitHub sync
cd C:\DEV\docs\gpt
git add . && git commit -m "Add: topic VXX" && git push

# Get latest commit hash
git log -1 --format=%H
```

---

**Full Details:** `C:\dev\.cursor\rules\project-standards.mdc` (lines 404-681)
**Repository:** https://github.com/BToth1028/gpt-context-library
**Instructions:** https://raw.githubusercontent.com/BToth1028/gpt-context-library/main/_admin/GPT_INSTRUCTIONS.md
