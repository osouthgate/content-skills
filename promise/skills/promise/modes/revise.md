Read before this: references/slates.md · references/anti-rationalizations.md · outcome-framework.md § The contract · § Section rules · § The framework as a review rubric
Phase 0 line: mode `revise` (say if inferred), framework source, docs home and its source, the doc's current path and `Status:`, whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: the existing doc named in the input, in place.

# Revise — evolving an existing outcome doc

The mode that runs most often over a doc's life, and the one where §0 is
most at risk: the doc already exists, so there is no interview protecting
it. Read the doc in full first — never revise from a diff or a summary of
it.

## What you may change without asking

The agent half (§3 remaining examples, §4, §5, §7), the numbered agent
notes, §9 answers (appended with a date, never deleted), and — inside §0
only — each rule's `→ AT-n` / `→ UNTESTED` tag and the `Scenarios:` count.
These two are the only agent-maintained metadata in the block — framework §
The contract. Nothing else in §0.

§6 too, but only while it carries no `Row` ids and no `Snapshot taken at`
line. Once either exists the bridge has happened and §6 is a snapshot
(framework § Lifecycle): never edit the table; propose the change as a map
change through `intake` or `reconcile` instead. A `Then` cell edited here
drifts from the map silently, and `bridge_validate.py` reports that drift
as `THEN_NOT_IN_MAP` with the map as the suspect.

## Filling a thin draft

The doc has `Depth: thin` (a `draft` with the human half only; modes/new.md
§ Thin draft). The agent half is written here, on request. First check the
human half: an outcome line, at least one confirmed rule, a decided
how-we'll-know and one seed example. Anything missing → ask for it the way
`new` does, and keep the doc thin until it is there; say which part is
missing. When it is all there, follow modes/new.md § Draft the agent half
for §3–§7, then delete the `Depth: thin` line in the same edit. Log the
fill in §8 with a date.

## What requires the human, every time

The §0 outcome line, any rule's text, and how-we'll-know. Adding a rule,
deleting one, splitting one into two, and "tightening the wording" are all
changes to the block. Propose them as a numbered note, or — for the outcome
line and how-we'll-know only — a candidate slate: references/slates.md.
**Rules are never slated:** verbatim confirmation only, and the block stays
untouched until the user confirms the exact text.

## Status consequences — state before the user answers, not after

- Doc is `draft` → confirmed §0 changes apply in place; log the change in
  §8 with a date.
- Doc is `agreed` or later → a §0 change un-ratifies it. Say so plainly
  *before* the change: "this drops the doc back to `draft` until you
  re-ratify." Where §6 carries `Row` ids, also name the map rows the
  changed rule's AT-n tags point at — they were filed from that rule, and
  a `proven` row proven against the earlier wording is drift `reconcile`
  will have to re-check. Never flip status forward yourself, in either
  direction.
- Doc is `building` or later and the changed rule carries `→ AT-n` → the
  acceptance row and its committed red test are now wrong, green or red.
  Name the AT-n rows and the test files affected. A map is configured and
  §6 carries `Row` ids → also name the map rows affected — the same drift,
  one layer up, and the reason `reconcile` exists.

## Before you write

Self-diff your own revision against the three erosion classes — framework §
The framework as a review rubric: did an OPEN decision become an
assertion; did §0 membership change without confirmation; did operational
content disappear with no stated home.

A map is configured (orient's `mapUsable`) and `Status:` is past `draft` →
run `python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc> --json`
before the first edit, as a baseline, and again after the last. An error
(`SNAPSHOT_LINE_MISSING`, `ROW_MISSING`, `ROW_ID_FORMAT`) or a
`THEN_NOT_IN_MAP` present only in the after-run is your edit to the
snapshot: revert it and route the change through `intake` or `reconcile`. A
finding present in both runs is map drift: name it in the close-out, never
fix it in §6. A doc at `agreed` whose §6 has no `Row` cell at all and no
snapshot line has not been armed; report those findings as "run `arm`", not
as drift or as a finding against the doc.

Re-stamp the test tags against the current §6, then re-count `Scenarios:`
with `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --write-counts`
(it rewrites only that line, and prints old and new).

Then run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and
fix every finding, or say why one stands. The lint checks shape only. It
does not check: that §3 holds at least one example, that §9 questions carry
an owner and a BLOCKING/non-blocking flag, that §4 invariants name an
enforcement point or UNENFORCED, that `Last decision:` is a real date, or
whether a filled Why line, example or mechanism is *true* — read those
yourself before close-out.

## Close out

Report the diff, not the doc: what changed in the agent half, which §0
changes are pending confirmation, which rules changed tag (including any
that went `→ UNTESTED`), the status consequence, any `bridge_validate.py`
finding new since the baseline run, and what you could not check. Paste §0
inline again — a revision the reviewer can't re-react to in chat is a
revision nobody reviewed.
