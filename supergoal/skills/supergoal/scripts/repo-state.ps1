<#
repo-state.ps1 — PowerShell port of repo-state.sh.

Evaluate the COMPLETE working-tree state relative to a baseline commit. This is the
Windows-native equivalent of scripts/repo-state.sh: identical subcommands, arguments,
stdout strings, and exit codes, so PROTOCOL.md / SKILL.md can invoke whichever matches
the host. See references/repo-state-comparison.md for the one canonical strategy.

This script never mutates the repository or the index. All output is for the audit
transcript. Paths containing spaces are handled (callers must quote the path argument).

Usage:
  repo-state.ps1 deliverable   <baseline> <path>
      -> "present — <evidence>" (exit 0) | "missing" (exit 1)
  repo-state.ps1 changed-files <baseline>
      -> newline-delimited paths changed since baseline (tracked + untracked + deleted)
  repo-state.ps1 added-lines   <baseline>
      -> every added/new line since baseline: tracked-diff '+' lines plus the full body
         of each untracked file. Feed to Select-String for cleanliness counts.
#>

[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Sub = '',
  [Parameter(Position = 1)][string]$Baseline = '',
  [Parameter(Position = 2)][string]$Path = ''
)

$ErrorActionPreference = 'Continue'

# Run git, return stdout lines as an array; stderr suppressed. $LASTEXITCODE is set by git.
function Invoke-Git {
  param([string[]]$GitArgs)
  $out = & git @GitArgs 2>$null
  if ($null -eq $out) { return @() }
  return @($out)
}

function Test-InGitRepo {
  & git rev-parse --is-inside-work-tree *> $null
  return ($LASTEXITCODE -eq 0)
}

# Test-BaselineOk <ref> — true only when <ref> resolves to a real commit in this repo.
function Test-BaselineOk {
  param([string]$Ref)
  if ([string]::IsNullOrEmpty($Ref)) { return $false }
  if ($Ref -eq 'no-git') { return $false }
  & git rev-parse --verify --quiet "$Ref^{commit}" *> $null
  return ($LASTEXITCODE -eq 0)
}

# Each Cmd-* function writes data lines to stdout via Write-Output and records the
# intended process exit code in $script:Rc. The numeric code is never written to stdout.
$script:Rc = 0

function Cmd-Deliverable {
  param([string]$Baseline, [string]$Path)

  if ((Test-InGitRepo) -and (Test-BaselineOk $Baseline)) {
    # 1) tracked change vs baseline: committed, staged, unstaged, or deleted.
    $stat = Invoke-Git @('diff', '--stat', $Baseline, '--', $Path)
    if ($stat.Count -gt 0) {
      $last = ($stat[-1]).TrimStart()
      Write-Output "present — changed vs baseline ($last)"
      $script:Rc = 0; return
    }
    # 2) brand-new untracked deliverable (diff-invisible).
    $untracked = Invoke-Git @('ls-files', '--others', '--exclude-standard', '--', $Path)
    if ($untracked.Count -gt 0) {
      Write-Output "present — untracked new file ($($untracked[0]))"
      $script:Rc = 0; return
    }
    # 3) backward-compat net: the path exists / is tracked but is unchanged this run.
    $tracked = Invoke-Git @('ls-files', '--', $Path)
    if ((Test-Path -LiteralPath $Path) -or ($tracked.Count -gt 0)) {
      Write-Output "present — exists, unchanged since baseline"
      $script:Rc = 0; return
    }
    Write-Output "missing"
    $script:Rc = 1; return
  }

  # Fallback: baseline missing/invalid or not a git repo — existence only.
  if (Test-Path -LiteralPath $Path) {
    Write-Output "present — exists on disk (baseline unavailable)"
    $script:Rc = 0; return
  }
  if (Test-InGitRepo) {
    $tracked = Invoke-Git @('ls-files', '--', $Path)
    if ($tracked.Count -gt 0) {
      Write-Output "present — tracked (baseline unavailable)"
      $script:Rc = 0; return
    }
  }
  Write-Output "missing"
  $script:Rc = 1; return
}

function Cmd-ChangedFiles {
  param([string]$Baseline)
  if ((Test-InGitRepo) -and (Test-BaselineOk $Baseline)) {
    $modified = Invoke-Git @('diff', '--name-only', $Baseline)             # modified/staged/deleted
    $untracked = Invoke-Git @('ls-files', '--others', '--exclude-standard') # untracked
    $all = @($modified) + @($untracked) | Where-Object { $_ -ne '' } | Sort-Object -Unique
    foreach ($f in $all) { Write-Output $f }
  }
  $script:Rc = 0
}

function Cmd-AddedLines {
  param([string]$Baseline)
  if ((Test-InGitRepo) -and (Test-BaselineOk $Baseline)) {
    # Added lines from tracked changes (strip leading '+', skip the '+++' file header).
    $diff = Invoke-Git @('diff', $Baseline)
    foreach ($line in $diff) {
      if ($line.StartsWith('+') -and -not $line.StartsWith('+++')) {
        Write-Output $line.Substring(1)
      }
    }
    # Full body of every untracked file — each line counts as newly added.
    # Skip binaries: added-lines feeds text greps, so binary bodies are only noise.
    $untracked = Invoke-Git @('ls-files', '--others', '--exclude-standard')
    foreach ($f in $untracked) {
      if ([string]::IsNullOrEmpty($f)) { continue }
      if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
      $bytes = [System.IO.File]::ReadAllBytes($f)
      if ($bytes.Length -eq 0) { continue }
      if ([Array]::IndexOf($bytes, [byte]0) -ge 0) { continue }  # has NUL -> treat as binary, skip
      Get-Content -LiteralPath $f
    }
  }
  $script:Rc = 0
}

switch ($Sub) {
  'deliverable' {
    if ([string]::IsNullOrEmpty($Baseline) -or [string]::IsNullOrEmpty($Path)) {
      [Console]::Error.WriteLine('usage: repo-state.ps1 deliverable <baseline> <path>')
      exit 2
    }
    Cmd-Deliverable $Baseline $Path
    exit $script:Rc
  }
  'changed-files' {
    if ([string]::IsNullOrEmpty($Baseline)) {
      [Console]::Error.WriteLine('usage: repo-state.ps1 changed-files <baseline>')
      exit 2
    }
    Cmd-ChangedFiles $Baseline
    exit $script:Rc
  }
  'added-lines' {
    if ([string]::IsNullOrEmpty($Baseline)) {
      [Console]::Error.WriteLine('usage: repo-state.ps1 added-lines <baseline>')
      exit 2
    }
    Cmd-AddedLines $Baseline
    exit $script:Rc
  }
  default {
    [Console]::Error.WriteLine(@'
repo-state.ps1 — evaluate the complete working-tree state vs a baseline commit.

  repo-state.ps1 deliverable   <baseline> <path>   present|missing (+ evidence), exit 0|1
  repo-state.ps1 changed-files <baseline>          paths changed since baseline
  repo-state.ps1 added-lines   <baseline>          added/new lines since baseline

<baseline> is a commit sha (or "no-git" / any invalid ref to force the filesystem
fallback). Compares the working tree — not just HEAD — so uncommitted, staged, and
untracked work is included. See references/repo-state-comparison.md.
'@)
    exit 2
  }
}
