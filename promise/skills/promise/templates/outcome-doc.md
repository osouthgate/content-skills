# <Capability>

Status: draft
Owner: <name>        Last decision: YYYY-MM-DD
Supersedes: —
<!-- Red gate: <sha> <YYYY-MM-DD> — arm writes this as its own header line, outside this comment, when Status becomes building -->

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: <name>, <date> — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** <one line — what is true after this ships>
**Rules:**
- <rule — one line, stated as a fact, verbatim>  → AT-1
- <rule — one line, stated as a fact, verbatim>  → AT-2
**How we'll know:** <the demoable or measurable signal, decided by a human>
**Scenarios:** 2 acceptance rows (§6), 1 worked example (§3).

Agent notes (appended, numbered — never edited into the block above; they
sit under §0 but do NOT count toward its 40-line budget):
1. <example note — a gap, contradiction, or question about a rule above>

## 1. Problem
*(human)*

What breaks today, in current-state terms — the behaviour, not the feature idea.
Evidence: a bug report, a quote, or a file:line.

## 2. Outcome
*(human)*

**After this ships, it is true that:** 2–5 observable statements expanding §0's
outcome line.
**Why we need it:** what it unlocks; what breaks or stays broken without it.
(The how-we'll-know line lives in §0 — one home, no copy here.)

## 3. Worked examples
*(human seeds ≥1, agent extends)*

Named actors, concrete state, expected outcome. Cover at minimum: the happy
path, the undo/reverse path, and any permission or visibility edge the
capability has.

**Ana <takes the primary action>.**
<Ben, under a different condition, gets the expected — and concretely
observable — outcome.>

## 4. Invariants
*(agent derives, human confirms)*

"X must never Y" one-liners. Each carries its enforcement point (constraint /
test / property / proof / file:line) or the flag UNENFORCED — and, where the
guarantee has an edge, a one-line boundary: the condition beyond which it does
not hold. Evidence names its proof strength: example, property or model.
Why — what breaks without it: <one line>

## 5. Mechanism
*(agent)*

The design: what exists today (with file:line evidence), what changes,
reuse-first. Each subsection ends with `Why: <one line>`.
Why — what breaks without it: <one line>

## 6. Acceptance
*(agent drafts, human confirms)*

| #    | Given   | When   | Then   | Altitude   | Row |
|------|---------|--------|--------|------------|-----|
| AT-1 | <given> | <when> | <then> | <altitude> |     |
| AT-2 | <given> | <when> | <then> | <altitude> |     |

Rows carry stable IDs (AT-1, AT-2, …) so §0 rules can cite them; renumbering
breaks the §0 tags, so IDs are append-only. Each row maps to a runnable test
or eval command. `Altitude` is one of `data` / `response` / `perception` /
`judgement` / `sibling` (references/altitude.md) — what the `Then` asserts
on; it is what `reconcile` compares evidence against. The `Row` column stays
empty until a capability map's `agreed` bridge files this scenario; then it
holds that row's id, and one line goes directly under the table, reading
exactly `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of
these scenarios from here on. `` — `bridge_validate.py` errors on a bridged
doc without it. Do not add that line before the bridge.
Why — what breaks without it: <one line>

## 7. Build phases
*(agent)*

Small, ordered, verifiable. Each phase names the acceptance rows it turns
green.
Why — what breaks without it: <one line>

## 8. Decisions
| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|

Decisions may be partially ruled: record the ruling made, by whom, and the
narrowed residual question.

## 9. Open questions
Qn — owner: <name> — BLOCKING | non-blocking
Answers appended inline with a date, never deleted.

## 10. Out of scope
Explicit. Link the one doc that owns each excluded surface.
