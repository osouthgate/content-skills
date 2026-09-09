# promise — architecture of the skill

*The durable spec for how this skill is built. Read this before editing any file in
`skills/promise/`. It is also the brief every contributor (human or agent) builds
against, so its interfaces are exact, not illustrative.*

---

## 1. Purpose

`/promise` carries a capability from **intent to proof** in one skill:

1. An **outcome doc** records the promise before anything is built — the human half
   verbatim and protected, the agent half derived (the Outcome Framework).
2. Where the project keeps a **capability map** — a machine-checked register of promises
   and the tests that prove them — the doc's acceptance rows become **rows** in that map
   when the doc is `agreed`, and the map becomes the source of the scenarios from then on.
3. **Arm** writes the acceptance rows as red tests. **Reconcile** moves a row's verdict
   only when the evidence reaches the altitude the row's own `Then` claims. **Intake**
   files feedback against existing promises instead of spawning new documents.

The Outcome Framework is how a promise is written down. The capability map is how the
project proves it kept it. This skill is the router over both.

The name is deliberate: an outcome doc *makes* a promise; a proven row *keeps* it; a
defect *breaks* it. One word covers both halves, so the skill is named for it rather than
for either half.

## 2. Decisions this shape rests on

| # | Decision | Why |
|---|----------|-----|
| S1 | **One skill, thin router, mode files loaded on demand, scripts for mechanics.** Not a set of sibling skills; not one monolith. | Claude Code routes subcommands in prose only (`$0` is the word; there is no frontmatter dispatch) and documents no skill-to-skill call, so a router of sibling skills would have to duplicate the contract into every sibling. A single large file would load every mode's instructions on every run although the modes are mutually exclusive, and would exceed the ≤500-line SKILL.md guidance. |
| S2 | **Config over fork.** The plugin is generic. A project supplies `.claude/promise.config.json` (§6). No project-specific path, command or vocabulary is hard-coded anywhere in this skill. | One implementation serves every repository; a project supplies only what differs. A per-project fork of the skill is a second copy of the contract, and two copies of a contract drift apart. |
| S3 | **The framework wins.** `outcome-framework.md` beside SKILL.md is the contract for the doc: template, section rules, lifecycle, review rubric. A project copy at `config.frameworkPath` wins over the bundled one. Mode files cite framework sections by number; they never restate them. | One home for the doc contract, and the mode files stay short. |
| S4 | **After `agreed`, where a map exists, the map is the source of scenarios.** §6 of the doc cites the map's rows (a `Row` column); it does not carry a second, independently edited copy. §0's rule tags keep the doc-local `AT-n` aliases, which are stable and append-only. | One promise, one home. A copy made at `agreed` would drift the day after. |
| S5 | **Scripts are Python 3, standard library only, invoked via `${CLAUDE_SKILL_DIR}`.** One implementation runs on every OS. `python3` on POSIX, `python` on Windows if `python3` is absent. No `.sh`/`.ps1` parity pairs. | A parity pair is two implementations of one behaviour. Markdown parsing in shell is unreliable. |
| S6 | **Mechanical steps are scripts; judgement is prose; decisions are made in front of the user.** Sub-agents may rank, read and draft. They never decide a routing, a verdict move, a merge, or a status change. | Delegating enumeration is free; delegating a decision loses the reason it was made. |
| S7 | **Every checkable rule of the framework has a check in `lint_outcome.py`**, and the check runs at the end of every writing mode. What the lint cannot check, the mode file says so, in one line. | A rule that is only written down is advisory; a rule with a check is enforced. The lint makes the framework's shape rules hold in every doc, not only in the ones a careful author wrote. |

## 3. File tree (exact)

