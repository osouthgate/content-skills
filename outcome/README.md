# outcome

> One doc per capability, with the human's decisions in verbatim and first — and a
> §0 TLDR a founder can read in 60 seconds and disagree with.

Most planning docs are the agent's *output*: a human writes intent, an agent expands it
into a plan, a reviewer reviews the expansion — a paraphrase of a decision, several
removes from the decision itself. Meaning drifts silently, plans proliferate, and the
hard questions get quietly deferred to the model.

This plugin inverts that. The doc is the agent's **input**: the human half (outcome,
rules, success signal) enters verbatim after line-by-line confirmation and is protected
from rewriting; the agent's job is to find contradictions in it, propose the mechanism
with file:line evidence, and derive testable acceptance.

## What's in the box

- **`skills/outcome/SKILL.md`** — the `/outcome` skill: five modes
  (`new` / `revise` / `review` / `merge` / `arm`).
- **`skills/outcome/outcome-framework.md`** — the framework itself: the contract, the
  11-section template (with a clickable table of contents), section rules, lifecycle,
  and the review rubric. The skill defers to it wherever they disagree.

## The shape of a doc it produces

```
§0 TLDR        ← protected human block: outcome line, rules as bullets (each
                 tagged → AT-n or UNTESTED), how-we'll-know, scenario count.
                 ≤ 40 lines. If a reader can't disagree with §0 alone, the
                 doc failed.
§1 Problem     ← current behaviour, with evidence
§2 Outcome     ← what's true after, and why
§3 Worked examples  ← named actors, concrete state, expected outcome
§4 Invariants  ← "X must never Y", each with enforcement point + boundary
§5 Mechanism   ← file:line evidence, commit-pinned; uncapped when dense
§6 Acceptance  ← Given/When/Then rows with stable AT-n IDs → become red tests
§7 Build phases
§8 Decisions   ← owners, dates, partial rulings
§9 Open questions   ← BLOCKING flags
§10 Out of scope
```

Key mechanics:

- **Protected human half.** Agents may never rewrite, expand, or paraphrase inside §0 —
  disagreements become numbered notes below the block. Candidate blocks extracted from
  transcripts are frozen until a human confirms them line by line.
- **Rules map to tests.** Every §0 rule carries the acceptance-row IDs that test it, or
  reads `UNTESTED` — visible at a glance, mirroring `UNENFORCED` on invariants.
- **The success signal is a forced choice.** "How we'll know" is elicited as a verbatim
  candidate slate (red→green test / watched demo / prod number / customer claim) —
  never a placeholder. And once chosen, the signal is re-read against every open
  decision: a signal that can't be staged under an option has ruled that option out.
- **Review mode.** Point it at a doc authored elsewhere and it applies the framework as
  a rubric — verifying claims against live code before critiquing, diffing re-revisions
  for decision erosion and quote drift, and delivering paste-ready inline feedback.
- **Arm mode.** `agreed → building` means the acceptance rows are committed as failing
  tests first, RED proof pasted into the doc.

## Install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install outcome@content-skills
```

Then: `/outcome <idea, ticket, or transcript>` — or `/outcome review <doc>` to apply
the rubric to something another agent wrote.

## License

MIT — see [LICENSE](./LICENSE).
