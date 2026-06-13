# The acceptance gate — test-first, made real

The plan ships a set of tests/evals that are **RED at plan start, GREEN at completion**. That
list of commands is the machine-checkable definition of done: supergoal builds toward it, the
audit verifies against it, and nobody reads the diff to know it's finished.

This only works if six things are true. Each one closes a specific failure mode.

## 1. Commit the tests RED, first commit on the branch

Test-first has teeth only if the red tests are *committed before implementation*. That's what
lets the build and the final audit check against committed tests rather than the agent's
self-report. **Planning owns the red tests; the build owns turning them green.**

```bash
git checkout -b feat/<slug>        # plan-file + tests ride the feature branch, never a protected one
# ... write tests + stubs ...
git add <test paths> <stub paths>
git commit -m "test(<scope>): red acceptance gate for <subject>"
git rev-parse HEAD                 # → record as spec_sha in the plan frontmatter
```

## 2. Typed stubs that throw — or you deadlock

The trap: committed tests import `fooBar`, which doesn't exist yet → strict `type-check` goes
RED → the build's "baseline must be green before I start" gate refuses to dispatch. You've
bricked the build on commit one.

Fix: scaffold the stub alongside the test so the symbol exists and is typed, but throws:

```ts
// stub — implementation is the build's job
export function fooBar(input: FooInput): FooResult {
  throw new Error("NotImplemented: fooBar");
}
```

Now: **type-check GREEN** (compiles), **test RED** (throws at runtime / fails the assertion).
"Compiles, doesn't work yet" — exactly the starting state you want.

## 3. Run them red, paste the proof

A test that's red because of a typo or a bad import path is a worthless gate — it'll go
"green" the moment the typo is fixed, proving nothing. Run the suite, confirm each test fails
**for the right reason** (assertion failure / NotImplemented throw, not a collection error),
and paste that output into the plan's `### Red proof` block. Now "done" has a witnessed start line.

## 4. Evals: threshold / golden-set, never exact

For recall, search-ranking, GATEKEEPER, ERB-shaped work, exact-match assertions are wrong —
ranking is probabilistic and brittle to reorderings. Assert against a **threshold or golden
set**:

```bash
pnpm eval:recall --suite X --threshold 0.8     # GREEN = score ≥ 0.8; RED = below, or suite errors
```

Record *suite + threshold* in the acceptance list. The existing test-plan templates in the
target repo already prescribe this — match them.

## 5. Seal the tests, enforce out-of-band

Under 3-strike retry pressure, a build agent will "fix" a failing test by editing the test.
An in-prompt "don't touch the tests" rule **always** fails. The only real defenses are
out-of-band:

- **Frontmatter seal:** record `sealed_paths` + `spec_sha`. The build's final audit runs
  `git diff <spec_sha> -- <sealed_paths>` and hard-fails on any change.
- **PreToolUse hook (if configured):** block `Edit`/`Write` on `sealed_paths` while the build
  runs. This belongs in the repo's harness config (e.g. loam-web's lefthook / `.claude/settings.json`),
  not in this skill — note it as a recommendation if it isn't present.

## 6. Exemption valve

Not every plan is code. A docs-only or pure-design plan has no meaningful failing test. Such a
plan sets `acceptance: exempt — <reason>` in frontmatter and skips Phase 3 entirely. The valve
is **explicit** — an honest exemption with a reason, never a silent skip because writing tests
was inconvenient.

## The artifact

```markdown
## Acceptance
acceptance: required
spec_sha: a1b2c3d
sealed_paths:
  - apps/web/src/features/X/__tests__/X.test.ts
  - evals/src/recall/suites/X.ts

- [ ] pnpm test -- features/X                        # RED now (3 fail) → GREEN at done
- [ ] pnpm eval:recall --suite X --threshold 0.8     # RED now (0.0)   → GREEN at done

### Red proof
```
FAIL  features/X  › resolves the X case
  Error: NotImplemented: fooBar
```
```
