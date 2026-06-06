<#
summarize-repo.ps1 — compressed repo map for planning context (PowerShell port of
summarize-repo.sh). Writes markdown to stdout.
#>

$ErrorActionPreference = 'SilentlyContinue'
$isGit = Test-Path '.git'

"# Repo map"
""
"_Generated $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')_"
""

# --- High level shape ---
"## Top-level layout"
Get-ChildItem -Force | Where-Object { $_.Name -notlike '.*' } | Select-Object -First 40 | ForEach-Object { "- $($_.Name)" }
""

# --- Source dirs ---
"## Source directories (depth 2)"
foreach ($root in @('src','app','lib','pages','components','server','api','packages','apps')) {
  if (Test-Path -PathType Container $root) {
    "### ``$root/``"
    Get-ChildItem -Directory -Recurse -Depth 1 $root -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {
      "- $($_.FullName | Resolve-Path -Relative)"
    }
    ""
  }
}

# --- File counts by extension ---
"## File counts (top extensions)"
if ($isGit) {
  $files = @(git ls-files 2>$null)
} else {
  $files = @(Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\\/](node_modules|\.git|dist|build)[\\/]' } | ForEach-Object { $_.Name })
}
$files | ForEach-Object { $ext = [System.IO.Path]::GetExtension($_).TrimStart('.'); if ($ext -and $ext.Length -le 6) { $ext } } |
  Group-Object | Sort-Object Count -Descending | Select-Object -First 10 | ForEach-Object { "- ``.$($_.Name)``: $($_.Count) files" }
""

# --- Largest source files ---
"## Largest source files (top 15 by line count)"
if ($isGit) {
  $skip = '\.(json|lock|yaml|yml|md|svg|png|jpg|jpeg|gif|webp|woff2?|ttf|otf|map|min\.js|min\.css)$'
  @(git ls-files 2>$null) | Where-Object { $_ -notmatch $skip } | ForEach-Object {
    if (Test-Path -PathType Leaf -LiteralPath $_) {
      $lc = (Get-Content -LiteralPath $_ -ErrorAction SilentlyContinue | Measure-Object -Line).Lines
      [PSCustomObject]@{ Path = $_; Lines = $lc }
    }
  } | Sort-Object Lines -Descending | Select-Object -First 15 | ForEach-Object { "- ``$($_.Path)`` ($($_.Lines) lines)" }
}
""

# --- Tests presence ---
"## Test surface"
foreach ($pat in @('test','tests','__tests__','spec','specs')) {
  $count = @(Get-ChildItem -Recurse -Directory -Filter $pat -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\\/](node_modules|\.git)[\\/]' }).Count
  if ($count -gt 0) { "- Directories named ``$pat``: $count" }
}
$testFiles = @(Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
  $_.FullName -notmatch '[\\/](node_modules|\.git)[\\/]' -and
  ($_.Name -like '*.test.*' -or $_.Name -like '*.spec.*' -or $_.Name -like 'test_*.py' -or $_.Name -like '*_test.go')
}).Count
"- Test files (by name pattern): $testFiles"
""

# --- Config & infra files ---
"## Notable config / infra"
$patterns = @('tsconfig.json','next.config.*','vite.config.*','webpack.config.*','tailwind.config.*','postcss.config.*','eslint.config.*','.eslintrc.*','prettier.config.*','.prettierrc*','jest.config.*','vitest.config.*','playwright.config.*','cypress.config.*','drizzle.config.*','prisma/schema.prisma','schema.prisma','turbo.json','nx.json','lerna.json','pnpm-workspace.yaml','docker-compose.*','Dockerfile*','.github/workflows','.gitlab-ci.yml','fly.toml','vercel.json','netlify.toml','wrangler.toml')
$found = foreach ($p in $patterns) { Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object { $_.Name } }
$found | Sort-Object -Unique | ForEach-Object { "- ``$_``" }
""

# --- Recent activity ---
"## Recent activity (last 10 commits)"
if ($isGit) {
  git log --no-merges --pretty=format:"- ``%h`` %ad %s" --date=short -10 2>$null
  ""
  ""
  "## Files churned in last 20 commits (top 10)"
  @(git log --no-merges --name-only --pretty=format: -20 2>$null) | Where-Object { $_ -ne '' } |
    Group-Object | Sort-Object Count -Descending | Select-Object -First 10 | ForEach-Object { "- ``$($_.Name)`` ($($_.Count)×)" }
}
""

"_End repo map._"
