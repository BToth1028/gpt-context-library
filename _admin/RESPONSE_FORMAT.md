# GPT Response Format Rules

**Last Updated:** 2025-11-04

## File Naming

- **Single file response:** Name it `GPT_RESPONSE.md`
- **Multiple files:** Name main response `GPT_RESPONSE.md` + list additional files

## Required Header Format

**Line 1:** Target path (where files should be saved)
```
Target path: C:\DEV\docs\gpt\[tier1]\[tier2]\[tier3]\YYMMDD-HHMM_VXX\response
```

**Line 2 (optional):** Additional files list (comma-separated)
```
Files: watcher-v2.ps1, config.json, README.md
```

## File Location

- Save all files to your Downloads folder
- Use exact filenames listed in `Files:` line
- Watcher will auto-move them to target path

## Example Response

```markdown
Target path: C:\DEV\docs\gpt\automation\startup-systems\file-watcher\251104-1500_V01\response
Files: improved-watcher.ps1, test-suite.ps1

## Summary
...your content here...
```

## What NOT to Include

- Don't add explanatory text before the Target path line
- Don't use markdown bold (`**`) around "Target path:"
- Don't add quotes or formatting to file names
- Keep the format exactly as shown above
