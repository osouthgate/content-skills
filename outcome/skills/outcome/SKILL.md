---
name: outcome
description: |
  SUPERSEDED by the `promise` plugin (same framework, seven modes). If `/promise` is
  available in this session, use it instead of this skill.
  Turn a requirement/idea/request/transcript into ONE outcome doc per capability using
  the Outcome Framework (outcome-framework.md bundled beside this skill): human half
  verbatim first (§0 TLDR — outcome line, rules as bullets, how-we'll-know — then
  problem and outcome detail), then the agent half (invariants, worked examples,
  mechanism, Given/When/Then acceptance with AT-n IDs, build phases). Use when the
  user says "/outcome", "outcome doc for X", "design this", "plan this", "spec this",
  "write a plan/design for X", or hands over a braindump/transcript/ticket to
  structure. Also: "review this doc/pack" against the framework rubric with
  code-verified feedback for another agent (review mode), "merge these docs"
  (capability consolidation), and "arm <doc>" (agreed→building red-test transition).
---

# /outcome

Produce or evolve **the one doc for a capability** — `<your docs dir>/<capability>.md`
in the Outcome Framework shape. The framework doc is the single source of truth for the
template, contract, and lifecycle: **read it first, every run.** It lives at
`outcome-framework.md` in this skill's directory; if your project keeps its own copy
(e.g. `docs/how-to/outcome-framework.md`), the project copy wins. Do not duplicate or
drift from its template; if the framework and this skill disagree, the framework wins.

You produce the doc up to `draft` (or run a transition). You do not implement the feature.

## Modes

| Invocation | Mode |
|---|---|
| `/outcome <idea/ticket/transcript>` | **new** — create a doc (default) |
| `/outcome revise <doc> ...` | **revise** — evolve an existing outcome doc |
| `/outcome review <doc/URL/paste>` | **review** — apply the framework as a rubric to a doc authored elsewhere; emit paste-ready feedback |
| `/outcome merge <docs...>` | **merge** — consolidate overlapping docs into one, delete the rest |
| `/outcome arm <doc>` | **arm** — `agreed → building`: acceptance rows become red tests |

Mode detection: if the input is a substantial existing document (especially one authored
by another agent) and the user asks to review/critique/give feedback, use **review** —
don't force the new-doc interview onto someone else's draft.

## Phase 0 — Orient

Read the framework doc. State in one line which mode you're in and which capability
this is about.

## Phase 1 — Elicit the human half (never skip, never draft ahead of it)

