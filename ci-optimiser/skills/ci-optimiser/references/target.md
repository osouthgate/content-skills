# The target: fast CI that does not lie

A brief for a session (or a person) asked to make CI as fast as possible. Use
it with `techniques.md` (how) and the ledger (numbers). Where your repository
differs from a rule here, write down why next to the rule in your own notes.

## Target

A pull request gets its result in **under 2 minutes at the median and under 3
at p95**, measured from the ledger as PR wall time (queue + run), not job time.
This is an aim. A repo with a large integration suite sets its own number from
the ledger and tightens it.

## Two rules outrank speed

1. **The full suite runs before anything reaches the default branch**, for
   example in a merge queue. Test selection only narrows PR feedback; it never
   decides what ships.
2. **Never get faster by hiding failures.** No retries, wider timeouts or
   skipped tests. A check that needs a retry has a bug; find it. Moving a test
   off the PR lane is allowed only because rule 1 still runs it before merge.

If the repo has no merge queue and every merge ships, rule 1 is the first
owner step, before any test selection on PRs.

## Owner steps first (they unblock the rest)

Bring these as one list, each with its expected monthly cost. Do not do them
yourself:

1. A merge queue for the default branch, with the full suite as its required
   check.
2. Any change to required checks, branch protection or rulesets.
3. Any new runner, machine, vendor account, secret or bigger bill (for
   example a remote build cache that needs a token, or a larger runner).

## First, audit

Pull at least the last 150 runs (`ledger.ts pull --since 14d`) and split every
job into **waiting, setup and running**, at p50 and p95. Fix the biggest
bucket first.

Do not assume which bucket wins. It is often said that "it is rarely the
tests". Measure: in a repo with a real database suite, the tests can be most
of the time, and container start and migrations a few per cent.

## Budgets

Set each budget from the measured p95 **for each runner class**, with
headroom, then tighten. A faster machine finishes the same shard in half the
time, so one budget for mixed runners makes red runs that are not real.

| Bucket | Aim | How |
|---|---|---|
| Waiting | under 10 s | Enough runners on a shared label; a newer push to the same PR cancels the older run. Buy capacity only when the ledger shows queue time at p95 (owner step) |
| Setup | under 30 s | Cache hits above 95%, seeded from the default branch; a blobless clone (`filter: blob:none`) when history is needed, a shallow one when it is not. **PR code never writes a shared cache entry** |
| Lint | as low as measured allows | A faster linter for syntax rules; keep the slower one for type-aware rules and any ratchet that reads its suppression comments. Run both side by side first |
| Type check | as low as measured allows | A native or incremental checker, on changed packages and their dependents |
| Format | | A faster formatter, if it is faster on this repo. Measure first |
| Install and scripts | | The fastest package manager this repo's tools support. A repo rule ("only X") is a measured reason until the owner changes it |
| Tests | under 60 s per shard, long term | Isolate state per worker; reset state after every file; run in random order to flush leaks; shard by measured duration; buy cores before shards and match concurrency to cores |
| Shape | | Lint, type check, build and tests in parallel jobs; move slow checks that do not depend on each other out of the slowest job |
| Selection | | On PRs run only what the diff can reach, with forced full runs on risky paths and path-reading tests always run. **Then hide a real change on purpose and confirm CI goes red, not green.** Measure the selectable share over the last N merged PRs, and shadow the selection for weeks before it decides anything. Needs rule 1 first |
| Matrix | | A fast subset on PRs and the wide matrix after merge or on a schedule (techniques.md section 16); never move a leg that fails alone. Needs rule 1 first |
| Local | under 9 s | A pre-push hook that runs format, lint and type check on changed files |
| Keep it fast | | Fail a job that exceeds its budget, only after budgets exist for each runner class |

## Switching tools

The tools above are candidates, not mandates. Take anything newer that is
faster **on this repo**, and keep an old tool only with a measured reason.
Before each switch, run old and new side by side and list everything the new
one misses.

## How to deliver

- One small PR per change, with before and after numbers from real runs
  (ledger medians, not one run), recorded in the improvements log.
- Do everything possible without the owner first. Bring anything that needs an
  account, a secret, a setting or a bigger bill as one list with commands and
  the expected monthly cost.
- End with total CI time and cost, before and after: runner minutes per week
  from the ledger, PR wall time p50 and p95, and the monthly bill.
