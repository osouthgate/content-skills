Read before this: outcome-framework.md § Lifecycle · references/altitude.md · references/anti-rationalizations.md
Read at the bridge step: the project's `map.recipe`, if a map is configured.
Phase 0 line: mode `arm` (say if inferred), framework source, docs home and its source, the doc's `Status`, the count of unresolved BLOCKING §9 questions, whether the lint passes, whether a map is configured, and whether the project is adopted.
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
§6 rows and the §0 rules with their tags. Propose grouping the AT rows into map rows
**by the §0 rule each row is tagged from** — a rule is the promise at story
grain, so its rows are one story's scenarios. One map row is one story plus 1–5
scenarios; a rule with more, or rows that serve two rules, is a chain — split it,
with a parent. Rows no rule cites form one group the human places explicitly.

Present the grouping as a table, **(Recommended)** first, with a completeness score
per option — **the grouping is the user's decision**, not this mode's.

File each approved group as a **not-built row**, per the recipe — the recipe's
lockstep names every file it touches, and a must-priority row needs a real test or
a dated, reasoned exemption from day one. Write the new row id into the `Row` column
of each §6 line it covers, and add one line under the §6 table: `Snapshot taken at
`agreed` on <date>; the map is the source of these scenarios from here on.` §0's
rule tags stay AT aliases; they do not change. From this point `reconcile` reads the
map, never §6.

Then run `python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc>`. Fix every
error it reports — a missing `Row`, a bad row id, a missing snapshot line — before
the steps below. A warning is drift against the map's current text, not a defect
here: name it in the close-out rather than editing §6, which is now a snapshot.

No map → skip this section; there is no bridge step, §6 gains no `Row` column, and
`bridge_validate.py` does not run.

## With or without a map

1. **Git preflight, then create `feat/<slug>`** — slug is the capability title in
   lower-case kebab form. Refuse and say why if: HEAD is detached; the branch
   already exists; the working tree has staged changes that are not the test
   files this mode writes (an unrelated staged file would ride into the red-gate
   commit); the current branch is a protected one you would be committing on.
   Show `git status --short` before and after.
2. **Write the §6 rows as failing tests**, with typed stubs that throw, so
   `commands.typeCheck` stays green while the tests fail at the assertion. If
   `typeCheck` is `null`, say so and rely on the tests alone — never invent a
   command the project does not have.
3. **Run them RED.** Paste the failing output into §6.
4. **Show the staged diff, then commit only the test files by explicit path** as the
   branch's first commit — `test(<scope>): red acceptance gate for <capability>` —
   and record the sha in the doc header as its own line, directly under
   `Supersedes:`: `Red gate: <sha> <YYYY-MM-DD>`.
5. **With a map**, cite each red test in the lane its altitude picks, per
   `map.lanes` (`references/altitude.md`), so the row's evidence is honest from day
   one — under-proven, visibly, rather than silent.
6. **Ask, then write `Status: building`.** Show the red output and the commit sha
   and ask the human to confirm the gate; on yes, write `building`. This is the
   only status this skill writes, and the commit the human approved is the act
   it records — say so in the close-out. `agreed` and `shipped` stay human-typed.
7. Red proof cannot be witnessed in this environment (no dependencies, no sandbox) →
   **say so loudly in §6 with the exact command** that would prove it — never
   silently skip the step.
8. **Run `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks`** if a map is
   configured, then `scripts/lint_outcome.py`.

## Close out

Paste §0 inline. List: the rows filed (with a map) or the AT rows armed (without
one), the tests written, the commit sha, any `bridge_validate.py` drift warnings,
and what could not be checked in this environment.
