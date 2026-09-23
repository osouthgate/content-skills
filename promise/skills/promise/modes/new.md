Read before this: references/slates.md · references/anti-rationalizations.md · references/altitude.md · templates/outcome-doc.md · outcome-framework.md § The contract · § Section rules
Phase 0 line: mode `new` (say if inferred), framework source, docs home + its source, `plansFolder` (or "none"), whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: one new doc under `docsHome`, or under the `--docs-home` folder the user named when `docsHome` is null.

# New — create an outcome doc

Produce **the one doc for a capability**, in the Outcome Framework shape.
You produce the doc up to `draft`. You do not implement the capability.

## Elicit the human half

Never skip this, never draft ahead of it. The human half is §0 TLDR, §1
Problem, §2 Outcome, and one seed worked example — framework § The contract
(the 60-second standard): §0 ≤ 40 lines, the whole human half ≤ 150 lines.

- **Interview-first.** Ask for the human half in the user's own words — six
  lines is enough. Five prompts, one turn: *what is true after this ships*
  (§0 outcome line, expanded in §2), *why do we need it* (§2), *what must
  always / never be true* (§0 rules — echo every line back for verbatim
  confirmation before it enters), *how will we know* (§0 — the user's
  decision; never fill it in), and *walk me through one concrete example*
  (the §3 seed — named actors, concrete state, expected outcome; you extend
  it later, never invent it). Confirm the **owner** for the header: propose
  `git config user.name` as the **(Recommended)** default and wait for a yes
  — `render_outcome.py` requires `--owner` and the lint rejects a placeholder.
- **The outcome line and how-we'll-know are forced choices, never blanks.**
  Ask the open question first. If it doesn't come back as one crisp line,
  run the candidate-slate procedure for whichever field stalled —
  references/slates.md. **Rules are never slated:** extract candidates from
  the interview answer, braindump or transcript and present them back line
  by line for verbatim confirmation; only confirmed lines enter §0, exactly
  as confirmed.
- **Once the signal is chosen, re-read every OPEN decision against it** —
  framework § Section rules. An option under which the signal can't be
  staged has been ruled out; record the narrowing in §8 with the
  implication stated, and leave ratification with the human.
- **§0 is protected** the instant it's written — framework § The contract.
  Disagreements, gaps and contradictions become numbered agent notes below
  the block, never edits inside it.
- **Keep the confirmation sheet small and staged.** One screen. Large
  source material → confirm the ~10 most load-bearing lines first; the rest
  can follow in later passes. A sheet with everything on it doesn't get
  answered.
- **A pending sheet doesn't block other work.** User redirects to review,
  iteration, or anything else before answering → do that work; the human
  half stays pending, and you re-surface the *open remainder* compactly
  (never the full sheet again) at the next natural decision point. Only
  drafting a NEW doc's agent half waits on the human half.
- Can't yet state the outcome or rules? Stop. That's the finding — the
  capability isn't ready for a doc. Offer to help think it through
  conversationally; write nothing to `docsHome`.

## Capability hunt — one doc per capability

Before creating anything, check Phase 0's `existingDocs` for overlapping
surface — it already enumerated the docs home, so don't re-search it from
scratch. `plansFolder` is not null → also search it (every status folder)
for the same capability.

- Overlap found → propose **merge-and-delete**: name the surviving doc, the
  docs to fold in, and the docs to delete. A sibling doc is a bug, not a
  cross-reference target. Three or more docs, or entangled scenarios → point
  the user at `/promise merge` instead of resolving it inline here.
- `plansFolder` present and a touched plan doc has still-live content →
  migrate it into the new doc's §7, then propose deleting the plan file in
  the same commit as the new doc. It receives no new docs.
- Wait for the user's yes before deleting anything.
- `docsHome` is null → ask where outcome docs should live before writing a word.
  A folder is created only on the user's explicit choice — here, by passing the
  folder they named with `--create-docs-home` below. `adopt` can pin the folder in
  the config on the user's say-so, but it is still created here, on the first
  write. Never create one unprompted.

## Draft the agent half

