# Cursor ↔ ChatGPT Workflow

**Date:** 2025-11-04  
**Purpose:** Clarify roles and file ownership in the GPT consultation process

---

## The Players

1. **Cursor AI** - Code assistant in your IDE (this is me)
2. **ChatGPT** - Web-based AI consultant (separate service)
3. **You** - The human orchestrating both

---

## The Workflow

### Step 1: Working with Cursor (Me)

**You say:** "Put together a briefing for GPT"

**Cursor creates:**
- `briefing.md` in the version's `/request/` folder
- Contains: problem context, what we tried, current status
- This is FOR ChatGPT, not FROM ChatGPT

**Cursor DOES NOT create:**
- ❌ `GPT_RESPONSE.md` 
- ❌ Any files in `/response/` folder
- ❌ Any files that simulate ChatGPT's output

### Step 2: You Consult ChatGPT

**You do:**
1. Copy the briefing content
2. Paste it into ChatGPT's web interface
3. Read ChatGPT's response

**Cursor is not involved** - This happens in your browser

### Step 3: You Save ChatGPT's Response

**Option A: Manual Save**
1. Copy ChatGPT's response
2. Create `GPT_RESPONSE.md` in Downloads
3. Add header with target path:
   ```markdown
   **Target path:** C:\DEV\docs\gpt\automation\...\response
   
   **Files:** file1.py, file2.bat
   
   [ChatGPT's response here]
   ```
4. Watcher script (`gpt-response-watcher.ps1`) moves it automatically

**Option B: Use Script**
1. Run `.\scripts\save-gpt-response.ps1`
2. Manually paste ChatGPT's response

### Step 4: Back to Cursor

**You say:** "Implement what ChatGPT suggested"

**Cursor does:**
- Reads the response file in `/response/`
- Implements changes
- Continues iteration

---

## File Ownership Rules

### Files Cursor Creates

✅ **Briefings for ChatGPT:**
- `briefing.md`
- `BRIEFING.txt`
- Any files in `/request/` folder

✅ **Code and implementation:**
- Modified source files
- New features
- Bug fixes

✅ **Documentation:**
- README updates
- Architecture notes

### Files ChatGPT Creates (via You)

✅ **Response files:**
- `GPT_RESPONSE.md` (you save this manually)
- Any files in `/response/` folder

✅ **Solution documents:**
- Analysis from ChatGPT
- Recommendations
- Alternative approaches

### Files Cursor NEVER Creates

❌ `GPT_RESPONSE.md` - This is always FROM ChatGPT, saved by you
❌ Anything in `/response/` folder - Reserved for ChatGPT's output
❌ Anything that simulates or pretends to be ChatGPT's response

---

## Why This Matters

**Clarity of source:**
- If I (Cursor) create `GPT_RESPONSE.md`, it's unclear whether it's my analysis or ChatGPT's
- The `/response/` folder specifically means "ChatGPT's output"
- You orchestrate both tools - you control when each is involved

**Workflow integrity:**
- The watcher script expects responses FROM ChatGPT
- Creating fake responses breaks the version tracking
- Each tool stays in its lane

---

## Example Session

**Good workflow:**

```
You: "Hey Cursor, put together a briefing for GPT about the startup script issue"
Cursor: ✅ Creates briefing.md with context

You: [Opens ChatGPT, pastes briefing]
ChatGPT: [Provides solution]

You: [Saves ChatGPT response as GPT_RESPONSE.md]
Watcher: ✅ Moves file to /response/ folder

You: "Cursor, implement what ChatGPT suggested"
Cursor: ✅ Reads response, implements changes
```

**Bad workflow:**

```
You: "Put together a briefing for GPT"
Cursor: ❌ Creates briefing.md AND GPT_RESPONSE.md
        (This is wrong - I haven't consulted ChatGPT yet!)
```

---

## Quick Reference

| File | Creator | Location | Purpose |
|------|---------|----------|---------|
| `briefing.md` | Cursor | `/request/` | Context for ChatGPT |
| `GPT_RESPONSE.md` | You (from ChatGPT) | Downloads → `/response/` | ChatGPT's solution |
| Implementation | Cursor | Source files | Execute solution |

---

## Related Scripts

- `scripts/gpt-response-watcher.ps1` - Auto-moves responses from Downloads
- `scripts/save-gpt-response.ps1` - Manual response save helper
- `scripts/prepare-gpt-briefing.ps1` - Briefing generator (if needed)

---

**Last Updated:** 2025-11-04  
**Reason:** Clarified after Cursor mistakenly created GPT_RESPONSE.md

