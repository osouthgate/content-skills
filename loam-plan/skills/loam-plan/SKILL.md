---
name: loam-plan
description: Turn an idea or ticket into a grounded, test-first plan. Triggered by `/loam-plan`, "plan this out", "write a plan for X", "spec this", "build a plan from this idea", "I want to implement LOA-XXX", or before handing work to supergoal/`/goal`. Reads the repo's design → how-to → plan lattice and routes on what already exists: refuses to plan an undesigned thing (sends you to design first), writes a self-grounding plan whose `## Grounding` header carries its own design/how-to context, scaffolds a failing-test acceptance gate committed RED as the first commit on the feature branch (so "done" is a machine-checkable set of commands, not vibes), then auto-invokes `plan-eng-review`. Portable across repos via a per-repo config; degrades gracefully when the reviewer or a lattice layer is absent. Prefer this over an ad-hoc plan whenever the work will be built and needs a verifiable definition of done.
argument-hint: <idea, feature, or ticket id (e.g. LOA-123) to plan>
---

# Loam Plan

You are running the **loam-plan** workflow. The user's subject is:

$ARGUMENTS

Your job: turn that idea/ticket into a **grounded, test-first plan** — a `plan-<slug>.md`
artifact that (a) carries its own design + how-to context, (b) ships a failing-test
acceptance gate that defines "done" as runnable commands, and (c) has been critiqued by
`plan-eng-review`. You do **not** implement the feature — that's `supergoal`/`/goal`. You
produce the plan and the red tests that the build will turn green.

The keystone idea: **the value is not a new artifact — it is a grounded *transition*
between artifacts the repo already has.** Design is the spec layer; the plan is the
task-breakdown layer; how-to is the operability layer. loam-plan reads that lattice as
state and routes on it.

---

## The pipeline (four phases + a gate)

```
Phase 0  Resolve config        — find the lattice paths + the gate commands for THIS repo
Phase 1  Assemble lattice ctx  — design? how-to? plan(+status)? related code?
  ── LATTICE GATE ──           — undesigned ⇒ STOP, route to design, register how-to debt
Phase 2  Draft grounded plan   — plan-<slug>.md with a ## Grounding header
Phase 3  Scaffold acceptance   — failing tests/evals + typed stubs, run RED, commit first
Phase 4  Auto-invoke review    — plan-eng-review on the draft (degrade gracefully if absent)
```

Two human checkpoints only: the **lattice gate** (when the thing isn't designed, you stop
and ask) and the implicit review of `plan-eng-review`'s output. Everything else runs through.

---

## Phase 0 — Resolve config (where is the lattice, what are the gates?)

Skills are portable; repos are not. osdb's gates (`pnpm type-check/lint/test` + `loamdb-probe`)
are not loam-web's (the `smoke-*` ladder + `convex deploy --dry-run`), and the lattice dirs
differ too. **Never hardcode paths or commands — resolve them.**

1. **Read the repo config if present:** `.claude/loam-plan.yml` (or `.loam-plan.yml` at root).
   See `references/config.md` for the schema. It declares the lattice dirs, the plan-status
   folders, the gate commands, the test layout, and (if any) the repo's native gate.
2. **Always auto-detect, and VERIFY any profile/config against the actual tree.** A profile or a
   `references/config.md` "known repo profiles" row can be stale (docs get moved). For each path the
   config claims, confirm it exists. **On mismatch, trust the tree and warn** — never grep a moved
   directory, find no design, and wrongly trip the lattice gate. Auto-detect:
   - Lattice: probe for `docs/designs/`, `docs/how-to/`, and `plans/` (with status subfolders
     `backlog/ toDo/ in_progress/ done/`).
   - Gates: read `package.json` scripts (`type-check`, `lint`, `test`, `test:*`, `eval:*`) or a
     `gates.md` at root.
   - Tests + **substrate**: infer the convention (colocated `__tests__/` vs central `packages/*/test/`)
     **and whether the test run is lightweight or Docker-required** (grep for Testcontainers / a
     `docker info` precondition in CLAUDE.md). This decides whether Phase 3 can witness a red proof here.
   - **Native gate**: check for a repo-owned test-first mechanism (e.g. a `plans/test-plans/` folder +
     a test-planning playbook). If present, Phase 3 defers to it (see Phase 3).
3. If you cannot find a `plans/` location, ask where plans live before continuing. Do not invent one.

Print a one-line config summary (lattice dirs + gate commands + test substrate + native gate?) so the
user can correct a bad auto-detect before any files are written.

---

## Phase 1 — Assemble lattice context

Search the three lattice layers and the related code for the subject. This is the phase
`plan-eng-review` can't do — it's a critic, not a gatherer.