Instantiate the template with `python3 "${CLAUDE_SKILL_DIR}/scripts/render_outcome.py"
--title "<Capability>" --owner "<name>" [--docs-home <folder> --create-docs-home]`
— it writes `<docsHome>/<slug>.md`, refuses to overwrite, and leaves every
interview placeholder for you to fill. `docsHome` null → pass the folder the
user chose in the capability hunt as `--docs-home`, with `--create-docs-home`
so the script creates it. Phase 0 warned `docsHome does not exist` (the user
pinned it in `adopt`) → pass `--create-docs-home` alone. Otherwise omit both
flags and it writes under Phase 0's `docsHome`. Every current-state claim
carries file:line evidence, verified this run — never remembered from an
earlier one.

- **§3 Worked examples:** extend the user's seed to cover at minimum the
  happy path, the undo/reverse path, and any permission or visibility edge
  the capability has — ABC form, named actors, concrete state, expected
  outcome. Show the diff between your examples and the user's seed.
- **§4 Invariants:** if an invariants-analysis skill is available this
  session, offer it in one line, scoped to this capability, and wait for a
  yes — never auto-invoke it. Declined, or none available → derive §4
  yourself and say the four moves (uniqueness claim, two-concepts-one-knob,
  fail-open-or-closed, schema-wins) ran unassisted. Either way, §4 lands the
  same shape: standing + new invariants, one line each, enforcement point
  (constraint / test / property / proof / file:line) or **UNENFORCED**, its
  proof strength where the point is evidence (`example`, `property` or
  `model`, `references/altitude.md` § Proof strength), plus a boundary line
  where the guarantee has an edge.
- **§5 Mechanism:** reuse-first — anything new names the existing primitive
  considered and why it's insufficient. The project's own nouns only;
  define any imported term explicitly. Subject spans repositories → read
  the other repository's own contract docs before claiming storage-layer
  facts.
- **§6 Acceptance:** Given/When/Then rows, derived from §3 — every worked
  example yields at least one row. Capabilities about access, permission or
  visibility → phrase rows as user questions: `Given <role> | When they ask
  "<question>" | Then answered / refused / partially answered`. Each row's
  altitude goes in the `Altitude` column — exactly one of `data`,
  `response`, `perception`, `judgement`, `sibling` (references/altitude.md);
  the lint rejects anything else. The `Row` column is already in the
  template: leave it empty at `draft` — `arm` fills it when a map files the
  rows, and nothing is filed in the map before then. After drafting rows,
  stamp each §0 rule's tag (`→ AT-n`, or `→ UNTESTED`) and say which rules
  came out UNTESTED.
- **§7 Build phases:** small, ordered, verifiable; each phase names the §6
  rows it turns green.
- Every agent-half section ends `Why — what breaks without it:` — framework
  § The contract. Can't write the line → cut the section.
- Length budgets — framework § The contract, § Section rules. §5 may run
  long when information-dense; if it's long AND the capability has two
  separable outcomes, propose the split by outcome, not by layer.

Before close-out, run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py"
<doc>` and fix every finding, or say why one stands. The lint checks shape
only. It does not check: that §3 holds at least one example, that §9
questions carry an owner and a BLOCKING/non-blocking flag, that §4
invariants name an enforcement point or UNENFORCED, that `Last decision:`
is a real date, or whether a filled Why line, example or mechanism is
*true* — read those yourself before close-out.

## Close out at draft

- Number the agent notes and open questions (owner + BLOCKING flag on
  each).
- Surface every decision you couldn't make as an explicit question with a
  **(Recommended)** option and one reason; state the invariants at stake in
  each option.
- Set `Status: draft`. Moving to `agreed` is a human act — never do it
  yourself.
- **Paste §0 inline in chat, verbatim.** It is the close-out deliverable —
  the reviewer reacts to it in the conversation, not to a doc path. If they
  can't disagree with §0 alone, the doc failed, whatever else it contains.
- Report: doc path, agent-note count, BLOCKING question count, any rules
  tagged UNTESTED, any proposed deletions awaiting a yes, and what you
  could not check.
