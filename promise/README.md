# promise

> One doc per capability, the human's decisions verbatim and first — and then the
> promise is carried into the project's capability map, its red tests, and its proof.

An outcome doc *makes* a promise. A proven row in a capability map *keeps* it. A defect
*breaks* it. Most planning skills stop at the doc; most test maps start after the build.
The two never meet, so the doc's acceptance rows and the map's scenarios become two
copies of one promise, and copies drift.

`promise` is one skill over both halves. The Outcome Framework is how a promise is
written down. The capability map is how a project proves it kept it.

## Modes

| Invocation | What it does |
|---|---|
| `/promise <idea, ticket, transcript>` | **new** — interview first, then one outcome doc at `draft` |
| `/promise revise <doc> <change>` | **revise** — evolve a doc; §0 changes go through the human, with the status consequence stated first |
| `/promise review <doc or paste>` | **review** — apply the framework as a code-verified rubric to a doc authored elsewhere; paste-ready findings |
| `/promise merge <docs…>` | **merge** — one doc per capability: fold siblings into a survivor, delete the rest, with the user's yes |
| `/promise arm <doc>` | **arm** — `agreed → building`: file the §6 rows into the capability map, commit them as red tests first |
| `/promise intake <feedback>` | **intake** — feedback in, promise changes out: match each item to an existing row, route it, draft Gherkin, name the test and the kill mutation |
| `/promise reconcile <PR, branch, test file>` | **reconcile** — the work shipped: move a row's verdict only when the evidence reaches the altitude its own `Then` claims |
| `/promise adopt` | **adopt** — set a project up: write `.claude/promise.config.json` and a short `CLAUDE.md` section that routes every agent and person to this skill |

Say what you want in plain words. A leading mode word is a shortcut, never a requirement:
the skill infers the mode from your words and from what it finds in the project, tells you
which it picked, and asks only when two are genuinely plausible.

## What's in the box

```
skills/promise/
  SKILL.md                 the router — contract summary, mode table, Phase 0
  outcome-framework.md     the contract for the doc: template, section rules, lifecycle, rubric
  modes/                   one file per mode, loaded only when that mode runs
  references/              architecture.md · slates.md · altitude.md · anti-rationalizations.md · config.md
  templates/               outcome-doc.md · promise.config.example.json · claude-md-section.md
  scripts/                 orient.py · lint_outcome.py · outcome_rows.py · adopt.py · adapter.py · render_outcome.py · framework_section.py · bridge_validate.py   (Python 3, stdlib only)
tests/                     unit tests and one-change fixtures for every lint rule
```

## The shape of a doc

```
§0 TLDR        ← protected human block: outcome line, rules as bullets (each tagged
                 → AT-n or UNTESTED), how-we'll-know, scenario count. ≤ 40 lines.
§1 Problem     · §2 Outcome     · §3 Worked examples
§4 Invariants  · §5 Mechanism   · §6 Acceptance (AT-n rows; a Row column once bridged)
§7 Build phases · §8 Decisions · §9 Open questions · §10 Out of scope
```

## The bridge

| Doc status | Without a capability map | With one |
|---|---|---|
| `draft` | The doc is the only home of the promise | Same |
| `agreed` | — | `arm` files each §6 row as a not-built row; §6 cites them |
| `building` | Red tests committed first, failing output in §6 | Same, each test cited in the lane its altitude picks |
| `shipped` | Human flips it when the rows are green | Human flips it when every bridged row is proven at its `Then`'s altitude |

## Adopt a project

Run `/promise adopt`. It writes `.claude/promise.config.json` if there is none and inserts a
short fenced section into the project's `CLAUDE.md`, so every agent and person working there
is routed to `/promise` before writing a design, plan or spec doc by hand. Both steps are
idempotent; `adopt.py --dry-run` shows the diff first. Every config field is optional;
without a `map` the skill works on documents alone.

```json
{
  "docsHome": "docs/designs",
  "commands": { "typeCheck": "pnpm type-check", "test": "pnpm test" },
  "map": {
    "recipe": "docs/testing/how-to-add-a-row.md",
    "find": "pnpm capability:find",
    "row": "pnpm capability:find --row",
    "lanes": { "data": "tests[]", "response": "tests[]", "perception": "e2eTests[]", "judgement": "evalTests[]" }
  }
}
```

Full contract: [`skills/promise/references/config.md`](skills/promise/references/config.md).
Design of the skill itself: [`skills/promise/references/architecture.md`](skills/promise/references/architecture.md).

## Scripts

```bash
python3 skills/promise/scripts/orient.py --mode new          # what the project looks like, as JSON
python3 skills/promise/scripts/lint_outcome.py docs/designs   # every shape rule, stable ids, exit 1 on findings
python3 skills/promise/scripts/outcome_rows.py docs/designs/foo.md --json
python3 skills/promise/scripts/framework_section.py "The contract" "Lifecycle"   # only the sections a mode needs
python3 skills/promise/scripts/outcome_rows.py --search "login stays private" --dir docs/designs   # which promise covers this?
python3 skills/promise/scripts/adopt.py --dry-run                 # config + CLAUDE.md section, as a diff
python3 skills/promise/scripts/adapter.py show                    # the project commands the skill would run; runs nothing
python3 skills/promise/scripts/render_outcome.py --title "Export a channel" --owner Ana   # a new doc from the template
python3 skills/promise/scripts/bridge_validate.py docs/designs/foo.md --json   # the bridge's staleness check, against the map
python3 -m unittest discover -s promise/tests -v              # from the repository root
```

## Install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install promise@content-skills
```

Supersedes the `outcome` plugin, which stays for one release.

## License

MIT — see [LICENSE](./LICENSE).