- **Design:** grep `docs/designs/` for the subject. Is there a design doc? Read it.
- **How-to:** grep `docs/how-to/` (and runbooks). Is there an operability guide / named pattern?
- **Plans:** grep all status folders. Is there an existing plan? **The folder it lives in IS its
  status** (`backlog`/`toDo`/`in_progress`/`done`). Note related plans even if not the same subject.
- **Code:** find the touchpoints — the files/modules this work will change. Cite them by path.
- **Ticket:** if the subject is `LOA-XXX`, pull the ticket (Linear MCP if available) for acceptance
  criteria and link it.
- **Cross-repo:** if this repo calls a paired/sibling repo across a contract boundary (e.g. an app
  layer calling a storage/API layer), the authoritative *design* for that boundary's behavior may
  live in the **other** repo, not here. When the subject touches that seam: read this repo's
  cross-repo-contracts rule (if any) first, then — if the sibling repo is checked out locally — fold
  its `docs/designs/` + `docs/how-to/` + any integration map into the grounding. If it isn't local,
  record in `## Grounding` where the cross-repo design lives (link it) and flag it read-before-build.
  Direction matters: a *consumer* conforms to the *provider's* design; the provider only consults the
  integration map for "who consumes this," it does not couple up. Skip when the subject is single-repo.

Resolve which **routing row** you're in (see `references/lattice.md` for the full table):

| design? | how-to? | plan status | loam-plan does |
|---|---|---|---|
| ✓ | ✓ | done | **Delta plan** — "what's the gap / what broke", not a fresh build |
| ✓ | — | toDo / in_progress | **Implementation plan** conforming to the design; how-to owed-on-ship |
| ✓ | — | none | **Produce the plan** from the design; register how-to debt |
| — | — | any | **LATTICE GATE → stop** (next section) |

### ── The lattice gate ──

If **no design exists**, do not silently draft. Stop and tell the user:

> "`<subject>` isn't designed yet — there's no `docs/designs/` doc for it. Planning an
> implementation now is premature. Options: (a) run `/office-hours` or write a design doc
> first, then come back; (b) if this is genuinely trivial/mechanical, re-run with
> `--exempt-design \"<reason>\"` and I'll plan it anyway and register the how-to as owed."

Wait for the user. **Explicit exemption, never silent bypass.** If exempted, record the reason
in the plan's frontmatter (`design: exempt — <reason>`) and proceed.

---

## Phase 2 — Draft the grounded plan

Create `plans/<status>/plan-<slug>.md` from `templates/plan.md`. Default status folder is the
"todo/next" one (`toDo/` in loam-web). The non-negotiable part is the **`## Grounding` header**:
it carries the design/how-to/plan/code context *into the artifact itself*, so `plan-eng-review`
(and any human) reads a self-contained plan and needs zero extra lookups. Same principle as
"the resume schema is the state machine, not the UI": **put the contract in the artifact.**

```markdown
## Grounding
- Design: docs/designs/X.md        (exists | exempt — <reason>)
- How-to: docs/how-to/X.md         (exists | owed-on-ship)
- Related plans: plan-Y (in_progress), plan-Z (done)
- Conforms to pattern: <named pattern from the how-to>
- Code touchpoints: apps/web/...
- Ticket: LOA-XXX
```

Then write the plan body: goal, phased task breakdown (small, verifiable, ordered), risks, and
the `## Acceptance` section (filled in Phase 3). Conform to the patterns named in the how-to —
don't reinvent a pattern the repo already has.

---

## Phase 3 — Scaffold the acceptance gate (test-first)

This is what makes the plan trustworthy: a set of tests/evals that are **RED now and must be
GREEN at completion** — the machine-checkable definition of done. Read `references/acceptance-gate.md`
for the full mechanics.

**First, two routing checks (from Phase 0):**

- **Does the repo have a NATIVE test-first gate?** (config `acceptance.native_gate`, e.g. a
  `plans/test-plans/<ticket>.md` per-ticket model wired into the PR template.) If so, **defer to it**:
  emit *that* artifact from its template and map the work to the repo's stage model — do **not**
  impose the sealed `__tests__/` + `spec_sha` ritual on top. Conform to the repo, don't compete.
- **Can a red proof actually be WITNESSED here?** If the test substrate is Docker-required or deps
  aren't installed (fresh clone / sandbox / CI-less box), you may not be able to run the test red.
  That's a normal state with its own acceptance value — see the `specified-unwitnessed` state below.
  Prefer mock-based unit tests (no Docker) for the red gate when the repo's integration tests need it.

The six rules that make the sealed-commit gate a real gate, not theatre:

