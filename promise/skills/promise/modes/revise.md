Read before this: references/slates.md · references/anti-rationalizations.md · outcome-framework.md § The contract · § Section rules · § The framework as a review rubric
Phase 0 line: mode `revise` (say if inferred), framework source, docs home and its source, the doc's current path and `Status:`, whether a map is configured, and whether the project is adopted.
Writes: the existing doc named in the input, in place.

# Revise — evolving an existing outcome doc

The mode that runs most often over a doc's life, and the one where §0 is
most at risk: the doc already exists, so there is no interview protecting
it. Read the doc in full first — never revise from a diff or a summary of
it.

## What you may change without asking

The agent half (§3 remaining examples, §4, §5, §6, §7), the numbered agent
notes, §9 answers (appended with a date, never deleted), and — inside §0
only — each rule's `→ AT-n` / `→ UNTESTED` tag and the `Scenarios:` count.
These two are the only agent-maintained metadata in the block — framework §
The contract. Nothing else in §0.

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
  re-ratify." Never flip status forward yourself, in either direction.
- Doc is `building` and the changed rule carries `→ AT-n` → the acceptance
  row and its committed red test are now wrong. Name the AT-n rows and the
  test files affected. A map is configured and §6 carries a `Row` column →
  also name the map rows affected — the same drift, one layer up, and the
  reason `reconcile` exists.

## Before you write

Self-diff your own revision against the three erosion classes — framework §
The framework as a review rubric: did an OPEN decision become an
assertion; did §0 membership change without confirmation; did operational
content disappear with no stated home.

Re-stamp the test tags against the current §6, then re-count `Scenarios:`
with `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --write-counts`
(it rewrites only that line, and prints old and new).

Then run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and
fix every finding, or say why one stands.

## Close out

Report the diff, not the doc: what changed in the agent half, which §0
changes are pending confirmation, which rules changed tag (including any
that went `→ UNTESTED`), the status consequence, and what you could not
check. Paste §0 inline again — a revision the reviewer can't re-react to in
chat is a revision nobody reviewed.