The human half is §0 TLDR (outcome line, rules, how-we'll-know, scenario count), §1
Problem, §2 Outcome, and one seed worked example. Budgets: §0 ≤ 40 lines; the whole
human half ≤ 150 lines.

- **Interview-first.** Ask for them in the user's own words — six lines is enough. Ask the
  three prompts explicitly: *what is true after this ships* (§0 outcome line, expanded in
  §2), *why do we need it* (§2), *how will we know* (§0 — the user's decision; never fill
  it in).
- **How-we'll-know is a forced choice, never a blank.** Elicit it as ONE question
  with 3–4 candidates, each written **verbatim as it would appear in §0** — not as a
  description of a kind of signal. Label each candidate with its kind: (a) a test that
  flips red→green, (b) a demo someone watches, (c) a number in prod that must hold at a
  value, (d) a claim we can now make to a customer. Call out the anti-pattern in the
  options: "the acceptance tests pass" duplicates §6 and decides nothing new — §0's
  signal should buy something §6 doesn't. **Never write a placeholder into the doc** — a
  blank in a file is indistinguishable from a decision at review time and survives to
  `agreed`. If the user won't pick, the doc stays `draft` with the question logged
  BLOCKING in §9.
- **Once the signal is chosen, re-read every OPEN decision against it** (framework rule:
  the success signal can rule an open decision). An option under which the signal cannot
  be staged has been ruled out — record the narrowing in §8 with the implication stated;
  ratification stays with the human.
- **Braindump/transcript input:** extract candidate rules and the candidate outcome, then
  present them back **line by line for verbatim confirmation**. Only confirmed lines enter
  §0, exactly as confirmed. Unconfirmed material becomes agent notes or open questions.
- **The protected block.** Once written, §0 is read-only to you and every future agent —
  with one carve-out: the trailing `→ AT-n` / `→ UNTESTED` test tag on each rule is
  agent-maintained metadata you keep current as §6 rows change; only the tag, never the
  rule text. Disagreements, gaps, and contradictions become numbered **agent notes below
  the block** — never edits inside it.
- **Keep the confirmation sheet small and staged.** One screen. If the source material
  is large, confirm the ~10 most load-bearing lines first; the rest can follow in later
  passes. A 40-item sheet doesn't get answered (field finding).
- **A pending sheet does not block review work.** If the user redirects to reviewing,
  iterating with another agent, or anything else before answering, do that work — the
  human half stays pending, and you re-surface the *open remainder* compactly (never
  re-ask answered items, never repeat the full sheet) at the next natural decision
  point. Only drafting the agent half of a NEW doc waits on the human half.
- If the user can't yet state the outcome or rules, stop. That's the finding: the
  capability isn't ready for a doc. Offer to help them think it through conversationally —
  but write nothing to the docs directory.

## Phase 2 — Capability hunt (one doc per capability)

Before creating anything, search the docs directory (and any legacy plan folders) for
overlapping surface. If overlap exists:

- Propose **merge-and-delete** — name the surviving doc, the docs to fold in, and the docs
  to delete. A sibling doc is a bug, not a cross-reference target.
- Migrate any still-live content from touched legacy plan docs into the outcome doc's §7,
  then propose deleting the plan file. Legacy plan folders receive no new docs.
- Wait for the user's yes before deleting anything.

## Phase 3 — Draft the agent half

Grounded in code, from the human half:

- **§3 Worked examples:** extend the user's seed to cover at minimum the happy path, the
  disconnect/undo path, and the permission-removal path — ABC form, named actors, concrete
  state, expected outcome. Show the diff between your examples and the user's seed.
- **§4 Invariants:** if an invariants-analysis skill is available, invoke it scoped to
  this capability; otherwise derive them directly. Standing + new invariants, one line
  each, enforcement point (constraint / test / file:line) or **UNENFORCED**, plus a
  boundary line where the guarantee has an edge.
- **§5 Mechanism:** every current-state claim carries file:line evidence — verified, not
  remembered. Reuse-first: anything new names the existing primitive considered and why it
  is insufficient. The project's own nouns only; no imported vocabulary without explicit
  definition. If the subject spans repos, read the other repo's contract docs before
  claiming storage-layer facts.
- **§6 Acceptance:** Given/When/Then rows with stable, append-only IDs (AT-1, AT-2, …),
  each mappable to a runnable test/eval command. Derive rows from §3 — every worked
  example yields at least one row. For capabilities about access, permissions, or
  visibility, phrase rows as user questions: `Given <role> | When they ask "<question>"
  | Then answered / refused / partially answered`. After drafting rows, stamp each §0
  rule's test tag (`→ AT-n`, or `→ UNTESTED` if nothing tests it) — and say which rules
  came out UNTESTED.
- **§7 Build phases:** small, ordered, verifiable; each phase names the §6 rows it greens.
- **Every agent-half section** ends with `Why — what breaks without it: <one line>`. If you
  can't write the line, cut the section and say so.
- **Length budget:** §0 ≤ 40 lines; human half ≤ 150 lines; §1–§3 one screen each. §5 may
  run long when information-dense; if it's long AND the capability has two separable
  outcomes, propose the split by outcome, not by layer.

## Phase 4 — Close out at draft

- Verify the `Contents:` anchor links resolve — headings must stay bare
  (`## 4. Invariants`); annotations live on the italic line below the heading.
- Number the agent notes and open questions (owner + BLOCKING flag on each).
- Surface every decision you could not make as an explicit question with a recommended
  option; state the invariants at stake in each option.
- Set `Status: draft`. Moving to `agreed` is a human act — never do it yourself.
- **Paste §0 inline in chat, verbatim.** The TLDR is the close-out deliverable — the
  reviewer reacts to it in the conversation, not to a doc path. If the reviewer can't
  disagree with §0 alone, the doc failed, whatever else it contains.
- Below the pasted §0, report: doc path, agent-note count, BLOCKING question count, any
  rules tagged UNTESTED, and any proposed deletions awaiting a yes.

## Review mode — a doc authored elsewhere

The framework doubles as a review rubric (see the framework doc's "review rubric"
section — it is the authority). Process:

1. **Read 100% of the source** — chunked if large; state what fraction you read if you
   couldn't finish. Never review a skim.
2. **Verify before critiquing.** Spot-check every load-bearing current-state claim
   against live code with file:line. Three outcome classes, all valuable: confirmed
   (say so — it builds the doc's credibility), wrong (invented identifiers, stale
   claims), and **understated** (the code is worse than the doc admits — the sharpest
   findings are usually here).
3. **Run the rubric** — the framework doc's list is the authority; do not work from
   memory of it. It covers shape (§0 TLDR ≤ 40 lines with verbatim rules each tagged
   `→ AT-n` or UNTESTED, worked examples, GWT acceptance, decision register,
   disposition, one-doc rule) AND depth (invariants argued with mechanism + boundary,
   commit-pinned evidence, design-vs-description flags, rejected alternatives with
   receipts, outcome present even in mechanism-heavy specs).
4. **On a re-review, diff against the prior revision** for the three erosion classes:
   OPEN decisions silently asserted; verbatim/quote-block membership changed without
   human confirmation; operational content deleted with no stated home. Also credit
   what improved — and verify any NEW claims the revision introduced (revisions add
   claims too).
5. **Judge pushback on its merits.** If the doc's author rejected earlier feedback with
   an argument, engage the argument — accept it, or counter with a better mechanism.
   Don't re-assert.
6. **Deliver findings inline in chat** as a numbered, paste-ready fenced markdown block,
   most severe first, each item actionable by the other agent without this
   conversation. Files can be unreachable across app boundaries — inline is the
   contract; a file copy is optional extra.
7. **Track convergence.** When the external doc approaches framework shape, say what
   separates it from `agreed` — usually the human half — and offer to close it via the
   pending interview rather than another review round.

## Arm mode — `agreed → building`

Preconditions: status is `agreed`, zero unresolved BLOCKING questions. Then:

1. `git checkout -b feat/<capability>` (never a protected branch).
2. Write the §6 rows as failing tests; scaffold typed stubs that throw
   `NotImplemented` so the type-checker stays green while tests fail at assertion.
3. Run them RED; paste the failing output into §6; commit
   (`test(<scope>): red acceptance gate for <capability>`) as the branch's first commit
   and record the sha in the doc header.
4. Flip `Status: building`. If red proof can't be witnessed here (no deps/sandbox), say so
   loudly in §6 with the exact command — never silently skip.

## Anti-rationalizations

| Excuse | Reality |
|---|---|
| "The braindump is clear enough, I'll write the rules block myself." | Then the block starts life as a paraphrase — the exact validity→visibility failure. Confirm line by line. |
| "I'll tidy the wording inside the rules block." | The block is read-only. Append a numbered note. |
| "This overlaps an existing plan but merging is disruptive." | A sibling doc is a bug. Propose the merge; the user decides. |
| "The why-line for this section is obvious." | Then it costs one line. If you can't write it, the section goes. |
| "I'll fill in 'how we'll know' — it's implied." | Outcomes are decided, not generated. Ask. |
| "Status agreed is a formality, I'll flip it." | It's the human act the whole framework protects. Never. |
| "The revision improved, no need to diff it." | Revisions are where decisions erode, quote blocks drift, and content silently dies. Diff every re-review. |
| "The doc's claims cite code, so they're grounded." | Cited ≠ verified. One invented identifier was caught only by grepping. Check them. |
| "The user hasn't answered the sheet, so I'm blocked." | Only new-doc drafting waits on the human half. Review, iterate, verify — and re-surface the open remainder compactly. |
| "The doc is good, I'll just link it." | If the reviewer can't disagree with §0 alone, the doc failed, whatever else it contains. Paste §0 inline. |
| "They haven't picked a signal, I'll leave a placeholder." | A placeholder reads as done-and-deferred and survives to `agreed`. Present the verbatim candidate slate; if unanswered, the doc stays `draft` with a BLOCKING question. |
