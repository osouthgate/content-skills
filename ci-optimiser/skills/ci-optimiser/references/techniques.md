# CI optimisation techniques

A playbook of changes that cut CI time, each with how to find it and how to
make it safe. Read it after the ledger report has named the biggest cost
(SKILL.md, step 2). Every technique follows the loop: measure, change one
thing in its own PR, measure again.

## 0. Measure the right thing first

- **Find where a step's time goes before changing it.** A test step's wall time
  is not its test time. Many runners print a split (for example Vitest's
  `Duration X (transform, setup, import, tests, environment)`, pytest's
  `--durations`). When the parts are summed across workers, `sum / wall` is the
  real parallelism. If it is far below the worker count, the step is starved
  (CPU cap, serial files, one long file).
- **Per-file cost.** Run each test file on its own and time it, or parse the
  per-file lines a reporter prints in the job log. Take the max per file across
  shards and rank. Do not trust a committed durations file without its date.
- **Per-case cost inside one long file** comes from log timestamps.
- **Separate overhead from tests.** Sum of per-file test time against the step
  time. The gap is import, setup, container start and teardown.
- **Mixed runners skew shards.** A shard on a faster machine finishes early;
  compare per-shard time by runner before rebalancing.
- **Hooks are CI too.** Time each git-hook step on a throwaway local commit,
  running each command by hand. Push nothing.
- **Hosted CI that never starts is not fast.** When jobs fail in 0 s with an
  annotation about billing or a spending limit, the ledger has no timings for
  that period. Time the steps locally (same commands, same order) and say so.

## 1. Remove duplicate runs

- **Find:** two jobs or matrix legs running the same suite; files or legs that
  differ only by a mode suffix; a step that runs a test file another step also
  runs (overlapping discovery patterns).
- **Make it safe:** prove equivalence from the code (the two modes map to the
  same thing; the file lists overlap exactly), and that no expectation depends
  on the dropped copy. Keep every distinct test running somewhere.

## 2. Cancel superseded runs

- **Find:** a PR-triggered workflow with no `concurrency` group. Count PR runs
  where a newer push to the same branch started before the older run finished.
