# The Outcome Framework — one doc per capability

A document format and contract for capability docs that are the **input** to design and
planning, not the record of it. The human's decisions go in verbatim and first; the
agent's job is to find contradictions in them, propose the mechanism, and build.

Pairs with the `/outcome` skill (SKILL.md beside this file), which produces and evolves
docs in this shape. This file is the single source of truth for the template, contract,
and lifecycle — the skill defers to it wherever they disagree.

---

## Why this exists

Most planning docs are the agent's output rather than the agent's input. A human writes
intent, an agent expands it into a plan, a reviewer reviews the expansion — a paraphrase
of a decision, several removes from the decision itself. Three failures fall out of that
loop, all observed in practice:

1. **Meaning drifts silently.** A one-line rule about *validity* comes back as a section
   about *visibility*. No diff, no flag.
2. **Volume replaces decisions.** Generating a plan is cheap, so a new plan appears
   whenever a question comes up. A hundred onboarding plans; three connector plans that
   should be one. "Death by plan."
3. **The hard question gets deferred to the model.** The agent happily writes a
   wow-moment section without anyone having decided what the wow moment is.

The fix is structural, not stylistic: **the human's decisions go into the doc verbatim
and first; the agent's job is to find contradictions in them, propose the mechanism,
and build.**

---

## The contract