```
promise/                                  ← the plugin
  .claude-plugin/plugin.json
  LICENSE            README.md            CHANGELOG.md
  skills/promise/
    SKILL.md                              ← router. ≤ 150 lines. Frontmatter + contract summary + mode table + dispatch + Phase 0.
    outcome-framework.md                  ← THE contract for the doc (template, rules, lifecycle, rubric, decisions F1–F7)
    modes/
      new.md        revise.md    review.md    merge.md
      arm.md        intake.md    reconcile.md    adopt.md
    references/
      architecture.md                     ← this file
      slates.md                           ← outcome-line slate + signal slate procedures; rules are never slated
      altitude.md                         ← the proof taxonomy: signal kinds ↔ altitudes ↔ lanes ↔ what counts as evidence
      anti-rationalizations.md            ← the excuse/reality table, all modes
      config.md                           ← user-facing contract for .claude/promise.config.json
    templates/
      outcome-doc.md                      ← the §0–§10 skeleton, ONE canonical shape
      promise.config.example.json         ← every field, with comments in a sibling `$comment`
      claude-md-section.md                ← the ≤20-line block `adopt` inserts into a project's CLAUDE.md (§13)
    scripts/
      orient.py                           ← Phase 0: resolve framework, config, docs home, commands, existing docs → JSON
      lint_outcome.py                     ← shape checks over one doc or a directory → findings, exit code
      outcome_rows.py                     ← extract §0 rules+tags and §6 rows as JSON; the bridge's input
      adopt.py                            ← write the config and the CLAUDE.md section, idempotently (§13)
      framework_section.py                ← print named `## ` sections of the resolved framework; modes read sections, not the file
  tests/
    test_scripts.py                       ← unittest; runs with `python3 -m unittest discover promise/tests`
    fixtures/                             ← one conforming doc + one fixture per violation class + a mini repo
