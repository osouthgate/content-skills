# loam-plan

Turn an idea or ticket into a **grounded, test-first plan**.

`loam-plan` reads a repo's **design → how-to → plan** lattice and routes on what already
exists. It refuses to plan an undesigned thing, writes a plan that carries its own context,
scaffolds a failing-test acceptance gate (committed RED as the first commit on the branch),
then auto-invokes `plan-eng-review`. The result is a plan whose **definition of done is a list
of runnable commands**, not vibes — ready to hand to `supergoal`/`/goal` to build toward green.

## Why it exists

In a mature repo, the design doc IS the spec and the `plans/` folder IS the task-breakdown.
So "spec something" isn't a new artifact — it's a *grounded transition* between artifacts you
already have. The missing primitive is **context assembly against the lattice** plus a
**test-first acceptance gate** — neither of which a plan *reviewer* (`plan-eng-review`) can do,
because it's a critic, not a gatherer.

## The pipeline

```
Phase 0  Resolve config        — lattice paths + gate commands for THIS repo (config or auto-detect)
Phase 1  Assemble lattice ctx  — design? how-to? plan(+status)? related code?
  ── GATE ──                   — undesigned ⇒ stop, route to design, register how-to debt
Phase 2  Draft grounded plan   — plan-<slug>.md with a self-grounding ## Grounding header
Phase 3  Scaffold acceptance   — failing tests/evals + typed stubs, run RED, commit first
Phase 4  Auto-invoke review    — plan-eng-review (graceful self-review fallback if absent)
```

## Install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install loam-plan@content-skills
```

## Usage

```
/loam-plan <idea, feature, or ticket id (e.g. LOA-123)>
```

Optional: drop a `.claude/loam-plan.yml` at the repo root to declare the lattice paths, gate
commands, and reviewer — see `skills/loam-plan/references/config.md`. Without it, the skill
auto-detects (loam-web's `docs/` + `plans/` taxonomy works out of the box).

## Pairs with

- **`plan-eng-review`** — the critic loam-plan auto-invokes in Phase 4.
- **`supergoal`** — the build engine that turns the red acceptance gate green.
- **`autonomous-run`** — operating posture for running the build unattended.

## Design

See [`docs/dev-flow-design.md`](../docs/dev-flow-design.md) in this repo for the full rationale,
the routing table, and the cross-cutting TDD/permission fixes.
