# Anti-rationalizations

*Excuse → reality, all modes. Cite "framework § <Name>" or "architecture § <Name>" for
the rule behind each reality line; this file does not restate either.*

| Excuse | Reality |
|---|---|
| "The braindump is clear enough, I'll write the rules block myself." | Then the block starts life as a paraphrase, and a paraphrase can read as faithful while asserting something the source didn't. Confirm line by line. |
| "I'll tidy the wording inside the rules block." | The block is read-only. Append a numbered note. |
| "This overlaps an existing plan but merging is disruptive." | A sibling doc is a bug. Propose the merge; the user decides. |
| "The why-line for this section is obvious." | Then it costs one line. If you can't write it, the section goes. |
| "I'll fill in 'how we'll know' — it's implied." | Outcomes are decided, not generated. Ask. |
| "Status agreed is a formality, I'll flip it." | It's the human act the whole framework protects. Never. |
| "The revision improved, no need to diff it." | Revisions are where decisions erode, quote blocks drift, and content silently dies. Diff every re-review. |
| "The doc's claims cite code, so they're grounded." | Cited ≠ verified. An invented identifier reads exactly like a real one until you grep for it. Check them. |
| "The user hasn't answered the sheet, so I'm blocked." | Only new-doc drafting waits on the human half. Review, iterate, verify — and re-surface the open remainder compactly. |
| "The doc is good, I'll just link it." | If the reviewer can't disagree with §0 alone, the doc failed, whatever else it contains. Paste §0 inline. |
| "They haven't picked a signal, I'll leave a placeholder." | A placeholder reads as done-and-deferred and survives to `agreed`. Present the verbatim candidate slate; if unanswered, the doc stays `draft` with a BLOCKING question. |
| "The outcome line is obvious from the ticket, I'll just write it." | Then §0 opens with your framing, ratified by nobody. Ask once; if the answer isn't one crisp line, slate it with sources — and keep "none of these" on the list. |
| "They liked candidate B, so B goes in." | If they edited B, the edit goes in, not B. Quote the final text back before it enters §0. |
| "The rules are slow to confirm — I'll offer a pick-list instead." | Rules are the one thing never slated. Pickable rules are agent framing with a human signature on it — the exact loop the framework exists to break. |
| "The project copy of the framework isn't there, I know the template anyway." | Then you're working from memory of a doc that changes. Fall through to the bundled copy and read it. |
| "This project has no detected docs home, I'll create one." | Phase 0 resolves `docsHome` from config or detection; when neither finds one it's `null` and the mode asks before writing. The skill never creates a docs folder — one you invent is a sibling-doc problem you authored. |
| "Running `/promise` implies I can auto-invoke another skill for §4." | It doesn't. If the project has an invariants-analysis skill, offer it in one line and wait for a yes — running one skill isn't consent to auto-invoke a second. Declined or absent, derive §4 directly. |
| "It's just a wording tweak to a rule in a revision." | Wording is meaning. It's a §0 change: propose it, confirm it verbatim, and say what it does to the status and to any `→ AT-n` test. |
| "The PR merged, so the row is proven." | A PR merging says the code shipped, not that the test was watched to catch the row's actual defect. No kill witness, no promotion (architecture § Vocabulary) — the verdict moves when the evidence reaches the `Then`'s altitude, not when the branch does. |
| "A test already exists for this row, I'll cite it." | An existing-but-uncited test is a candidate, not proof. Watch it fail against the row's Given/When before citing it — a test never seen to catch the failure might be passing for an unrelated reason. |
| "The feedback says it's broken, so it's a defect." | Feedback names a symptom, not a row. Match it to the specific promise it contradicts and verify the failure against that row's `Then` before filing a defect — otherwise it's a routing guess, and the wrong row's verdict moves. |
| "The grouping of acceptance rows into map rows is obvious, I'll do it." | Grouping is a product judgment — the "so that" behind a set of scenarios — not a mechanical fold. Architecture § The bridge makes it a human act at `agreed`; the agent proposes the grouping, it doesn't file it unapproved. |
| "The map's recipe is long, I know the mechanics." | The recipe is the authority for that project's mechanics, and it's the thing most likely to have changed since you last read it. Read it fresh from the file every time — working from memory of a doc that changes is exactly how drift starts. |
| "I'll bump the ratchet so the run passes." | A ratchet locks a count so it can only improve. Moving it to make today's run pass records the regression as the new baseline instead of fixing it — run `map.checks` (architecture § Config contract) to see what actually failed, then fix that. |
| "This is data-altitude evidence for a perception Then, close enough." | A database check proves the data changed, not that anyone saw it. A `Then` about perception needs perception-lane evidence (architecture § Vocabulary — altitude, lane); a lower-altitude proof standing in for a higher one is the gap the bridge exists to catch, not a rounding error. |
| "The user didn't give a mode word, I'll ask which mode they meant." | Infer it from the input and Phase 0's findings, state the inference in one line, and proceed. Ask only when two modes are genuinely plausible, and then as one Recommended-first question. |
| "The project has no CLAUDE.md section for promise — not my job." | Phase 0 reports it as `adopted: false`. Offer `adopt` once, with the reason, then continue with what was asked. |
| "I'll paraphrase the CLAUDE.md block to fit this project's style." | The block is rendered by `adopt.py` between markers so it stays identical everywhere and can be replaced in place. Change the template, not the instance. |
