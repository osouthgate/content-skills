# Per-repo config — the portability seam

Skills are portable; repos are not. loam-plan resolves everything repo-specific in Phase 0,
either from a config file or by auto-detection. Hardcoding paths or gate commands is the one
thing that breaks portability across loam-web ↔ osdb ↔ anything else.

## Option A — `.claude/loam-plan.yml` (preferred, explicit)

Drop this at the repo root or under `.claude/`. loam-plan reads it first.

```yaml
# Where the lattice lives
lattice:
  designs: docs/designs        # the spec/PRD layer
  howtos:  docs/how-to         # the operability layer
  plans:   plans               # the task-breakdown layer
  plan_status_folders: [backlog, toDo, in_progress, done]   # folder = status
  default_status: toDo         # where a fresh plan lands

# How tests are laid out (for scaffolding the acceptance gate)
tests:
  convention: colocated        # colocated (__tests__/ next to code) | central (packages/*/test)
  unit_glob: "**/__tests__/**/*.test.ts"
  substrate: lightweight       # lightweight (unit tests run on a bare clone) | docker-required (Testcontainers etc.)
  # If docker-required, Phase 3 prefers mock-based unit tests for the red gate so the proof can be
  # captured without spinning up the full stack; it falls back to `specified-unwitnessed` otherwise.

# Optional: the repo's OWN test-first gate, if it has one. When present, Phase 3 DEFERS to it
# (emits this artifact + maps to the stage model) instead of the sealed __tests__/ + spec_sha ritual.
acceptance:
  native_gate:                 # omit if the repo has no native gate
    artifact: plans/test-plans/{ticket}.md   # per-ticket test plan written before code
    template: plans/test-plans/_TEMPLATE.md
    model_doc: docs/how-to/test-planning-playbook.md   # the Stage 1–4 gate model
    pr_wired: true             # the PR template requires this section

# The gate commands — the red/green check. These are what "GREEN at done" runs.
gates:
  type_check: pnpm type-check
  lint: pnpm lint
  test: pnpm test
  evals:                       # optional, for recall/search/gatekeeper-shaped work
    - pnpm eval:recall --suite {suite} --threshold {threshold}

# The reviewer to auto-invoke in Phase 4 (skill name or slash command)
review:
  command: plan-eng-review     # falls back to built-in self-review if absent

# Optional: the seal-enforcement hook, if the repo has one
seal:
  pretooluse_hook: true        # loam-plan will note if this is missing
```

## Option B — auto-detect (when no config exists)

State assumptions out loud before writing anything:

1. **Lattice** — probe for `docs/designs/`, `docs/how-to/`, `plans/` with the four status
   subfolders. loam-web matches this exactly out of the box.
2. **Gates** — read `package.json` scripts for `type-check`, `lint`, `test`, `test:*`, `eval:*`;
   or a `gates.md` at root. List exactly what you'll run.
3. **Tests** — infer the convention: colocated `__tests__/` (loam-web) vs central
   `packages/*/test/` (osdb).
4. **Reviewer** — check whether `plan-eng-review` (skill or `/plan-eng-review`) is available.

If `plans/` can't be located, **ask** — don't invent one.

## Known repo profiles

> ⚠️ **Profiles drift. Auto-detection ALWAYS runs and OVERRIDES a profile that disagrees with the
> tree.** Treat this table as a hint, never as truth — verify each path against the actual repo in
> Phase 0. A stale profile that points at moved directories will make you grep the wrong place,
> find no design, and wrongly trip the lattice gate ("not designed") on something that *is*
> designed. When the profile and the tree disagree, **trust the tree and warn.**

| Repo | designs | how-to | plans | gates | tests | acceptance layer |
|---|---|---|---|---|---|---|
| **loam-web** | `docs/designs/` | `docs/how-to/` | `plans/{backlog,toDo,in_progress,done}/` | `pnpm type-check/lint/test` + `convex deploy --dry-run` + smoke ladder | colocated `__tests__/` | sealed red tests + `spec_sha` |
| **osdb** | `docs/designs/` | `docs/how-to/` | `plans/{backlog,toDo,in_progress,done,spikes}/` | `pnpm type-check/lint/test` + `loamdb-probe`; **`pnpm test` needs Docker (Testcontainers: pg+pgvector+AGE+Redis)** | central `packages/*/test/` | **native: `plans/test-plans/LOA-XXX.md` (per-ticket, PR-wired, Stage 1–4 model — see `docs/how-to/test-planning-playbook.md`). Defer to this; don't impose the sealed-commit ritual.** |

osdb has a **native test-first gate** (`plans/test-plans/`) that explicitly disclaims external
skills. When planning in osdb, Phase 3 emits a `plans/test-plans/<ticket>.md` from `_TEMPLATE.md`
and maps the work to a Stage, *instead of* the sealed `__tests__/` + `spec_sha` ritual. See the
`acceptance.native_gate` config block below.
