# The Outcome Framework — one doc per capability

A document format and contract for capability docs that are the **input** to design and
planning, not the record of it. The human's decisions go in verbatim and first; the
agent's job is to find contradictions in them, propose the mechanism, and build.

Pairs with the `/promise` skill (SKILL.md beside this file), which produces and evolves
docs in this shape. This file is the single source of truth for the contract, section
rules, lifecycle and review rubric — the skill defers to it wherever they disagree. The
template itself is `templates/outcome-doc.md`, rendered by `scripts/render_outcome.py`
and linted by `scripts/lint_outcome.py --template templates/outcome-doc.md`.

---

## Why this exists

Most planning docs are the agent's output rather than the agent's input. A human writes
intent, an agent expands it into a plan, a reviewer reviews the expansion — a paraphrase
of a decision, several removes from the decision itself. That loop produces three
failures:

1. **Meaning drifts silently.** A paraphrase can read as faithful while quietly
   asserting something the source didn't, and a reviewer approving the paraphrase is
   not the same as the reviewer confirming the original. Nothing in the loop diffs the
   paraphrase against the source, so drift carries no flag.
2. **Volume replaces decisions.** Generating a plan is cheap, so a new plan appears
   whenever a question comes up rather than an existing one getting resolved — plans
   proliferate faster than decisions get made, because writing a new document is
   easier than confronting an old one.
3. **The hard question gets deferred to the model.** Confident prose can describe an
   outcome as though it were decided when nobody has actually decided it, and the
   fluency of the writing hides the gap.

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
     **`pending verbatim confirmation`**. An unfrozen candidate block changes membership
     between revisions without anyone deciding it, so it is frozen from that moment: no
     agent may add, remove, or reword entries in any later revision; only human
     confirmation changes it.
   - **Agent half** — Invariants, remaining worked examples, Mechanism, Acceptance,
     Build phases. The agent drafts these *from* the human half; the human strikes
     and corrects. Acceptance is agent-drafted only until the capability-map bridge:
     once bridged, §6 is a read-only snapshot (F7; § Lifecycle) and the map is where
     the scenarios change.
2. **One doc per capability.** A sibling doc covering overlapping surface is a bug:
   merge and delete, don't cross-reference. On supersede, **delete** the superseded
   doc — "if we can't easily find it, we probably don't have it" cuts both ways. A
   file the human keeps anyway carries `superseded-by <doc>` (§ Lifecycle).
3. **The 60-second standard, with numbers.** §0 alone — ≤ 40 lines counted from the
   §0 heading to the line above the agent notes, one screen — must let a reader
   disagree with something specific in 60 seconds; the lint fails a §0 past 40 lines
   (`TLDR_BUDGET`). The whole human half (§0–§2 plus the seed example)
   is ≤ 150 lines; the lint warns past that (`HUMAN_HALF_BUDGET`) rather than failing,
   because the seed example's length is the human's call. If a reader needs more than
   §0 to object, the doc failed, whatever else it contains. (§5 Mechanism is
   deliberately uncapped — see the length-budget rule.)
4. **Every agent-drafted section §4–§7 carries one line: "Why — what breaks without
   it."** If that line can't be written, cut the section. (The founder-doc test.) The
   lint checks §4–§7 (`WHY_LINE`); the examples the agent adds to §3 extend a human
   section and carry no Why line.
5. **Worked examples before prose.** Every rule ships with at least one scenario in
   ABC form — named actors, concrete state, expected outcome. A rule that can't be
   expressed as a scenario isn't a rule yet. A §0 carries at least one rule;
   `lint_outcome.py` reports an empty `**Rules:**` block (`RULES_PRESENT`).
6. **Acceptance criteria are scenarios, not adjectives.** Given / When / Then, one row
   per scenario, each row naming the altitude its `Then` asserts on and mappable to a
   runnable test.
