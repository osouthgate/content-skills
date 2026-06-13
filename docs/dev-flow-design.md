# Dev-Flow Design — `loam-plan` and the planning workflow

Status: **Working draft** (2026-06-13)
Scope: a planning/dev-flow skill set for `content-skills`, proven first against `loam-web`.
Inspiration: [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (24 skills, 6 phases).

---

## TL;DR

- **Don't rebuild the 24.** addyosmani's value is the Define → Plan → Build → Verify → Review → Ship spine. Mapped against what we already own (gstack in osdb, `supergoal`/`autonomous-run` in content-skills, the `smoke-*` ladder in loam-web), the back four phases are already covered — and ours carry incident lessons an off-the-shelf copy can't.
- **The genuine gap is the front two phases:** turning an idea into a *grounded* plan. That's `loam-plan` (and, later, a cheaper `brief` front door).
- **Don't call it `/spec`.** In our repo, `docs/designs/` already IS the spec/PRD layer and `plans/` IS the task-breakdown. `/spec` collides with two artifact types we've already named. Name the skill for the artifact it emits: a **plan**.
- **The value isn't a new artifact — it's a grounded transition** between artifacts we already have. The thing that's missing today is *context assembly against the lattice*, which `plan-eng-review` (a pure critic) will never do.

---

## Vocabulary: our lattice already encodes the states

addyosmani uses `/spec` because in his world the design doc doesn't exist yet. We already have that layer. The folder a thing lives in *is* its status — no frontmatter state machine required.

| addyosmani phase | Our artifact | Where it lives |
|---|---|---|
| spec-driven-development (PRD) | **Design** | `docs/designs/X.md` |
| planning-and-task-breakdown | **Plan** | `plans/{backlog,toDo,in_progress,done}/plan-X.md` (folder = status) |
| documentation / operability | **How-to** | `docs/how-to/X.md` |

So "build a plan from an idea" is really a transition across this lattice, and the lattice is readable as state.

---

## What we already own vs. the gap

| Phase | addyosmani | What we have | Verdict |
|---|---|---|---|
| **Define** | interview-me, idea-refine, spec-driven-dev | gstack `/office-hours` (idea stage) | **Gap: plan.** office-hours refines *product ideas*; nothing turns a decided thing into a grounded implementation plan. |
| **Plan** | planning-and-task-breakdown | `/plan-eng-review` (critic, not gatherer) | **Gap: context assembly.** No front door that reads the lattice + related code and grounds a draft. |
| **Build** | TDD, incremental, doubt-driven, … | `supergoal` `/goal`, `autonomous-run` | Covered — supergoal is the build engine. The hole is TDD-*as-a-gate* (out-of-band hook), not a skill. |
| **Verify** | browser-testing, debugging | `/qa`, `/investigate`, `smoke-local/dev/pr/prod` | Covered, richer than theirs. |
| **Review** | code-review, simplify, security, perf | `/review`, `/code-review`, `/security-review`, `/simplify` | Covered. |
| **Ship** | git, ci-cd, docs-adrs, observability | `/ship`, `/release`, `/document-release`, `/docs-sync` | Covered; `/release` carries incident lessons a copy can't. |

**Conclusion:** build `loam-plan` (and later a cheap `brief`). Reuse everything downstream verbatim.

---

## `loam-plan` design

### One skill, three phases

`loam-plan <idea | LOA-XXX>`:

1. **Assemble lattice context.** Read `docs/designs/`, `docs/how-to/`, `plans/*` (+ folder = status), and the related code touchpoints for the subject.
2. **Draft the plan, grounded in that context** → `plans/toDo/plan-X.md`, conforming to the patterns named in the relevant how-to.
3. **Auto-invoke `plan-eng-review`** on its own draft (decided 2026-06-13). One command yields a grounded **and** critiqued plan — fits the autonomous-run direction.

Context-assembly is a *phase inside* `loam-plan`, **not** a separate skill — YAGNI until a second consumer (office-hours, investigate) actually needs it. Extract then, not now.

### The lattice gate (front door)

Before drafting, check the lattice. `loam-plan` does **not** silently draft an undesigned thing:

| design? | how-to? | plan status | `loam-plan` does |
|---|---|---|---|
| ✓ | ✓ | done | **Delta plan** — "what's the gap / what broke", not a fresh build |
| ✓ | — | toDo / in_progress | **Implementation plan** conforming to the existing design; flag how-to as owed-on-ship |
| ✓ | — | none | **Produce the plan** from the design; register how-to debt |
| — | — | any | **Stop.** Route to `/office-hours`/design first; you're at idea stage. Register the how-to as a future deliverable. |

That last row enforces the discipline ("if it isn't designed, design it first") at the front door instead of on the honor system.

### Self-grounding artifact — the key move

Don't teach `plan-eng-review` (or any reviewer) to chase down the design and how-to docs. **Put the grounding in the plan itself.** `loam-plan` writes a `## Grounding` header:

```markdown
## Grounding
- Design: docs/designs/X.md        (exists | MISSING — flagged)
- How-to: docs/how-to/X.md         (exists | owed-on-ship)
- Related plans: plan-Y (in_progress), plan-Z (done)
- Conforms to pattern: <named pattern from the how-to>
- Code touchpoints: apps/web/...
```

Now `plan-eng-review` needs **zero changes** — it reads a richer artifact and the how-to context is already *in* the plan. A human skimming the plan gets the same grounding. This mirrors our own rule "the resume schema is the state machine, not the UI": **put the contract in the artifact, not the tool that reads it.**

---

## Portability seam: `gates.md`

Flow skills must never hardcode gates — osdb gates (`pnpm type-check/lint/test` + `loamdb-probe`) ≠ loam-web gates (the `smoke-*` ladder + `convex deploy --dry-run`). Each repo declares its gate chain in a `gates.md` the skills execute. That one file is the portability seam between repos.

---

## Cross-cutting fixes (adopt from day one)

Three independent critiques of the broader five-doors flow converged on these; they apply regardless of how much of the flow we build:

1. **TDD enforcement must be out-of-band** — a `PreToolUse` hook blocking Edit/Write on sealed test paths + a `spec_sha` diff check, *not* an in-prompt "don't edit the tests" rule. loam-web's lefthook is the natural home.
2. **Red tests vs. strict type-check is a real contradiction** — scaffold typed stubs that throw `NotImplementedError`; use threshold/golden-set assertions (not exact orderings) for search/NLP work.
3. **Permission engineering is the unbudgeted babysitter** — onboarding must emit the settings allowlist or autonomous builds prompt a dozen times regardless of architecture.
4. **Plan-file state rides the feature branch** — created early; the `toDo/ → done/` move is the last commit on the PR, never a post-merge push to a protected branch.
5. **Invoke existing skills, never copy them** — `loam-plan` calls `plan-eng-review` and (downstream) `/release`; it never inlines their procedure, so accruing incident lessons keep flowing.

---

## Build sequencing

1. **`loam-plan`** — the keystone (this doc). Portable skill in content-skills, reads a per-repo `gates.md`/lattice config, proven against loam-web's existing `docs/`+`plans/` corpus.
2. **`brief`** — a cheaper front door (ticket → context pack + triage verdict) once `loam-plan` is proven. Likely reuses the extracted lattice-assembler.
3. **Out-of-band TDD gate** — hook config, not a skill (fix #1).

`supergoal` already covers `/build`; `/release` covers ship. That's the whole flow with one or two new skills instead of five.

---

## Open questions

- **`brief` vs. `office-hours` overlap** — office-hours is product-idea-stage; `brief` is ticket-triage. Confirm they don't merge.
- **Where the lattice config lives** — `gates.md` per repo is decided; is the design/how-to/plan path map in the same file or a sibling?
- **Delta-plan semantics** (top lattice row) — when something is `done` + has a how-to, is the output a plan or a `/investigate` handoff?
