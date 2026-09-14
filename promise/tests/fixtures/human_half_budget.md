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
- Muting is per member; it never changes what other members see.  → AT-3
- Mute state survives sign-out and a new device.  → UNTESTED
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
Filler line 1 of the padding used to push the human half past its line budget.
Filler line 2 of the padding used to push the human half past its line budget.
Filler line 3 of the padding used to push the human half past its line budget.
Filler line 4 of the padding used to push the human half past its line budget.
Filler line 5 of the padding used to push the human half past its line budget.
Filler line 6 of the padding used to push the human half past its line budget.
Filler line 7 of the padding used to push the human half past its line budget.
Filler line 8 of the padding used to push the human half past its line budget.
Filler line 9 of the padding used to push the human half past its line budget.
Filler line 10 of the padding used to push the human half past its line budget.
Filler line 11 of the padding used to push the human half past its line budget.
Filler line 12 of the padding used to push the human half past its line budget.
Filler line 13 of the padding used to push the human half past its line budget.
Filler line 14 of the padding used to push the human half past its line budget.
Filler line 15 of the padding used to push the human half past its line budget.
Filler line 16 of the padding used to push the human half past its line budget.
Filler line 17 of the padding used to push the human half past its line budget.
Filler line 18 of the padding used to push the human half past its line budget.
Filler line 19 of the padding used to push the human half past its line budget.
Filler line 20 of the padding used to push the human half past its line budget.
Filler line 21 of the padding used to push the human half past its line budget.
Filler line 22 of the padding used to push the human half past its line budget.
Filler line 23 of the padding used to push the human half past its line budget.
Filler line 24 of the padding used to push the human half past its line budget.
Filler line 25 of the padding used to push the human half past its line budget.
Filler line 26 of the padding used to push the human half past its line budget.
Filler line 27 of the padding used to push the human half past its line budget.
Filler line 28 of the padding used to push the human half past its line budget.
Filler line 29 of the padding used to push the human half past its line budget.
Filler line 30 of the padding used to push the human half past its line budget.
Filler line 31 of the padding used to push the human half past its line budget.
Filler line 32 of the padding used to push the human half past its line budget.
Filler line 33 of the padding used to push the human half past its line budget.
Filler line 34 of the padding used to push the human half past its line budget.
Filler line 35 of the padding used to push the human half past its line budget.
Filler line 36 of the padding used to push the human half past its line budget.
Filler line 37 of the padding used to push the human half past its line budget.
Filler line 38 of the padding used to push the human half past its line budget.
Filler line 39 of the padding used to push the human half past its line budget.
Filler line 40 of the padding used to push the human half past its line budget.
Filler line 41 of the padding used to push the human half past its line budget.
Filler line 42 of the padding used to push the human half past its line budget.
Filler line 43 of the padding used to push the human half past its line budget.
Filler line 44 of the padding used to push the human half past its line budget.
Filler line 45 of the padding used to push the human half past its line budget.
Filler line 46 of the padding used to push the human half past its line budget.
Filler line 47 of the padding used to push the human half past its line budget.
Filler line 48 of the padding used to push the human half past its line budget.
Filler line 49 of the padding used to push the human half past its line budget.
Filler line 50 of the padding used to push the human half past its line budget.
Filler line 51 of the padding used to push the human half past its line budget.
Filler line 52 of the padding used to push the human half past its line budget.
Filler line 53 of the padding used to push the human half past its line budget.
Filler line 54 of the padding used to push the human half past its line budget.
Filler line 55 of the padding used to push the human half past its line budget.
Filler line 56 of the padding used to push the human half past its line budget.
Filler line 57 of the padding used to push the human half past its line budget.
Filler line 58 of the padding used to push the human half past its line budget.
Filler line 59 of the padding used to push the human half past its line budget.
Filler line 60 of the padding used to push the human half past its line budget.
Filler line 61 of the padding used to push the human half past its line budget.
Filler line 62 of the padding used to push the human half past its line budget.
Filler line 63 of the padding used to push the human half past its line budget.
Filler line 64 of the padding used to push the human half past its line budget.
Filler line 65 of the padding used to push the human half past its line budget.
Filler line 66 of the padding used to push the human half past its line budget.
Filler line 67 of the padding used to push the human half past its line budget.
Filler line 68 of the padding used to push the human half past its line budget.
Filler line 69 of the padding used to push the human half past its line budget.
Filler line 70 of the padding used to push the human half past its line budget.
Filler line 71 of the padding used to push the human half past its line budget.
Filler line 72 of the padding used to push the human half past its line budget.
Filler line 73 of the padding used to push the human half past its line budget.
Filler line 74 of the padding used to push the human half past its line budget.
Filler line 75 of the padding used to push the human half past its line budget.
Filler line 76 of the padding used to push the human half past its line budget.
Filler line 77 of the padding used to push the human half past its line budget.
Filler line 78 of the padding used to push the human half past its line budget.
Filler line 79 of the padding used to push the human half past its line budget.
Filler line 80 of the padding used to push the human half past its line budget.
Filler line 81 of the padding used to push the human half past its line budget.
Filler line 82 of the padding used to push the human half past its line budget.
Filler line 83 of the padding used to push the human half past its line budget.
Filler line 84 of the padding used to push the human half past its line budget.
Filler line 85 of the padding used to push the human half past its line budget.
Filler line 86 of the padding used to push the human half past its line budget.
Filler line 87 of the padding used to push the human half past its line budget.
Filler line 88 of the padding used to push the human half past its line budget.
Filler line 89 of the padding used to push the human half past its line budget.
Filler line 90 of the padding used to push the human half past its line budget.
Filler line 91 of the padding used to push the human half past its line budget.
Filler line 92 of the padding used to push the human half past its line budget.
Filler line 93 of the padding used to push the human half past its line budget.
Filler line 94 of the padding used to push the human half past its line budget.
Filler line 95 of the padding used to push the human half past its line budget.
Filler line 96 of the padding used to push the human half past its line budget.
Filler line 97 of the padding used to push the human half past its line budget.
Filler line 98 of the padding used to push the human half past its line budget.
Filler line 99 of the padding used to push the human half past its line budget.
Filler line 100 of the padding used to push the human half past its line budget.
Filler line 101 of the padding used to push the human half past its line budget.
Filler line 102 of the padding used to push the human half past its line budget.
Filler line 103 of the padding used to push the human half past its line budget.
Filler line 104 of the padding used to push the human half past its line budget.
Filler line 105 of the padding used to push the human half past its line budget.
Filler line 106 of the padding used to push the human half past its line budget.
Filler line 107 of the padding used to push the human half past its line budget.
Filler line 108 of the padding used to push the human half past its line budget.
Filler line 109 of the padding used to push the human half past its line budget.
Filler line 110 of the padding used to push the human half past its line budget.
Filler line 111 of the padding used to push the human half past its line budget.
Filler line 112 of the padding used to push the human half past its line budget.
Filler line 113 of the padding used to push the human half past its line budget.
Filler line 114 of the padding used to push the human half past its line budget.
Filler line 115 of the padding used to push the human half past its line budget.

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

| #    | Given | When | Then | Altitude |
|------|-------|------|------|----------|
| AT-1 | Ana is in a channel | she mutes it | she gets no push or badge from it | perception |
| AT-2 | Ana has muted a channel | she unmutes it | notifications resume immediately | perception |
| AT-3 | Ana has muted a channel | Ben (unmuted) gets a message in it | Ben is still notified normally | perception |
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

Snoozing (a time-boxed mute) is a separate capability, owned by
[Channel snoozing](channel-snoozing.md); notification digests by
[Notification digests](notification-digests.md). Neither is written yet, and
this doc does not wait for either.
