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

| Repo | designs | how-to | plans | gates | tests |
|---|---|---|---|---|---|
| **loam-web** | `docs/designs/` | `docs/how-to/` | `plans/{backlog,toDo,in_progress,done}/` | `pnpm type-check/lint/test` + `convex deploy --dry-run` + smoke ladder | colocated `__tests__/` |
| **osdb** | `docs/loamdb/`, `docs/shared/` | `docs/loamdb/guides/` | (per-repo; confirm) | `pnpm type-check/lint/test` + `loamdb-probe` | `packages/*/test/` |

Confirm osdb's `plans/` location with the user before first use there — its taxonomy differs
from loam-web's.