7. **Outcomes are decided, not generated.** The outcome line and the "how we'll know"
   line in §0 are human decisions. The agent may propose a **slate of verbatim
   candidates** — each citing the source line it derives from, what it commits you to,
   and what to think about, with "none of these — here's mine" always on offer and never
   last — but the agent may not fill either section in, and a candidate the human edits
   enters as the edit, not the candidate. **Rules are exempt from slating**: they enter
   §0 only by verbatim line-by-line confirmation. A slate trades anchoring risk for the
   greater harm of a blank, and rules are where anchoring does the most damage — a
   pickable rule is agent framing with a human signature on it.

---

## The template

The skeleton lives in `templates/outcome-doc.md` — one file, rendered by
`scripts/render_outcome.py`, kept green by
`scripts/lint_outcome.py --template templates/outcome-doc.md`.
It is not duplicated here: two copies would drift, which is the failure this
framework exists to prevent. What each section must contain is in
§ Section rules, below. The header lines are `Status:` (one of `draft`, `agreed`,
`building`, `shipped`, `superseded-by <doc>`), `Owner:` with `Last decision:`,
`Supersedes:` (the docs merged into this one, or `—`), and — once `building` —
`Red gate: <sha> <YYYY-MM-DD>` directly under `Supersedes:` (§ Lifecycle).

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
  section's acceptance test. Rules are always `- ` bullets, their one canonical format
  — a numbered list is a rewrite, not a rendering choice. **The rules have exactly one
  home.** A §0 that duplicated a rules section elsewhere would drift from it — the
  exact "meaning drifts silently" failure this framework exists to prevent. The agent
  treats §0 as read-only and appends numbered notes below, with two carve-outs: the
  trailing `→ AT-n` / `→ UNTESTED` test tag on each rule (mirroring UNENFORCED on
  invariants) and the `Scenarios:` counts — both agent-maintained metadata, re-derived
  from §3/§6 on every revision, the tag never the rule text and the count never the
  lines it counts. A rule tagged UNTESTED on a doc moving to `agreed` is a finding.
  **The 40-line budget covers the block itself** — the heading and author line, outcome
  line, rules, how-we'll-know, scenario counts, up to the line above the agent notes.
  Numbered agent notes sit below it and are exempt, but they are not a
  loophole: past ~8 notes the front door has become a discussion thread, so consolidate
  them, or promote the substantive ones to §9 open questions with owners. Notes are
  where the agent argues; §0 is where the human decided.
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
  is the partially-ruled convention (§8, below) applied in the other direction
  (signal → mechanism, not mechanism → signal). Worked example: a chosen signal of
  *"two accounts in the same workspace ask the same question and get different
  answers"* is unstageable under a data model that maps a CRM's shared records to
  workspace scope — so it selected owner-level scoping and narrowed a BLOCKING
  question without anyone arguing the mechanism.
- **§3 Worked examples** are the reading surface: named actors, concrete state,
  expected outcome. The human seeds at least one; the agent extends. Cover at minimum
  the happy path, the undo/reverse path, and any permission or visibility edge the
  capability has. If a reviewer only reads §0, §2, §3, they should be able to catch a
  wrong design.
