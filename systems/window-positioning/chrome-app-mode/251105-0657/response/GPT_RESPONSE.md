**Target path:** C:\DEV\docs\gpt\systems\window-positioning\chrome-app-mode\251105-0657\response
**Files:** start-dashboard-fixed.ps1, move-window.ps1, window-tests.ps1

# Deterministic Chrome app-mode window placement

## Summary
Cause: a resident Chrome broker or cached profile bounds override `--window-position`. Your failing launcher pre-starts Chrome indirectly and reuses a profile with saved app-window placement. Result: window opens on the wrong monitor. Fix: launch app-mode as the first Chrome instance for a dedicated profile, purge cached bounds, and enforce final placement via Win32 after the window appears.

## What works
- First Chrome window with fresh profile honors `--window-position=-400,100`.
- Post-launch Win32 `SetWindowPos` guarantees final coordinates.

## What does not work
- Any pre-running Chrome broker for the same user session.
- Reusing a profile with `app_window_placement` in `Preferences`.

## Implementation guide
1) Use `start-dashboard-fixed.ps1`. It creates an isolated profile, purges cached bounds, polls the server without arbitrary delays, launches app-mode in one shot, and enforces placement with `move-window.ps1`.
2) Run `window-tests.ps1` to validate cold/warm starts and move-only behavior.
3) Keep a dedicated `--user-data-dir` per app. Do not pre-start generic Chrome.

## Testing steps
1. Close all Chrome processes.
2. Run `window-tests.ps1`.
3. Confirm the app window lands at X=-400, Y=100 with size 1200x800.
4. Re-run with an existing profile to confirm the post-launch move still enforces placement.

## Notes
- For per-monitor targeting, extend `move-window.ps1` to query virtual screen metrics and clamp into the desired monitor work-area.
- Limit profile edits to `Preferences` keys that affect windowing to avoid profile bloat.
