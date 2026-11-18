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
node --test SKILL/tests/*.test.ts
```

`pull` reads the Actions API with `GITHUB_TOKEN`, `GH_TOKEN` or a logged-in
`gh`, one day per query, and never writes to GitHub. Day files hold branch
names, commit titles and runner names: decide before committing them to a
public repository.