1. **Write the failing tests yourself and commit them RED** — as the *first commit on the
   feature branch*, before any implementation. (Create/checkout the feature branch first if the
   repo isn't already on one — plan-file state must ride the branch, never a protected branch.)
2. **Scaffold typed stubs that throw, not just tests** — `export function foo(): X { throw new
   Error("NotImplemented") }` — so strict `type-check` stays GREEN while the tests fail at
   runtime/assertion. Skip this and the committed tests break the type-check, and the build's
   "baseline must be green" gate deadlocks on first run.
3. **Run them red and paste the output into the plan** — confirm they fail *for the right
   reason* (assertion, not import/typo). A test red from a typo is a worthless gate.
4. **Evals are threshold/golden-set, not exact** — for recall/search/GATEKEEPER-shaped work,
   green = *meets threshold* (`eval:recall --suite X --threshold 0.8`), never exact orderings.
5. **Seal the tests** — record the test paths + the red-commit `spec_sha` in the plan
   frontmatter (`sealed_paths`, `spec_sha`). The build audit hard-fails on any `git diff` to
   those paths; if a `PreToolUse` hook is configured it blocks Edit/Write on them during the
   build. This is the only real defense against the build agent editing a test to pass.
6. **Exemption valve** — non-code plans (docs, pure design) set `acceptance: exempt — <reason>`
   in frontmatter and skip this phase. Explicit, never silent.

**Three acceptance states** (pick one, record it in frontmatter — never silently skip):

- `required` — red proof captured: tests written, run, failing for the right reason, `### Red proof`
  pasted, `spec_sha` recorded. The full gate.
- `specified-unwitnessed` — **code plan, but the red proof can't be captured in this environment**
  (no deps / Docker-required substrate / sandbox). The tests are still written into the plan as code
  blocks + stub, but `spec_sha` is `pending` and `### Red proof` is honestly empty with the reason
  ("deps not installed; run `pnpm install && <test cmd>` to witness"). This is **loud, not a skip** —
  the build must witness red before it starts. Distinct from `exempt`.
- `exempt — <reason>` — no test is meaningful (docs / pure design). Skip the phase.

Fill the `## Acceptance` section with the runnable commands and their current RED state:

```markdown
## Acceptance
acceptance: required
spec_sha: <sha of the red-test commit>
sealed_paths:
  - apps/web/src/features/X/__tests__/X.test.ts
  - evals/src/recall/suites/X.ts

- [ ] pnpm test -- features/X                        # RED now (3 fail) → GREEN at done
- [ ] pnpm eval:recall --suite X --threshold 0.8     # RED now (0.0)   → GREEN at done
```

Commit: `git commit -m "test(<scope>): red acceptance gate for <subject>"` and record the sha
back into the plan frontmatter. This is the first commit on the branch.

---

## Phase 4 — Auto-invoke plan-eng-review

Hand the finished draft to the critic (decided: auto-invoke, so one command yields a grounded,
test-anchored, **and** critiqued plan).

- **If `plan-eng-review` is available** (gstack skill, or `/plan-eng-review`): invoke it on the
  plan file. Apply or triage its findings, then re-state the plan's status.
- **If it is not available** in this host/repo: say so plainly and run a built-in adversarial
  self-review instead — check the plan against its own `## Grounding` (does the design support
  every phase?) and `## Acceptance` (does every phase map to a red test that will go green?).
  Note that the external reviewer was unavailable so the user can run it manually.

Do not inline `plan-eng-review`'s procedure into the plan — invoke the skill so its accruing
incident lessons keep flowing.

---

## Output

End by reporting:
- the plan path + which routing row it took,
- the `## Grounding` summary (one line),
- the acceptance commands and their RED proof (or the exemption + reason),
- the review verdict (plan-eng-review's, or the self-review + "reviewer unavailable"),
- the next action (`supergoal`/`/goal` to build toward green, or design-first if gated).

## Anti-rationalizations

| Excuse | Reality |
|---|---|
| "It's obviously designed, I'll skip the lattice check." | The check is one grep per layer and it's what makes the plan grounded. Do it. |
| "I'll describe the tests instead of writing them." | Described tests aren't a gate. Commit them RED or there's nothing to build toward. |
| "Tests break type-check, I'll commit them red and move on." | That deadlocks the build's baseline gate. Scaffold throwing stubs so type-check stays green. |
| "I'll let the build write the tests." | Then the build grades its own homework. Planning owns the red tests; that's the seal. |
| "plan-eng-review isn't here, skip review." | Run the built-in self-review and say the external one was unavailable. Never skip silently. |
| "No design doc, but I get the gist, I'll plan anyway." | Stop at the gate. Route to design, or take an explicit `--exempt-design` with a reason. |
