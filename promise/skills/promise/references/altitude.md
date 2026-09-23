# Altitude — the proof taxonomy

*What a `Then` asserts on, the only lane that can reach it, and what a verdict is
allowed to move on. Read before drafting any `Then`, before deciding whether a
verdict moves, and before recording a kill witness. Cited from `modes/new.md`,
`modes/intake.md`, `modes/reconcile.md` and `modes/arm.md`.*

Every scenario's `Then` asserts on something. **Altitude** names what kind of thing
that is — a stored fact, a returned value, a person's experience, a model's
judgement, or behaviour this project cannot see because it lives elsewhere. The
altitude a `Then` is written at decides the only kind of test that can prove it.

## The five values

Four altitudes describe what a `Then` asserts on inside this project. The fifth
value, `sibling`, is not an altitude of this project's own behaviour — it marks a
`Then` whose proof lives in another repo — but it takes the same column and the same
lane rule, so the column admits exactly these five.

| Altitude | What the `Then` asserts on | Lane — the kind of test that reaches it | Cited in | What does NOT prove it |
|---|---|---|---|---|
| **data** | A stored fact — a record, a field, a computed value | A test against the data layer itself, calling the query or function directly | `map.lanes.data` | A test of the rendered surface, however convincing; a judgement-altitude eval. Neither reaches the stored fact directly. |
| **response** | What a request gets back — status, body, the shape a caller receives | A test against the boundary itself — the real handler, edges mocked (or a live lane when several systems must be real together) | `map.lanes.response` | A data-altitude test of the underlying query — it can pass while the boundary wraps it wrong. A rendered-surface test proves what a person sees, not what the caller received. |
| **perception** | What a person sees, is told, or lands on | A test that drives the real rendered surface — the actual render a person's screen would show, not a simulated one | `map.lanes.perception` | A DOM-simulation test run with no real render pipeline behind it — it exercises component logic, not what appears. A data- or response-altitude test, however strong. |
| **judgement** | Whether a model chose well — routing, tone, a judged answer | A scored suite run through a judge, not the fast deterministic run | `map.lanes.judgement` | A deterministic unit test of a helper the model happens to call; one hand-checked transcript with no scored suite behind it. |
| **sibling** | Behaviour that lives in another repo | That repo's own test suite | `map.lanes.sibling` | Nothing in this repo proves it directly — a citation here is trust in another project's proof, not this project's. |

A `Then` written as *"I see…"*, *"I am told…"* or *"I land on…"* is perception. A
`Then` written as *"is stored"*, *"is recorded"*, or that names a field, is data.
Read the sentence that was actually written before picking the lane — not the test
that would be convenient to write.

## The `Altitude` column

Every §6 acceptance row records its altitude in the `Altitude` column, between
`Then` and `Row` (`templates/outcome-doc.md`; framework § Section rules, §6). The
value is one of the five words above, exactly as written. It is the left-hand
operand of the verdict rule below: `reconcile` compares the altitude the evidence
reaches against the value in this column, not against a re-reading of the `Then`.

The tooling reads and checks it:

- `scripts/lint_outcome.py` — `ACCEPTANCE_ALTITUDE` (error): the column is present
  and a data cell is empty or not one of the five. `ALTITUDE_MISSING` (warn): a §6
  table has no `Altitude` header, so a doc written before the column existed still
  lints; add the column when the doc is next revised.
- `scripts/outcome_rows.py` — emits `"altitude"` on every row (`null` when the
  column is absent), so `arm` and `reconcile` read the operand instead of deriving
  it.

The column states the altitude; it does not prove the `Then` is written at it. A row
whose `Then` wording and `Altitude` disagree — an *"I see…"* `Then` marked `data` —
is a review finding: fix the sentence or the value, whichever is wrong.

## Signal kinds and where they land

An outcome doc's §0 states *how we'll know*, as one of four signal kinds. They map
onto altitude and lane unevenly:

| Signal kind (§0) | Altitude it targets | Lane | Notes |
|---|---|---|---|
| (a) a test that flips red→green | Whichever altitude the `Then` is written at | The lane that altitude picks, above | The ordinary case — what `arm` writes red and `reconcile` promotes |
| (b) a demo someone watches | Usually perception | A live walkthrough a person actually watches | A human-witnessed event, not necessarily an automated citation. Record who watched it and when. |
| (c) a number in prod that must hold at a value | — | **No test lane** | Verified by the operational check named in §0 — a dashboard, a metric threshold — never by a test. `reconcile` records a check of it as a **dated observation**, never as a citation into an evidence array. |
| (d) a claim we can make to a customer | Usually response or perception, depending what is claimed | Whichever lane proves the claim true | Cited normally once the altitude the claim rests on is identified. |