- **Make it safe:** cancel only pull-request runs. Pushes to the default branch
  must finish, so each merge commit keeps its own result:

  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
    cancel-in-progress: ${{ github.event_name == 'pull_request' }}
  ```

## 3. Move tests off the pull-request lane, not out of CI

- **Find:** one-off migration, backfill or cutover tests, and slow tests that
  guard nothing a PR can change.
- **Make it safe:**
  - Use an explicit list of exact file names, never a glob, guarded by a test
    that every name exists on disk.
  - Gate on the PR diff: skip only when the PR touches none of the paths the
    files exercise. Pushes to the default branch, the schedule and a manual
    dispatch always run them. An unreadable diff runs them (unknown never
    means skip).
  - Trigger paths include what the files really import: code under test,
    shared test support, fixtures, suite config, container image, lock file and
    the workflow.
  - Anything that guards privacy, tenant isolation or another security
    boundary stays on every PR.
  - Get an independent review of the list and the owner's yes before merging.

## 4. Run independent groups in parallel

- **Find:** one job with many steps that do not depend on each other, which
  sets the PR wall time.
- **Make it safe:** split into parallel jobs (or a matrix over test files)
  with every test still run exactly once. Keep the old job name as the check
  that people and merge tools wait on, or ask the owner before the name
  changes. Parallel jobs cost more runner time (each repeats setup), so check
  both wall and total in the ledger.
- **Within a job:** run test files in parallel processes when the files are
  independent (each uses its own temp folder, port and database). Prove it by
  running the full suite in parallel several times, in a random order, with the
  same pass count as the serial run.

## 5. Keep the dependency store between runs

- **Find:** an install or download step that repeats the same work on every
  run (package installs, browser downloads, toolchain downloads).
- **Make it safe:** cache on the lock file (or the tool's version) with a key
  that changes when the inputs change. Restore from the default branch; never
  let PR code write a cache that the default branch reads. On self-hosted
  runners, a store shared by a host's runners can replace the cache step.
  Rolling out runner changes happens outside the repo: owner step.

## 6. Balance shards, and split the file that fills one

- **Find:** the shard plan by measured time. When one file is longer than the
  average shard, the run cannot finish faster than that file.
- **Make it safe:** split the file by its natural groups, using per-group time
  from log timestamps. Update counts that guard the file list. Refresh the
  durations file from a recent full run.

## 7. Find slow patterns inside the slowest files

Rank files by time (section 0), then look in the top ten for:

- **Serial write loops:** one round trip per row. Batch, or build the fixture
  once per file.
- **Full set-up per test:** a fresh database, repository or server built in
  each test. Build once, or clone a prepared template.
- **Fixed sleeps and polling:** wait on the event, or shorten the interval.
- **Subprocesses started per case** (an interpreter, `git`, a browser): reuse
  one where the test does not need a fresh process.
- **One file with many slow end-to-end cases:** split it so it can share
  shards.

## 8. Mocks that answer with a retryable error

- **Find:** tests whose durations are round multiples of a timeout. Look for a
  test double that answers an unknown request with a 5xx or 429.
- **Why:** HTTP clients retry 5xx and 429 with backoff, so every unmatched call
  waits out the caller's deadline.
- **Make it safe:** change the refusal, not the product. Answer the mock's own
  "no fixture matched" with a 4xx and the same body; keep a test that asserts
  the refusal.

## 9. A job pinned to one runner

- **Find:** queue time while other runners are idle: the job names a label
  only one runner has.
- **Make it safe:** move the job to a shared label when it needs nothing that
  only that runner has (Docker socket, OS, a secret).

## 10. Scheduled workflows

- **Check the start time, not the cron.** A busy account can start a schedule
  hours late, in working hours, where it takes runners PRs need.
- **A workflow that is always red alarms nobody.** Count failures per job over
  two weeks before tuning speed; fix the always-failing jobs first.

## 11. Bigger levers (owner decisions)

- **More shards or bigger runners:** shorter wall time, more cost. Check queue
  time first.
- **Isolated state per worker** (one database per worker): the biggest gain
  for a serial integration suite, and the biggest change.
- **Run only affected tests on a PR**, with all of these safety nets: force a
  full run when the diff touches the lock file, test setup, shared fixtures,
  suite config, the workflow or the container image; always run tests that read
  files by path; keep the full suite on the default branch and before merge;
  shadow the selection for weeks and switch only when it would have missed
  nothing.

## 12. Faster drop-in tools

- **Find:** lint and type-check steps by total runner time.
- **Make it safe:** compare rule coverage first (above all type-aware rules),
  run both side by side, switch only when the new one reports the same errors,
  and keep every ratchet that counts suppressions working.

## 13. Hygiene checklist

`scripts/workflow-scan.ts` checks the first five automatically.

| Check |
|---|
| A newer push cancels the older PR run (technique 2) |
| Every job has `timeout-minutes` set above its measured p90 |
| Clones are shallow unless a step reads history |
| Dependency and browser downloads are cached (technique 5) |
| Long serial jobs are split where the parts are independent (technique 4) |
| Shards are balanced by recorded time, not file count |
| One database, port or container per parallel worker |
| A remote build cache, if the build tool has one, with complete cache keys (owner step if it needs a token) |

## Getting the data in a restricted session

- `ledger.ts pull` reads `GITHUB_TOKEN` first. If that token is for another
  repository, the API answers 404. Use `import`: save
  `gh api 'repos/<o>/<r>/actions/runs?status=completed&created=<day>'` as
  `runs.json` and each run's `.../runs/<id>/jobs?per_page=100` as
  `jobs-<id>.json`, then `ledger.ts import <folder>`.
- Always pass `--repo`.

## Rules that held

- One change per PR, each with its expected saving and the ledger lines it
  should move.
- A moved test still runs somewhere, on a named trigger, from a list guarded
  by a test.
- A red check after a speed change is real until shown otherwise: check the
  same test on the default branch before calling it flaky.
- Estimates are not savings. Record the measured saving after a few runs.
