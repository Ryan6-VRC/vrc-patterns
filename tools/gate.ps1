#requires -Version 7
<#
  vrc-patterns gate: compile + round-trip + decompile-equality over every entry.

  Boots Unity batchmode against the workspace TestEditor (which loads the avatar-tools package by
  file: ref, so it always has the current CompileController/ControllerFixpoint) and runs
  ControllerFixpoint.RunGate over this repo's entries. The gate's mechanism lives in the tool; the
  loop + pass/fail lives here (this script). Exit 0 iff every entry passes.
#>
[CmdletBinding()]
param(
  [string]$AtelierRoot = '',
  [string]$Unity = 'C:/Program Files/Unity/Hub/Editor/2022.3.22f1/Editor/Unity.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$log  = Join-Path $PSScriptRoot 'gate.log'

# Default AtelierRoot from the repo's MAIN checkout (git worktree list line 1), whose parent is the
# Atelier workspace root — correct from the main checkout and from any git-worktree slice, where a
# fixed ../.. hop would land in the worktrees dir instead.
if (-not $AtelierRoot) {
  $mainWt = (& git -C $root worktree list --porcelain | Select-Object -First 1) -replace '^worktree ', ''
  $AtelierRoot = (Resolve-Path (Join-Path $mainWt '..')).Path
}
$editor = Join-Path $AtelierRoot 'TestEditor'

if (-not (Test-Path $editor)) {
  $setup = Join-Path $AtelierRoot 'tools/setup-test-editor.ps1'
  if (-not (Test-Path $setup)) {
    Write-Error "AtelierRoot '$AtelierRoot' has no tools/setup-test-editor.ps1 — pass -AtelierRoot <path to the Atelier workspace root>."
    exit 1
  }
  Write-Host "TestEditor missing — provisioning."
  & pwsh $setup -Sync
}

if (Test-Path $log) { Remove-Item $log }
# Custom args (--root <dir>) are appended plain; Unity ignores them, RunGate reads them from
# Environment.GetCommandLineArgs(). Unity.exe is GUI-subsystem, so -Wait needs Start-Process.
$p = Start-Process -FilePath $Unity -PassThru -Wait -ArgumentList @(
  '-batchmode', '-quit', '-projectPath', $editor,
  '-executeMethod', 'Ryan6Vrc.AvatarTools.Editor.ControllerFixpoint.RunGate',
  '-logFile', $log, '--root', $root
)
if (Test-Path $log) { Get-Content $log | Select-String -Pattern '\[gate\]' }
Write-Host "gate exit=$($p.ExitCode)"
exit $p.ExitCode
