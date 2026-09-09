Read before this: outcome-framework.md § Lifecycle · references/anti-rationalizations.md · the project's `map.recipe` if configured
Phase 0 line: mode `arm` (say if inferred), the doc's `Status`, the count of unresolved BLOCKING §9 questions, whether the lint passes, whether a map is configured, and whether the project is adopted.
Writes: a `feat/<capability>` branch, red tests, §6 (failing output + commit sha) and `Status:` in the doc; with a map, also each group's not-built row per the recipe and the §6 `Row` column.

# Arm — `agreed → building`

## Preconditions

- `Status:` is `agreed`.
- Zero unresolved BLOCKING questions in §9.
- `scripts/lint_outcome.py` passes on the doc.
- A map is configured, or it is not — state which; the rest of this mode branches on
  it.

Any precondition unmet → stop and say which one, rather than arming partway.

## The bridge, with a map

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --json` to get the
§6 rows. Propose grouping the AT rows into map rows by their `so that`: one map row
is one story plus 1–5 scenarios; more scenarios, or two distinct `so that` clauses,
is a chain — split it, with a parent.

Present the grouping as a table, **(Recommended)** first, with a completeness score
per option — **the grouping is the user's decision**, not this mode's.

File each approved group as a **not-built row**, per the recipe — the recipe's
lockstep names every file it touches, and a must-priority row needs a real test or
a dated, reasoned exemption from day one. Write the new row id into the `Row` column
of each §6 line it covers. §0's rule tags stay AT aliases; they do not change.

No map → skip this section; there is no bridge step, and §6 gains no `Row` column.

## With or without a map

1. **Create `feat/<capability>`** — never a protected branch.
2. **Write the §6 rows as failing tests**, with typed stubs that throw, so
   `commands.typeCheck` stays green while the tests fail at the assertion. If
   `typeCheck` is `null`, say so and rely on the tests alone — never invent a
   command the project does not have.
3. **Run them RED.** Paste the failing output into §6.
4. **Commit as the branch's first commit** — `test(<scope>): red acceptance gate for
   <capability>` — and record the sha in the doc header.
5. **With a map**, cite each red test in the lane its altitude picks, per
   `map.lanes` (`references/altitude.md`), so the row's evidence is honest from day
   one — under-proven, visibly, rather than silent.
6. **Flip `Status: building`.** This is the only status this mode writes, and the
   only place in this skill that writes any status forward — say so in the
   close-out.
7. Red proof cannot be witnessed in this environment (no dependencies, no sandbox) →
   **say so loudly in §6 with the exact command** that would prove it — never
   silently skip the step.
8. **Run `map.checks`** if configured, then `scripts/lint_outcome.py`.

## Close out

Paste §0 inline. List: the rows filed (with a map) or the AT rows armed (without
one), the tests written, the commit sha, and what could not be checked in this
environment.
