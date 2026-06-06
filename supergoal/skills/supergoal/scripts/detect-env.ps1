<#
detect-env.ps1 — environment recon for greenfield Supergoal runs (PowerShell port of
detect-env.sh). Writes markdown to stdout.
#>

$ErrorActionPreference = 'SilentlyContinue'

function Get-ToolVersion {
  param([string]$Tool)
  $cmd = Get-Command $Tool -ErrorAction SilentlyContinue
  if (-not $cmd) { return $null }
  $v = (& $Tool --version 2>$null | Select-Object -First 1)
  if ([string]::IsNullOrWhiteSpace($v)) { $v = '(version unknown)' }
  return $v
}

"# Environment context (greenfield)"
""
"_Generated $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')_"
""

"## CWD"
"- ``$(Get-Location)``"
$entries = @(Get-ChildItem -Force -ErrorAction SilentlyContinue)
"- Contents: $($entries.Count) entries"
$entries | Select-Object -First 10 | ForEach-Object { "  - $($_.Name)" }
""

"## System"
"- OS: $([System.Environment]::OSVersion.VersionString) ($([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture))"
"- Shell: ``PowerShell $($PSVersionTable.PSVersion)``"
"- User: $env:USERNAME"
""

"## Toolchains available"
foreach ($tool in @('node','npm','pnpm','yarn','bun','deno','python','python3','uv','poetry','pip','go','cargo','rustc','swift','xcrun','docker','make','git','gh')) {
  $v = Get-ToolVersion $tool
  if ($v) { "- ``$tool`` — $v" }
}
""

"## Git"
$gitUser = (git config --global user.name 2>$null); if ([string]::IsNullOrWhiteSpace($gitUser)) { $gitUser = '(unset)' }
$gitEmail = (git config --global user.email 2>$null); if ([string]::IsNullOrWhiteSpace($gitEmail)) { $gitEmail = '(unset)' }
"- Configured user: $gitUser <$gitEmail>"
""

if (Get-Command gh -ErrorAction SilentlyContinue) {
  "## GitHub CLI"
  & gh auth status *> $null
  if ($LASTEXITCODE -eq 0) { "- Authenticated" } else { "- Not authenticated" }
}
""

"_End environment context._"
