#requires -Version 7
<#
  vrc-patterns README lint: the one README rule that is enforced rather than stated.

  CONVENTIONS.md §The README — prose never speaks for the checks. A README sentence attributing
  coverage to `--check` or the gate ("`--check` asserts/holds/refuses ...") is the failure mode: the
  claim outlives the assert it describes, and the next reader trusts a check that no longer exists
  (measured — six-plus such sentences in one entry survived the commit that deleted their asserts).
  A README may name the command; it may not say what the command covers.

  Text-only and Unity-free, so it runs standalone while rewriting an entry as well as first inside
  gate.ps1. Exit 0 iff every entry README passes.
#>
[CmdletBinding()]
param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)
$ErrorActionPreference = 'Stop'

$verbs = 'assert|hold|refus|pin|guard|catch|verif|enforc'
$patterns = @(
  "(?i)--check[^\r\n]{0,40}?($verbs)",
  "(?i)($verbs)\w*[^\r\n]{0,40}?--check",
  "(?i)the gate[^\r\n]{0,40}?($verbs)"
)
# No reverse form for "the gate": an entry says "the gate param", and a verb 40 chars ahead of that
# is ordinary avatar prose ("a cube pinned at rest ... is the gate param not landing"), not a claim
# about this repo's gate. `--check` has no such second meaning, so it keeps both directions.

# Every README except the repo root's, which is the catalog and speaks for the library, not an entry.
$rootReadme = (Join-Path $Root 'README.md')
$files = Get-ChildItem -LiteralPath $Root -Recurse -File -Filter 'README.md' |
  Where-Object { $_.FullName -ne $rootReadme -and -not $_.FullName.Contains([IO.Path]::DirectorySeparatorChar + '.git' + [IO.Path]::DirectorySeparatorChar) }

$failed = $false
foreach ($f in $files) {
  $rel = [IO.Path]::GetRelativePath($Root, $f.FullName).Replace('\', '/')
  $n = 0
  Get-Content -LiteralPath $f.FullName | ForEach-Object {
    $line = $_
    $i = $script:lineNo = $n + 1
    foreach ($p in $patterns) {
      $m = [regex]::Match($line, $p)
      if ($m.Success) {
        $failed = $true
        Write-Host "[readme-lint] $rel`:$i attributes coverage to a check: ...$($m.Value)..."
        break
      }
    }
    $n++
  }
}


if ($failed) {
  Write-Host "[readme-lint] FAIL — CONVENTIONS.md §The README: the check prints its own scope; a README may say only ``run generate.py --check``. Figure pins are asserts inside --check, never claims here."
  exit 1
}
Write-Host "[readme-lint] pass — $($files.Count) entry READMEs."
exit 0
