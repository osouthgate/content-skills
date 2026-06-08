# Changelog

This is the changelog for the **content-skills adaptation** of `supergoal`. For the upstream
project's history, see https://github.com/robzilla1738/supergoal.

## 0.7.0-win.1

Adds a **host-capability layer** so the run adapts to Claude Code vs Codex without changing the
plan. The plan, phase specs, failure protocol, memory writeback, and audit are unchanged; only
*how* phases are driven and *how deeply* they're verified now varies by detected capability.

- Stage 0 now detects a **capability profile** (host, subagent fan-out, end-to-end verification
  surfaces, `/loop`, cloud) and writes `.supergoal/capabilities.md`. Detection is additive and
  degrades gracefully — a missing capability falls back to the portable path, never fails.
- **Subagent fan-out (Claude Code):** independent phases (per the dependency graph the planner
  already builds) run as parallel ready-sets instead of strictly single-file. Codex runs the
  same plan sequentially. Constraints: non-overlapping deliverables, Polish & Harden last/solo.
- **End-to-end self-verification:** when a web browser-driver / mobile simulator / runnable
  service surface is detected, behavior-shipping phases must exercise the running app, surfaced
  as a new `E2E:` line in `SUPERGOAL_PHASE_VERIFY`. No surface → unit evidence only, stated
  honestly.
- New reference `references/claude-capabilities.md`; updated `SKILL.md` (Stage 0/4/7, operating
  principles), `templates/PROTOCOL.md`, `references/phase-design.md`, and `references/goal-format.md`.
- The single `/goal` condition now says "in dependency order (parallel ready-sets when fan-out
  is available, else sequential)" instead of "sequentially".
- Posture levers (auto permissions, cloud, `/loop`) are recorded but owned by the new companion
  **`autonomous-run`** skill, not toggled by Supergoal.

## 0.6.1-win.1

Cross-platform adaptation of upstream **v0.6.1**. Functionally equivalent; adds native Windows
support.

- Added PowerShell parity ports of all five helper scripts: `detect-env.ps1`,
  `detect-stack.ps1`, `summarize-repo.ps1`, `repo-state.ps1`, `validate-phase.ps1`. Identical
  subcommands, arguments, stdout, and exit codes to the `*.sh` originals, which are retained
  unchanged.
- Added `tests/repo-state.test.ps1` — the same fixture scenarios as `tests/repo-state.test.sh`,
  run against the PowerShell port. All scenarios pass.
- Made `SKILL.md`, `templates/PROTOCOL.md`, and the reference docs OS-aware: detect the host
  shell once, then invoke `.ps1` (Windows) or `.sh` (Unix). Stage 7 now copies **both** forms
  of `repo-state` into `.supergoal/`.
- Packaged for the `content-skills` marketplace with attribution preserved (`LICENSE`,
  `NOTICE.md`, `README.md`).
