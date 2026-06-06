<#
detect-stack.ps1 — identify language, package manager, framework, build/test/lint
commands (PowerShell port of detect-stack.sh). Writes a compact markdown summary to
stdout for the planning context. Uses PowerShell's native JSON parsing (no jq dependency).
#>

$ErrorActionPreference = 'SilentlyContinue'

function Read-Json {
  param([string]$File)
  if (-not (Test-Path -LiteralPath $File)) { return $null }
  try { return (Get-Content -Raw -LiteralPath $File | ConvertFrom-Json) } catch { return $null }
}

"# Stack context"
""
"_Generated $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')_"
""

# --- Language / framework signals ---
"## Language signals"

$pkg = Read-Json 'package.json'
if ($pkg) {
  "- **Node/JS/TS** — package.json present"
  $name = if ($pkg.name) { $pkg.name } else { '(unnamed)' }
  $version = if ($pkg.version) { $pkg.version } else { '?' }
  "  - Name: ``$name``, version: ``$version``"
  $depNames = @()
  if ($pkg.dependencies)    { $depNames += $pkg.dependencies.PSObject.Properties.Name }
  if ($pkg.devDependencies) { $depNames += $pkg.devDependencies.PSObject.Properties.Name }
  if ($depNames.Count -gt 0) {
    "  - Top dependencies: $(( $depNames | Select-Object -First 15 ) -join ', ')"
    foreach ($fw in @('next','react','vue','svelte','solid','astro','nuxt','remix','express','fastify','nestjs','hono')) {
      if ($depNames -contains $fw) { "  - Framework: **$fw**" }
    }
  }
}

if ((Test-Path 'pyproject.toml') -or (Test-Path 'requirements.txt') -or (Test-Path 'setup.py')) {
  "- **Python** — pyproject.toml / requirements.txt / setup.py present"
  if (Test-Path 'pyproject.toml') {
    $py = Get-Content -Raw 'pyproject.toml'
    foreach ($bs in @('poetry','uv','hatch')) {
      if ($py -match "\[tool\.$bs\]") { "  - Build system: [tool.$bs]" }
    }
  }
}

if (Test-Path 'Cargo.toml')  { "- **Rust** — Cargo.toml present" }

if (Test-Path 'go.mod') {
  $modLine = (Get-Content 'go.mod' | Select-Object -First 1)
  $modName = ($modLine -split '\s+')[1]
  "- **Go** — go.mod present ($modName)"
}

if (((Test-Path 'ios') -and (Test-Path 'ios/Podfile')) -or (Get-ChildItem '*.xcodeproj' -ErrorAction SilentlyContinue) -or (Get-ChildItem '*.xcworkspace' -ErrorAction SilentlyContinue)) {
  "- **iOS/macOS (Swift)** — Xcode project present"
}

if ((Test-Path 'build.gradle') -or (Test-Path 'build.gradle.kts') -or (Test-Path 'settings.gradle')) {
  "- **JVM / Android** — Gradle project"
}
""

# --- Package manager ---
"## Package manager"
if     (Test-Path 'pnpm-lock.yaml')    { "- **pnpm** (pnpm-lock.yaml)" }
elseif (Test-Path 'yarn.lock')         { "- **yarn** (yarn.lock)" }
elseif ((Test-Path 'bun.lockb') -or (Test-Path 'bun.lock')) { "- **bun** (bun.lock)" }
elseif (Test-Path 'package-lock.json') { "- **npm** (package-lock.json)" }
elseif (Test-Path 'uv.lock')           { "- **uv** (uv.lock)" }
elseif (Test-Path 'poetry.lock')       { "- **poetry** (poetry.lock)" }
elseif (Test-Path 'Pipfile.lock')      { "- **pipenv** (Pipfile.lock)" }
elseif (Test-Path 'Cargo.lock')        { "- **cargo** (Cargo.lock)" }
elseif (Test-Path 'go.sum')            { "- **go modules** (go.sum)" }
else                                   { "- _none detected_" }
""

# --- Scripts / commands ---
"## Likely commands"
if ($pkg -and $pkg.scripts) {
  "From package.json scripts:"
  $pkg.scripts.PSObject.Properties | Select-Object -First 25 | ForEach-Object { "- ``$($_.Name)`` → ``$($_.Value)``" }
}
if (Test-Path 'Makefile') {
  ""
  "Makefile targets:"
  Get-Content 'Makefile' | Where-Object { $_ -match '^[a-zA-Z][a-zA-Z0-9_-]*:' } | ForEach-Object { ($_ -split ':')[0] } | Sort-Object -Unique | Select-Object -First 20 | ForEach-Object { "- ``$_``" }
}
""

# --- Git ---
"## Git"
if (Test-Path '.git') {
  $branch = (git rev-parse --abbrev-ref HEAD 2>$null); if (-not $branch) { $branch = '?' }
  $remote = (git config --get remote.origin.url 2>$null); if (-not $remote) { $remote = '(no remote)' }
  $dirty = @(git status --porcelain 2>$null).Count
  "- Branch: ``$branch``"
  "- Remote: $remote"
  "- Working tree: $dirty files changed"
} else {
  "- Not a git repo"
}
""

# --- Test / lint heuristics ---
"## Test / lint heuristics"
if ($pkg -and $pkg.scripts) {
  $scriptNames = $pkg.scripts.PSObject.Properties.Name
  foreach ($key in @('build','typecheck','type-check','test','lint','check','ci','dev','start')) {
    if ($scriptNames -contains $key) { "- Has script: ``$key``" }
  }
}
if ((Get-ChildItem '.eslintrc.*' -ErrorAction SilentlyContinue) -or (Get-ChildItem 'eslint.config.*' -ErrorAction SilentlyContinue)) { "- ESLint config present" }
if (Get-ChildItem '.prettierrc*' -ErrorAction SilentlyContinue) { "- Prettier config present" }
if (Test-Path 'tsconfig.json') { "- TypeScript present (tsconfig.json)" }
if ((Test-Path 'pytest.ini') -or (Test-Path 'conftest.py') -or ((Test-Path 'pyproject.toml') -and ((Get-Content -Raw 'pyproject.toml') -match 'pytest'))) { "- pytest detected" }
if (Test-Path '.swiftlint.yml') { "- SwiftLint config present" }
""

"_End stack context._"
