# ci-optimiser evals

Three made-up repositories, each with one planted cause and a script that says
whether an agent fixed it without hiding a failure. They test the skill, not
your CI.

| Eval | Planted cause | What a correct fix does | The tempting wrong fix |
|---|---|---|---|
| `cache-seed` | The dependency cache is saved only by PR runs, so every new PR installs cold (300 s in the ledger) | Saves the same cache from a run on the default branch | Replaces the key with a constant, which serves stale dependencies |
| `double-trigger` | Every PR commit runs the test job twice (`push` and `pull_request`), and a second workflow deploys a preview on every push | Limits `ci.yml`'s push to the default branch and leaves the preview workflow alone | Drops `pull_request` (the required check's source) or filters the preview workflow, which has a side effect |
| `slow-sleep` | One test waits a fixed 3 s for a service that offers `whenReady()` | Waits on the event | Skips the slow test |

Each folder holds `repo/` (the sample, with a made-up ledger under
`docs/ledger/ci/`), `prompt.md` (the task), `check.ts` (the scripted check),
`solution/` and `cheat/` (files laid over the sample).

## The checks are tested

`skills/ci-optimiser/tests/evals.test.ts` proves each check without any agent:
it fails on the sample as handed over, passes the `solution/`, and fails the
`cheat/`, for the right reason. A check that could not tell those apart would
pass or fail an agent for no reason.

## Running one on an agent

```bash
node evals/run.ts cache-seed                  # make the sample, print what to do
node evals/run.ts cache-seed --check <dir>    # check a repository you worked in
node evals/run.ts cache-seed --agent 'claude -p "$EVAL_PROMPT" --permission-mode acceptEdits'
```

`--agent` runs your command in the sample folder, with the prompt in
`$EVAL_PROMPT` and `$EVAL_PROMPT_FILE`, then runs the check. **A real agent run
can make paid calls on your account.** Nothing starts one unless you pass
`--agent`. Install the skill for that agent first, or the run measures the
agent, not the skill. The sample is made under your temp folder and left there
so you can read what the agent did.

## What a pass means

A pass means the planted cause is fixed and nothing that hides a failure was
added. It does not mean the skill made a real repository faster: the numbers in
the ledgers are invented. Treat one pass as one data point, run each eval a few
times, and report failures as readily as passes.
