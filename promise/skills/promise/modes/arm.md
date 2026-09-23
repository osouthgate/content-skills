Read before this: outcome-framework.md § Lifecycle · references/altitude.md · references/anti-rationalizations.md
Read at the bridge step: the project's `map.recipe`, if a map is configured.
Phase 0 line: mode `arm` (say if inferred), framework source, docs home and its source, the doc's `Status`, the count of unresolved BLOCKING §9 questions, whether the lint passes, whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: a `feat/<capability>` branch, red tests, §6 (failing output), the header (`Red gate:` line) and `Status:` in the doc, committed by explicit path as the branch's second commit; with a map, also each group's not-built row per the recipe and the §6 `Row` column; when the human takes the starter-map offer, also the three starter files and the config's `map` object.

# Arm — `agreed → building`

## Preconditions

- `Status:` is `agreed`.
- Zero unresolved BLOCKING questions in §9. The lint does not check the
  BLOCKING count — read §9 yourself.
- `scripts/lint_outcome.py` passes on the doc (the lint checks shape, not
  whether the filled lines are true — read §4–§7 yourself).
- A map is configured, or it is not — state which; the rest of this mode branches on
  it.

Any precondition unmet → stop and say which one, rather than arming partway.

## First, the branch

**Git preflight, then create `feat/<slug>`** — slug is the capability title in
lower-case kebab form. Refuse and say why if: HEAD is detached; `feat/<slug>`
already exists; the working tree has staged changes that are not the test files
this mode writes (an unrelated staged file would ride into the red-gate commit).
Name the branch `feat/<slug>` is cut from; if it is not the project's main branch,
say so and ask before continuing — a branch cut from the wrong base is the user's
call, not this mode's guess. Show `git status --short` before and after. Every
edit below — map rows, §6, the header — lands on `feat/<slug>`, never on the
branch you started from.

## No map yet — offer the starter

When no map is configured (orient's `mapUsable` is false) **and** the config's
`map` is `null` or absent, offer once, on `feat/<slug>`, before anything is filed:

- **(Recommended)** — start the project's capability map now, from the skill's
  starter. Reason: this doc is a promise a human has just agreed, and the map is
  where the project's promises add up — one row per story, each naming the tests
  that prove it, with an honest verdict — so the platform's map starts with its
  first real promise, not on the day of adoption.
- Arm without a map. §6 stays the only home of these rows; `arm` can offer again
  on the next agreed doc.

Show `python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" --dry-run` (the three
files and the config diff it prints; `--dest <folder>` if the human wants another
home than `docs/capabilities`). On yes, run it without `--dry-run`, then re-run
`orient.py` and confirm `mapUsable` is true. The dry run printed every command the
new map configures, so that yes is also the session's yes for running them (SKILL.md
Phase 0). Then carry on with the bridge below, with the map just started.

A config whose `map` is an object, even an incomplete one, is the project's own map
in progress: never offer the starter over it (`start_map.py` refuses it too) — say
which keys are missing, per orient's warnings, and arm without a map.

## The bridge, with a map

On `feat/<slug>`, after the branch step above:

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --json` to get the
§6 rows and the §0 rules with their tags. Propose grouping the AT rows into map rows
**by the §0 rule each row is tagged from** — a rule is the promise at story
grain, so its rows are one story's scenarios. One map row is one story plus 1–5
scenarios; a rule with more, or rows that serve two rules, is a chain — split it,
with a parent. Rows no rule cites form one group the human places explicitly. An
AT row that already carries a `Row` id is not re-filed.

Present the grouping as a table, **(Recommended)** first, with one concrete reason —
**the grouping is the user's decision**, not this mode's.

(Gated once per session — SKILL.md Phase 0 asks before the first configured
command runs. `adapter.py` runs the project's own commands, unsandboxed, in the
project root; they may install packages or write files.) Before filing anything,
read `map.recipe` from the file and run
`python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" --json next-id` (and
`--json row <an existing id>` if the recipe names one). The recipe unreadable, or
either call exiting non-zero (2 = refused, 127 = executable not found, anything
else = the project's own command failed) → **stop before filing**, paste the
adapter's output verbatim, and say the map config is broken (`map.recipe` /
`map.row` / `map.nextId`). Phase 0 does not check these — `orient.py` checks the
config's shape and `adapter.py show` runs nothing — so this is the first point
that can. Fix the config, never the doc; never invent a row id.

