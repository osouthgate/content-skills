Read before this: references/altitude.md · references/anti-rationalizations.md
Read at Apply, not before: the project's `map.recipe` and `map.index`, if a map is configured.
Phase 0 line: mode `reconcile` (say if inferred), framework source, docs home and its source, what shipped (PR / branch / commit / test file / claim), whether a map is configured (orient's `mapUsable`), whether any `commands.*` is configured, and whether the project is adopted.
Writes: per the recipe's lockstep files when a map is configured (a dated finding, the evidence array, a kill witness); else the outcome doc's §0 tags, `Scenarios:` count and a dated §8 entry.

# Reconcile — the work shipped; now update the promise

The mirror direction of `intake`: work landed, and some promise's proof is now
closer to true, or further from it, and nothing notices on its own.

## Recognise the input

A PR, a branch, a commit, a test file, "we already do this," or "isn't `<row>`
covered by X?" — never a feedback list. A feedback list is `modes/intake.md`.

Whenever a map is configured (orient's `mapUsable`) and an outcome doc is
involved — named in the input, matched in Phase 0's `existingDocs`, or found
by the probes below — run
`python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc>` on it before
reading the map. A `THEN_NOT_IN_MAP` finding means §6 and the map disagree —
the map moved on, or §6 was edited after its snapshot — read the map
(`adapter.py row <id>`), never §6, for what a scenario asserts now, and say so
in the hand-back.

## Invariant inversion

`intake`'s invariant 6 — reproduce before believing — inverts here:
**"watch it die before believing."** A passing test nobody cited is a claim about
the row, not evidence for it, until you have seen it fail under a named mutation.

## Find the promise

There is no direct lookup by file. Take the union of three probes:

1. (Gated once per session — SKILL.md Phase 0 asks before the first configured
   command runs.) Write what a person can now do, in their own words, to a
   scratch file with the Write tool, then run
   `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" find --query-file <that file>`.
   The text never appears on a command line.
2. Grep the map for a file the work touched.
3. Grep the touched test files for the project's own test-declaration marker
   (whatever the recipe calls it).

Then `adapter.py row <id>` on every candidate, and **read the finding to the end** — a row with
declared-but-uncited test files is usually the answer. Nothing matches → this is a
NEW-ROW item; go to `modes/intake.md`.

No map → the same three probes run against the outcome docs in `docsHome` instead —
a doc's own text (`outcome_rows.py --search-file <that file> --dir <docsHome>`),
its §6 rows, and its cited test files.

## Establish what evidence now exists

Per scenario on the candidate row:

| Scenario | Its `Then` | Altitude the `Then` claims | New evidence | Altitude the evidence reaches | Watched dying? |
|---|---|---|---|---|---|

The altitude a `Then` claims is written down already: the row's own altitude in
the map, or the §6 `Altitude` column on the doc — read it, do not re-derive it,
and say so if the two disagree. For anything already-included — a test that
exists but was never cited — the last column is not optional: run the mutation,
watch the cited title fail under it and pass without it, and quote the failure.
Run the recipe's citation-strength and provenance checks too, if it names them:
an existence-only assertion is weak evidence, and a file shared by several rows
needs to be checked against the right one.

## Decide whether the verdict moves — in front of the user

> The verdict moves only when the new evidence reaches the altitude the row's own
> `Then` claims — `references/altitude.md`.

Compare the two altitude columns from the step above, per scenario. Remember: the
row is proven only when *every* scenario is. Present the call as a recommendation —
**(Recommended)** — with one concrete reason; the decision is the user's,
especially when the honest answer is "this stays under-proven, and the work still
mattered."

## Apply, in lockstep

Everything the recipe's lockstep names, plus what is specific to this direction:

- **A dated finding, appended** in every place the recipe names — what landed, what
  it now proves, and what it still does not. Never touch the lede.
- **Citation into the lane the altitude earns**, via `map.lanes` — exact titles,
  not a paraphrase.
- **A kill witness, if and only if the row became proven.** No watched kill, no
  promotion — this mode refuses to record one otherwise.
- **A defect found instead of a gap closed** → file it, add the reference, set the
  severity, and do not promote the row.
- **A pinning test for wrong behaviour** must say so in its own finding text, and
  name the assertion to flip later, when the behaviour is fixed.

## Update the bridged outcome doc, if one exists

- Re-stamp §0's rule tags by hand (which rows test which rule is a judgement), then
  `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --write-counts` for
  the `Scenarios:` line.
- Add a dated §8 (Decisions) entry.
- State whether every bridged row is now proven. **The human flips `Status:
  shipped`, never this mode.**

No map → the step above is the whole of `reconcile` — tags, `Scenarios:` count, a
dated §8 entry — and the mode says so in its Phase 0 line.

## Verify and hand back

The same sequence every writing mode runs. Run
`python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks` if a map is configured
and `map.checks` is set (the adapter refuses with exit 2 otherwise — that is not a
failed check); then `adapter.py --json verify` if any `commands.*` is configured —
the cited tests must pass under the configured commands, not only under the
ad-hoc mutation runs above; `[]` means nothing was verified: say so, never report
a pass; then `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>`,
always. Hand back what moved, what did not and why. Offer a reading assignment —
the 1–3 `file:line` spots that let the user own the verdict — and leave taking
it to them.

## What this mode refuses to do

- Promote a row without a watched kill.
- Edit a `Then` an existing row already promises — that is a DECISION, not a
  reconciliation.
- Loosen a checker, raise a ceiling, or bump a ratchet to make a run pass.
- Promote a row because a PR merged, an issue closed, or a suite went green.
  Reaching the `Then`'s altitude promotes a row; nothing else does.
