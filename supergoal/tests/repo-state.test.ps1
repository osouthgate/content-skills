<#
repo-state.test.ps1 — fixture tests for scripts/repo-state.ps1 (PowerShell port of
repo-state.test.sh). Exercises the canonical "complete working-tree state vs baseline"
comparison against throwaway git repositories, one per scenario.

Run from anywhere:
  pwsh -File tests/repo-state.test.ps1
Exits 0 if every assertion passes, 1 otherwise.
#>

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$RS = Join-Path $RepoRoot 'skills/supergoal/scripts/repo-state.ps1'

if (-not (Test-Path $RS)) { Write-Error "FATAL: repo-state.ps1 not found at $RS"; exit 1 }

$script:pass = 0
$script:fail = 0
function Ok($m)  { $script:pass++; Write-Host "  [PASS] $m" -ForegroundColor Green }
function No($m, $d) { $script:fail++; Write-Host "  [FAIL] $m`n        $d" -ForegroundColor Red }

# Run the script under test; capture stdout (as single string) and exit code.
# NB: do not name the param $Args — it collides with the automatic $args variable.
function Run {
  param([string[]]$CmdArgs)
  $script:OUT = (& pwsh -NoProfile -File $RS @CmdArgs 2>&1 | Out-String).Trim()
  $script:RC = $LASTEXITCODE
}
function AssertEq($m, $exp, $act)       { if ($exp -eq $act) { Ok $m } else { No $m "expected [$exp] got [$act]" } }
function AssertRc($m, $exp)             { if ("$exp" -eq "$script:RC") { Ok $m } else { No $m "expected exit $exp got $($script:RC) (out: $($script:OUT))" } }
function AssertContains($m, $needle, $hay) { if ($hay -like "*$needle*") { Ok $m } else { No $m "[$hay] missing substring [$needle]" } }
function AssertMissing($m, $needle, $hay)  { if ($hay -like "*$needle*") { No $m "[$hay] unexpectedly contains [$needle]" } else { Ok $m } }

