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
- **A commit that runs twice.** A workflow on both `push` (no `branches:`
  filter) and `pull_request` runs every PR commit once per event.
  - **Find:** in the ledger, the same commit with a `push` run on a
    non-default branch and a `pull_request` run. A push run on the default
    branch that shares a PR's commit is a post-merge run; do not count it.
  - **Make it safe:** limit `push` to the default branch only after two
    checks. The required check must be the `pull_request` one (otherwise merges
    block). And the push run must have no side effect the PR run lacks: a
    per-commit preview deploy, a tagged image or a cache warm makes it not
    redundant.

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
- **Seed the cache from the default branch.** A branch reads its own caches and
  its base branch's, never another PR's. If only PR runs save the cache, every
  new PR starts cold.
  - **Find:** the cache step's hit or miss line in PR job logs, and whether any
    job on a push to the default branch (or a schedule) saves the same key. A
    save in a merge queue run does not count: it lands on a temporary ref a new
    branch cannot read.
  - **Make it safe:** save with the same key template as the reader, from a
    push to the default branch (or a small warm-up workflow with
    `workflow_dispatch`). Keep the lock file hash in the key; widening a key
    to force a hit risks stale dependencies. Fork PRs can read the base
    branch's cache, so seeding helps them without giving them write access.
- **A cache can cost more than it saves.** Restoring a large archive (download,
  then unpack onto the runner's disk) can take longer than a warm install it
  replaces. Compare the restore step's time on a hit with the install step's
  time on a miss, from the ledger or job logs, before adding a cache for a
  fast install. If restore is slower, remove the cache.
- **Judge a cache change on warm runs.** The first run after a key change is
  cold. Compare after several runs on the default branch have saved and
  restored it, never on the first run.
- **Parallel jobs that share one key.** A saved cache cannot be changed, so
  the first job to save a key wins and the others restore whatever it built
  (a lint job's cache for a test job). Give each job its own key (add the job
  name), and check what each restored. One team's test jobs went from a
  median of 76 s to 180 s after a shared Go cache key, and fell to 41 s with a
  key per job (reported by CloudX, not reproduced here).
- **A key that misses the toolchain.** A key built from the lock file alone
  can hit while holding files a newer compiler or tool version cannot use.
  Add the tool version to the key. Confirm with the tool's own hit rate
  (`sccache --show-stats`, `ccache -s`), not the restore step's "hit".
- **The cache has a size cap, and old entries leave.** GitHub keeps 10 GB per
  repository by default, evicts the least recently used entries beyond it, and
  drops an entry not read for 7 days (defaults; check the repository's
  settings). A cache that was listed and is gone earlier than that points at
  eviction: list sizes with `gh api repos/OWNER/NAME/actions/cache/usage`.
  A manual delete looks the same, so name the reason before ranking it.
- **Docker image builds** with no layer cache (`cache-from` and `cache-to`, or
  a builder that keeps one) rebuild every layer each run. Read the build log
  for layers rebuilt before adding one.

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

## 11. A default branch that keeps moving

Fast checks do not help when every merge makes the other open PRs stale and
their checks run again.

- **Find:** the catch-up rate. Over the last 40 merged PRs, count the ones
  whose commits include a merge of the default branch into the PR ("Merge
  branch 'main'", "Merge remote-tracking branch 'origin/main'"), and the
  number of such commits per PR. `gh pr list --state merged --json
  number,createdAt,mergedAt,commits` has everything needed. Also count check
  runs per merged PR. One repo with several agents merging about 50 PRs a day
  had 19 of 40 PRs catch up at least once, and one PR six times.
- **Why:** a rule of "the PR head must contain the default branch tip" turns
  every merge into a rerun for every other PR. The cost grows with the number
  of authors, not with the size of the suite.
- **Fix:** a merge queue. Reviewed changes wait in a line; the queue runs the
  checks on a temporary merge of the change with the current default branch,
  and lands it when they pass. Nobody updates a branch by hand. Hosted queues
  exist (GitHub merge queue, Mergify); when hosted CI is not available, one
  local lane that takes one change at a time does the same job.
- **Make it safe:** the rule to keep is that what lands has passed the checks
  as merged with the branch it lands on. A clean merge with the default branch
  is not a new review. A conflict or a failed check sends the change back with
  the reason. Keep the owner's approval on gate files and risky changes.
- **Also reduce collisions:** a file that most PRs touch (one very large
  module, a shared changelog) causes most of the catch-ups. Split it, or use
  one changelog fragment file per change.
- **Measure before and after:** catch-up rate (target near zero), time from
  ready to landed (median and p90), check runs per landed change (target one),
  and reverts per 100 landed changes. If reverts rise, tighten the checks
  before making the queue faster.

## 12. Bigger levers (owner decisions)

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

## 13. Faster drop-in tools

- **Find:** lint and type-check steps by total runner time.
- **Make it safe:** compare rule coverage first (above all type-aware rules),
  run both side by side, switch only when the new one reports the same errors,
  and keep every ratchet that counts suppressions working.

## 14. Hygiene checklist

`scripts/workflow-scan.ts` checks the first ten automatically.

| Check |
|---|
| A newer push cancels the older PR run (technique 2) |
| Every job has `timeout-minutes` set above its measured p90 |
| Clones are shallow unless a step reads history |
| Dependency and browser downloads are cached (technique 5) |
| Long serial jobs are split where the parts are independent (technique 4) |
| One commit does not run on both `push` and `pull_request` (technique 2) |
| No `continue-on-error: true` hides a failure (report it; never change it to save time) |
| No matrix has `max-parallel: 1` without a reason |
| No fixed `sleep` waits for a service (technique 7) |
| No cache key holds the commit or run id without a `restore-keys` fallback (technique 5) |
| Shards are balanced by recorded time, not file count |
| One database, port or container per parallel worker |
| A remote build cache, if the build tool has one, with complete cache keys (owner step if it needs a token) |

## 15. Trigger scope

(Sections 15 to 20 are the later additions: trigger scope, a fast subset,
build once, bill rounding, flaky reruns, and waiting for a machine.)

Work that a change cannot affect is the cheapest work to remove, but only
where the proof still runs somewhere.

- **Path filters:** an expensive workflow (full build, browser tests, a
  scanner matrix) with no `paths` or `paths-ignore` runs for a docs-only PR.
  Include everything the workflow really reads: code under test, shared
  support, fixtures, config, lock file, container image and the workflow
  itself. A required check that is skipped by a path filter stays pending
  forever: use a small always-running job with the same name, or ask the owner.
- **Draft PRs:** an expensive job on every push to a draft is often unread.
  Gate it with `github.event.pull_request.draft == false` only if the required
  checks still run when the PR is marked ready (`ready_for_review` in `types`).
- **Event types:** `pull_request` runs on `opened`, `synchronize` and
  `reopened` by default. Adding `edited`, `labeled` or `assigned` re-runs CI
  for a title or label change. Keep them out unless a job reads them.
- **Filter before the runner starts.** A job that checks a comment's author or
  body in a step has already taken a runner. Put the check in the job's `if:`.
- **Schedules:** a cron more often than anyone reads the result wastes runners;
  see section 10 for start-time drift.
- **Workflow chains:** `workflow_run` hand-offs add a queue wait per link.
  Jobs with `needs:` in one workflow start sooner; check the `needs:` a job
  does not use as well.
- **Shard matrices:** `fail-fast: false` keeps every shard running after one
  fails. Keep it only where each shard's result is worth reading.

## 16. A fast subset before merge, the full matrix after

Every PR waiting for every OS, runtime version and heavy configuration is
often more than the merge decision needs.

- **Find:** a PR workflow that runs a wide matrix and sets the wall time. Over
  a long window (not a few hours), count each leg's **leg-unique failures**:
  runs where that leg failed and every other leg passed. Ignore skipped legs
  and any job that only reports other jobs' results.
- **Make it safe:**
  - A leg with leg-unique failures catches something no other leg catches. Do
    not move it. A subset on one OS cannot stand in for another OS.
  - Keep on the PR the oldest and newest supported runtime on the main OS, plus
    every leg that fails alone. Move the rest to a push on the default branch,
    a merge queue, or a schedule often enough to keep the unproven window short.
  - A red post-merge run must reach an owner and must block a release. Every
    merged commit is covered by a run that starts on the merge.
  - Keep one required check on the PR path. Do not leave a moved job listed as
    required: PRs would wait for a check that never runs.
  - Measure the selectable share: over the last N merged PRs, how often the
    proposed subset would have reached the same result as the full matrix.
    Replay known red commits and plant a defect aimed at a moved leg. If the
    evidence does not justify removing a leg from the merge gate, it is not a
    speed-up.

## 17. Build once, test on each platform

- **Find:** a matrix where each platform builds and tests, and one platform
  (Windows, ARM, an emulated architecture under QEMU) is the long pole because
  of compile time. Split its compile time from its test time with step timings.
- **Make it safe:** build the test binaries on a fast runner (cross-compiling
  for the target), upload them as an artifact, and run them natively on the
  target. Prefer a native runner over emulation. Keep a fully native
  build-and-test of that platform somewhere (after merge or on a schedule): a
  cross-built binary can differ in linker, toolchain or bundled libraries. The
  saving is the compile step's time, not the test time, which stays.

## 18. Bill rounding

Hosted runners bill each job rounded up to the minute. Three 20-second matrix
legs bill as three minutes, though their work fits in one.

- **Find:** many sub-minute legs of one matrix, all on the same runner class.
- **Make it safe:** merge only legs that are **not** on the critical path. If
  the merged legs would take longer than the longest parallel job, merging
  makes the PR slower. This saves billing minutes, never wall time; say so.

## 19. Flaky reruns

A job that fails and then passes on a rerun of the same commit is a
reliability cost, not a wait cost: the wait counts the final attempt only.

- **Find:** jobs with a failed attempt and a later passing attempt of the same
  run, in the ledger (same `runId`, `attempt` 1 and 2).
- **Measure per occurrence:** the runner minutes of the failed attempt's jobs
  that ran again, and the extra wait (first attempt's start to the passing
  attempt's end, minus a typical passing run; an estimate, so show the actual
  interval too). Add a daily cost on the last required finish. A flake in a
  workflow that does not finish last costs no wait, unless its rerun holds a
  runner, a slot or a shared resource another required job waits for.
- **Make it safe:** find the cause (shared state, an order, a clock, a port, a
  mock that answers 5xx: see section 8). Never add a retry, a longer timeout
  or a quarantine: a flake that needs one has a bug, and a retry turns a
  sometimes-failing test green without changing the code. One team that cut
  its end-to-end suite from 174 tests to 87 saw the flake rate fall from 100%
  to under 15% (reported by Clipboard, not reproduced here).

## 20. Waiting for a machine

Queue time is not a test problem. Before changing anything, find which limit
the queued jobs hit.

- **A plan's concurrent-job limit** (20 jobs, 5 on macOS, on the free plan;
  check the owner's plan): jobs wait for others to finish. Fewer, folded jobs
  or cancelled superseded runs help; a larger plan is an owner step.
- **A `concurrency` group** that holds jobs one at a time, or a matrix with
  `max-parallel` set: read the workflow.
- **A runner label with no free machine:** self-hosted or provider runners
  have their own capacity. Count queued jobs by label in the ledger.
- **Approval or environment waits:** a long gap before the first job, or
  between two jobs, that no job explains. Say which, from the workflow, before
  naming a cause.
- **Worker count against cores:** a test runner using 2 of 4 cores, or the
  reverse. Check `nproc` on the runner (a standard hosted Linux runner has
  more cores on a public repository than a private one: check the plan) and
  the runner's worker setting. With ideal scaling, twice the workers halves the
  time of tests that run in parallel: that is a ceiling. Repeat runs at each
  worker count to measure it.
- **Moving a job to another runner** (macOS especially) can drop platform
  coverage and can change cost: an owner decision.

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
- A file that looks wrong may be that way on purpose. Read its git history
  (`git log -p -- <file>`) and the PR that added the line before changing it.
  A change that contradicts the recorded intent is a policy change for the
  owner, not a quick win.