Kind (c) is the one to hold onto: it is real evidence, and it has no citation.
Nothing in `map.lanes` names an array for it, and no mode should invent one.

## The verdict rule

> **A verdict moves only when the evidence reaches the altitude the row's own `Then`
> claims — not the altitude the test was convenient to write at.** Passing a
> stricter test at a lower altitude is real progress. It is progress on a different
> sentence, and the verdict does not move until something proves the sentence that
> was actually written.

## Worked example

A board renders items grouped by state. One scenario's `Then` reads: *"the item does
not appear anywhere on the board."* Its `Altitude` cell says `perception`.

A data-altitude test proves the underlying query excludes the item from its result
set — a direct call to the query, asserting the excluded item's id is absent from
what comes back. That test can be strong, real, and correctly cited.

**The verdict does not move.** The `Then` is about the rendered board — perception —
and the new evidence is data. A query excluding a row is necessary for the board to
be correct; it is not sufficient, because the exclusion could still be undone
somewhere between the query and the render: a second, unfiltered query, a
client-side merge, a cached copy. The row stays exactly as proven as it was before
this test landed, which may honestly be `under-proven`.

**What would move it:** a perception-altitude test that drives the actual rendered
board and asserts the item is absent from every grouping it renders — not only the
one group it would "normally" land in. An exclusion bug often hides in a grouping
nobody thought to check.

## Kill mutation

Mutate the `Then`, never the assertion. Change the production behaviour a scenario
depends on — never the test that checks it — and watch the cited test fail. Revert
the mutation and watch it pass again. That pairing is what turns a citation into a
**kill witness**: a recorded mutation a cited test is known to catch.

An uncited passing test found during `reconcile` is not evidence until it has been
watched dying this way. A test written for a neighbouring concern often passes for
reasons that have nothing to do with the row's own `Then`; a test that could not
fail under any mutation is worse than no test, because it reads as proof while
proving nothing.

**Absence assertions need a positive control.** A `Then` that says an item does
*not* appear, is *not* told, or does *not* happen needs a companion case proving the
item *can* appear under different setup — otherwise the assertion may be passing
because nothing could ever appear, not because the exclusion works.

## Proof strength

Altitude says *what* a piece of evidence reaches. Proof strength says *how much* of
it: how many of the cases a rule covers the evidence actually checks. The two are
independent — a `data`-altitude test can check two cases or ten thousand.

| Strength | What it checks | Typical tool | What it does NOT prove |
|---|---|---|---|
| **example** | The cases someone chose and wrote down | Any ordinary test, e2e run or scored eval | Any case nobody wrote. Every lane holds this today |
| **property** | The real code, on inputs generated to break the rule, many per run | A property-based test (fast-check, Hypothesis, QuickCheck) | Inputs the generator cannot produce. It is still a sample, a large and hostile one |
| **model** | Every reachable state of a model of the code | A machine-checked proof (Lean) or an exhaustive model check (TLA+/TLC) | The code. The model is a second, hand-written copy of the logic, and can differ from the code while every theorem stays green |

Proof strength is recorded on §4 invariants, beside the enforcement point
(`outcome-framework.md` § Section rules). It does not change §6: a row's verdict still
moves on altitude alone (§ The verdict rule), and a property test is cited in the same
lane as any other test of its altitude.

**A `model` proof never enforces an invariant alone.** It names a **conformance
test**: a test at the invariant's own altitude that runs the real code and checks each
step it takes against the model — every transition the code makes is one the model
allows. Without it the honest entry is the proof plus UNENFORCED for the code, never
the proof alone. Candidates are small state machines with a "must never" rule: a
status lifecycle, a resume flow, a job queue. Anything at `perception` or `judgement`
altitude is not; a model cannot state what a person sees or whether a model chose well.

**A proof is red until nothing in it is assumed.** A Lean proof with `sorry` or
`admit` left in it, or one that depends on an axiom the project did not choose
(`#print axioms <theorem>` lists them), is a claim, not a proof — the same standing as
a failing test at the red gate. A TLA+ run counts only with the state space it
explored and no bound hit before it finished.

**Kill the model, not the proof.** The kill mutation (§ Kill mutation) carries over:
change the model the way a bug would change the code — allow the forbidden transition,
drop the guard — and watch the proof fail; revert and watch it pass. A proof that
survives every such change proves something weaker than it says, usually because a
hypothesis is false or the model can never reach the state in question. That record is
the proof's kill witness. The positive control carries over too: prove, once, that the
state the rule protects is reachable at all.