function New-Repo {
  $d = Join-Path ([System.IO.Path]::GetTempPath()) ("sg-" + [System.Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  Push-Location $d
  git init -q
  git config user.email t@example.com
  git config user.name tester
  git config commit.gpgsign false
  git config core.autocrlf false
  git config core.safecrlf false
  New-Item -ItemType Directory -Force -Path 'src' | Out-Null
  New-Item -ItemType Directory -Force -Path 'dir with space' | Out-Null
  "baseline"               | Set-Content -NoNewline -Path 'keep.txt'
  "export const existing = 1" | Set-Content -NoNewline -Path 'src/existing.ts'
  "old"                    | Set-Content -NoNewline -Path 'dir with space/old file.ts'
  git add -A *> $null
  git commit -qm baseline *> $null
  Pop-Location
  return $d
}
function Base-Of($d) { Push-Location $d; $b = (git rev-parse HEAD); Pop-Location; return $b }
function Cleanup($d) { if ($d -and (Test-Path $d)) { Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue } }

Write-Host "repo-state.test.ps1 — fixtures for $RS`n"

# [1] Clean repository
Write-Host "[1] Clean repository (no changes since baseline)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
Run @('changed-files', $b);                  AssertEq "changed-files is empty" "" $script:OUT
Run @('added-lines', $b);                    AssertEq "added-lines is empty" "" $script:OUT
Run @('deliverable', $b, 'src/existing.ts'); AssertRc "existing unchanged file -> exit 0" 0
AssertContains "existing file reported present" "present" $script:OUT
Run @('deliverable', $b, 'src/never.ts');    AssertRc "absent deliverable -> exit 1" 1
AssertEq "absent deliverable prints 'missing'" "missing" $script:OUT
Pop-Location; Cleanup $d

# [2] Modified tracked file, NOT committed
Write-Host "[2] Modified tracked file, NOT committed (the core bug)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
Add-Content -Path 'src/existing.ts' -Value 'console.log("dbg")'
Run @('deliverable', $b, 'src/existing.ts'); AssertRc "modified-uncommitted -> present (exit 0)" 0
AssertContains "evidence proves a real diff" "changed vs baseline" $script:OUT
Run @('added-lines', $b);                    AssertContains "added-lines surfaces the debug print" "console.log" $script:OUT
Run @('changed-files', $b);                  AssertContains "changed-files lists the modified file" "src/existing.ts" $script:OUT
Pop-Location; Cleanup $d

# [3] Staged tracked file
Write-Host "[3] Staged tracked file (in index, not committed)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
"export const staged = 2" | Set-Content -Path 'src/staged.ts'
git add src/staged.ts *> $null
Run @('deliverable', $b, 'src/staged.ts');   AssertRc "staged new file -> present (exit 0)" 0
AssertContains "staged file present" "present" $script:OUT
AssertContains "staged evidence proves a real diff" "changed vs baseline" $script:OUT
Run @('changed-files', $b);                  AssertContains "changed-files lists the staged file" "src/staged.ts" $script:OUT
Pop-Location; Cleanup $d

# [4] New untracked deliverable
Write-Host "[4] New untracked deliverable (never git add-ed)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
"export const fresh = 3`nconsole.log(""u"")" | Set-Content -Path 'src/untracked.ts'
Run @('deliverable', $b, 'src/untracked.ts'); AssertRc "untracked deliverable -> present (exit 0)" 0
AssertContains "untracked deliverable flagged as untracked" "untracked" $script:OUT
Run @('added-lines', $b);                     AssertContains "added-lines includes untracked body" "console.log" $script:OUT
Run @('changed-files', $b);                   AssertContains "changed-files lists the untracked file" "src/untracked.ts" $script:OUT
Pop-Location; Cleanup $d

# [5] Deleted tracked file
Write-Host "[5] Deleted tracked file (deletion is the deliverable)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
Remove-Item -Force 'src/existing.ts'
Run @('deliverable', $b, 'src/existing.ts');  AssertRc "deleted-since-baseline -> present (exit 0)" 0
AssertContains "evidence shows it changed vs baseline" "changed vs baseline" $script:OUT
Run @('changed-files', $b);                   AssertContains "changed-files lists the deleted path" "src/existing.ts" $script:OUT
Pop-Location; Cleanup $d

# [6] Changes committed AFTER baseline
Write-Host "[6] Changes committed AFTER baseline"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
"export const shipped = 4" | Set-Content -Path 'src/committed.ts'
git add src/committed.ts *> $null; git commit -qm "after baseline" *> $null
Run @('deliverable', $b, 'src/committed.ts'); AssertRc "committed-after-baseline -> present (exit 0)" 0
AssertContains "evidence shows the diff" "changed vs baseline" $script:OUT
Pop-Location; Cleanup $d

# [7] Paths containing spaces
Write-Host "[7] Paths containing spaces"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
"new"  | Set-Content -Path 'dir with space/new file.ts'
Add-Content -Path 'dir with space/old file.ts' -Value 'edit'
Run @('deliverable', $b, 'dir with space/new file.ts'); AssertRc "spaced untracked path -> present" 0
AssertContains "spaced untracked flagged untracked" "untracked" $script:OUT
Run @('deliverable', $b, 'dir with space/old file.ts'); AssertRc "spaced modified path -> present" 0
AssertContains "spaced modified shows diff" "changed vs baseline" $script:OUT
Run @('changed-files', $b);                              AssertContains "changed-files keeps spaced path intact" "dir with space/new file.ts" $script:OUT
Pop-Location; Cleanup $d

# [8] Invalid / unavailable baseline
Write-Host "[8] Invalid / unavailable baseline (graceful filesystem fallback)"
$d = New-Repo; Push-Location $d
"x" | Set-Content -Path 'src/fallback.ts'
Run @('deliverable', 'no-git', 'src/fallback.ts'); AssertRc "no-git sentinel, file exists -> present" 0
AssertContains "fallback notes baseline unavailable" "baseline unavailable" $script:OUT
Run @('deliverable', 'no-git', 'src/ghost.ts');    AssertRc "no-git sentinel, file absent -> missing" 1
Run @('deliverable', '0000000000000000000000000000000000000000', 'src/existing.ts'); AssertRc "bogus sha, file exists -> present (no crash)" 0
AssertContains "bogus sha falls back" "baseline unavailable" $script:OUT
Pop-Location
$od = Join-Path ([System.IO.Path]::GetTempPath()) ("sgx-" + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $od | Out-Null; Push-Location $od
"hi" | Set-Content -Path 'here.txt'
Run @('deliverable', 'deadbeef', 'here.txt');      AssertRc "non-repo dir, file exists -> present" 0
Run @('deliverable', 'anything', 'gone.txt');      AssertRc "non-repo dir, file absent -> missing" 1
Pop-Location; Cleanup $d; Cleanup $od

# [10] .gitignore'd file (excluded from untracked detection)
Write-Host "[10] .gitignore'd file (excluded from untracked detection)"
$d = New-Repo; Push-Location $d
"ignored/" | Set-Content -Path '.gitignore'
git add .gitignore *> $null; git commit -qm gitignore *> $null
$b = (git rev-parse HEAD)
New-Item -ItemType Directory -Force -Path 'ignored' | Out-Null
"export const ig = 1`nconsole.log(""ignored debug"")" | Set-Content -Path 'ignored/artifact.ts'
Run @('deliverable', $b, 'ignored/artifact.ts'); AssertRc "ignored file that exists -> present (exit 0)" 0
AssertContains "ignored file uses exists-fallback, NOT untracked" "exists, unchanged" $script:OUT
AssertMissing "ignored file is not mislabelled untracked" "untracked" $script:OUT
Run @('changed-files', $b);                      AssertMissing "changed-files excludes the ignored file" "ignored/artifact.ts" $script:OUT
Run @('added-lines', $b);                        AssertMissing "added-lines excludes ignored debug output" "ignored debug" $script:OUT
Pop-Location; Cleanup $d

# [11] Renamed tracked file
Write-Host "[11] Renamed tracked file (delete old path + add new path)"
$d = New-Repo; $b = Base-Of $d; Push-Location $d
git mv src/existing.ts src/renamed.ts *> $null
Run @('deliverable', $b, 'src/renamed.ts');  AssertRc "renamed-to path -> present (exit 0)" 0
AssertContains "renamed-to path shows a diff" "changed vs baseline" $script:OUT
Run @('deliverable', $b, 'src/existing.ts'); AssertRc "renamed-from path -> present as a change" 0
Run @('changed-files', $b);                  AssertContains "changed-files lists the new name" "src/renamed.ts" $script:OUT
Pop-Location; Cleanup $d

Write-Host "`n----------------------------------------"
Write-Host ("Results: {0} passed, {1} failed" -f $script:pass, $script:fail)
if ($script:fail -gt 0) { exit 1 }
Write-Host "All fixture scenarios passed."
exit 0
