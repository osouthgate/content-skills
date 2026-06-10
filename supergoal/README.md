# supergoal (cross-platform)

> Plan deeply, then auto-execute under a single `/goal` until the task is verifiably
> complete across every phase — with built-in retry, fix-spec recovery, per-phase memory
> writeback, and a final audit that re-verifies the work against the approved plan.

This is a **Windows-adapted** packaging of [`supergoal`](https://github.com/robzilla1738/supergoal)
by **Robert Courson**, bundled into the `content-skills` marketplace. It is functionally
equivalent to upstream **v0.6.1** with cross-platform helper scripts added. See
[`NOTICE.md`](NOTICE.md) for full attribution and the list of changes, and [`LICENSE`](LICENSE)
(MIT — original copyright retained).

## What it does

Turns a vague "build/fix/ship X — and don't stop until it's done" request into a deeply
planned, autonomously executed `/goal` run. Two human gates only:

1. **Clarifying questions** for genuine gaps (often zero on a well-described brownfield task).
2. **Plan review** — an explicit go/no-go before anything runs.

After you approve, it prints a single ready-to-paste `/goal` line. You paste it once; from
there the run is autonomous until `SUPERGOAL_RUN_COMPLETE` is printed.

> **Note:** Slash commands only fire from *your* input — the skill never auto-dispatches
> `/goal`. The one paste is the deliberate hand-off point.

## Plans persist, and you can have more than one

A plan is a **committed artifact**, not scratch. Everything lives under `.supergoal/`:

```
.supergoal/
  INDEX.md              # signpost: every plan, its status, baseline
  PROTOCOL.md           # shared operating manual
  repo-state.{sh,ps1}   # shared helpers
  plans/<slug>/         # one folder per plan (ROADMAP, STATE, phases/, goals/goal_prompt.md, …)
```

- **Persistence.** `.supergoal/` is meant to be committed (don't gitignore it). The plan — including the ready-to-paste `/goal` line saved at `plans/<slug>/goals/goal_prompt.md` — then survives an ephemeral/cloud session, travels with the branch, and can be dispatched by a teammate from the checkout alone. Stage 7 commits the plan and captures the baseline *as that commit*, so a resume can tell whether anything has changed since dispatch.
- **Multiple plans.** Each plan gets a date-stamped `plans/<slug>/` folder, tracked in `INDEX.md`. Re-running `/supergoal` reads the signpost and offers to **resume** an in-progress plan or **start a new one**. Plans are dispatched one at a time; for genuinely parallel work, give each its own branch or git worktree (one plan per working tree).

## Install

From Claude Code:

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install supergoal@content-skills
```

Then in a session: `/supergoal <describe what you want built, fixed, or shipped>`.

## Cross-platform

Every helper script ships in two parity forms with identical CLI and output:

| Helper | POSIX (macOS/Linux/Codex/git-bash) | Windows (PowerShell) |
|--------|-----------------------------------|----------------------|
| Greenfield env recon | `detect-env.sh` | `detect-env.ps1` |
| Stack detection | `detect-stack.sh` | `detect-stack.ps1` |
| Repo map | `summarize-repo.sh` | `summarize-repo.ps1` |
| Working-tree vs baseline | `repo-state.sh` | `repo-state.ps1` |
| Phase-spec validation | `validate-phase.sh` | `validate-phase.ps1` |

The skill detects the host shell once and invokes the matching form. On Windows this matters:
the platform `bash.exe` is frequently a non-functional WSL stub, so the `.ps1` ports are what
make the skill actually run. `repo-state.ps1` — the only helper invoked at runtime during the
autonomous loop — is verified to byte-for-byte behavioral parity with the bash original.

**Requirements:** `git` on `PATH`. PowerShell 7+ (`pwsh`) on Windows; `bash` on Unix.

## Tests

```bash
bash tests/repo-state.test.sh      # POSIX parity fixtures
```

```powershell
pwsh -File tests/repo-state.test.ps1   # PowerShell parity fixtures
```

Both run the same fixture scenarios (clean tree, uncommitted/staged/untracked/deleted/renamed
changes, spaced paths, invalid baseline, `.gitignore`'d files) against their respective port.

## Credit

All design and original implementation: **Robert Courson** —
https://github.com/robzilla1738/supergoal. This adaptation only adds Windows/PowerShell parity
and OS-aware documentation. Not affiliated with or endorsed by the original author.