```

Budgets, enforced by review: `SKILL.md` ≤ 150 lines; each `modes/*.md` ≤ 220 lines; each
`references/*.md` ≤ 220 lines except this file and the framework. A mode file that needs
more is restating the framework — cite it instead.

## 4. Mode dispatch — the input decides, not the syntax

The user types `/promise` and says what they want in plain words. **A leading mode word is a
shortcut, never a requirement.** People will not remember eight mode names and must not have
to. The router reads the input and Phase 0's findings, names the mode it inferred in one
line ("Reading this as **reconcile** — you named a PR"), and proceeds. It never answers "use
`/promise <mode>`", never refuses for syntax, and asks only when two modes are genuinely
plausible — then as one question with a `(Recommended)` option first, one reason, and a
completeness score per option.

| Mode | Mode file | The input looks like… |
|---|---|---|
| `new` (default) | `modes/new.md` | an idea, ticket, transcript or braindump; "design / plan / spec this", "write a doc for X", "how should we build X" — and nothing below matches |
| `revise` | `modes/revise.md` | a path to, or the title of, an existing outcome doc plus a change: "update", "add a rule", "change the outcome", "the signal is wrong", "tighten §5" |
| `review` | `modes/review.md` | a substantial doc, URL or paste authored elsewhere plus a critique verb: "review", "critique", "feedback", "is this any good", "check this against the framework" |
| `merge` | `modes/merge.md` | two or more doc paths or titles; "fold these", "these overlap", "consolidate", "which one survives" |
| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", "arm it", "write the red tests", "file the rows", "kick off the build" |
| `intake` | `modes/intake.md` | a list of complaints, wishes, bug reports or feedback about the product; "what does this map to", "turn this into scenarios / gherkins", "which capability covers X", "add this as a scenario to <row>" |
| `reconcile` | `modes/reconcile.md` | a PR number, branch, commit or test file; "we shipped X", "we already do this", "isn't X covered", "update the map / the row / the doc now that Y landed" |
| `adopt` | `modes/adopt.md` | "set this project up", "install / configure promise here", "add promise to CLAUDE.md" — or Phase 0 reports the project is not adopted and the user agrees to fix that first |

Inference uses Phase 0 too: an input that names or matches the title of a doc in
`existingDocs` leans `revise` (with a change) or `review` (with a critique verb); an input
matching `map.rowIdPattern` leans `intake` or `reconcile`; an input naming a test file or a
commit leans `reconcile`. A recognised first word (`new`, `revise`, `review`, `merge`, `arm`,
`intake`, `reconcile`, `adopt`) wins outright and skips inference.

SKILL.md loads **only** the mode file for the detected mode, plus the references that mode
names in its header. It never loads all eight.

## 5. Phase 0 — orient (every mode, every run)

SKILL.md runs, at load time or as its first action — with no part of the user's message on
the command line, because a quote in the message would break the shell line and user text is
never composed into a command:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py" [--mode <mode>] [--cwd <path>] [--input-file <path|->]
```

`orient.py` never fails hard on a valid invocation. It prints one JSON object to stdout and
exits 0; problems go in `warnings[]`. A usage error (an unknown flag) exits 2 like any CLI. When `python3` itself is absent, the router names the host's one-line
install and continues by applying the scripts' rules by hand for that run; a second
implementation in another language is refused (S5), because two implementations of one
rule set drift and then the same doc passes in one project and fails in another. Schema (every key always present; `null` when unknown):

```json
{
  "skillDir": "/abs/path/to/skills/promise",
  "cwd": "/abs/path/of/project",
  "mode": "new",
  "frameworkPath": "/abs/path — the project copy if config.frameworkPath exists, else the bundled copy",
  "frameworkSource": "project | bundled",
  "config": { "path": "/abs/.claude/promise.config.json or null", "loaded": true, "raw": { } },
  "docsHome": "docs/designs",
  "docsHomeSource": "config | detected | none",
  "plansFolder": "plans or null",
  "commands": { "typeCheck": "pnpm type-check or null", "test": "pnpm test or null", "lint": "pnpm lint or null", "source": "config | detected | none" },
  "map": { "…the config.map object verbatim, or null…" },
  "claudeMd": { "path": "/abs/CLAUDE.md or null", "hasPromiseSection": false },
  "adopted": false,
  "mapUsable": false,
  "suggestedMode": "revise or null — from --input, see below",
  "signals": [ "matches existing doc 'Foo' + a change verb" ],
  "ambiguous": false,
  "existingDocs": [ { "path": "docs/designs/foo.md", "title": "Foo", "status": "draft", "lastDecision": "YYYY-MM-DD" } ],
  "warnings": [ "no config found at .claude/promise.config.json; using detection" ]
}
```

Detection rules when config is absent:

- **docsHome**: first existing of `docs/designs`, `docs/design`, `docs/specs`, `docs/rfcs`,
  `design`, `docs`. None → `null`, and the mode asks the user before writing. The skill
  never creates a docs folder.
- **plansFolder**: `plans` if it exists, else `null`.
- **commands**: from `package.json` `scripts` (`type-check` | `typecheck` | `tsc` → typeCheck;
  `test`; `lint`) prefixed by the package manager the lockfile implies (`pnpm-lock.yaml` →
  `pnpm`, `yarn.lock` → `yarn`, `bun.lockb` → `bun`, else `npm run`); else `Makefile` targets
  of the same names (`make <target>`); else `justfile` recipes (`just <recipe>`); else `null`.
- **existingDocs**: every `*.md` under docsHome (one level deep) whose text contains a line
  starting `## 0. TLDR`. `status` is the first token after `Status:`; `title` is the H1.
- **claudeMd**: `CLAUDE.md` at the project root, else `.claude/CLAUDE.md`, else `null`.
  `hasPromiseSection` is true when the file contains the marker `<!-- promise:begin`.
- **adopted**: true when a config was loaded AND `claudeMd.hasPromiseSection` is true. When
  false, `warnings[]` carries `project not adopted — run /promise adopt`, and the router
  offers `adopt` once per session (Recommended) before continuing with the requested mode.
- **suggestedMode / signals**: `--input-file <path>` (or `-` for stdin; `--input "<text>"`
  exists for tests and programmatic callers) makes the
  script read the input against the §4 table deterministically — a leading mode word, an
  `existingDocs` title or path plus a critique or change verb, two doc matches, a PR or
  commit or test-file pattern, a `map.rowIdPattern` match, a list of complaints, an
  adopt phrase — and name the rule that fired. Without the flag both are `null` / `[]`.
  `ambiguous` is true only when two rules for different modes both matched; then the router
  asks. It is a hint the router confirms in its one-line statement, never a decision.
- **mapUsable**: true only when `map` carries `recipe`, `find`, `row` and `lanes` with the
  right types; an incomplete map stays in `map` with a warning naming the missing keys, and
  the modes treat it as not configured.

The mode file states, in one line, what Phase 0 resolved: mode (and that it was inferred,
if it was), framework source, docs home and its source, whether a map is configured, and
whether the project is adopted.

## 6. Config contract — `.claude/promise.config.json`

Location: `<project>/.claude/promise.config.json`; fallback `<project>/promise.config.json`.
All fields optional. Unknown fields are a warning, not an error.

```json
{
  "$schema": "promise.config/v1",
  "docsHome": "docs/designs",
  "frameworkPath": "docs/how-to/outcome-framework.md",
  "plansFolder": "plans",
  "commands": { "typeCheck": "pnpm type-check", "test": "pnpm test", "lint": "pnpm lint" },
  "map": {
    "recipe": "docs/testing/adding-or-extending-a-capability.md",
    "index": "docs/testing/AGENTS.md",
    "find": "pnpm capability:find",
    "row": "pnpm capability:find --row",
    "nextId": "pnpm capability:find --next-id",
    "rowIdPattern": "^C\\d+[a-z]?$",
    "lanes": {
      "data": "tests[]", "response": "tests[]", "perception": "e2eTests[]",
      "judgement": "evalTests[]", "sibling": "osdbTests[]"
    },
    "checks": [
      "npx vitest run apps/web/src/__tests__/capability-coverage.test.ts",
      "pnpm test:declare",
      "pnpm citations:strength",
      "pnpm coverage:report"
    ],
    "issueTracker": { "kind": "github", "repo": "owner/repo", "template": ".github/ISSUE_TEMPLATE/capability-work.md" }
  }
}
```

Semantics the mode files rely on:

- **`map` absent** → there is no capability map. `arm` writes red tests only. `intake`
  matches feedback against the §6 rows of the docs in `docsHome` and files the routing
  table into the doc (§6 / §9). `reconcile` updates the doc only (tags, `Scenarios:`
  count, a dated §8 entry). Each of those modes says "no map configured" in its Phase 0
  line.
- **`map.recipe`** is the project's own how-to for writing a row. **It is the authority
  for the mechanics** — which files a row touches, what lockstep means there, what a
  citation looks like. The mode files never restate a project's mechanics; they say "read
  the recipe, work from the file". The generic *procedure* (split, match, route, draft,
  prove, apply, verify) lives in the mode file; the *mechanics* live in the recipe.
- **`map.find` / `map.row` / `map.nextId`** are shell commands the modes run verbatim with
  the argument appended (`<find> "<query>"`, `<row> <id>`).
- **`map.lanes`** maps the four altitudes (plus `sibling`) to the project's evidence-array
  names, so `altitude.md` can be generic and the mode file can say "cite in the lane the
  altitude picks".
- **`map.checks`** run at the end of `arm`, `intake` and `reconcile`, in order, before the
  mode hands back.

## 7. Vocabulary (use these words; define nothing else)

| Word | Meaning |
|---|---|
| **promise** | Something a person will be able to do, stated so it can be checked. An outcome doc makes one; a row keeps or breaks one. |
| **outcome doc** | The one document per capability in the Outcome Framework shape. |
| **capability map / map** | A project's machine-checked register of promises and their proof. Optional; configured in §6. |
| **row** | One entry in the map: a user story plus 1–5 Gherkin scenarios, evidence arrays, a verdict. Ids follow `map.rowIdPattern`. |
| **AT-n** | A doc-local acceptance-row id in §6. Stable, append-only. After the bridge it is an alias for a row's scenario, never a second copy. |
| **altitude** | What a `Then` asserts on: **data** (a stored fact), **response** (what a request returns), **perception** (what a person sees, is told, lands on), **judgement** (whether a model chose well). |
| **lane** | The kind of test that reaches an altitude, and the evidence array it is cited in. |
| **verdict** | The row's honest proof state (`proven` / `under-proven` / `not built` / `awaiting-decision`, or the project's own enum). It moves only when evidence reaches the `Then`'s altitude. |
| **kill witness** | A recorded production mutation that a cited test is known to catch. No watched kill, no promotion. |
| **signal** | §0's *how we'll know*: one of four kinds — a red→green test, a watched demo, a number in prod, a claim we can make to a customer. |

## 8. The bridge — doc status × map

| Doc status | Without a map | With a map |
|---|---|---|
| `draft` | Doc is the only home. §6 rows are the promise. | Same. Nothing is filed in the map yet. |
| `agreed` (human act) | — | `arm` files each §6 row as a **not-built row** per the recipe. A person groups AT rows into rows **by the §0 rule each row is tagged from** — a rule is the promise at story grain — one row = one story, 1–5 scenarios; more is a chain with a parent; rows no rule cites are one group the person places. §6 gains a `Row` column and a snapshot line, and is not edited again: it is the record of what was agreed, the map is the live source. §0 tags keep AT aliases. A staleness check between the two is planned (§14). |
| `building` | Red tests written and committed first; failing output pasted in §6; sha in header. | Same, plus each red test is cited in the lane its altitude picks. |
| `shipped` | Human flips it when §6 rows are green. | Human flips it when **every** bridged row is `proven` at its `Then`'s altitude. `reconcile` is how rows get there. Doc keeps §0, §2, §4 as the living record. |

`agreed` and `shipped` are typed by a human. `building` is written by `arm`, only after
the human has seen the red-gate commit and confirmed it — the commit is the human act
the status records. `revise` states when a §0 change would drop a doc back to `draft`.

## 9. `lint_outcome.py` — what it checks

```
python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc.md | directory> [--json] [--strict] [--template]
```

Exit 0 when no error-severity findings; exit 1 when any error (or, under `--strict`, any
warning); exit 2 on a usage error. Human output is one line per finding:
`<path>:<line>: <RULE_ID> <message>`. `--json` prints
`{"path": …, "findings": [{"rule": …, "line": …, "message": …, "severity": "error|warn"}], "stats": {…}}`
for one file, and a JSON array of those objects for a directory, so stdout is always one
parseable value. A directory lints every `*.md` containing `## 0. TLDR`.

| Rule id | Checks | Severity |
|---|---|---|
| `HEADER_STATUS` | A `Status:` line exists and its first token is one of `draft` `agreed` `building` `shipped` `superseded-by`; `superseded-by` names a target. Other text after the token is allowed. | error |
| `HEADER_OWNER` | `Owner:` and `Last decision:` present, with non-empty values. | error |
| `CONTENTS_LINE` | A `Contents:` line exists and links to all eleven anchors `#0-tldr` … `#10-out-of-scope`. | error |
| `HEADINGS_BARE` | Exactly one `## <n>. <Name>` per n in 0..10, matching the template's names, with nothing after the name on that line. | error |
| `TLDR_BUDGET` | Lines from `## 0. TLDR` up to (not including) the `Agent notes` line — or `## 1.` if there are none — number ≤ 40. Report the count. | error |
| `TLDR_FIELDS` | The block contains `**Outcome:**`, `**Rules:**`, `**How we'll know:**`, `**Scenarios:**`, and the Outcome and How-we'll-know values are non-empty. | error |
| `RULES_FORMAT` | Every rule is a `- ` bullet with text before its tag. Numbered rules, and any other non-blank text in the rules block, are findings. | error |
| `RULES_TAGGED` | Every rule ends with `→ AT-n[, AT-m…]` or `→ UNTESTED`. | error |
| `TAGS_RESOLVE` | Every `AT-n` cited in a §0 tag exists as a row id in §6. | error |
| `AT_IDS_UNIQUE` | §6 row ids are unique and match `AT-\d+`. | error |
| `ACCEPTANCE_TABLE` | §6 holds at least one acceptance table — header first cell `#`, `ID` or `AT`, four or five columns — with at least one data row; every data row has the right cell count and non-empty Given, When and Then. Other tables in §6 are ignored. | error |
| `SCENARIOS_COUNT` | The `**Scenarios:**` line's acceptance-row count equals the number of §6 rows. The worked-example count is checked only if §3 examples are parseable (`### ` or bold-led blocks); otherwise `warn` that it was not checked. | error / warn |
| `WHY_LINE` | §4, §5, §6, §7 each contain a line beginning `Why — what breaks without it:`. | error |
| `UNTESTED_ON_AGREED` | A rule tagged `UNTESTED` while `Status:` is `agreed`, `building` or `shipped`. | error |
| `PLACEHOLDER` | `TBD`, `TODO`, `<fill`, `decide later` inside §0; any `<…>` placeholder in §0, in the `Owner:` / `Last decision:` values, or in a §6 data cell; a literal `YYYY-MM-DD`. `--template` exempts the angle-bracket and date placeholders so the bundled template can be linted; every other rule stays active. A copied, unfilled template therefore fails a normal lint. | error |
| `UNREADABLE` | The path cannot be read or is not valid UTF-8 — one finding for the file, never a traceback. | error |
| `AGENT_NOTES_MANY` | More than 8 numbered agent notes under §0. | warn |
| `HUMAN_HALF_BUDGET` | §0 through the end of §2 plus the first §3 example ≤ 150 lines (measured to the end of §2 when §3 is not parseable; say so). | warn |

`--strict` promotes `warn` to `error`. `HEADINGS_BARE` fires on a malformed heading even when a
well-formed heading for the same number also exists. The lint is deterministic and needs no
network.

## 10. `outcome_rows.py` — the bridge's input

```
python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc.md> [--json]
```

Prints `{"path", "status", "rules": [{"index", "text", "tags": ["AT-1", …] | ["UNTESTED"]}],
"rows": [{"id": "AT-1", "given", "when", "then", "row": "C207" | null}], "signal": "…"}`.
`row` is the optional `Row` column (§8). A rule with no tag at all yields `tags: []`, which
the lint reports as `RULES_TAGGED`; the script extracts, it does not judge. Human output is
a compact table. This is what
`arm` reads to file rows and what `reconcile` reads to re-stamp tags. Two more flags:
`--write-counts` rewrites only the `**Scenarios:**` line from the real §6 row count (and
the §3 example count when countable), idempotently — the count is agent-maintained
metadata, so a script may own it; `--search "<text>" --dir <docsHome>` ranks every §6 row
and §0 rule across the docs by token overlap — intake's matcher when no map is configured.

## 11. Rules for every file in this skill

- **Cite the framework by section; never restate it.** "§6 rows — framework § *Acceptance*"
  is a citation. A paragraph explaining what §6 is, is a copy. A mode's header names the
  framework sections it needs (`outcome-framework.md § The contract · § Lifecycle`) and
  reads only those, through `scripts/framework_section.py`; only `new` needs most of it.
- **Each mode file opens with a 3-line header**: `Read before this:` (the reference files
  this mode needs), `Phase 0 line:` (what to state), `Writes:` (which files it may touch).
- **Sanitised.** No real people, companies, repo paths, dates or ticket ids from any
  project. Actors in examples are `Ana`, `Ben`, `Priya`. Project-shaped facts are shown as
  config, never as prose.
- **Every recommendation put to the user is one option marked `(Recommended)` first, with
  one concrete reason, and a 1–10 completeness score per option.** Every decision is the
  user's; the skill never resolves a `BLOCKING` question by drafting.
- **The user's edit enters, not the candidate.** Wherever a slate or draft is approved
  with changes, the changed text is what is written.
- **Verify before believing.** A current-state claim carries `file:line` the writer read
  this run. A test found uncited is evidence only after it was watched dying.
- **Say what was not checked.** Every mode's close-out names what it could not verify.
- **Never require syntax.** A mode word is a shortcut; the input decides (§4). `/promise fix
  the doc` gets `revise`, not a usage message.

## 12. Tests for the scripts

`python3 -m unittest discover -s promise/tests -v` must pass on a clean checkout with no
third-party packages. Fixtures cover: one fully conforming doc (lint exits 0); one fixture
per `error` rule in §9 (each is caught, and only it); `orient.py` against a fixture mini
repo (`package.json` + `pnpm-lock.yaml` + `docs/designs/` with one outcome doc) and
against an empty directory (all-null, warnings present, exit 0); `outcome_rows.py`
round-trips the conforming fixture; `adopt.py` on a temp project (dry-run writes nothing;
first run creates the config and the CLAUDE.md section; second run is a byte-identical
no-op; a hand-edited block is restored in place; a missing CLAUDE.md is created; a
pre-existing config is never overwritten) and `orient.py` then reports `adopted: true`. A
fixture that could not fail is worse than none — each violation fixture is the conforming
doc with exactly one change.

## 13. `adopt.py` — the config and the CLAUDE.md section

A project is **adopted** when it has a config (§6) and its `CLAUDE.md` carries the promise
section, so every person and agent working in that repository is routed to this skill
instead of writing a design, plan or spec doc by hand.

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" [--cwd <path>] [--dry-run] [--docs-home <dir>] [--no-config] [--no-claude-md]
```

- **Config**: writes `.claude/promise.config.json` if absent — `docsHome` (from
  `--docs-home`, else orient's detection, else omitted), `commands` (detected), and
  `"map": null` with a sibling `$comment` saying what to fill in and pointing at
  `references/config.md`. It never overwrites an existing config, and says so.
- **CLAUDE.md section**: renders `templates/claude-md-section.md` with `{docsHome}`,
  `{configPath}` and `{frameworkPath}`, and places it between `<!-- promise:begin` and
  `<!-- promise:end -->` markers: appended after a blank line when absent, replaced in place
  when present, `CLAUDE.md` created at the project root when no file exists. The rendered
  block is ≤ 20 lines and says: capability work goes through `/promise` in plain words (the
  mode is inferred); one doc per capability in the docs home, in the Outcome Framework
  shape; §0 is the human's verbatim block and agents only append notes below it; `Status:`
  moves forward only by a human; where a map is configured it is the source of scenarios
  after `agreed` and a verdict moves only at the altitude the row's own `Then` claims;
  before writing any design, plan or spec doc by hand, run `/promise` — a sibling doc is a
  bug.
- **Idempotent**: a second run with the same inputs changes no bytes and reports
  `"changed": false`. `--dry-run` prints a unified diff and writes nothing.
- Exit 0 on success or no-op; 2 on a usage error. Prints one JSON object on stdout:
  `{"configWritten": bool, "configPath": "…", "claudeMdWritten": bool, "claudeMdPath": "…", "changed": bool, "dryRun": bool}`.

The `adopt` mode confirms the docs home and the config contents with the user
(Recommended-first, scores), runs the script, then runs `orient.py` and shows `adopted` is
now true. Every other mode offers `adopt` once per session when Phase 0 reports the project
is not adopted, and continues with the requested mode either way.

## 14. Scripts that exist, and scripts that are planned

Shipped: `orient.py`, `lint_outcome.py`, `outcome_rows.py`, `adopt.py`,
`framework_section.py`, `adapter.py` (runs every configured command with the user's text
as one argument — never a composed shell string), `render_outcome.py` (instantiates the
template; refuses to overwrite).

Planned, in the order they pay back. Each replaces a step a mode currently performs by
reading prose, so drift is the cost of not having it:

| Script | Replaces | Used by |
|---|---|---|
| `inspect_outcome.py DOC` | status, BLOCKING count, lint result, §0 text, note count, UNTESTED rules, counts, Row references — one JSON for every close-out | new, revise, review, arm, reconcile |
| `diff_outcome.py BEFORE AFTER` | the three erosion classes and status movement, as a diff the model then judges | revise, review, merge |
| `bridge_validate.py DOC` | Row ids against `rowIdPattern`, every AT row mapped, the §6 snapshot against the map's current scenarios | arm, reconcile |
| `evidence_probe.py --ref PR\|SHA\|BRANCH\|FILE` | changed files, declared row ids, cited and uncited test titles, ranked candidates | reconcile, intake |
| `kill_witness.py --test … --mutation …` | clean-tree check, apply the approved mutation, capture the named failure, restore exactly, rerun green, print the witness | intake, reconcile |
| `arm_gate.py DOC --branch SLUG` | the Git preflight, the red run, staged-path inspection, the explicit-path commit | arm |
| `issue_search.py --tracker … --row … --text …` | open and closed duplicate candidates before any issue is filed | intake, reconcile |
| `feedback_items.py INPUT` | numbering already-structured items and flagging compound sentences; the split stays a judgement | intake |
| `inventory.py --docs-home DIR --query TEXT` | §0 rules, §5 claims and §6 rows across docs, exact duplicates, ranked overlaps | new, merge |
