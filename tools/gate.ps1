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
  [string]$AtelierRoot = (Resolve-Path "$PSScriptRoot/../..").Path,
  [string]$Unity = 'C:/Program Files/Unity/Hub/Editor/2022.3.22f1/Editor/Unity.exe'
)
$ErrorActionPreference = 'Stop'
$editor = Join-Path $AtelierRoot 'TestEditor'
$root   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$log    = Join-Path $PSScriptRoot 'gate.log'

if (-not (Test-Path $editor)) {
  Write-Host "TestEditor missing — provisioning."
  & pwsh (Join-Path $AtelierRoot 'tools/setup-test-editor.ps1') -Sync
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
