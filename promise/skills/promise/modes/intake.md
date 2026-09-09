Read before this: references/altitude.md · references/anti-rationalizations.md
Read at Apply, not before: the project's `map.recipe` and `map.index`, if a map is configured — the match and route steps need only the adapter's output.
Phase 0 line: mode `intake` (say if inferred), framework source, docs home and its source, the item count, whether the input is a feedback list, a single "add a scenario to `<row>`" ask, or a "which promise covers X" lookup (then run only the match step and answer), whether a map is configured, and whether the project is adopted.
Writes: per the recipe when a map is configured; else the outcome docs' §6 (Acceptance) and §9 (Open questions).

# Intake — feedback in, promise changes out

Feedback in, **row changes out** — each item filed where the map, or the doc,
already keeps that kind of claim.

## Invariants — state them, never trade them for speed

1. **A promise is its scenarios.** A row is one story plus 1–5 `Scenario:` blocks;
   new promises are appended as scenarios, and the story is never rewritten to fit
   one.
2. **Proof is per scenario, recorded per row.** An unproven scenario appended to a
   proven row demotes the row. That is the honest state — record it, do not avoid
   it by leaving the scenario out.
3. **The recipe's lockstep rule is never traded for speed, and no ceiling or ratchet
   is ever loosened.** A row change touches every file the recipe names, in one
   commit, or it is not filed yet.
4. **Findings are dated append-logs, never rewritten.** The oldest line is the
   record of what was believed then; add to it, do not edit it.
5. **Altitude decides the lane** — `references/altitude.md`.
6. **Reproduce before believing.** A feedback item that says something is broken is
   a claim; read the code the row cites before filing it as a defect.
7. **Delegate enumeration, never decisions.** Sub-agents may rank, read and draft;
   the relation call is made in front of the user, one item at a time, with a
   recommendation.

## Split the input into atomic items

One row per distinct observable claim. Keep the person's words verbatim — they
carry forward into the row as a paraphrase, and titles rarely share vocabulary with
how a need is actually asked.

| # | Verbatim | Kind (guess) | Surface |
|---|---|---|---|
| 1 | "…" | defect / new outcome / new need / wording-only | … |

A sentence carrying two claims is two items. Do not paraphrase in this table.

## Match each item (also: the only step for a single ask or a lookup)

For every item, in this order:

1. Run `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" find "<the verbatim item>"`;
   read the top 3–5 results, not only the first. A rank is where to start reading,
   not a match. The adapter passes the item as one argument — never paste it into
   a shell command yourself.
2. Read each plausible candidate in full with `adapter.py row <id>` — the story,
   the scenarios, the verdict, every evidence array. **Read the finding to the
   end**; the lede is the oldest claim.
3. No map → `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" --search "<the
   verbatim item>" --dir <docsHome>` ranks every §6 row and §0 rule across the
   outcome docs; read the top hits in their docs before deciding.
4. Decide the relation:

   | Relation | Meaning |
   |---|---|
   | EXISTING-SCENARIO | A scenario already promises this `Then`, and the product honours it → nothing to file beyond the paraphrase; check the row's verdict |
   | DEFECT | A scenario already promises this `Then`, and the product breaks it → an issue on the existing row, no new scenario |
   | EXTEND | Same story, new observable `Then` → a new scenario on that row |
   | NEW-ROW | No row states the need — a new "so that" |
   | SURFACE | Only about the screen — a placement, a wording, a colour |
   | DECISION | A wording quarrel with an existing `Then`, or "should the product…" |

   **EXTEND vs NEW-ROW:** can the row's `As / I want / so that` stay unchanged? If
   it must be edited to fit the scenario, the item is NEW-ROW.

More than ~5 items → **delegate steps 1–2**, one sub-agent per item, each required
to run `map.find` and quote the scenario it matched; a candidate with no quoted
scenario is discarded. Do step 4 (the relation call) yourself.

Present the match table and **stop for approval** before drafting any Gherkin.
Recommend one relation per item — **(Recommended)** first — with one concrete
reason and a 1–10 completeness score per option.

## Draft the Gherkin

For EXTEND and NEW-ROW items only, in the map's voice:

- No screens, clicks or component names in a scenario. "I am told," not "a toast
  appears" — a screen fact is a SURFACE item instead.
- Every `Then` has an observable, and states its **altitude** beside it.
- EXTEND reuses the row's `As / I want / so that` unchanged. If it needs editing,
  the item is NEW-ROW, not EXTEND.
- NEW-ROW gets a real "so that" — why it matters, not what it does — and 1–3
  scenarios.

Show each draft beside the row's existing scenarios so the user can see whether it
is a genuine extension or a restatement. The user's edit is what enters, not the
draft.

## Find the tests, then name the gap

For each approved item, per the recipe's own commands (`map.row`, or its
equivalent for a project with no map): every evidence array, and any test that
already declares itself for the row but that no evidence array cites.

| Item | Row | Relation | Existing tests | Altitude | Lane + file to add | Kill mutation |
|---|---|---|---|---|---|---|

**Kill mutation is mandatory** for anything you intend to call proven: name the
source change that would break the scenario's `Then`. Cannot name one → the
scenario is not testable as written; say so and route it to DECISION instead.

## Apply (only after approval of the match, draft and gap steps)

Work one commit per row or small group.

Before filing any issue, `issueTracker` configured → **search it first**, by the
row id and by the promise in plain words, open and closed. Ask: *would closing that
issue do this work?* Yes → comment there, do not file. Adjacent → file, and
cross-link both ways. Record the search terms and what you found in the issue body.

Per relation:

- **DEFECT** — search first (above); open an issue titled with the scenario's
  `Then`, quoting the verbatim feedback and the row; append a dated finding with a
  severity; leave the row's Status unchanged unless it claimed tested for the
  `Then` you just broke.
- **EXTEND** — append the scenario to the row; append a dated finding in every
  place the recipe names, saying what the scenario adds and what proves it — or
  that nothing does yet, in which case demote the verdict and touch everything the
  recipe's lockstep names; add the verbatim feedback as a paraphrase on the row.
- **NEW-ROW** — everything the recipe's lockstep names, in one commit. A
  must-priority row lands with a real test or a dated, reasoned
  accepted-uncovered exemption — or it is not must yet.
- **SURFACE** and **DECISION** — per the recipe's own shape for each.

No map — the same relations land in the docs instead, and only there:

| Relation | Where it goes |
|---|---|
| EXISTING-SCENARIO | nothing to file; note the paraphrase in the row's §9 answer or §8 entry if it sharpens the promise |
| DEFECT | a dated §8 entry naming the AT row broken, plus a §9 question (BLOCKING if the doc is `agreed` or later) — the human decides whether the doc drops back to `draft` |
| EXTEND | a new AT row appended to §6 of the doc whose story holds it; §0's tag for the rule it serves is re-stamped; `Scenarios:` re-counted |
| NEW-ROW | a new outcome doc through the `new` procedure — never a row bolted onto a doc with a different story |
| SURFACE | a line in §10 (out of scope) naming the doc that owns the surface, or a §9 non-blocking note when none does |
| DECISION | a §9 question with an owner and a BLOCKING flag |

## Verify and hand back

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks`, then `adapter.py verify`
(the project's type-check, test and lint commands, in that order).

Report per item: what was filed, where, what proves it now, and what is still owed
(a missing lane, a decision, a kill witness). Close with a reading assignment — the
1–3 `file:line` spots the user should read to own the verdicts, one comprehension
question each.
