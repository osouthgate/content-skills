# Claude vs Codex — capability-aware execution

Supergoal runs on both Claude Code and Codex, and the **plan** it produces is
host-agnostic. But the two hosts have genuinely different execution capabilities,
and a run that ignores the difference leaves Claude's strengths on the table. This
reference defines the **capability profile** Stage 0 detects, and exactly how each
capability changes execution. The default everywhere is the portable, sequential
behavior; capabilities are **additive** — detected, recorded, and applied only when
present.

> **Principle: detect, don't assume; degrade gracefully.** Never hard-require a
> capability. A missing capability means "fall back to the portable path," never
> "fail." This mirrors supergoal's existing tool-discovery stance — capabilities
> are just a second axis of the same idea.

## The profile

Stage 0 writes `$SUPERGOAL_PLAN_DIR/capabilities.md` (this plan's folder) with these fields. Detect each by
inspecting the **tool list** and **environment**, not by guessing:

| Capability | Signal (present → capable) | Portable fallback when absent |
|---|---|---|
| **Host** | `Agent`/Task tool + `AskUserQuestion` + skills list → Claude Code; otherwise Codex | n/a — drives the rows below |
| **Subagent fan-out** | `Agent`/Task tool in the tool list | Sequential single-session execution (today's default) |
| **Web self-verify** | browser-driver tools (Claude in Chrome, Playwright, `mcp__*` browser) | Build/test/lint evidence only |
| **Mobile self-verify** | iOS/Android simulator MCP tools | Build/test/lint evidence only |
| **Service self-verify** | a runnable dev/serve command (`package.json` scripts, `Makefile`, `Procfile`, `docker compose`) | Build/test/lint evidence only |
| **`/loop`** | `loop` in the skills list | `/goal` only |
| **Cloud / ephemeral** | remote container env (fresh clone, no persistent local state) | Local — commit cadence less critical |

Record one line per field: `field: <value> — <signal that decided it>`. Stage 3
(deep think), Stage 4 (decompose), and the phase loop read this file.

## How each capability changes execution

### Subagent fan-out (the Claude-only lever)

The single biggest Claude/Codex divergence. Supergoal's default is **one `/goal`,
phases sequential** — correct and necessary on Codex, which has no subagent
primitive. On Claude, the `Agent` tool lets **independent** phases run concurrently.

- **Where the decision is made:** Stage 4 already records each phase's
  `Depends on phases:` line. Phases with **no unsatisfied dependency on each other**
  are independent and may run in parallel. This is exact, not heuristic — it falls
  straight out of the dependency graph the planner already builds.
- **What changes:** in the phase loop, instead of strictly `1 → 2 → 3`, the executor
  dispatches each **ready set** (all phases whose dependencies are already complete)
  as parallel subagents in a single message, waits for the set to finish, then
  recomputes the ready set. The Polish & Harden phase, which depends on everything,
  is always last and always solo.
- **What does NOT change:** every phase still prints its full `SUPERGOAL_PHASE_START`
  / `VERIFY` / `DONE` contract into the **main** transcript (subagents report their
  conclusion back; the orchestrator surfaces the blocks), `STATE.md` is still the
  single source of truth, and the final audit is unchanged. The evaluator must still
  see one `SUPERGOAL_PHASE_DONE` per phase.
- **Hard constraint — isolation:** parallel workers that edit the same files corrupt
  each other. Only fan out phases whose **deliverables don't overlap**. If two
  otherwise-independent phases touch the same files, either serialize them or give
  each worker its own git worktree. When in doubt, serialize — a correct sequential
  run beats a fast corrupted one.
- **Codex / no `Agent` tool:** ignore all of the above; run strictly sequential. The
  plan is identical; only the execution shape differs.

This also resolves the apparent tension with `phase-design.md`'s "true parallel
phases are rare in a single-session goal chain." That guidance is about a
**single-session, single-agent** loop — exactly right when there's no subagent
primitive. Subagent fan-out *is* the mechanism that makes independent phases
parallelizable; the dependency lines the planner already writes are what gate it.

### End-to-end self-verification

Supergoal's mandatory commands (build/typecheck/lint/test) prove the code compiles
and unit checks pass — they do **not** prove the running app works. When a
verification surface exists, phases that ship user-facing behavior must verify
**end to end** against it, and that evidence becomes part of the phase's acceptance.

- **Web surface present** → the phase loads the running app via the browser driver,
  exercises the new behavior, and asserts on real UI / captures a screenshot path.
- **Mobile surface present** → boot the simulator, drive the app to the new screen,
  screenshot.
- **Service surface present** → start the full server/service, hit the real
  endpoint(s), surface the response.
- **No surface** → state it plainly in the phase VERIFY (`E2E surface: none — unit
  evidence only`) and let the audit's coverage banner flag the trust-prior gap. Do
  not claim end-to-end coverage that wasn't produced.

This slots into the existing `Evidence required` list (see `phase-design.md`) as a
first-class evidence type, and into the `SUPERGOAL_PHASE_VERIFY` block as an
`E2E:` line. The final audit treats a present-surface E2E assertion as
`re_verified`; a `none` surface as `trust-prior`, which is exactly what the coverage
% and honesty banner already account for.

### `/loop`, cloud, auto-mode

These don't change the supergoal algorithm — they're operating-posture levers owned
by the **`autonomous-run`** companion skill. Stage 0 records them in
`capabilities.md` so the Stage 7 hand-off can mention them (e.g. "this is a cloud
session — commit at phase boundaries; un-pushed work is lost on idle"), but
supergoal itself does not toggle permission modes or dispatch `/loop`. Keep the
division clean: supergoal plans and executes; autonomous-run sets posture.

## What stays identical across hosts

The plan is portable. ROADMAP.md, phase specs, acceptance criteria, the failure
3-strike protocol, memory writeback, and the final audit are **the same on both
hosts**. Capabilities change only *how the phases are driven* (parallel vs
sequential) and *how deeply each is verified* (end-to-end vs unit) — never *what the
plan is*. A capability-aware run and a portable run must reach the same end state;
the capable one just gets there faster and proves it more thoroughly.
