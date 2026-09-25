# promise

**A spec says what we will build. A promise says what we will make true for users,
and how we will prove it.**

`promise` is a Claude Code skill for teams that ship with coding agents. You write
the outcome and the rules in your own words. The model may argue with them in
numbered notes, but it may not rewrite them. Before any code is written, your
acceptance rows become failing tests, committed on their own. When the work lands,
the doc says which rules are now proven.

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install promise@content-skills
/promise <an idea, a ticket, or a pasted transcript>
```

## The smallest useful path

No config and no project setup. Four steps:

1. `/promise <an idea, a ticket, or a pasted transcript>` — the model interviews you
   (what is true after this ships; why; what must always or never be true; how we'll
   know; one concrete example), then writes one doc at `Status: draft`. Only the
   first answer is required: with less, you get a thin draft (below).
2. You read §0, the short block at the top of the doc. It should be specific enough
   that you *could* disagree with it; when you don't, edit `Status:` to `agreed`.
   The model never types `agreed`.
3. `/promise arm <doc>` — the model branches, writes the acceptance rows as failing
   tests, commits only those test files, records `Red gate: <sha> <date>` in the
   header, and — after you have seen the red output and said yes — writes
   `Status: building`.
4. Build it. When the work lands, `/promise reconcile <PR>` re-stamps which rules
   are now tested and logs the decision. You type `shipped`.

## What you read

This is the part of a doc a founder reads in sixty seconds and can disagree with:

```markdown
## 0. TLDR
*(author: Priya, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member can mute a channel so it stops notifying them.
**Rules:**
- A muted channel never sends a push or a badge count until it is unmuted.  → AT-1, AT-2
- Muting is per member; it never changes what other members see.  → AT-3
**How we'll know:** Ana mutes a busy channel and gets zero notifications from it
for a day, then unmutes and notifications resume.
**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Confirmed there is no existing mute primitive to reuse.
```

Everything under that block — invariants, mechanism with `file:line` evidence,
Given/When/Then rows, build phases — is derived from it by the model and checked
by a linter. The `→ AT-n` tags say which acceptance row tests each rule; `UNTESTED`
is allowed at `draft` and is a lint error once a human marks the doc `agreed`. The
whole doc this block opens is [`examples/channel-muting.md`](examples/channel-muting.md);
what a session looks like on screen is [`examples/transcript.md`](examples/transcript.md).

## Start thin

You do not need every answer to start. When you have the outcome line but not yet
the rules, the signal or an example, `/promise` offers a **thin draft**: `Status:
draft` with `Depth: thin` in the header, §0–§2 in your own words, and §3–§7 marked
"not written yet". Each gap becomes a BLOCKING question in §9, never a line the
model wrote for you. The idea is in version control the same day.

A thin draft cannot be agreed: the lint rejects `Depth: thin` on any status past
`draft` (`THIN_DRAFT`). When the questions have answers, `/promise revise <doc>`
writes the agent half and removes the line. The gates after that are unchanged.

## Why "promise"

An outcome doc *makes* a promise; a proven row *keeps* it; a defect *breaks* it.
A promise has an owner, a person it is made to, and a result you can check. A
spec, an intent or a plan does not have all three.

Each feature starts as a promise in plain words — "a muted channel never sends a
notification". The model cannot change those words; it can only argue with them in
notes. Before the build, the promise becomes failing tests. When they pass, the
promise is kept. When a bug appears, you know which promise it broke.

An `intent.md` records what you want; a promise records what you commit to and how
you will prove it. A thin draft is the intent stage of a promise.

## What a script checks, and what is an instruction to the model

| Enforced by a script (deterministic, exit code) | Where |
|---|---|
| Doc shape: header, headings, §0 budget, rule format and tags, tag resolution, scenario counts, why-lines, placeholders, `UNTESTED` on `agreed` | `lint_outcome.py` (stable rule ids; one-change fixtures under `tests/fixtures/`) |
| A thin draft (`Depth: thin`) stays a `draft`; past `draft` the full shape applies | `lint_outcome.py THIN_DRAFT` |
| Every §6 row names the altitude its `Then` asserts on: `data`, `response`, `perception`, `judgement` or `sibling` | `lint_outcome.py ACCEPTANCE_ALTITUDE`; a table with no `Altitude` column is `ALTITUDE_MISSING`, a warning, so older docs keep linting |
| A `building` doc carries a `Red gate: <sha> <YYYY-MM-DD>` line of the right shape | `lint_outcome.py BUILDING_NEEDS_GATE` |
| A bridged doc's `Row` ids, snapshot line and `Then` text against the map's current text (a bridged doc is one whose §6 rows `arm` has filed into a map) | `bridge_validate.py` |
| Project commands run with the caller's text as one argv element, never a composed shell string — inline or read from a file (`--query-file`, `--search-file`) | `adapter.py`, `outcome_rows.py` |
| A partial map is refused, not run: when `orient.py` reports `mapUsable: false`, `adapter.py` refuses (exit 2) and `bridge_validate.py` reports `MAP_NOT_CONFIGURED`, both naming the missing keys | `orient.py`, `adapter.py`, `bridge_validate.py` |
| Config key names, field types, paths that escape the project, configured paths that are not on disk, `rowIdPattern` compilation | `orient.py` `warnings[]` |

| Followed by the model — not yet script-enforced | Where the rule lives | Planned script |
|---|---|---|
| §0 stays verbatim between revisions; a §0 change drops an `agreed` doc to `draft` | `modes/revise.md` | `diff_outcome.py` |
| A row is promoted only after a watched kill (mutation → test fails → revert → passes) | `modes/intake.md`, `modes/reconcile.md` | `kill_witness.py` |
| `arm`'s git preflight, red run, and test-only red-gate commit | `modes/arm.md` | `arm_gate.py` |
| `agreed` and `shipped` are typed by a human, never by the skill | `SKILL.md`; the wording is locked by `tests/test_status_authority.py` | — |
| Configured project commands run only after `adapter.py show` has been printed and you have said yes, once per session | the router's first step, orient (`SKILL.md` § Phase 0); `references/config.md` § Trust model | — |

Until the planned scripts ship, `references/anti-rationalizations.md` is the guard on
the second table.

## The shape of a doc

```
§0 TLDR        ← protected human block (a mode rule; see the table above): outcome line,
                 rules as bullets (each tagged → AT-n or UNTESTED), how-we'll-know,
                 scenario count. ≤ 40 lines.
§1 Problem     · §2 Outcome     · §3 Worked examples
§4 Invariants  · §5 Mechanism   · §6 Acceptance (AT-n rows, each with an Altitude; a Row column, added or filled once bridged)
§7 Build phases · §8 Decisions · §9 Open questions · §10 Out of scope
```

## Modes

| Invocation | What it does |
|---|---|
| `/promise <idea, ticket, transcript>` | **new** — interview first, then one outcome doc at `draft` (a thin draft when only the outcome line is known) |
| `/promise revise <doc> <change>` | **revise** — evolve a doc; §0 changes go through the human, with the status consequence stated first; fills a thin draft's agent half |
| `/promise review <doc or paste>` | **review** — apply the framework as a code-verified rubric to a doc authored elsewhere; paste-ready findings |
| `/promise merge <docs…>` | **merge** — one doc per capability: fold siblings into a survivor, delete the rest, with the user's yes |
| `/promise arm <doc>` | **arm** — `agreed → building`: commit the §6 rows as failing tests first and record the red gate in the doc; with a map, also file them as not-built rows and cite each test in its lane |
| `/promise intake <feedback>` | **intake** — feedback in, promise changes out: match each item to an existing §6 row (or map row), route it, draft the scenario, name the test and the mutation that would break it |
| `/promise reconcile <PR, branch, test file>` | **reconcile** — the work shipped: re-stamp §0's tags and log the decision; with a map, move a row's verdict only when the evidence reaches the altitude its own `Then` claims |
| `/promise adopt` | **adopt** — set a project up: write `.claude/promise.config.json` and a short `CLAUDE.md` section that routes every agent and person to this skill |

Say what you want in plain words. A leading mode word is a shortcut, never a
requirement: the skill infers the mode, says which it picked, and asks only when
two are genuinely plausible.

## Adopt a project

Run `/promise adopt`. It writes `.claude/promise.config.json` if there is none and
inserts a short fenced section into `CLAUDE.md` so every agent and person in the
repo is routed to `/promise` before writing a design, plan or spec by hand. Both
steps are idempotent; `adopt.py --dry-run` shows the diff first. Every field is
optional. This is the whole config most projects need:

```json
{
  "version": 1,
  "docsHome": "docs/designs",
  "commands": { "typeCheck": "pnpm type-check", "test": "pnpm test" },
  "map": null
}
```

## Optional: a capability map

Most projects need none of this. A *capability map* is a project's own
machine-checked register of promises and the tests that prove each one, with a
verdict per row (`not-built` / `under-proven` / `proven`): what the product
promises, and how much of that is proven today. `arm` offers a starter map when
your first doc is `agreed`. With a map, `arm` files the acceptance rows into it,
`intake` routes feedback onto existing rows, and `reconcile` moves a row's verdict
only when the new evidence reaches the altitude its `Then` claims, after a mutation
was watched to make the cited test fail. [`examples/minimap/`](examples/minimap/) is
a three-row map you can run the bridge against.

Full contract: [`references/config.md`](skills/promise/references/config.md).
Design of the skill itself: [`references/architecture.md`](skills/promise/references/architecture.md).

## Seven words

| Word | Meaning |
|---|---|
| **outcome doc** | The one document per capability, in the Outcome Framework shape. |
| **§0** | Its protected human block: outcome line, rules, how-we'll-know, scenario count. ≤ 40 lines. |
| **AT-n** | A doc-local acceptance-row id in §6. Stable, append-only. |
| **red gate** | The commit that contains only the failing tests; its sha in the header is what `building` records. |
| **altitude** | What a `Then` asserts on — `data`, `response`, `perception`, `judgement`, or `sibling` for a claim about another capability — and therefore the only kind of test that can prove it. |
| **thin draft** | A `draft` with `Depth: thin`: the human half only, each gap a BLOCKING question. It cannot be agreed; `revise` fills it. |
| **capability map** | A project's own register of promises and proof. Optional; the map terms (row, lane, recipe, snapshot line, kill witness) are in [`references/architecture.md`](skills/promise/references/architecture.md) § Vocabulary. |

## What's in the box

```
skills/promise/
  SKILL.md                 the router — contract summary, mode table, Phase 0
  outcome-framework.md     the contract for the doc: section rules, lifecycle, rubric; points at the template
  modes/                   one file per mode, loaded only when that mode runs
  references/              architecture.md · slates.md · altitude.md · anti-rationalizations.md · config.md
  templates/               outcome-doc.md · promise.config.example.json · claude-md-section.md · starter-map/
  agents/                  openai.yaml — Codex skill metadata for the same skill
  scripts/                 orient.py · lint_outcome.py · outcome_rows.py · adopt.py · adapter.py · render_outcome.py · framework_section.py · bridge_validate.py · start_map.py   (Python 3, stdlib only)
examples/                  channel-muting.md (a lint-clean doc, not a fixture) · transcript.md (one annotated session) · minimap/ (a three-row capability map with its find/row/next-id script and config)
tests/                     unit tests and one-change fixtures for the lint rules
```

## Scripts

Run these from the `promise/` directory of this repo (inside an adopted project,
`${CLAUDE_SKILL_DIR}` replaces `skills/promise`). They point at the shipped fixture
`tests/fixtures/conforming.md`; substitute a doc under your `docsHome`.

```bash
python3 skills/promise/scripts/orient.py --mode new                                   # the project, as one JSON object
python3 skills/promise/scripts/lint_outcome.py tests/fixtures/conforming.md           # every shape rule; stable ids; exit 1 on an error finding
python3 skills/promise/scripts/outcome_rows.py tests/fixtures/conforming.md --json    # §0 rules + tags, §6 rows with their altitude
python3 skills/promise/scripts/framework_section.py "The contract" "Lifecycle"        # only the sections a mode needs
python3 skills/promise/scripts/outcome_rows.py --search "muted channel still notifies" --dir examples   # which promise covers this?
python3 skills/promise/scripts/lint_outcome.py --template skills/promise/templates/outcome-doc.md   # the bundled template itself; exit 0
python3 skills/promise/scripts/adopt.py --dry-run                                     # the config + CLAUDE.md section it would write, as a diff
python3 skills/promise/scripts/adapter.py show                                        # the configured project commands; runs nothing
python3 skills/promise/scripts/render_outcome.py --title "Export a channel" --owner Ana --docs-home docs/designs --dry-run   # a new doc from the template, printed, nothing written
python3 skills/promise/scripts/render_outcome.py --title "Export a channel" --owner Ana --docs-home docs/designs --dry-run --thin   # the same, as a thin draft
python3 skills/promise/scripts/bridge_validate.py tests/fixtures/conforming.md --json # the bridge's staleness check (NOT_BRIDGED on a draft)
(cd .. && python3 -m unittest discover -s promise/tests -v)                           # the test suite, stdlib only
```

A freshly rendered doc fails `lint_outcome.py` with `PLACEHOLDER` findings until its
`<…>` slots are filled; that is the intended state of a `draft` nobody has interviewed
for yet. Drop `--dry-run` to write the doc; `--docs-home` is needed only until a config
or an existing docs folder sets `docsHome`, and a folder that does not exist yet is
created only with `--create-docs-home`. `lint_outcome.py --template
skills/promise/templates/outcome-doc.md` is how the bundled template itself is linted
— the flag exempts its `<…>` and `YYYY-MM-DD` placeholders; every other rule stays active.

## Install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install promise@content-skills
# in a project:
/promise adopt                            # optional: config + CLAUDE.md section
/promise <idea, ticket, or transcript>    # first outcome doc
```

### Codex and other hosts

Codex and Cursor read the same `SKILL.md`, but not from a Claude marketplace
checkout: copy or symlink `promise/skills/promise/` to `~/.agents/skills/promise`
(one user) or `<repo>/.agents/skills/promise` (one project), then say
`$promise <what you want, in plain words>`. Two notations are Claude Code-only —
`CLAUDE_SKILL_DIR` and the `!`-prefixed load-time line — and the
"Other hosts" section at the top of `SKILL.md` says how to read them; on Codex,
run `python3 <skill dir>/scripts/orient.py` yourself as the first step.

## Where the ideas come from

Most of the doc shape is prior art, on purpose: §6 is Cucumber-style scenarios with
stable ids (a traceability matrix); §8 is an ADR log; §10 is Google-design-doc
non-goals; `arm` is the failing-test-first gate; the CLAUDE.md section is the
"constitution"/"steering" pattern of spec-kit and Kiro; the kill witness is a
killed mutant from mutation testing. What is new here is narrower: the human's
block is read-only to the model and it may only append notes; rules are never
offered as a pick-list, because a menu of paraphrases is still a paraphrase; and a
row's verdict moves only when evidence reaches the altitude the `Then` sentence was
written at.

## License

MIT — see [LICENSE](./LICENSE).