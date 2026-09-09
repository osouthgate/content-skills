# <Capability>

Status: draft
Owner: <name>        Last decision: YYYY-MM-DD
Supersedes: —

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
**Scenarios:** 2 acceptance rows (§6), 1 worked examples (§3).

Exactly two things inside this block are agent-maintained metadata, and an
agent may edit ONLY these two: the trailing `→ AT-n` / `→ UNTESTED` tag on
each rule (never the rule text), and the `Scenarios:` counts. Everything
else — outcome line, rule text, how-we'll-know — is frozen and changes only
by human confirmation.

Agent notes (appended, numbered — never edited into the block above):
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
path, the disconnect/undo path, the permission-removal path.

**Ana <takes the primary action>.**
<Ben, under a different condition, gets the expected — and concretely
observable — outcome.>

## 4. Invariants
*(agent derives, human confirms)*

"X must never Y" one-liners. Each carries its enforcement point (constraint /
test / file:line) or the flag UNENFORCED — and, where the guarantee has an
edge, a one-line boundary: the condition beyond which it does not hold.
Why — what breaks without it: <one line>

## 5. Mechanism
*(agent)*

The design: what exists today (with file:line evidence), what changes,
reuse-first. Each subsection ends with `Why: <one line>`.
Why — what breaks without it: <one line>

## 6. Acceptance
*(agent drafts, human confirms)*

| #    | Given   | When   | Then   | Row |
|------|---------|--------|--------|-----|
| AT-1 | <given> | <when> | <then> |     |
| AT-2 | <given> | <when> | <then> |     |

Rows carry stable IDs (AT-1, AT-2, …) so §0 rules can cite them; renumbering
breaks the §0 tags, so IDs are append-only. Each row maps to a runnable test
or eval command. The `Row` column is optional: empty until a capability
map's `agreed` bridge files this scenario, then it holds that row's id.
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
