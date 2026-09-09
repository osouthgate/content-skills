# Channel muting

Status: draft
Owner: Priya        Last decision: 2026-01-01
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Priya, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member can mute a channel so it stops notifying them.
**Rules:**
- A muted channel never sends a push or a badge count until it is unmuted.  → AT-1, AT-2
- Muting is per member; it never changes what other members see.  → UNTESTED
**How we'll know:** Ana mutes a busy channel and gets zero notifications from it
for a day, then unmutes and notifications resume.
**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Confirmed there is no existing mute primitive to reuse.

## 1. Problem

Every message in a channel notifies every member today, so a busy channel
drowns out quieter ones. Evidence: Ben muted Slack's equivalent feature within
his first week on every busy channel he joined.

## 2. Outcome

**After this ships, it is true that:**
- A member can mute any channel they are in from its header menu.
- A muted channel sends no push notification and no unread badge.
- Muting is reversible and visible only to the member who set it.

**Why we need it:** without it, members leave busy channels entirely rather
than muting them, and lose access to search and history.

## 3. Worked examples

### Example: Ana mutes a busy channel

Ana is in #general, which is noisy. She opens the channel menu and selects
Mute. She sends herself a test message from another account: no push, no
badge. She unmutes; the next message notifies her normally.

### Example: muting is per member

Ana mutes #general. Ben, in the same channel, never muted it. Ben still gets
pushes and badges for #general; Ana gets none. Muting one member's view never
changes another member's.

## 4. Invariants

A muted channel must never push a notification to the member who muted it,
until they unmute it. Enforcement: `notifications.ts:112` checks the mute
table before every send.
Why — what breaks without it: a mute that still pushes is worse than no mute
at all, because the member believes they are protected.

## 5. Mechanism

Today, every channel member is notified on every message (`messages.ts:88`).
This adds a `mutedChannels` join table keyed by (member, channel); the send
path checks it before writing a notification. Why: reuses the existing send
path instead of forking it.
Why — what breaks without it: without a single check point, a second send
path could forget to honour a mute.

## 6. Acceptance

| # | Label | Given | When | Then |
|---|-------|-------|------|------|
| AT-1 | routine | Ana is in a channel | she mutes it | she gets no push or badge from it |
| AT-2 | routine | Ana has muted a channel | she unmutes it | notifications resume immediately |
| AT-3 | routine | Ana has muted a channel | Ben (unmuted) gets a message in it | Ben is still notified normally |
Why — what breaks without it: without a table, "acceptance" is a claim with
nothing to point at.

## 7. Build phases

Phase 1 turns AT-1 and AT-2 green: the mute table and the send-path check.
Phase 2 turns AT-3 green: a regression test that an unmuted member is
unaffected.
Why — what breaks without it: without phases, the red tests all appear on
day one with nothing shippable in between.

## 8. Decisions

| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|
| 1 | 2026-01-01 | Mute state is per member, not per channel. | Priya | Matches how every reference product does it; a shared mute would surprise someone. |

## 9. Open questions

Q1 — owner: Priya — non-blocking: should muting a channel also mute its
threads? Not decided yet; ships without thread-level muting.

## 10. Out of scope

Snoozing (a time-boxed mute) is a separate capability, owned by a future doc.
Notification digests are owned by the digest doc, not this one.
