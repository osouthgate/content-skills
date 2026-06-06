<#
validate-phase.ps1 — verify a phase spec has the required structure (PowerShell port of
validate-phase.sh).

Usage: validate-phase.ps1 <path-to-phase-spec.md>

Exits 0 if the file has the required markers and sections.
Exits 1 with specific errors otherwise.
#>

[CmdletBinding()]
param([Parameter(Position = 0)][string]$File = '')

$ErrorActionPreference = 'Continue'

if ([string]::IsNullOrEmpty($File)) {
  [Console]::Error.WriteLine('usage: validate-phase.ps1 <path-to-phase-spec.md>')
  exit 2
}
if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
  [Console]::Error.WriteLine("validate-phase.ps1: file not found: $File")
  exit 2
}

$content = Get-Content -Raw -LiteralPath $File
$lines = Get-Content -LiteralPath $File
$errors = 0

function Check-Marker {
  param([string]$Marker, [string]$Label)
  if ($content -notmatch [regex]::Escape($Marker)) {
    [Console]::Error.WriteLine("[X] $File`: missing $Label ($Marker)")
    $script:errors++
  }
}

function Check-Section {
  param([string]$Heading)
  $esc = [regex]::Escape($Heading)
  if ($content -notmatch "(?im)^## $esc" -and $content -notmatch "(?im)^\*\*$esc") {
    [Console]::Error.WriteLine("[X] $File`: missing section: $Heading")
    $script:errors++
  }
}

# Required markers
Check-Marker 'SUPERGOAL_PHASE_START' 'phase-start marker'

# Required sections
Check-Section 'Work'
Check-Section 'Acceptance criteria'
Check-Section 'Mandatory commands'
Check-Section 'Evidence required'

# Sanity check: at least a few bullet lines
$crits = @($lines | Where-Object { $_ -match '^\s*-' }).Count
if ($crits -lt 3) {
  [Console]::Error.WriteLine("[!] $File`: only $crits bullet lines — acceptance criteria look thin")
}

if ($errors -gt 0) {
  [Console]::Error.WriteLine("[FAIL] $File`: $errors structural error(s)")
  exit 1
}

$lineCount = $lines.Count
Write-Output "[OK] $File`: structure ok ($lineCount lines, $crits bullets)"
exit 0
