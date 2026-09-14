# Adding or extending a row — the recipe for this map

This is the file `map.recipe` points at. The promise modes read it for the
mechanics of this project's map and never restate them: which files a row
touches, what lockstep means here, what a citation looks like, and which lane a
`Then` lands in. The map is `map.json`; its only reader is `capability_find.py`.

## What a row is

One row is one user story plus one to five Given/When/Then scenarios, four
evidence arrays, and a verdict. Ids are `CAP-<n>`, append-only; `python3
capability_find.py --next-id` prints the next one. A scenario that came from an
outcome doc keeps the doc's `AT-n` id in its `at` field as an alias, so the doc's
§0 tags and the map agree without either copying the other.

| Field | Meaning |
|---|---|
| `story` | The promise at story grain — one sentence a person can disagree with. |
| `doc` | The outcome doc that made the promise, or `null` for a row filed from feedback. |
| `scenarios[]` | `id`, `at` (the doc's AT alias or `null`), `given`, `when`, `then`, `altitude`. |
| `tests[]`, `e2eTests[]`, `evalTests[]`, `siblingTests[]` | Citations, one string each: `<test file>::<test name>`. |
| `verdict` | `not-built`, `under-proven` or `proven`. |
| `parent` | Optional — the id of the row this one continues when a story outgrew five scenarios (a chain). |

## The lockstep rule

A row and the thing that promises it move together, in this order, in one
commit:

1. The outcome doc's §6 row exists and its `Then` is final — the map copies the
   `Then` text verbatim, so `bridge_validate.py` can find it again later.
2. `python3 capability_find.py --next-id` for the id. Never reuse a deleted id.
3. Append the row to `map.json` with every scenario, all four evidence arrays
   (empty when nothing is cited yet) and `"verdict": "not-built"`.
4. Write the id into the doc's `Row` column for every §6 line the row covers, and
   add the snapshot line under the table.
5. `python3 capability_find.py --check`, then `bridge_validate.py` on the doc.

Nothing lands out of order, and step 5 reads both directions: a row whose `doc`
names a file with no §6 line citing it fails `--check`, and a `Row` cell citing an
id the map does not have fails `bridge_validate.py` (`ROW_NOT_FOUND`); a map `Then`
that no longer matches the doc's snapshot is reported there as `THEN_NOT_IN_MAP`.

## Routing table — what a piece of feedback becomes

| The feedback is… | It becomes… |
|---|---|
| a case an existing scenario already covers | no map change; cite the row in the reply |
| a new case under an existing story | a new scenario appended to that row (a row keeps at most five; a sixth means a new row with `parent` naming this one) |
| a story no row makes | a new row, filed through the lockstep rule above, with `doc` pointing at the outcome doc that promises it |
| a decision the story needs first | a §9 question in the owning doc, not a row |

## Lane table — which array a `Then` is cited in

| The `Then` asserts on | Altitude | Array | What counts as a citation |
|---|---|---|---|
| a stored fact | `data` | `tests[]` | a test calling the query or function directly |
| what a request returns | `response` | `tests[]` | a test against the real handler |
| what a person sees, is told, or lands on | `perception` | `e2eTests[]` | a test driving the real rendered surface |
| whether a model chose well | `judgement` | `evalTests[]` | a scored suite run through a judge |
| behaviour that lives in another repo | `sibling` | `siblingTests[]` | that repo's own test, by path |

A citation in the wrong array is real evidence at the wrong altitude: it stays
in the map and the verdict does not move (CAP-3 shows this).

## Verification block

Run, in order, before calling anything done:

```
python3 capability_find.py --check
python3 ../../skills/promise/scripts/bridge_validate.py docs/designs/channel-muting.md
```

## Shipped work — the mirror direction

Code landed and a test now proves a scenario:

1. Find the row (`python3 capability_find.py "<words from the story>"`) and the
   scenario the test asserts on.
2. Cite the test in the array the scenario's `altitude` picks — never in the
   array the test was convenient to write for.
3. Move `verdict` to `proven` only when every scenario in the row has a citation
   at its own altitude and each citation has been watched to fail under a
   mutation of the production behaviour. One scenario short, or one citation at
   a lower altitude, is `under-proven`.
4. `python3 capability_find.py --check`.