- **§4 Invariants** is where an invariants-analysis pass plugs in (a dedicated skill if
  you have one, manual otherwise): standing invariants of the touched area + new ones
  this work introduces, each as an "X must never Y" one-liner with its enforcement
  point (constraint / test / property / proof / file:line) or UNENFORCED, and, where
  the guarantee has an edge, a one-line **boundary** — the condition beyond which it
  does not hold ("cannot prevent X across two scopes; that is user error, not a
  violation"). An invariant without a boundary claim overpromises. Four useful moves:
  the uniqueness claim, two-concepts-one-knob, fail-open-or-closed, schema-wins.
  An enforcement point that is evidence also names its **proof strength** —
  `example`, `property` or `model` (references/altitude.md § Proof strength): how many
  of the cases the "never" covers the evidence actually checks. "Must never" is a claim
  about every case; an invariant held only by `example` tests says so, so the reader
  sees the gap rather than reading one or two cases as all of them. A `model` proof
  (Lean, TLA+, any machine-checked proof) checks a model of the code, never the code
  itself: it never enforces an invariant alone, and names the conformance test that
  ties the model to the code.
- **§5 Mechanism** carries file:line evidence for every current-state claim,
  reuse-first, and "existing primitive considered / why insufficient" for anything
  new — without mandatory tables and diagrams. Add a diagram only when it replaces
  prose, not alongside it. Four disciplines that keep a long mechanism section honest:
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
  append-only IDs (AT-n) — they are what §0's test tags cite. Every row starts and
  ends with a pipe; a row missing one is still read, GFM-style, and the lint reports
  it at its own line (`ACCEPTANCE_TABLE`). Each row names its
  altitude in the `Altitude` column — `data`, `response`, `perception`, `judgement`
  or `sibling` (references/altitude.md): what its `Then` asserts on, and therefore
  the only kind of test that can prove it; `reconcile` compares evidence against it.
  The lint rejects a value outside those five (`ACCEPTANCE_ALTITUDE`) and warns when
  a table has no `Altitude` column (`ALTITUDE_MISSING`); a row whose `Then` wording
  and altitude disagree (an "I see…" `Then` marked `data`) is a review finding. For
  capabilities about access, permissions, or visibility, rows are phrased as user
  questions — `Given <role> | When they ask "<question>" | Then answered / refused /
  partially answered` — because that is the form the capability will actually be
  exercised in, and the form a non-engineer can propose test cases in without reading
  code. The `Row` column — in the template from the start; a table written without
  it gains it at the bridge — stays empty until the capability-map bridge (F7;
  § Lifecycle) files the row; from then on it cites the map's row id, and the map —
  not this column — is what changes.
- **§7 Build phases** are small, ordered and verifiable; each names the acceptance
  rows it turns green. **§8 Decisions** is a table (`# | Date | Decision | Owner |
  Why`); a decision may be **partially ruled** — record the ruling made, by whom, and
  the narrowed residual question. Narrowing is progress; a register that only knows
  OPEN/answered loses it. **§9 Open questions** each carry an owner and `BLOCKING |
  non-blocking`; answers are appended inline with a date, never deleted. **§10 Out of
  scope** is explicit and links the one doc that owns each excluded surface.
- **Length budget — it binds the review surface, not the whole doc.** §0 ≤ 40 lines.
  The human half (§0–§2 + seed example) ≤ 150 lines. §1–§3 one screen each. The review
  surface (§0–§4, §8, §9) must together stay readable in one sitting. §5 Mechanism may
  run long **when it is information-dense** — a long spec with a rationale on every
  rule and zero filler beats two thin docs. The filler detector: *the complexity budget
  is spent in the document, not in the code* — every extra paragraph must be buying
  simplicity in the implementation. If §5 is long AND the capability has two separable outcomes,
  split by outcome, not by layer.

---

## Lifecycle

```
draft ──(human half complete + agent notes resolved)──► agreed
agreed ──(acceptance rows committed RED; the sha recorded as a header line)──► building
building ──(rows green + shipped)──► shipped
any ──(merge, with the human's yes)──► deleted   (the survivor's `Supersedes:` line is the record)
any ──► superseded-by <doc>   (only when the human keeps the file instead of deleting it)
```

- **The capability map is the goal.** One row per promise, each naming the tests
  that prove it and an honest verdict, is the map of the platform: what it promises
  and how much of that is proven. Outcome docs make promises one capability at a
  time; the map is where they add up. A project without one is offered the skill's
  starter map (`scripts/start_map.py`) by `arm`, when its first doc is `agreed` —
  the first moment there is a real promise to put in it — and by `adopt` when an
  agreed doc already exists. Declining is allowed and changes nothing below: §6
  stays the doc's only home until a map exists.
- **Where the project keeps a capability map, `agreed` is the doc's entry to the
  bridge; `arm` performs the bridge as its first step on `feat/<slug>`.** Between the
  human's edit and `arm`, `bridge_validate.py` reports `ROW_MISSING` /
  `SNAPSHOT_LINE_MISSING`: that means not yet armed, never drift. F7 (§ Design
  decisions of the framework itself) is the one statement of what the bridge is and
  why; architecture § The bridge carries the procedure. The bridge
  leaves two traces the tooling checks: each §6 row's `Row` cell holds the map's row
  id, and one line sits directly under the §6 table —
  `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of these scenarios from here on. ``
  — after which §6 is not edited again. `bridge_validate.py` requires that line
  (`SNAPSHOT_LINE_MISSING`) and a filled `Row` cell (`ROW_MISSING`) whenever the
  status is `agreed` or later and a map is configured (orient's `mapUsable`).
  `shipped` requires every bridged row **proven** at the altitude its own `Then`
  claims: a row proven at a lower altitude than its `Then` asserts is not shipped,
  whatever the map says elsewhere. No map configured ⇒ none of this applies, and §6
  stays the only home.
- **`building` records the act that earned it.** The red-gate commit's sha and date
  sit in the header as their own line, `Red gate: <sha> <YYYY-MM-DD>`, directly under
  `Supersedes:`. `arm` writes it when it writes the status; `lint_outcome.py` rejects
  a `building` doc without it (`BUILDING_NEEDS_GATE`).
- **One docs folder is the one home** (e.g. `docs/designs/`). Outcome docs live there.
  Legacy plan folders receive **no new docs** — the build phases live inside the
  outcome doc (§7). Existing plans migrate into their capability's outcome doc as
  they are touched, then get deleted.
- Status lives in the doc header, not the folder. Folder=status is retired.
- **A thin draft is a `draft` that holds the human half only.** It carries
  `Depth: thin` in its header; §3–§7 each say they are not written yet. It lets an
  idea reach version control before its rules, signal or example are known: the
  gaps are BLOCKING §9 questions, never text the agent wrote in the human's place.
  §0's rules are still verbatim-confirmed. `lint_outcome.py` accepts the shape on a
  `draft` only (`THIN_DRAFT`), so a thin doc cannot be agreed; `revise` writes the
  agent half and removes the line.
- A doc in `draft` with unresolved BLOCKING questions cannot move to `agreed`.
- **A superseded doc is deleted, not kept.** Merge folds it into the survivor, names
  it on the survivor's `Supersedes:` line and in a §8 row, and deletes the file with
  the human's yes. `superseded-by <doc>` is the status merge writes only when the
  human chooses to keep the file: a pointer to the survivor, never a second home. The
  lint requires the target (`HEADER_STATUS`) and `bridge_validate.py` treats such a
  doc as not bridged.
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
   tags and the `Scenarios:` counts may change; outcome line, rule text, and
   how-we'll-know may not.) Where the outcome line or signal came from a candidate
   slate, was the final text confirmed back — or does the doc carry the agent's
   phrasing with nobody's approval on it? An unconfirmed slate pick is a blank wearing
   a suit.
3. **Decision erosion** — did any OPEN decision become an assertion between revisions?
   Decisions are ratified by humans, never resolved by drafting.
4. **Deletion without disposition** — did operational content vanish between revisions
   with no stated home (appendix, companion doc, archive)? Compression must name where
   the content went.
5. **Framework shape** — §0 TLDR present and ≤ 40 lines, worked examples present,
   Given/When/Then acceptance present with an altitude on every row, every §0 rule
   carries acceptance-row IDs or **UNTESTED** (an UNTESTED rule on an `agreed`+ doc is
   a finding), invariants carry enforcement points or UNENFORCED, decisions have
   owners + blocking flags, disposition names what gets deleted, evidence paths
   resolvable by any reader.
6. **Depth, not just shape** — invariants *argued* (mechanism + boundary), not listed,
   and their proof strength named (an invariant held only by `example` tests states
   that, rather than reading as proved for every case; a `model` proof names its
   conformance test);
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
| F2 | Interview-first elicitation; rules enter §0 only after verbatim line-by-line confirmation | A paraphrase can read as faithful while asserting something the source didn't, and a human approving the paraphrase does not confirm it matches the original — verbatim line-by-line confirmation removes the paraphrase step where that gap opens |
| F3 | §0 TLDR leads every doc and IS the protected block; there is no separate rules section (moved, not copied) | A reader must be able to STOP after one screen; a copy would drift from the original — the exact silent-drift failure the framework prevents |
| F4 | How-we'll-know is a forced choice from a verbatim candidate slate; placeholders banned (no pick ⇒ doc stays `draft` with a BLOCKING question); the chosen signal is re-read against every OPEN decision | A blank in a file is indistinguishable from a decision at review time; and a signal can silently select a mechanism — narrowings must be recorded, not discovered |
| F5 | The outcome line is a forced choice on the same pattern as F4 — open question first, then a verbatim candidate slate (selected-because / commits-you-to / think-about), "none of these" never last, edits enter not candidates. Rules stay exempt: verbatim-confirm-only, never slated | F4 fixed the placeholder failure for one of §0's three fields and left the other two as blanks — the same argument applies to the outcome line; rules are excluded because a slate is itself a paraphrase offered as a menu, and picking from a menu of paraphrases ratifies whichever paraphrase reads closest, not the source — reintroducing the paraphrase loop at the exact spot the framework protects |
| F6 | Revise mode gets an explicit procedure: only agent-maintained metadata (the `→ AT-n`/`→ UNTESTED` tag, the `Scenarios:` counts) changes inside §0 without asking; a rule's text, the outcome line, and how-we'll-know all require the human, every time. Agent notes sit below §0, exempt from its 40-line budget, but consolidate or promote past ~8 | Without a stated procedure, revise is the mode where §0 is most at risk — the doc already exists, so there's no interview protecting it; and an unbounded notes list quietly turns the front door into a discussion thread nobody reads in 60 seconds |
| F7 | Where a project keeps a capability map, `agreed` is the doc's entry to the bridge and `arm` performs it as its first step on `feat/<slug>`: a human groups the confirmed §6 rows into the map's rows by the §0 rule each is tagged from — one row per story, 1–5 scenarios, more is a chain with a parent, rows no rule cites are one group the human places — and from then on the map is the source of the scenarios. §6 is a read-only snapshot, marked by the snapshot line under its table (§ Lifecycle), and its `Row` column cites the map's row id; §0 keeps citing the doc-local `AT-n` aliases, which stay stable and append-only rather than being replaced by the map's ids. `shipped` needs every bridged row proven at the altitude its own `Then` claims. No map ⇒ §6 stays the only home | One promise, one home — a copy made at `agreed` would drift the day after, the same failure the framework exists to prevent, just moved one level up |
| F8 | Proof strength is a second axis beside altitude, recorded only on §4 invariants: `example` (chosen cases), `property` (the real code on generated cases), `model` (a machine-checked proof over every reachable state of a model). A proof counts only with no `sorry`, `admit` or unproved axiom left in it and a watched kill on the model; a `model` proof never enforces an invariant without a conformance test that runs the real code against the model. §6 rows, the map's lanes and the verdict rule are unchanged | Altitude says *what* a piece of evidence reaches; it never said *how much* of it. "Must never" is a claim about every case, and without the axis a test of two cases reads the same as a proof of all of them. A proof about a model is the strongest evidence of the three and the easiest to over-read, because the model is not the code: hence the conformance test, and hence the axis stays out of the verdict rule, which already guards the step from evidence to code |
| F9 | The capability map is the goal, offered at the first agreed doc: the skill ships a starter (`templates/starter-map/` — an empty `map.json`, its stdlib reader, a recipe) and `start_map.py` installs it and fills the config's `map`. `arm` offers it, Recommended, when no map is configured; `adopt` offers it when an agreed doc already exists. It never replaces a project's own map, even a partial one, and once installed the files are the project's to change | A promise that lives only in its own doc cannot be counted with the others, so "what does this platform promise, and how much is proven" has no answer. Offering the map at adoption would put an empty register in front of a project with nothing to put in it; offering it at the first agreed doc starts the map with a real row. Shipping a starter rather than only an example makes the offer one command, not a project of its own |
| F10 | A thin draft (`Depth: thin`) holds the human half only, and is a `draft` that cannot be agreed | A doc that asks for rules, a signal and a worked example before it is written stops the ideas that most need a home; a thin draft takes the idea as it is and turns each gap into a BLOCKING question, and the lint keeps it out of `agreed`, so the checks at every gate stay as strict as before |