1. **The doc has two halves.**
   - **Human half** — §0 TLDR (outcome line, rules, how-we'll-know), Problem, Outcome,
     and at least one worked example. Written (or dictated and confirmed line-by-line)
     by a human. The agent may never rewrite, expand, or paraphrase inside it. If the
     agent thinks a rule is wrong, incomplete, or contradicts another rule, it appends
     a **numbered note below the block**.
     An agent-extracted candidate block (e.g. quotes pulled from a transcript) is marked
     **`pending verbatim confirmation`** and is FROZEN from that moment — no agent may
     add, remove, or reword entries in any later revision; only human confirmation
     changes it. (Field finding: an unfrozen candidate block changed membership in
     every revision without anyone deciding it.)
   - **Agent half** — Invariants, remaining worked examples, Mechanism, Acceptance,
     Build phases. The agent drafts these *from* the human half; the human strikes
     and corrects.
2. **One doc per capability.** A sibling doc covering overlapping surface is a bug:
   merge and delete, don't cross-reference. On supersede, **delete** the old doc —
   "if we can't easily find it, we probably don't have it" cuts both ways.
3. **The 60-second standard, with numbers.** §0 alone — ≤ 40 lines, one screen — must
   let a reader disagree with something specific in 60 seconds. The whole human half
   (§0–§2 plus the seed example) is ≤ 150 lines. If a reader needs more than §0 to
   object, the doc failed, whatever else it contains. (§5 Mechanism is deliberately
   uncapped — see the length-budget rule.)
4. **Every agent-half section carries one line: "Why — what breaks without it."**
   If that line can't be written, cut the section. (The founder-doc test.)
5. **Worked examples before prose.** Every rule ships with at least one scenario in
   ABC form — named actors, concrete state, expected outcome. A rule that can't be
   expressed as a scenario isn't a rule yet.
6. **Acceptance criteria are scenarios, not adjectives.** Given / When / Then, one row
   per scenario, each row mappable to a runnable test.
7. **Outcomes are decided, not generated.** The "how we'll know" line in §0 is a human
   decision. The agent may propose candidates; it may not fill the section in.

---

## The template

```markdown
# <Capability>

Status: draft | agreed | building | shipped | superseded-by <doc>
Owner: <name>        Last decision: YYYY-MM-DD
Supersedes: <docs deleted when this doc was agreed — or "—">

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: <name>, <date> — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** <one line — what is true after this ships, in the owner's words>
**Rules:**
- One-line rules, verbatim. This is their ONE home — there is no other rules section.  → AT-1, AT-4
- Schema constraints count as rules; when code intent and schema disagree, schema wins.  → UNTESTED
**How we'll know:** the demoable or measurable signal. Decided here, by a human.
**Scenarios:** <N> acceptance rows (§6), <M> worked examples (§3).

The trailing `→ AT-n` / `→ UNTESTED` tag on each rule is agent-maintained
test-mapping metadata — the ONLY thing an agent may edit inside this block,
and only the tag, never the rule text. Everything else is frozen.

Agent notes (appended, numbered — never edited into the block above):
1. <contradiction / gap / question about a rule>

## 1. Problem
*(human)*

What breaks today, in current-state terms — the behaviour, not the feature idea.
Evidence: an incident, a quote, or a file:line.

## 2. Outcome
*(human)*

**After this ships, it is true that:** 2–5 observable statements expanding §0's
outcome line.
**Why we need it:** what it unlocks; what breaks or stays broken without it.
(The how-we'll-know line lives in §0 — one home, no copy here.)

## 3. Worked examples
*(human seeds ≥1, agent extends)*

Named actors, concrete state, expected outcome. Cover at minimum:
the happy path, the disconnect/undo path, the permission-removal path.

    Ana connects, full-syncs A, B, C.
    Ben connects. Prior sync exists → ACL probe returns B, C, D.
    Expected: no full sync. B, C = edge write only. Zero content fetches. D full-syncs.

## 4. Invariants
*(agent derives, human confirms)*

"X must never Y" one-liners. Each carries its enforcement point
(constraint / test / file:line) or the flag UNENFORCED — and, where the guarantee
has an edge, a one-line **boundary**: the condition beyond which it does not hold
("cannot prevent X across two scopes; that is user error, not a violation").
An invariant without a boundary claim overpromises.
Why — what breaks without it: <one line>

## 5. Mechanism
*(agent)*

The design: what exists today (with file:line evidence), what changes, reuse-first.
Each subsection ends with `Why: <one line>`.
Why — what breaks without it: <one line>

## 6. Acceptance
*(agent drafts, human confirms)*

| #    | Given | When | Then |
|------|-------|------|------|
| AT-1 | ...   | ...  | ...  |
Rows carry stable IDs (AT-1, AT-2, …) so §0 rules can cite them; renumbering
breaks the §0 tags, so IDs are append-only. Each row maps to a runnable test or
eval command. For capabilities about access, permissions, or visibility, phrase
rows as user questions:
Given <role> | When they ask "<question>" | Then answered / refused / partially answered.

## 7. Build phases
*(agent)*

Small, ordered, verifiable. Each phase names the acceptance rows it turns green.

## 8. Decisions
| # | Date | Decision | Owner | Why |
Decisions may be **partially ruled**: record the ruling made, by whom, and the
narrowed residual question ("mechanism agreed by both reviewers; remaining product
question: …"). Narrowing is progress — a register that only knows OPEN/answered
loses it.

## 9. Open questions
Qn — owner: <name> — BLOCKING | non-blocking
Answers appended inline with a date, never deleted.

## 10. Out of scope
Explicit. Link the one doc that owns each excluded surface.
```

---

## Section rules

- **Contents line + bare headings.** The doc opens with a one-line `Contents:` run of
  anchor links so any markdown viewer (GitHub, VS Code preview) jumps straight to a
  section. For the anchors to resolve, headings stay exactly `## <n>. <Name>` — the
  ownership/protection annotations live on the italic line *below* the heading, never
  inside it. An agent that decorates a heading breaks every link to it.
- **§0 TLDR is the protected block and the doc's front door.** ≤ 40 lines, one screen:
  outcome line, the rules as bullets, how-we'll-know, scenario count. A busy reader
  reads §0 in 60 seconds and can disagree with something specific — that is the
  section's acceptance test. **The rules have exactly one home.** A §0 that duplicated
  a rules section elsewhere would drift from it — the exact "meaning drifts silently"
  failure this framework exists to prevent. The agent treats §0 as read-only and
  appends numbered notes below, with one carve-out: the trailing `→ AT-n` /
  `→ UNTESTED` test tag on each rule is agent-maintained metadata (mirroring
  UNENFORCED on invariants) — only the tag, never the rule text. A rule tagged
  UNTESTED on a doc moving to `agreed` is a finding.
- **§1 Problem** names current behaviour, not the feature. "The watch loop polls every
  15 minutes whether or not anything changed" — not "we need webhooks".
- **§2 Outcome** is the section that makes this framework outcome-driven rather than
  task-driven. *True-after* forces observability; *why* forces the founder-doc test.
  The third prompt, *how-we'll-know*, lives in §0 (one home) — §2 expands, never
  restates, the §0 outcome line.
- **The success signal can rule an open decision.** Once how-we'll-know is chosen,
  re-read every OPEN decision (§8/§9) against it: an option under which the signal
  cannot be staged has been ruled OUT by the signal itself. Record the narrowing in
  the §8 table stating the implication, and leave ratification with the human — this
  is the existing partially-ruled convention applied in the other direction
  (signal → mechanism, not mechanism → signal). Worked example: a chosen signal of
  *"two accounts in the same workspace ask the same question and get different
  answers"* is unstageable under a data model that maps a CRM's shared records to
  workspace scope — so it selected owner-level scoping and narrowed a BLOCKING
  question without anyone arguing the mechanism.
- **§3 Worked examples** are the reading surface. If a reviewer only reads §0, §2, §3,
  they should be able to catch a wrong design.
- **§4 Invariants** is where an invariants-analysis pass plugs in (a dedicated skill if
  you have one, manual otherwise): standing invariants of the touched area + new ones
  this work introduces, each with enforcement point or UNENFORCED. Four useful moves:
  the uniqueness claim, two-concepts-one-knob, fail-open-or-closed, schema-wins.
- **§5 Mechanism** carries file:line evidence for every current-state claim,
  reuse-first, and "existing primitive considered / why insufficient" for anything
  new — without mandatory tables and diagrams. Add a diagram only when it replaces
  prose, not alongside it. Four disciplines borrowed from the best external specs
  (block/buzz `remote-agents.md` is the reference exemplar):
  - **Citation pin**: state once, near the top, the commit every file:line was
    verified against. Unpinned refs rot silently; pinned ones rot visibly.
  - **Design vs description**: any passage describing behavior that does not exist
    yet must say so and name what it gates (the Known-Defects pattern). A spec that
    reads uniformly as fact when half of it is intent is lying by tone.
  - **Correspondence table** (for build-heavy docs): spec concept → code symbol,
    with honest "*to be added*" rows.
  - **Considered-and-rejected with receipts**: alternatives carry the concrete reason
    they lose, not just their name.
- **§6 Acceptance** is the red-test gate: when the doc moves to `building`, the
  acceptance rows become failing tests committed RED first. Rows carry stable,
  append-only IDs (AT-n) — they are what §0's test tags cite. For capabilities about
  access, permissions, or visibility, rows are phrased as user questions —
  `Given <role> | When they ask "<question>" | Then answered / refused / partially
  answered` — because that is the form the capability will actually be exercised in,
  and the form a non-engineer can propose test cases in without reading code.
- **Length budget — it binds the review surface, not the whole doc.** §0 ≤ 40 lines.
  The human half (§0–§2 + seed example) ≤ 150 lines. §1–§3 one screen each. The review
  surface (§0–§4, §8, §9) must together stay readable in one sitting. §5 Mechanism may
  run long **when it is information-dense** — a 1,700-line spec with a rationale on
  every rule and zero filler beats two thin docs (the buzz exemplar would be worse
  split). The filler detector is buzz's own rule: *the complexity budget is spent in
  the document, not in the code* — every extra paragraph must be buying simplicity in
  the implementation. If §5 is long AND the capability has two separable outcomes,
  split by outcome, not by layer.

---

## Lifecycle

```
draft ──(human half complete + agent notes resolved)──► agreed
agreed ──(acceptance rows committed RED)──► building
building ──(rows green + shipped)──► shipped
any ──► superseded-by <doc>   (and the superseded doc is DELETED)
```

- **One docs folder is the one home** (e.g. `docs/designs/`). Outcome docs live there.
  Legacy plan folders receive **no new docs** — the build phases live inside the
  outcome doc (§7). Existing plans migrate into their capability's outcome doc as
  they are touched, then get deleted.
- Status lives in the doc header, not the folder. Folder=status is retired.
- A doc in `draft` with unresolved BLOCKING questions cannot move to `agreed`.
- `shipped` docs keep §0 (TLDR — outcome, rules, how-we'll-know), §2 (outcome detail),
  §4 (invariants) as the living record; §7 (build phases) may be pruned.

---

## The framework as a review rubric

When the capability doc is authored elsewhere (another agent, another repo, a pasted
pack), the framework doubles as the review standard. A conforming review checks:

1. **Claims vs code** — every current-state claim spot-verified with file:line; an
   invented identifier or stale claim is a finding, not a nitpick.
2. **Human half integrity** — is there a §0 verbatim block; is it confirmed or pending;
   did its membership change since the last revision without human confirmation? (Test
   tags may change; rule text may not.)
3. **Decision erosion** — did any OPEN decision become an assertion between revisions?
   Decisions are ratified by humans, never resolved by drafting.
4. **Deletion without disposition** — did operational content vanish between revisions
   with no stated home (appendix, companion doc, archive)? Compression must name where
   the content went.
5. **Framework shape** — §0 TLDR present and ≤ 40 lines, worked examples present,
   Given/When/Then acceptance present, every §0 rule carries acceptance-row IDs or
   **UNTESTED** (an UNTESTED rule on an `agreed`+ doc is a finding), invariants carry
   enforcement points or UNENFORCED, decisions have owners + blocking flags,
   disposition names what gets deleted, evidence paths resolvable by any reader.
6. **Depth, not just shape** — invariants *argued* (mechanism + boundary), not listed;
   evidence pinned to a commit; design-vs-description flagged wherever behavior doesn't
   exist yet; alternatives rejected with receipts. A doc can have every section present
   and still be shallow — shape checks alone won't catch it.
7. **Outcome present even in mechanism-heavy specs** — a spec with superb invariants
   and zero "why this capability / what's true after" fails the founder-doc test at
   the capability level, however good its per-rule rationale is. At minimum, the why
   is summarized in place with a link to the doc that owns it.
8. **Signal vs open decisions** — does the how-we'll-know line contradict, or
   silently resolve, any OPEN decision? An outcome that no OPEN decision can deliver
   is either the wrong outcome or a decision nobody noticed making. If the signal
   rules an option out, that narrowing belongs in the decisions table, not in
   anyone's head.

Review findings are delivered as a numbered, paste-ready feedback block **inline in
chat** (files may be unreachable across agent/app boundaries), most severe first, each
finding actionable without this conversation.

---

## Design decisions of the framework itself

The framework eats its own dog food — a compact register of its load-bearing choices:

| # | Decision | Why |
|---|----------|-----|
| F1 | One doc per capability — the outcome doc IS the design and the plan | Kills proliferation at the root; exactly one place to look |
| F2 | Interview-first elicitation; rules enter §0 only after verbatim line-by-line confirmation | Makes the validity→visibility class of drift structurally impossible |
| F3 | §0 TLDR leads every doc and IS the protected block; there is no separate rules section (moved, not copied) | A reader must be able to STOP after one screen; a copy would drift from the original — the exact silent-drift failure the framework prevents |
| F4 | How-we'll-know is a forced choice from a verbatim candidate slate; placeholders banned (no pick ⇒ doc stays `draft` with a BLOCKING question); the chosen signal is re-read against every OPEN decision | A blank in a file is indistinguishable from a decision at review time; and a signal can silently select a mechanism — narrowings must be recorded, not discovered |
