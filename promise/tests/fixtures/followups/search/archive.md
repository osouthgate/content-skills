# Channel archiving

Status: draft
Owner: Ben        Last decision: 2026-02-03
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Ben, 2026-02-03 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member can archive a channel so it stops appearing in the sidebar.
**Rules:**
- An archived channel is read-only until it is unarchived.  → AT-1
- Archiving never deletes messages.  → AT-2
**How we'll know:** Priya archives a quiet channel and it drops out of her
sidebar within a minute, with its history still searchable.
**Scenarios:** 2 acceptance rows (§6), 1 worked examples (§3).

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Confirmed archiving is distinct from deleting in every reference product checked.

## 1. Problem

Old, inactive channels crowd the sidebar alongside active ones, so members
scroll past dozens of dead channels to reach the ones they use.

## 2. Outcome

**After this ships, it is true that:**
- A member can archive any channel they are in from its header menu.
- An archived channel leaves every member's sidebar.
- Its message history stays searchable.

**Why we need it:** without it, the only way to declutter the sidebar today
is to leave the channel, which loses access to its history too.

## 3. Worked examples

### Example: Priya archives a quiet channel

Priya opens a channel nobody has posted in for months and selects Archive.
It disappears from her sidebar and every other member's. She later searches
for an old decision in it and the message still comes back.

## 4. Invariants

An archived channel must never accept a new message until it is unarchived.
Enforcement: `channels.ts:203` rejects a send when the channel's archived
flag is set.
Why — what breaks without it: a channel that still accepts messages while
"archived" is not actually archived, just hidden.

## 5. Mechanism

Today every channel a member has joined always renders in the sidebar
(`sidebar.ts:58`). This adds an `archivedAt` field on the channel; the
sidebar query excludes archived channels and the send path checks the same
field. Why: one field read by both paths keeps them from disagreeing.
Why — what breaks without it: two separate archived flags could drift, so a
channel reads as archived in the sidebar but still accepts messages.

## 6. Acceptance

| #    | Given | When | Then |
|------|-------|------|------|
| AT-1 | Priya is in a channel | she archives it | the channel becomes read-only and leaves the sidebar |
| AT-2 | a channel is archived | Ana searches for an old message in it | the message still appears in search results |
Why — what breaks without it: without a table, "acceptance" is a claim with
nothing to point at.

## 7. Build phases

Phase 1 turns AT-1 green: the archived flag, the sidebar filter, the send-path check.
Phase 2 turns AT-2 green: confirming archived channels stay in the search index.
Why — what breaks without it: without phases, both land on day one with
nothing shippable in between.

## 8. Decisions

| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|
| 1 | 2026-02-03 | Archiving is reversible, not permanent. | Ben | Members archive channels they might reopen later; permanent removal is a separate, deliberate action. |

## 9. Open questions

Q1 — owner: Ben — non-blocking: should an archived channel's slot in
`@mentions` autocomplete disappear too? Not decided yet; it still resolves.

## 10. Out of scope

Deleting a channel outright is a separate, irreversible capability, owned by
a future doc. Auto-archiving after inactivity is not in this version.
