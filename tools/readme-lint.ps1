#requires -Version 7
<#
  vrc-patterns README lint — the wave-scoped budget + attribution check, CONVENTIONS.md §The README.

  Two rules, per entry README named in tools/readme-budgets.csv:
    1. Budget: (Get-Content -Raw).Length must not exceed the entry's cap.
    2. Prose never speaks for the checks: no line may attribute coverage to `--check` or "the gate"
       (a coverage verb within ~40 chars of either), per the contract's enforced rule.

  A README whose SHA-256 still matches its baseline (its slice hasn't run) is skipped — so this is
  green on main and on every not-yet-rewritten entry, and only bites a README a rewrite has changed.

  Wave-scoped scaffolding: the wave's final slice PR deletes this script, its gate.ps1 call, and the
  csv together. gate.ps1 calls it before booting Unity; it also runs standalone.
#>
[CmdletBinding()]
param([string]$Root = '')
$ErrorActionPreference = 'Stop'
if (-not $Root) { $Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
$csv = Join-Path $Root 'tools/readme-budgets.csv'
if (-not (Test-Path -LiteralPath $csv)) {
  Write-Host "[readme-lint] no readme-budgets.csv — wave complete or not started; nothing to lint."
  exit 0
}

# `--check` or "the gate" within ~40 chars of a coverage verb, either order, case-insensitive.
# Stems, not whole words: pins/pinned→pin, holds→hold, verified/verification→verif, enforced→enforc.
$verb = 'assert|hold|refus|pin|guard|catch|verif|enforc'
$subj = '--check|the gate'
$attribution = "(?:(?:$subj).{0,40}(?:$verb))|(?:(?:$verb).{0,40}(?:$subj))"

$fail = 0
foreach ($row in Import-Csv -LiteralPath $csv) {
  $path = Join-Path $Root $row.path
  if (-not (Test-Path -LiteralPath $path)) {
    Write-Host "[readme-lint] FAIL $($row.path): file missing (a rewrite empties contents, it never deletes the file)."
    $fail++; continue
  }
  $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if ($hash -eq $row.baseline_sha256) { continue }  # unchanged since PR 1 base — this slice hasn't run

  $raw = Get-Content -Raw -LiteralPath $path
  $len = $raw.Length
  $cap = [int]$row.cap
  if ($len -gt $cap) {
    Write-Host "[readme-lint] FAIL $($row.path): $len chars over cap $cap (CONVENTIONS.md §The README — cut, do not negotiate the cap up)."
    $fail++
  }
  $n = 0
  foreach ($line in ($raw -split "`r?`n")) {
    $n++
    if ([regex]::IsMatch($line, $attribution, 'IgnoreCase')) {
      Write-Host "[readme-lint] FAIL $($row.path):$n prose speaks for the checks — route to source, say only ""run generate.py --check"" (CONVENTIONS.md §The README)."
      $fail++
    }
  }
}

if ($fail -gt 0) { Write-Host "[readme-lint] $fail failure(s)."; exit 1 }
Write-Host "[readme-lint] ok."
exit 0
