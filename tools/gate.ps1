#requires -Version 7
<#
  vrc-patterns gate: compile + decompile-equality over every entry, at any depth. It does NOT round-trip
  the schema — that a decompile recompiles identically is a property of avatar-tools, proven in that
  package's own fixpoint suites, and a break there is a tool bug that must not fail an entry's admission.

  Boots Unity batchmode against the workspace TestEditor (which loads the avatar-tools package by
  file: ref, so it always has the current CompileController/ControllerFixpoint) and runs
  ControllerFixpoint.RunGate over this repo's entries. The gate's mechanism lives in the tool; the
  loop + pass/fail lives here (this script). Exit 0 iff every entry passes, README lint included.
#>
[CmdletBinding()]
param(
  [string]$AtelierRoot = '',
  # Unity.exe for the batchmode run. Empty resolves it from TestEditor's own pinned version via the
  # workspace's tools/unity-editor.ps1. Pass one to override.
  [string]$Unity = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# Text-only, Unity-free, and first: a README rule broken here is knowable without a batchmode boot,
# and the boot below costs minutes. CONVENTIONS.md §The README owns the rule.
& (Join-Path $PSScriptRoot 'readme-lint.ps1') -Root $root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Default AtelierRoot from the repo's MAIN checkout (git worktree list line 1), whose parent is the
# Atelier workspace root — correct from the main checkout and from any git-worktree slice, where a
# fixed ../.. hop would land in the worktrees dir instead.
if (-not $AtelierRoot) {
  $mainWt = (& git -C $root worktree list --porcelain | Select-Object -First 1) -replace '^worktree ', ''
  $AtelierRoot = (Resolve-Path (Join-Path $mainWt '..')).Path
}
$editor = Join-Path $AtelierRoot 'TestEditor'

# The log goes to the workspace's disposable pile, NOT beside this script. Writing it into tools/ puts
# a file Unity treats as an asset inside the package tree: any venue that mounts this repo re-imports
# it on every write, and because the gate writes throughout its own run that becomes an infinite import
# loop which fails every entry with a null reference. Gitignoring it does not help — Unity imports what
# is on disk, not what git tracks.
$logDir = Join-Path $AtelierRoot 'test-output'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'patterns-gate.log'

if (-not (Test-Path $editor)) {
  $setup = Join-Path $AtelierRoot 'tools/setup-test-editor.ps1'
  if (-not (Test-Path $setup)) {
    Write-Error "AtelierRoot '$AtelierRoot' has no tools/setup-test-editor.ps1 — pass -AtelierRoot <path to the Atelier workspace root>."
    exit 1
  }
  Write-Host "TestEditor missing — provisioning."
  & pwsh $setup -Sync
  # $ErrorActionPreference='Stop' does NOT catch a failed native call here: measured,
  # $PSNativeCommandUseErrorActionPreference is False on pwsh 7.6.4, so a provisioner that refused
  # would fall straight through and the resolver below would blame a missing ProjectVersion.txt --
  # carrying the run toward batchmode against a venue that does not exist. Assert the outcome.
  if (-not (Test-Path -LiteralPath $editor)) {
    Write-Error "provisioning did not produce '$editor' — re-run $setup -Sync and read its refusal."
    exit 1
  }
}

# Resolved AFTER the provisioning above, which is what guarantees TestEditor has the
# ProjectVersion.txt the resolver reads. The ladder (Unity Hub registry, then Hub's default install
# dir) lives in the Atelier workspace because this gate and Atelier's EditMode runner are its two
# consumers, and both had independently hardcoded the same "…/2022.3.22f1/Editor/Unity.exe". A
# checkout that cannot reach it cannot reach TestEditor or the provisioner either, so this refuses
# in the same vocabulary as the block above rather than guessing a path.
if (-not $Unity) {
  $resolver = Join-Path $AtelierRoot 'tools/unity-editor.ps1'
  if (-not (Test-Path -LiteralPath $resolver)) {
    Write-Error "AtelierRoot '$AtelierRoot' has no tools/unity-editor.ps1 — pass -AtelierRoot <path to the Atelier workspace root>, or -Unity <path to Unity.exe>."
    exit 1
  }
  . $resolver
  try { $Unity = Resolve-UnityEditor $editor }
  catch { Write-Error "$($_.Exception.Message) — or pass -Unity <path to Unity.exe>."; exit 1 }
} elseif (-not (Test-Path -LiteralPath $Unity)) {
  # The sibling consumer (Atelier's run-editmode-tests.ps1) validates its override; taking one on
  # trust here would surface a typo as a raw Start-Process exception below, AFTER Remove-Item has
  # already destroyed the previous run's log.
  Write-Error "-Unity '$Unity' does not exist — pass a path to Unity.exe, or omit -Unity to resolve it from TestEditor's pinned version."
  exit 1
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