File each approved group as a **not-built row**, per the recipe — the recipe's
lockstep names every file it touches, and a must-priority row needs a real test or
a dated, reasoned exemption from day one. Write the new row id into the `Row` column
of each §6 line it covers, adding the column between `Altitude` and the table's edge
if the doc has none, and add one line under the §6 table: `Snapshot taken at
`agreed` on <date>; the map is the source of these scenarios from here on.` §0's
rule tags stay AT aliases; they do not change. From this point `reconcile` reads the
map, never §6.

Then run `python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc>`. Fix every
error before the steps below, by rule:

| Rule | Meaning | Do |
|---|---|---|
| `ROW_MISSING`, `SNAPSHOT_LINE_MISSING` | a doc omission | fix the doc |
| `ROW_ID_FORMAT` | the id written is not one the map issues | re-read it from `next-id` or the recipe and correct the `Row` cell; **never edit `map.rowIdPattern` to admit it** |
| `ROW_NOT_FOUND` | ambiguous | run `adapter.py --json row <id>` and read the child output: the map's own "no such row" text means a wrong id in the doc (fix the cell); a command failure means `map.row` is broken (stop, config problem) |
| `INVALID_ROW_ID_PATTERN`, `UNREADABLE` | config or file problem | stop and say so |
| `NO_ROW_ID_PATTERN`, `NO_MAP_ROW_COMMAND` (warn) | `map.rowIdPattern` is unset, or `map.row` is an empty string | say so; fix the config, not the doc |
| `THEN_NOT_IN_MAP` (warn) | drift against the map's current text | name it in the close-out; never edit §6, which is now a snapshot |

Loosening `map.rowIdPattern`, a checker, a ceiling or a ratchet to make
`bridge_validate.py` or `map.checks` pass is never a fix — the same rule `intake`
and `reconcile` state.

No map → skip this section; there is no bridge step, the `Row` column stays empty,
and `bridge_validate.py` does not run.

## With or without a map

1. **Write the §6 rows as failing tests**, with typed stubs that throw, so
   `commands.typeCheck` stays green while the tests fail at the assertion. If
   `typeCheck` is `null`, say so and rely on the tests alone — never invent a
   command the project does not have.
2. **Run them RED** with `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" --json verify`.
   Expect `typeCheck` exit 0 and `test` non-zero; the sequence stops there, so
   `lint` does not run at arm time — that is expected. Paste the `test` step's
   failing output into §6. A `typeCheck` step reporting exit 127 (`executable not
   found`) is a configured command that cannot run here: quote its stderr, treat
   `typeCheck` as `null` for this run (step 1), and prove the red gate per step 7 —
   never substitute or invent a command; a pre-existing `typeCheck` failure that would
   stop the sequence is run past with `verify --only test`, and named in the close-out.
   `[]` means no `commands.*` is configured: nothing ran; prove the red gate per step 7
   and say so.
3. **Show the staged diff, then commit only the test files by explicit path** as the
   branch's first commit — `test(<scope>): red acceptance gate for <capability>` —
   and record the sha in the doc header as its own line, directly under
   `Supersedes:`: `Red gate: <sha> <YYYY-MM-DD>`.
4. **With a map**, cite each red test in the lane its row's `Altitude` column
   picks, per `map.lanes` (`references/altitude.md`), so the row's evidence is
   honest from day one — under-proven, visibly, rather than silent.
5. **Ask, then write `Status: building`.** Show the red output and the commit sha
   and ask the human to confirm the gate; on yes, write `building`. This is the
   only status this skill writes, and the commit the human approved is the act
   it records — say so in the close-out. `agreed` and `shipped` stay human-typed.
6. **Commit the doc — and, with a map, the recipe's row files, plus the three
   starter files and the promise config when this run started the map — by
   explicit path**,
   as the branch's second commit: `docs(<scope>): arm <capability> — building`.
   Show `git status --short` after it. Anything else the tree now shows (a
   lockfile, `node_modules/`, a cache) came from the project's own commands; name
   it in the close-out, never add it.
7. Red proof cannot be witnessed in this environment (no dependencies, no sandbox) →
   **say so loudly in §6 with the exact command** that would prove it — never
   silently skip the step.
8. **Hand back.** Run `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks` if a
   map is configured and `map.checks` is set (the adapter refuses with exit 2
   otherwise — that is not a failed check); `adapter.py verify` if any `commands.*`
   is configured — at arm time the `test` step is red by design, say so rather
   than reporting a failure; then `scripts/lint_outcome.py <doc>`, always.

## Close out

Paste §0 inline. List: the rows filed (with a map) or the AT rows armed (without
one), the tests written, both commit shas (red gate, doc), any `bridge_validate.py`
drift warnings, what `git status --short` still shows and why, and what could not
be checked in this environment.
