Target path: C:\DEV\docs\gpt\automation\startup-systems\file-watcher-automation\251104-1445_V04\response

# Simple Stability Check – Code Snippets Only

Below are **minimal** additions to your existing `gpt-response-watcher.ps1` to ensure a file is fully written before it is moved. The format matches your request. 

## 1) Add this function **after line 49** (after other functions):

```powershell
function Test-FileStable([string]$path, [int]$waitMs = 500) {
    # Returns $true if file size stops changing between two reads
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try { $s1 = (Get-Item -LiteralPath $path -ErrorAction Stop).Length } catch { return $false }
    Start-Sleep -Milliseconds $waitMs
    try { $s2 = (Get-Item -LiteralPath $path -ErrorAction Stop).Length } catch { return $false }
    return ($s1 -eq $s2)
}
```

## 2) In the polling loop **around line 66**, before moving the file, add this check:

```powershell
if (Test-Path -LiteralPath $targetFile) {
    if (-not (Test-FileStable -path $targetFile -waitMs 500)) {
        continue  # still being written; check again on next poll
    }
    # existing move logic continues here...
}
```

### Why this works (brief)
- Two size reads with a short delay detect active writes without heavy locks.
- Uses `-LiteralPath` and guarded `Get-Item` calls to avoid exceptions while the file is open.

## Optional: safer move helper (tiny)
If you want one more line of safety during the move:
```powershell
try { Move-Item -LiteralPath $targetFile -Destination $dest -ErrorAction Stop } catch { continue }
```

_No other changes required. Keep your simple design as-is._
