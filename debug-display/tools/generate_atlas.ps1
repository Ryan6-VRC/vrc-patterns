<#
  Regenerates debug-display's 64-slot MSDF glyph atlas.

  WHY REGENERATE. The Lereldarion ancestor's atlas is 256x64 at 23x29 cells = 11x2 = 22 slots, and it
  fills all 22 (IDs 0-21) with 31 reserved as the space sentinel -- nine free slots, nowhere near A-Z.
  Author-time labels need letters, so the charset goes to 6 bits / 64 slots. Regenerating also makes the
  Font constants ours rather than a silent verbatim copy.

  THE CHARSET IS NOT COPIED HERE. It is parsed out of DisplayGlyphs.cs in vrc-unity-tools, which is its
  canon -- the atlas is generated FROM the table, so there is no committed second copy to drift. If the
  const moves or is renamed this script FAILS rather than falling back to a stale literal.

  TOOLCHAIN. msdf-atlas-gen is not installed on the authoring machine and is not vendored here: fetch the
  release binary, run this, commit the PNG, delete the binary. The version below is what the committed
  atlas was actually built with -- update it only alongside a regenerated PNG, because a different
  version can emit different metrics for identical arguments.

      msdf-atlas-gen v1.4 (win64)
      https://github.com/Chlumsky/msdf-atlas-gen/releases/download/v1.4/msdf-atlas-gen-1.4-win64.zip

      Geist Mono Regular, from geist-font v1.7.2
      https://github.com/vercel/geist-font/releases/download/v1.7.2/geist-font-v1.7.2.zip
      SIL Open Font License 1.1 -- "Copyright 2024 The Geist Project Authors", per the notice shipped
      in that release (the repo's own LICENSE.txt reads "(c) 2023 Vercel, in collaboration with
      basement.studio"; the release's wording governs the copy we actually bundled).
      OFL requires the notice and licence to accompany a bundled copy, so assets/GeistMono-OFL.txt
      ships beside the atlas. No Reserved Font Name is declared, so there is no naming restriction.
      The font must stay MONOSPACE: the fixed-cell grid and every advance in the layout arithmetic
      assume one advance width for all glyphs.

  AFTER RUNNING, the emitted JSON is the source for the shader's Font constants. Read them off it rather
  than trusting these defaults -- and check the grid origin, because Font::sdf() bakes in top-flush,
  left-flush placement (see -yorigin below).

  EXPECTED WARNING: "Grid cell too constrained to fully fit all glyphs, some may be cut off!"
  This is structural to -uniformcell, not a misconfiguration, and the ancestor's atlas has it too. The
  tool fits the uniform glyph box to the cell minus a 1px margin (22x28 in a 23x29 cell), so the 2px SDF
  range then wants 24x30 and the outer ~1px of FALLOFF is clipped -- the glyph outlines themselves are
  intact, which is what the emitted image confirms. Enlarging the cell does not help: the tool re-fits
  the box to whatever cell it is given, so the shortfall follows. What is lost is a little antialiasing
  headroom at extreme on-screen magnification. Verified by eye on the emitted atlas and again at render
  time; if glyph edges ever look chewed rather than soft, this is the first thing to revisit.
#>
param(
  # Where vrc-unity-tools is checked out; DisplayGlyphs.cs under it holds the charset canon.
  [string]$ToolsRoot = "C:/Users/Ryan/Documents/Atelier/vrc-unity-tools",
  [Parameter(Mandatory=$true)][string]$MsdfAtlasGen,   # path to msdf-atlas-gen.exe
  [Parameter(Mandatory=$true)][string]$Font,           # path to GeistMono-Regular.ttf
  [string]$OutDir = (Join-Path $PSScriptRoot "../assets"),
  # Grid geometry. Cell size and pxrange are carried over from the ancestor's atlas unchanged so its
  # *_em metrics stay comparable; only the slot count and column count change (11x2 -> 8x8).
  [int]$Cols = 8,
  [int]$CellW = 23,
  [int]$CellH = 29,
  [int]$AtlasW = 256,
  [int]$AtlasH = 256,
  [double]$PxRange = 2,
  # 34.22 px/em is the ancestor's implied size: its em_to_px works out to 22/0.64292 = 28/0.81826 =
  # 34.22 in both axes (equal "due to monospace", as its own comment says), fitting the glyph box into
  # the cell's usable 22x28 with a 1px margin.
  [double]$Size = 34.22,
  # Font::sdf() computes atlas_offset_px.y as atlas_size_px.y - cell_size_px.y * (row + 1), i.e. glyph
  # ID 0 sits in the TOP-left cell. Verified against the emitted image, not assumed.
  [ValidateSet("top","bottom")][string]$YOrigin = "top"
)
$ErrorActionPreference = "Stop"

# ── Charset, parsed from its canon ─────────────────────────────────────────────────────────────────
$glyphsCs = Join-Path $ToolsRoot "packages/com.ryan6vrc.avatar-tools/Editor/DisplayGlyphs.cs"
if (-not (Test-Path $glyphsCs)) { throw "charset canon not found at $glyphsCs (pass -ToolsRoot)" }

$src = Get-Content -Raw -Encoding UTF8 $glyphsCs
# Take the declaration through its terminating semicolon, then keep only the quoted segments. Comments
# on the continuation lines are stripped by the quote extraction itself.
$decl = [regex]::Match($src, 'public\s+const\s+string\s+Charset\s*=(?<body>.*?);', 'Singleline')
if (-not $decl.Success) { throw "could not find 'public const string Charset' in $glyphsCs" }
$charset = -join ([regex]::Matches($decl.Groups['body'].Value, '"(?<seg>[^"]*)"') |
                  ForEach-Object { $_.Groups['seg'].Value })

# 63, not 64: ID 63 is the space sentinel, which Font::sdf() early-returns on and which therefore has no
# atlas cell. The 8x8 grid's last cell is deliberately empty.
if ($charset.Length -ne 63) {
  throw "charset is $($charset.Length) glyphs, expected 63 (64 IDs minus the cell-less space sentinel)"
}
# The grid layout is codepoint-ordered by the generator, not charset-file-ordered, so the table's order
# IS the cell order only while it is codepoint-ascending. Asserted here as well as in the NUnit suite,
# because this script can be run without the suite and a violation is invisible in the output PNG.
for ($i = 1; $i -lt $charset.Length; $i++) {
  if ([int]$charset[$i - 1] -ge [int]$charset[$i]) {
    throw ("charset is not codepoint-ascending at index {0} ('{1}' >= '{2}') — msdf-atlas-gen orders the " +
           "uniform grid by codepoint, so every glyph would land in the wrong cell" -f `
           $i, $charset[$i - 1], $charset[$i])
  }
}
Write-Host "[atlas] charset ($($charset.Length) glyphs, codepoint-ascending) parsed from DisplayGlyphs.cs"

# msdf-atlas-gen's charset file takes hex codepoints; use them rather than a raw string so the
# non-ASCII glyphs (degree, infinity) cannot be mangled by file encoding on the way through.
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$charsetFile = Join-Path ([System.IO.Path]::GetTempPath()) "debug-display-charset.txt"
$codes = ($charset.ToCharArray() | ForEach-Object { "0x{0:x4}" -f [int]$_ }) -join ", "
Set-Content -Path $charsetFile -Value $codes -Encoding ASCII

# ── Generate ───────────────────────────────────────────────────────────────────────────────────────
$png  = Join-Path $OutDir "GlyphAtlas.png"
$json = Join-Path ([System.IO.Path]::GetTempPath()) "debug-display-atlas.json"

# -uniformorigin on is load-bearing: it fixes the glyph origin at the same position in every cell, which
# is what lets the shader carry ONE glyph_bottom_left_em for all 64 slots instead of a per-glyph table.
$argv = @(
  "-font", $Font,
  "-charset", $charsetFile,
  "-type", "msdf",
  "-format", "png",
  "-imageout", $png,
  "-json", $json,
  "-dimensions", $AtlasW, $AtlasH,
  "-uniformgrid",
  "-uniformcols", $Cols,
  "-uniformcell", $CellW, $CellH,
  "-uniformcellconstraint", "none",
  "-uniformorigin", "on",
  "-yorigin", $YOrigin,
  "-size", $Size,
  "-pxrange", $PxRange
)
Write-Host "[atlas] $MsdfAtlasGen $($argv -join ' ')"
& $MsdfAtlasGen @argv
if ($LASTEXITCODE -ne 0) { throw "msdf-atlas-gen failed with exit code $LASTEXITCODE" }

# ── Report the metrics the shader needs ────────────────────────────────────────────────────────────
# Emitted, never inferred: these are the numbers that go into the Font struct, and the whole reason the
# JSON is generated. A mismatch between them and the shader's constants garbles every glyph uniformly.
$meta = Get-Content -Raw $json | ConvertFrom-Json
$first = $meta.glyphs | Where-Object { $_.planeBounds } | Select-Object -First 1
Write-Host ""
Write-Host "[atlas] wrote $png"
Write-Host "[atlas] --- copy these into debug_display_common.hlsl's Font struct ---"
Write-Host ("  atlas_size_px            = float2({0}, {1})" -f $meta.atlas.width, $meta.atlas.height)
Write-Host ("  cell_size_px             = float2({0}, {1})" -f $CellW, $CellH)
Write-Host ("  atlas_distance_range_px  = {0}" -f $meta.atlas.distanceRange)
Write-Host ("  grid_columns             = {0}" -f $Cols)
if ($first) {
  Write-Host ("  glyph_bottom_left_em     = float2({0}, {1})" -f $first.planeBounds.left, $first.planeBounds.bottom)
  Write-Host ("  glyph_top_right_em       = float2({0}, {1})" -f $first.planeBounds.right, $first.planeBounds.top)
  Write-Host ("  advance_em               = {0}" -f $first.advance)
}
Write-Host ("  ascender_em              = {0}" -f $meta.metrics.ascender)
Write-Host ("  line_height_em           = {0}" -f $meta.metrics.lineHeight)
Write-Host "[atlas] --- also VERIFY glyph 0 sits in the TOP-left cell (Font::sdf assumes it) ---"
Remove-Item $charsetFile -ErrorAction SilentlyContinue
