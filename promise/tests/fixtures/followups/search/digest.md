# Daily digest

Status: draft
Owner: Priya        Last decision: 2026-02-01
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Priya, 2026-02-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member gets a daily digest email summarising channel activity.
**Rules:**
- The digest lists only channels the member can already see.  → AT-1
- A member can turn the digest off from their notification settings.  → AT-2
**How we'll know:** Ana receives a daily digest email every morning for a week,
and Ben turns his off and gets nothing the next day.
**Scenarios:** 2 acceptance rows (§6), 1 worked examples (§3).

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Confirmed there is no existing digest primitive to reuse.

## 1. Problem

Members miss activity in quiet channels because nothing surfaces it between
visits. Evidence: Ana asked twice in one week whether she had missed anything.

## 2. Outcome

**After this ships, it is true that:**
- A member gets one digest email per day summarising unread channels.
- The digest never lists a channel the member cannot already see.
- A member can turn the digest off from notification settings.

**Why we need it:** without it, members either over-check quiet channels or
miss activity in them entirely.

## 3. Worked examples

### Example: Ana gets her digest

Ana is subscribed to three channels. The nightly digest job runs. The next
morning she gets one email listing unread messages in all three.

## 4. Invariants

A digest must never list a channel the recipient cannot see at send time.
Enforcement: `digest.ts:41` re-checks membership right before rendering, not
at subscribe time.
Why — what breaks without it: a stale membership check would leak channel
names and message previews to someone who left or was removed.

## 5. Mechanism

Today nothing summarises channel activity between visits (`notifications.ts`
only handles live pushes). This adds a nightly job that reads each member's
unread counts and renders one email per member. Why: reuses the existing
unread-count table instead of a new activity log.
Why — what breaks without it: without a single job, two send paths could
double-send or disagree on what counts as "unread".

## 6. Acceptance

| #    | Given | When | Then |
|------|-------|------|------|
| AT-1 | Ana is subscribed to 3 channels | the daily digest job runs | Ana receives a daily digest email every morning |
| AT-2 | Ben is receiving the digest | he opens notification settings and turns it off | Ben can unsubscribe from the digest at any time |
Why — what breaks without it: without a table, "acceptance" is a claim with
nothing to point at.

## 7. Build phases

Phase 1 turns AT-1 green: the nightly job and the email template.
Phase 2 turns AT-2 green: the notification-settings toggle.
Why — what breaks without it: without phases, both land on day one with
nothing shippable in between.

## 8. Decisions

| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|
| 1 | 2026-02-01 | The digest is opt-out, not opt-in. | Priya | Most members want it; opt-in would mean most never see one. |

## 9. Open questions

Q1 — owner: Priya — non-blocking: should the digest be configurable to
weekly? Not decided yet; ships daily-only.

## 10. Out of scope

A real-time activity feed is a separate capability, owned by a future doc.
Per-channel digest frequency is not in this version.
