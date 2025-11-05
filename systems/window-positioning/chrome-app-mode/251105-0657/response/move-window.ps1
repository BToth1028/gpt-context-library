param(
  [Parameter(Mandatory=$true)] [int]$Pid,
  [int]$X = 0, [int]$Y = 0, [int]$W = 1200, [int]$H = 800,
  [int]$TimeoutMs = 8000
)

Add-Type -Namespace Win32 -Name Native -MemberDefinition @'
using System;
using System.Runtime.InteropServices;
public static class U32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  public static readonly IntPtr HWND_TOP = new IntPtr(0);
  public const uint SWP_NOZORDER = 0x0004;
  public const uint SWP_NOACTIVATE = 0x0010;
}
'@

$hFound = [IntPtr]::Zero
$start  = Get-Date
while (((Get-Date) - $start).TotalMilliseconds -lt $TimeoutMs) {
  [Win32.U32]::EnumWindows(
    { param([IntPtr]$h, [IntPtr]$l)
      if ([Win32.U32]::IsWindowVisible($h)) {
        [uint32]$p = 0; [Win32.U32]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
        if ($p -eq $Pid) { $script:hFound = $h; return $false }
      }
      return $true
    }, [IntPtr]::Zero
  ) | Out-Null

  if ($hFound -ne [IntPtr]::Zero) {
    [Win32.U32]::SetWindowPos($hFound, [Win32.U32]::HWND_TOP, $X, $Y, $W, $H,
      [Win32.U32]::SWP_NOZORDER -bor [Win32.U32]::SWP_NOACTIVATE) | Out-Null
    exit 0
  }
  Start-Sleep -Milliseconds 100
}
Write-Warning "Window not found for PID $Pid within $TimeoutMs ms"
exit 1
