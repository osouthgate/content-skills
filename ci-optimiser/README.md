# CI optimiser

Make CI faster, and keep it fast, by measurement. The skill keeps a ledger of
GitHub Actions runs (one JSON line per run: commit, PR, wall, queue, job and
step times), reports the biggest costs and the commit where a job changed
speed, scans workflow files for common slow patterns, and runs a measure,
change, measure loop.

It never makes CI faster by removing required checks, tests or security scans.
Settings, secrets, runners and anything that costs money stay with the owner.

## Install

```bash
claude plugin install ci-optimiser@content-skills
```

For Codex, Cursor or another skill host, link or copy the canonical
[`skills/ci-optimiser`](skills/ci-optimiser) directory into `~/.agents/skills/`,
`~/.codex/skills/` or `~/.cursor/skills/`. Read the full
[SKILL.md](skills/ci-optimiser/SKILL.md) before using it.

## CLI

Node 22.18 or later. No packages. Run from the root of the repository you
measure; `SKILL` is the installed `skills/ci-optimiser` folder.

```bash
node SKILL/scripts/ledger.ts pull --since 14d --repo owner/name
node SKILL/scripts/ledger.ts report --days 7 --branch main
node SKILL/scripts/optimise.ts --pull --repo owner/name    # one brief: test-results/ci-optimiser/brief.md
node SKILL/scripts/ledger.ts compare --job test --label ubuntu-latest \
  --before 2026-11-01..2026-11-10T14:00:00Z --after 2026-11-10T14:00:00Z..2026-11-14
node SKILL/scripts/diff-guard.ts diff                      # nothing added that hides a failure
node SKILL/scripts/diff-guard.ts tests --before a --after b  # JUnit reports, compared by test name
node --test SKILL/tests/*.test.ts
```

`pull` reads the Actions API with `GITHUB_TOKEN`, `GH_TOKEN` or a logged-in
`gh`, one day per query, and never writes to GitHub. Day files hold branch
names, commit titles and runner names: decide before committing them to a
public repository.

`compare` gives a before / after verdict from 5 or more passed runs a side: the
median shift with an exact 95% interval, and a check that failures did not
rise. It refuses a window that has not settled, because fast runs finish
first. `diff-guard` turns "never trade proof for speed" into checks: it lists
retries, skips, `continue-on-error`, `|| true`, wider timeouts and bypassed
hooks added by a change, and fails if a test stopped running.

## Where the rules come from

[`references/evidence.md`](skills/ci-optimiser/references/evidence.md) gives the
basis of each rule: reasoning, GitHub's docs, a choice, or another team's
reported result. [`references/agents-snippet.md`](skills/ci-optimiser/references/agents-snippet.md)
is the same set of rules, short enough to paste into a repository's AGENTS.md.

## Evals

[`evals/`](evals) holds three made-up repositories with a planted cause and a
scripted check. The checks are tested without any agent; running one on an
agent is opt-in and can make paid calls. A pass means the cause is fixed and
nothing that hides a failure was added, not that a real CI got faster.
