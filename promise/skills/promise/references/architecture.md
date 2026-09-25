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

## 2. Decisions this shape rests on

| # | Decision | Why |
|---|----------|-----|
| S1 | **One skill, thin router, mode files loaded on demand, scripts for mechanics.** Not a set of sibling skills; not one monolith. | Claude Code routes subcommands in prose only (`$0` is the word; there is no frontmatter dispatch) and documents no skill-to-skill call, so a router of sibling skills would have to duplicate the contract into every sibling. A single large file would load every mode's instructions on every run although the modes are mutually exclusive, and would exceed the ≤500-line SKILL.md guidance. |
| S2 | **Config over fork.** The plugin is generic. A project supplies `.claude/promise.config.json` (§6). No project-specific path, command or vocabulary is hard-coded anywhere in this skill. | One implementation serves every repository; a project supplies only what differs. A per-project fork of the skill is a second copy of the contract, and two copies of a contract drift apart. |
| S3 | **The framework wins.** `outcome-framework.md` beside SKILL.md is the contract for the doc: section rules, lifecycle, review rubric; the skeleton is `templates/outcome-doc.md`, which the framework points at. A project copy at `config.frameworkPath` wins over the bundled one. Mode files cite framework sections by number; they never restate them. | One home for the doc contract, and the mode files stay short. |
| S4 | **After `agreed`, where a map exists, the map is the source of scenarios.** §6 of the doc cites the map's rows (a `Row` column); it does not carry a second, independently edited copy. §0's rule tags keep the doc-local `AT-n` aliases, which are stable and append-only. | One promise, one home. A copy made at `agreed` would drift the day after. |
| S5 | **Scripts are Python 3, standard library only, invoked via `${CLAUDE_SKILL_DIR}`.** One implementation runs on every OS. The router invokes `python3`; if that is not on PATH it retries with `python`, then `py -3`, and uses the first spelling that runs for every script that session. The load-time preamble ends in `\|\| true` so a missing interpreter cannot abort the skill before this fallback is read. No `.sh`/`.ps1` parity pairs. | A parity pair is two implementations of one behaviour. Markdown parsing in shell is unreliable. |
| S6 | **Mechanical steps are scripts; judgement is prose; decisions are made in front of the user.** Sub-agents may rank, read and draft. They never decide a routing, a verdict move, a merge, or a status change. | Delegating enumeration is free; delegating a decision loses the reason it was made. |
| S7 | **Every shape rule of the framework has a check in `lint_outcome.py`** (§9), and the check runs at the end of every writing mode. The lint checks shape, not truth: whether §3 holds an example, whether §9 questions carry an owner and a BLOCKING flag, whether §4 invariants name an enforcement point, whether `Last decision:` is a real date, and whether a filled line is *true* are not checked — each writing mode says so in one line, so the author reads those sections themselves. | A rule that is only written down is advisory; a rule with a check is enforced. The lint makes the framework's shape rules hold in every doc, not only in the ones a careful author wrote. |

## 3. File tree (exact)

```
promise/                                  ← the plugin
  .claude-plugin/plugin.json
  LICENSE            README.md            CHANGELOG.md
  examples/                               ← runnable, outside the skill; linted and exercised by tests/test_examples.py
    channel-muting.md                     ← one conforming outcome doc: Altitude column, §10 owners, lint exit 0
    transcript.md                         ← a short annotated session: Phase 0 line, mode inference, one interview turn, one lint finding, the pasted §0
    minimap/                              ← a tiny capability map: map.json, capability_find.py (find / --row / --next-id), promise.config.json, recipe.md, README.md, docs/designs/ with the bridged doc
  skills/promise/
    SKILL.md                              ← router. ≤ 150 lines. Frontmatter + contract summary + mode table + dispatch + Phase 0.
    outcome-framework.md                  ← THE contract for the doc (contract, section rules, lifecycle, rubric, decisions F1–F9); the skeleton itself is templates/outcome-doc.md
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
      promise.config.example.json         ← every field, with comments in a sibling `$comment`; §6 shows it verbatim
      claude-md-section.md                ← the ≤20-line block `adopt` inserts into a project's CLAUDE.md (§13)
      starter-map/                        ← map.json (no rows), capability_find.py (its reader; examples/minimap runs the same bytes), recipe.md — what start_map.py installs (§13)
    agents/
      openai.yaml                         ← Codex skill metadata (same skill, second host)
    scripts/                              ← Python 3, stdlib only (S5)
      orient.py                           ← Phase 0: resolve framework, config, docs home, commands, existing docs → JSON (§5)
      lint_outcome.py                     ← shape checks over one doc or a directory → findings, exit code (§9)
      outcome_rows.py                     ← extract §0 rules+tags and §6 rows (with altitude) as JSON; the bridge's input (§10)
      adopt.py                            ← write the config and the CLAUDE.md section, idempotently (§13)
      framework_section.py                ← print named `## ` sections of the resolved framework; modes read sections, not the file
      adapter.py                          ← run one configured command; the caller's text is one argv element, never a shell string (§14)
      render_outcome.py                   ← instantiate templates/outcome-doc.md (--thin: the human half only); refuses to overwrite; makes the docs folder only with --create-docs-home
      bridge_validate.py                  ← a bridged doc's Row ids, snapshot line and Then text against the current map (§10)
      start_map.py                        ← install templates/starter-map/ and fill the config's map object; never over an existing map (§13)
  tests/                                  ← `python3 -m unittest discover -s promise/tests` (§12)
    test_scripts.py  test_shape.py  test_lint_hardening.py  test_acceptance_columns.py
    test_status_authority.py  test_followups.py  test_intake_phrases.py
    test_adapter_render.py  test_orient_render.py  test_bridge_validate.py  test_examples.py
    test_adopt_hardening.py  test_packaging.py  test_start_map.py  test_thin_draft.py
    fixtures/
      conforming.md + one-change violation docs      ← one fixture per lint rule
      lint-hardening/  acceptance-columns/  hardening/  ← per-rule violation families
      minirepo/  adapter/  bridge/  followups/         ← mini repos and script-level fixtures
```

Budgets, enforced by `tests/test_shape.py`: `SKILL.md` ≤ 150 lines; each `modes/*.md` ≤ 220
lines; each `references/*.md` ≤ 220 lines except this file and the framework. A mode file
that needs more is restating the framework — cite it instead.

## 4. Mode dispatch — the input decides, not the syntax

The user types `/promise` and says what they want in plain words. **A leading mode word is a
shortcut, never a requirement.** People will not remember eight mode names and must not have
to. The router reads the input and Phase 0's findings, names the mode it inferred in one
line ("Reading this as **reconcile** — you named a PR"), and proceeds. It never answers "use
`/promise <mode>`", never refuses for syntax, and asks only when two modes are genuinely
plausible — then as one question with a `(Recommended)` option first and one concrete
reason.

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
exits 0; problems go in `warnings[]`. A usage error — an unknown flag, a `--cwd` that is
not a directory, an `--input-file` that cannot be read — exits 2 like any CLI. When no
Python 3 interpreter runs under any of the spellings S5 names, the router names the host's
one-line install and continues by applying the scripts' rules by hand for that run; a second
implementation in another language is refused (S5), because two implementations of one
rule set drift and then the same doc passes in one project and fails in another. Schema (every key always present; `null` when unknown):

```json
{
  "skillDir": "/abs/path/to/skills/promise",
  "cwd": "/abs/path/of/project",
  "mode": "new — the --mode word, or null when the flag was not given",
  "frameworkPath": "/abs/path — the project copy if config.frameworkPath exists, else the bundled copy",
  "frameworkSource": "project | bundled",
  "config": { "path": "/abs/.claude/promise.config.json or null", "loaded": true, "raw": { } },
  "docsHome": "docs/designs",
  "docsHomeSource": "config | detected | none",
  "plansFolder": "plans or null",
  "commands": { "typeCheck": "pnpm type-check or null", "test": "pnpm test or null", "lint": "pnpm lint or null", "source": "config | detected | none" },
  "map": { "…the config.map object verbatim, or null…" },
  "mapUsable": false,
  "claudeMd": { "path": "/abs/CLAUDE.md or null", "hasPromiseSection": false },
  "adopted": false,
  "existingDocs": [ { "path": "docs/designs/foo.md", "title": "Foo", "status": "draft", "lastDecision": "YYYY-MM-DD" } ],
  "suggestedMode": "revise or null — from --input, see below",
  "signals": [ "matches existing doc 'Foo' + a change verb" ],
  "ambiguous": false,
  "warnings": [ "no config found at .claude/promise.config.json; using detection" ]
}
```

Detection rules when config is absent:

- **docsHome**: first existing of `docs/designs`, `docs/design`, `docs/specs`, `docs/rfcs`,
  `design`, `docs`. None → `null`, and the mode asks the user before writing. The skill
  never creates a docs folder unprompted; `new`/`adopt` may, on the user's explicit say-so,
  and `render_outcome.py` does it only when passed `--create-docs-home`.
- **plansFolder**: `plans` if it exists, else `null`.
- **commands**: from `package.json` `scripts` (`type-check` | `typecheck` | `tsc` → typeCheck;
  `test`; `lint`) prefixed by the package manager the lockfile implies (`pnpm-lock.yaml` →
  `pnpm`, `yarn.lock` → `yarn`, `bun.lockb` or `bun.lock` → `bun`, else `npm run`); else `Makefile` targets
  of the same names (`make <target>`); else `justfile` recipes (`just <recipe>`); else `null`.
- **existingDocs**: every `*.md` under docsHome, one level deep — the folder and its
  immediate subdirectories, the same scan `lint_outcome.py` and `outcome_rows.py
  --search` use (§9/§10) — whose text contains a line
  starting `## 0. TLDR` outside any fenced code block, so a framework copy or a doc
  quoting the template is not listed. `status` is the first token after `Status:`;
  `title` is the H1, both read from unfenced lines. A file that is not UTF-8 is skipped
  with a warning.
- **claudeMd**: `CLAUDE.md` at the project root, else `.claude/CLAUDE.md`, else `null`.
  `hasPromiseSection` is true when the file contains the marker `<!-- promise:begin`.
- **adopted**: true when a config was loaded AND `claudeMd.hasPromiseSection` is true. When
  false, `warnings[]` carries `project not adopted — run /promise adopt`, and the router
  offers `adopt` once per session (Recommended) before continuing with the requested mode.
- **suggestedMode / signals**: `--input-file <path>` (or `-` for stdin; `--input "<text>"`
  exists for tests and programmatic callers) makes the
  script read the input against the §4 table deterministically — a leading mode word, an
  `existingDocs` title or path plus a critique or change verb, two doc matches, a PR or
  commit or test-file pattern (a commit is a 7–40 hex run with at least one letter, or a
  digit-only run beside a word such as merged, landed, PR, commit or branch — a bare date
  or id on its own is not one),
  a `map.rowIdPattern` match, complaints (a sentence or a list), an adopt phrase — and
  name the rule that fired. Without the flag both are `null` / `[]`.
  `ambiguous` is true only when two rules for different modes both matched; then the router
  asks. It is a hint the router confirms in its one-line statement, never a decision.
- **mapUsable**: the single source of "is a map configured". True only when `map` carries
  `recipe`, `find` and `row` as strings and `lanes` as an object of strings. An incomplete
  map stays in `map` with a warning naming the missing keys (`map incomplete: missing …`);
  the modes treat it as not configured, `adapter.py` refuses map operations (exit 2, the
  message naming the missing keys) and `bridge_validate.py` reports `MAP_NOT_CONFIGURED`
  with the same keys named — neither runs with a partial map. A
  `recipe` or `index` file that does not exist, a `checks` value that is not an array of
  strings, an `issueTracker` that is not three strings, and a `rowIdPattern` that does not
  compile each warn without changing it.
- **Config warnings** (`warnings[]`, every one a string a person can act on): an unknown key
  at any level; a wrong-typed field; a path that escapes the project or uses backslashes; a
  `docsHome`, `frameworkPath`, `map.recipe` or `map.index` that does not exist
  (`frameworkPath` then falls back to the bundled copy; the others are returned as
  configured); a loaded config that pins no `docsHome` in a project where detection
  finds no docs folder either (`docsHome is null: …` — every later `new` would ask); a
  `$schema` key (deprecated — use `"version": 1`); a `version` other than
  `1`. A path that escapes the project includes a Windows drive-letter path on every
  OS. Whether a configured command exists is not checked — `adapter.py` reports exit 127
  when it runs one that is not there.

The mode file states, in one line, what Phase 0 resolved: mode (and that it was inferred,
if it was), framework source, docs home and its source, whether a map is configured
(`mapUsable`), and whether the project is adopted.

## 6. Config contract — `.claude/promise.config.json`

Location: `<project>/.claude/promise.config.json`; fallback `<project>/promise.config.json`.
All fields optional. Unknown fields are a warning, not an error. `"version": 1` names the
shape of the file; a `$schema` key from an earlier config is accepted with a deprecation
warning. `references/config.md` is the user-facing contract, field by field. The example
below is `templates/promise.config.example.json`, verbatim — one example in two places,
kept byte-identical:

```json
{
  "version": 1,
  "$comment": "Config for the promise plugin, at .claude/promise.config.json. Every field is optional — a project with none of this still gets full detection (see references/config.md). docsHome / frameworkPath / plansFolder / commands pin what orient.py would otherwise detect; map turns on the bridge to a project's own machine-checked register of promises, and most projects start with no map at all. This file shows every field at once so each one has an example: copy it, then delete whatever this project does not need.",
  "docsHome": "docs/designs",
  "frameworkPath": "docs/how-to/outcome-framework.md",
  "plansFolder": "plans",
  "commands": {
    "$comment": "The verify commands the writing modes run at hand-back through adapter.py verify. Each is an argv line, split and run with no shell. Once this object exists, detection is off for all three; a null or missing key means 'this project has none'. Delete the whole object to go back to detection.",
    "typeCheck": "pnpm type-check",
    "test": "pnpm test",
    "lint": "pnpm lint"
  },
  "map": {
    "$comment": "Present only when this project keeps its own capability map — a machine-checked register of promises and the tests that prove them. Start one with scripts/start_map.py, which installs the skill's starter map (templates/starter-map/) and writes this object; examples/minimap/ in the plugin repository runs the same reader over example rows. recipe is the authority for mechanics: read it, do not expect this skill to restate it. find/row/nextId and checks are argv lines, split and run with no shell (an argument is appended as one argv element) — no pipes, &&, env prefixes or cd; put such logic in a script and name it here. rowIdPattern validates any row id this skill writes or parses. lanes maps the four altitudes (plus sibling) to this project's own evidence-array names, so references/altitude.md can stay generic. checks run, in order, at the end of arm/intake/reconcile; the key is optional, but a project with no checks writes [] — with the key absent, adapter.py checks refuses (exit 2, 'map.checks is not configured'). issueTracker enables a duplicate-issue search before anything gets filed. A map counts as configured only with recipe, find, row and lanes (orient.py's mapUsable). Omit this whole object for a project with no map yet — see references/config.md 'Without a map'.",
    "recipe": "docs/how-to/adding-a-capability.md",
    "index": "docs/how-to/capability-map-index.md",
    "find": "scripts/capability-find",
    "row": "scripts/capability-find --row",
    "nextId": "scripts/capability-find --next-id",
    "rowIdPattern": "^CAP-\\d+$",
    "lanes": {
      "data": "tests[]",
      "response": "tests[]",
      "perception": "e2eTests[]",
      "judgement": "evalTests[]",
      "sibling": "siblingTests[]"
    },
    "checks": [
      "scripts/capability-check",
      "scripts/citation-strength-check"
    ],
    "issueTracker": {
      "kind": "github",
      "repo": "owner/repo",
      "template": ".github/ISSUE_TEMPLATE/capability.md"
    }
  }
}
```

Semantics the mode files rely on:

- **`map` absent, `null`, or unusable** (§5, `mapUsable`) → there is no capability map.
  `arm` writes red tests only. `intake` matches feedback against the §6 rows of the docs
  in `docsHome` and files the routing table into the doc (§6 / §9). `reconcile` updates
  the doc only (tags, `Scenarios:` count, a dated §8 entry). Each of those modes says "no
  map configured" in its Phase 0 line.
- **`map.recipe`** is the project's own how-to for writing a row. **It is the authority
  for the mechanics** — which files a row touches, what lockstep means there, what a
  citation looks like. The mode files never restate a project's mechanics; they say "read
  the recipe, work from the file". The generic *procedure* (split, match, route, draft,
  prove, apply, verify) lives in the mode file; the *mechanics* live in the recipe.
- **`map.find` / `map.row` / `map.nextId`** are argv lines `adapter.py` splits and runs
  with `shell=False`, the argument appended as one argv element (`adapter.py find <query>`
  or `adapter.py find --query-file <path>`, `adapter.py row <id>`); no pipes, `&&`, env
  prefixes or `cd`.
- **`map.lanes`** maps the four altitudes (plus `sibling`) to the project's evidence-array
  names, so `altitude.md` can be generic and the mode file can say "cite in the lane the
  altitude picks".
- **`map.checks`** run at the end of `arm`, `intake` and `reconcile`, in order, before the
  mode hands back. The key is optional, but a map with no checks writes `[]`: with the key
  absent, `adapter.py checks` refuses (exit 2, `map.checks is not configured`), and the
  modes run it only when a map is configured and `checks` is set — a refusal is
  reported as not run, never as a failed check.
- **Every configured command runs as the caller** — `references/config.md` § Trust model.
  The router prints `adapter.py show` and asks before the first configured command runs
  in a session; on no, the run continues as if no map and no `commands` were configured.

## 7. Vocabulary (use these words; define nothing else)

| Word | Meaning |
|---|---|
| **promise** | Something a person will be able to do, stated so it can be checked. An outcome doc makes one; a row keeps or breaks one. |
| **outcome doc** | The one document per capability in the Outcome Framework shape. |
| **capability map / map** | A project's machine-checked register of promises and their proof — the map of the platform. The goal state (F9): `arm` offers a starter when the first doc is agreed; configured in §6. |
| **row** | One entry in the map: a user story plus 1–5 Gherkin scenarios, evidence arrays, a verdict. Ids follow `map.rowIdPattern`. |
| **AT-n** | A doc-local acceptance-row id in §6. Stable, append-only. After the bridge it is an alias for a row's scenario, never a second copy. |
| **altitude** | What a `Then` asserts on: **data** (a stored fact), **response** (what a request returns), **perception** (what a person sees, is told, lands on), **judgement** (whether a model chose well) — plus **sibling**, a `Then` that only a sibling system's own tests can prove. §6's `Altitude` column carries one of the five. |
| **lane** | The kind of test that reaches an altitude, and the evidence array it is cited in. |
| **verdict** | The row's honest proof state — `proven` / `under-proven` / `not-built` in the minimap; a project may keep its own enum. It moves only when evidence reaches the `Then`'s altitude. |
| **kill mutation** | A production change, chosen before the test is trusted, that the cited test must fail on: applied, watched failing, reverted, watched passing (`references/altitude.md` § Kill mutation). |
| **kill witness** | The record of a kill mutation a cited test was watched to catch. No watched kill, no promotion. |
| **proof strength** | How much of a rule's cases the evidence checks: **example** (chosen cases), **property** (the real code on generated cases), **model** (every reachable state of a model, by machine-checked proof). Recorded on §4 invariants; a `model` proof needs a conformance test to reach the code (`references/altitude.md` § Proof strength). |
| **signal** | §0's *how we'll know*: one of four kinds — a red→green test, a watched demo, a number in prod, a claim we can make to a customer. |
| **slate** | A short list of candidate lines put to the human for the outcome line or the signal — never for a rule (`references/slates.md`). The human's edit enters, not the candidate. |
| **recipe** | `map.recipe`: the project's own how-to for writing a row. The authority for mechanics; a mode reads it and works from the file, never restates it. |
| **lockstep** | The recipe's rule for which files move together when a row changes, and in what order. Never traded for speed. |
| **ratchet** | A checker's floor or ceiling that only tightens — a coverage count, a citation-strength threshold. Loosening one to make a check pass is never a fix. |
| **red gate** | The commit that contains only the failing tests for a doc's §6 rows. Its sha and date sit in the header as `Red gate: <sha> <YYYY-MM-DD>`; that line is what `building` records. |
| **snapshot line** | The one line under a bridged doc's §6 table — `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of these scenarios from here on. `` — after which §6 is not edited. `bridge_validate.py` requires it. |
| **thin draft** | A `draft` doc with `Depth: thin` in its header: the human half only, §3–§7 not written yet, each gap a BLOCKING §9 question. It cannot be agreed (`THIN_DRAFT`); `revise` fills it. |
| **confirmation sheet** | The one-screen summary of the human half — outcome line, rules, signal, example — put to the user for approval before anything is written (`references/slates.md` § The confirmation sheet). |

## 8. The bridge — doc status × map

| Doc status | Without a map | With a map |
|---|---|---|
| `draft` | Doc is the only home. §6 rows are the promise. | Same. Nothing is filed in the map yet. |
| `agreed` (human act) | No extra step; the doc stays the only home. | `arm` files each §6 row as a **not-built row** per the recipe, grouped by the §0 rule each row is tagged from — the grouping rule is the framework's (§ Lifecycle, decision F7), not restated here. §6 gains a `Row` column and the snapshot line (§7), and is not edited again: it is the record of what was agreed, the map is the live source. §0 tags keep AT aliases (stable and append-only, never replaced by the map's ids). `bridge_validate.py` (§10) is the staleness check between the two. |
| `building` | Red tests written and committed first; failing output pasted in §6; sha in header. | Same, plus each red test is cited in the lane its altitude picks. |
| `shipped` | Human flips it when §6 rows are green. | Human flips it when **every** bridged row is `proven` at its `Then`'s altitude. `reconcile` is how rows get there. Doc keeps §0, §2, §4 as the living record. |

`agreed` and `shipped` are typed by a human. `building` is written by `arm`, only after
the human has seen the red-gate commit and confirmed it — the commit is the human act
the status records. `revise` states when a §0 change would drop a doc back to `draft`.
`merge` deletes a folded doc (`git rm`, one explicit-path commit with the survivor)
unless the user keeps the file, in which case it is marked `superseded-by <survivor>`
and nothing else in it changes again; a folded doc's map rows are re-pointed or retired
per the recipe, with the user.

## 9. `lint_outcome.py` — what it checks

```
python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc.md | directory> [--json] [--strict] [--template]
```

Exit 0 when no error-severity findings; exit 1 when any error (or, under `--strict`, any
warning); exit 2 on a usage error. Human output is one line per finding:
`<path>:<line>: <RULE_ID> <message>`. `--json` prints
`{"path": …, "findings": [{"rule": …, "line": …, "message": …, "severity": "error|warn"}], "stats": {…}}`
for one file, and a JSON array of those objects for a directory, so stdout is always one
parseable value. A directory lints every `*.md`, one level deep, whose `## 0. TLDR`
line sits outside a fence. Lines inside a fenced code block (``` or ~~~) are
illustrations: no heading, field marker, table row or placeholder inside one counts,
though the lines still count toward a line budget; an unclosed fence is its own finding
(`FENCE_UNCLOSED`), reported at the opening line.

| Rule id | Checks | Severity |
|---|---|---|
| `HEADER_STATUS` | A `Status:` line exists and its first token is one of `draft` `agreed` `building` `shipped` `superseded-by`; `superseded-by` names a target. Other text after the token is allowed. | error |
| `THIN_DRAFT` | A `Depth:` header line reads exactly `Depth: thin`, and only on a `draft` doc. A thin draft holds the human half only: on one, `ACCEPTANCE_TABLE` does not require a table (a table that is there is checked in full), `WHY_LINE` does not run, `SCENARIOS_COUNT` counts a §3 with no parseable example as zero, and `RULES_PRESENT` is a warning. Past `draft` the line is this error and every rule applies in full, so a thin doc cannot be agreed. | error |
| `HEADER_OWNER` | `Owner:` and `Last decision:` present, with non-empty values. | error |
| `CONTENTS_LINE` | A `Contents:` line exists and links to all eleven anchors `#0-tldr` … `#10-out-of-scope`. | error |
| `HEADINGS_BARE` | Exactly one `## <n>. <Name>` per n in 0..10, matching the template's names, with nothing after the name on that line. | error |
| `TLDR_BUDGET` | Lines from `## 0. TLDR` up to (not including) the `Agent notes` line — or `## 1.` if there are none — number ≤ 40. Report the count. | error |
| `TLDR_FIELDS` | The block contains `**Outcome:**`, `**Rules:**`, `**How we'll know:**`, `**Scenarios:**`, and the Outcome and How-we'll-know values are non-empty. `**How we'll know:**` with a curly apostrophe (U+2019) is the same marker. The rules block ends at the next bold `**Field:**` line, the next `## ` heading or the end of §0 — never end-of-file — so a missing marker is one finding, not a cascade. | error |
| `RULES_FORMAT` | Every rule is a `- ` bullet with text before its tag. Numbered rules, and any other non-blank text in the rules block, are findings. | error |
| `RULES_PRESENT` | `**Rules:**` is present but has no `- ` rule bullet under it, at every status. A block holding only stray text is `RULES_FORMAT`'s and does not also fire this. On a thin draft (`THIN_DRAFT`) it is a warning. | error / warn |
| `RULES_TAGGED` | Every rule ends with `→ AT-n[, AT-m…]` or `→ UNTESTED`. | error |
| `TAGS_RESOLVE` | Every `AT-n` cited in a §0 tag exists as a row id in §6. | error |
| `AT_IDS_UNIQUE` | §6 row ids are unique and match `AT-\d+`. | error |
| `ACCEPTANCE_TABLE` | §6 holds at least one acceptance table — a header row whose first cell is `#`, `ID` or `AT` and which names `Given`, `When` and `Then` exactly once each (any order, case-insensitive, extra columns allowed, optional `Row` and `Altitude` columns recognised by name, each at most once) — with at least one data row; every data row has the right cell count and non-empty Given, When and Then. Columns are matched by header name, never position, so an extra column or a reordered `Row` never shifts what a cell means, and a header naming a column twice does not qualify — never a guessed mapping. Every `#`/`ID`/`AT`-headed table in §6 is checked on its own terms: a malformed table is reported even when a sibling table in the same section qualifies fine. Other, non-`#`/`ID`/`AT` tables in §6 are ignored. A row directly under a table that contains a pipe but lacks its leading or trailing pipe is read GFM-style (outer pipes stripped), so no row below it is dropped, and is reported at its own line. A Why line or the Snapshot line directly under the table is not read as a row, pipe or not. | error |
| `ACCEPTANCE_ALTITUDE` | When a §6 acceptance table has an `Altitude` column, every data cell in it is exactly one of `data`, `response`, `perception`, `judgement`, `sibling`. An empty cell or any other value is a finding; an angle-bracket cell (`<altitude>`) is `PLACEHOLDER`'s, not this rule's. | error |
| `SCENARIOS_COUNT` | The `**Scenarios:**` line — `<N> acceptance rows (§6), <M> worked example(s) (§3)`, singular or plural — carries an acceptance-row count equal to the number of §6 rows. The worked-example count is checked only if §3 examples are parseable (`### ` or bold-led blocks); otherwise `warn` that it was not checked. | error / warn |
| `WHY_LINE` | §4, §5, §6, §7 each contain a line beginning `Why — what breaks without it:` with a value after the colon. A `<placeholder>` value is `PLACEHOLDER`'s. | error |
| `UNTESTED_ON_AGREED` | A rule tagged `UNTESTED` while `Status:` is `agreed`, `building` or `shipped`. | error |
| `BUILDING_NEEDS_GATE` | `Status:` is `building` and no header line (any line before the first `## ` heading, skipping anything inside a ` ``` `/`~~~` fence) matches `Red gate: <sha> <YYYY-MM-DD>` exactly — sha 7–40 hex characters (digits alone qualify), date a real calendar date (checked with Python's own date parser, not just the `\d{4}-\d{2}-\d{2}` shape); position among the header lines is not enforced, the line's own shape is. A hex-looking run inside another header value (`Supersedes: deadbeef`, a digit-only `Last decision:`), a `Red gate:` line inside a fenced code block, or one naming a date that does not exist (`2026-02-31`) does not satisfy it — the last of these is its own message, not silently treated as no line at all. | error |
| `PLACEHOLDER` | `TBD`, `TODO`, `<fill`, `decide later` inside §0; any `<…>` placeholder in §0, in the `Owner:` / `Last decision:` values, in a §6 data cell, in an agent note, on the first line of a §3 worked example, in a §9 question's owner, or in the value of a §4–§7 Why line (§5 body text is not scanned, so a generic like `Map<string, Row>` stays legal); a literal `YYYY-MM-DD`. `--template` exempts the angle-bracket and date placeholders so the bundled template can be linted; every other rule stays active. A copied, unfilled template therefore fails a normal lint. | error |
| `UNREADABLE` | The path cannot be read or is not valid UTF-8 — one finding for the file, never a traceback. | error |
| `FENCE_UNCLOSED` | A ``` or ~~~ fence is opened and never closed, so every line after it is read as an illustration by every other rule. Reported at the opening fence's own line, so the cascade of missing-heading findings it causes has a named cause. | error |
| `AGENT_NOTES_MANY` | More than 8 numbered agent notes under §0. | warn |
| `HUMAN_HALF_BUDGET` | §0 through the end of §2 plus the first §3 example ≤ 150 lines (measured to the end of §2 when §3 is not parseable; say so). | warn |
| `ALTITUDE_MISSING` | A §6 acceptance table has no `Altitude` header. A doc written before the column existed keeps linting; the column is how a `Then` says what it asserts on, and `reconcile` needs it to judge evidence. | warn |

`--strict` promotes `warn` to `error`. `HEADINGS_BARE` fires on a malformed heading even when a
well-formed heading for the same number also exists. The lint is deterministic and needs no
network.

## 10. `outcome_rows.py` — the bridge's input

```
python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc.md> [--json]
```

Prints `{"path", "status", "rules": [{"index", "text", "tags": ["AT-1", …] | ["UNTESTED"]}],
"rows": [{"id": "AT-1", "given", "when", "then", "altitude": "data" | null, "row": "CAP-207" | null}],
"signal": "…"}`. `altitude` is the §6 `Altitude` column (§9: one of five values; `null`
when the table has no such column); `row` is the optional `Row` column (§8). A rule with no
tag at all yields `tags: []`, which the lint reports as `RULES_TAGGED`; the script extracts,
it does not judge. Human output is a compact table. This is what `arm` reads to file rows
and what `reconcile` reads to re-stamp tags. Two more flags: `--write-counts` rewrites only
the `**Scenarios:**` line from the real §6 row count (and the §3 example count when
countable), idempotently, pluralising `worked example(s)` as the count requires — the count
is agent-maintained metadata, so a script may own it; `--search "<text>" --dir <docsHome>`
(or `--search-file <path>`, `-` for stdin, so the text never sits on a command line) ranks
every §6 row and §0 rule across the docs by token overlap — intake's matcher when no map is
configured. `--dir` is walked one level deep, as the lint scans (§9); a missing or
non-directory `--dir` exits 2.

### `bridge_validate.py` — the bridge's check

```
python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc.md> [--cwd <path>] [--json] [--strict]
```

Checks a bridged doc's §6 against the project's map. Config is resolved exactly as
`orient.py`/`adapter.py` do, under `--cwd`, and "configured" means orient's `mapUsable`
(§5): a map that is present but incomplete is `MAP_NOT_CONFIGURED`, with the missing keys
named in the message. Every `map.row` lookup runs through
`adapter.py --json row <id>` rather than a shell string composed from configuration
plus doc content, so a row id — however it is spelled — always travels as one argv
element.

Checked in this order — STATUS_UNKNOWN, then NOT_BRIDGED, then
MAP_NOT_CONFIGURED — because a doc with no readable status cannot be judged at
all, and a doc still at `draft`/`superseded-by` has not been bridged regardless
of whether a map exists to bridge it to:

| Rule id | Checks | Severity |
|---|---|---|
| `UNREADABLE` | DOC is missing or not valid UTF-8. | error |
| `STATUS_UNKNOWN` | `Status:` is missing or not one of the five tokens. Reports `bridged: false`; no other rule runs. | error |
| `NOT_BRIDGED` | `Status:` is `draft` or `superseded-by` — the bridge has not happened. Reports `bridged: false`; no other rule runs. | info |
| `MAP_NOT_CONFIGURED` | No `map` in the config (or `null`), no config at all, or a map orient reports as `mapUsable: false` — nothing usable to validate against; for an incomplete map the message names the missing keys. | error |
| `ROW_MISSING` | An AT row's `Row` cell is empty while `Status:` is `agreed`, `building` or `shipped`. | error |
| `ROW_ID_FORMAT` | A `Row` value does not match `map.rowIdPattern`. | error |
| `NO_ROW_ID_PATTERN` | `map.rowIdPattern` is not configured; `ROW_ID_FORMAT` is skipped. | warn |
| `INVALID_ROW_ID_PATTERN` | `map.rowIdPattern` is configured but does not compile as a regex — the exception text is carried in the message; `ROW_ID_FORMAT` is skipped, same as absence, but this is a misconfiguration, never silently treated as "no pattern". | error |
| `ROW_NOT_FOUND` | `map.row` is configured and `adapter.py row <id>` reports a non-zero exit or empty stdout. | error |
| `NO_MAP_ROW_COMMAND` | `map.row` is an empty string — still a string, so the map counts as usable, but no command is configured; the drift check against the map is skipped (an absent or non-string `map.row` is `MAP_NOT_CONFIGURED` instead). | warn |
| `SNAPSHOT_LINE_MISSING` | §6 has no line starting `Snapshot taken at` (a leading backtick or asterisk tolerated). | error |
| `THEN_NOT_IN_MAP` | A row's normalised `Then` is not a substring of its `Row` id's normalised current text in the map — a canary, not proof of agreement. The message names the three causes: the map moved on since the snapshot, the row was filed differently, or §6 was edited after the snapshot was taken. | warn |

`--strict` promotes every warn to error. Exit 0 with no error-severity finding; 1 with
any error (or, under `--strict`, any warning); 2 on a usage error. Human output is one
line per finding, then a summary line `bridge: <n> rows, <m> mapped, <k> drifted`.
`--json` prints one object: `{"path", "status", "bridged", "mapConfigured", "rows":
[{"id", "row", "line", "found", "inSync"}], "findings": [{"rule", "line", "message",
"severity"}], "stats": {"rows", "mapped", "drifted", "errors", "warnings"}}`. `arm` runs
it once the `Row` column and snapshot line are written, and fixes every error before
continuing; `reconcile` runs it before reading the map, because a `THEN_NOT_IN_MAP`
finding means §6 no longer says what the map says.

## 11. Rules for every file in this skill

- **Cite the framework by section; never restate it.** "§6 rows — framework § *Section
  rules*" is a citation. A paragraph explaining what §6 is, is a copy. A mode's header names
  the framework sections it needs (`outcome-framework.md § The contract · § Lifecycle`) and
  reads only those, through `scripts/framework_section.py`; only `new` needs most of it. A
  cited name is one `framework_section.py --list` prints — a `## ` heading of the framework
  itself, never a heading inside a fenced example.
- **Each mode file opens with a 3-line header**: `Read before this:` (the reference files
  this mode needs), `Phase 0 line:` (what to state), `Writes:` (which files it may touch).
  A mode that reads a project file only at a later step (`arm`, `intake`, `reconcile`) adds
  one `Read at <step>:` line between the first and the second.
- **Sanitised.** No real people, companies, repo paths, dates or ticket ids from any
  project. Actors in examples are `Ana`, `Ben`, `Priya`. Project-shaped facts are shown as
  config, never as prose.
- **Every recommendation put to the user is one option marked `(Recommended)` first, with
  one concrete reason.** Every decision is the user's; the skill never resolves a
  `BLOCKING` question by drafting.
- **The user's edit enters, not the candidate.** Wherever a slate or draft is approved
  with changes, the changed text is what is written.
- **Verify before believing.** A current-state claim carries `file:line` the writer read
  this run. A test found uncited is evidence only after it was watched dying.
- **Say what was not checked.** Every mode's close-out names what it could not verify.
- **Never require syntax.** A mode word is a shortcut; the input decides (§4). `/promise fix
  the doc` gets `revise`, not a usage message.

## 12. Tests for the scripts

`python3 -m unittest discover -s promise/tests` must pass on a clean checkout with no
third-party packages. The suites, one file each:

- `test_scripts.py` — the lint over one fully conforming doc (exit 0) and over one fixture
  per `error` rule in §9 (each is caught, and only it); `--strict` promotion; `orient.py`
  against the fixture mini repo (`package.json` + `pnpm-lock.yaml` + `docs/designs/` with
  one outcome doc, plus a complete map config) and against an empty directory (all-null,
  warnings present, exit 0); the config allowlist and type rules of §5; `outcome_rows.py`
  round-trips the conforming fixture; `adopt.py` on a temp project (dry-run writes nothing;
  first run creates the config and the CLAUDE.md section; second run is a byte-identical
  no-op; a hand-edited block is restored in place; a missing CLAUDE.md is created; a
  pre-existing config is never overwritten; malformed markers are refused; line endings and
  a BOM survive) and `orient.py` then reports `adopted: true`.
- `test_lint_hardening.py` — the second-shape variants of the header, `RULES_FORMAT`,
  `ACCEPTANCE_TABLE`, `PLACEHOLDER` and `HEADINGS_BARE` rules, `FENCE_UNCLOSED`,
  `--template` (and that a freshly rendered doc fails with `PLACEHOLDER` findings only),
  and `UNREADABLE` (`lint-hardening/not_utf8.md`).
- `test_acceptance_columns.py` — §6 columns matched by header name, never position;
  duplicate headers; a malformed table beside a valid one.
- `test_status_authority.py` — the status-authority wording in SKILL.md and arm.md,
  `BUILDING_NEEDS_GATE`, and a frozen allowlist of every sentence under `skills/promise/`
  that pairs `agreed`/`shipped` with a transition verb: a new one fails until a human reads
  it, and a stale entry fails too.
- `test_followups.py` — `orient.py --input-file` mode inference, rule by rule and against
  every example in the §4 table; `--write-counts`; `--search` / `--search-file`.
- `test_intake_phrases.py` — every intake phrase §4 lists infers `intake`.
- `test_adapter_render.py` — `adapter.py` (argv assembly, every refusal, `show`, `checks`,
  `verify`, `--query-file`, the `mapUsable` gate) and `render_outcome.py` (refuses to
  overwrite, refuses a missing docs home with exit 2, `--dry-run`, `--json`, slugs).
- `test_orient_render.py` — `orient.py`'s refusals (exit 2, one line, never a traceback),
  every config warning §5 lists, the fenced-illustration doc scan, the digit-run hint;
  `framework_section.py`; `render_outcome.py` and `--create-docs-home`.
- `test_bridge_validate.py` — every rule in §10's table in its stated order, against
  `fixtures/bridge/` and a fake `map.row` command, including hostile row ids.
- `test_shape.py` — this file's own rules: line budgets, the mode headers, relative links,
  the sanitiser, the example config, the template lints clean, framework sections resolve.
- `test_examples.py` — `examples/*.md` lint with exit 0 and `bridge_validate.py` runs
  against `examples/minimap/`.
- `test_adopt_hardening.py` — `adopt.py`'s refusals (a wrong-typed path, a hostile
  `--docs-home`, a non-UTF-8 `CLAUDE.md`), symlink and file-mode preservation,
  `"version": 1`, the all-or-nothing `commands` object.
- `test_thin_draft.py` — the thin draft: the filled fixture lints clean, `Depth: thin` past
  `draft` is `THIN_DRAFT` and brings back the full shape, an empty rules block is a warning
  only there, a §6 table and the `Scenarios:` claim are still checked, and
  `render_outcome.py --thin` writes the shape.
- `test_packaging.py` — the pre-install surfaces agree with the plugin: the marketplace
  description equals `plugin.json`'s, every mode count equals the number of mode files,
  `plugin.json`'s version equals the top CHANGELOG entry.

Fixtures: every `error` rule in §9 has a fixture that fires it alone; `AGENT_NOTES_MANY`,
`HUMAN_HALF_BUDGET` and `ALTITUDE_MISSING` each have one that fires as the only finding
with exit 0, and exit 1 under `--strict`. A violation fixture is the conforming doc with exactly one change, plus
the one forced edit where a single change would trip an unrelated rule
(`building_no_gate.md` drops the conforming doc's third, `UNTESTED` rule so
`UNTESTED_ON_AGREED` stays quiet — every fixture whose status is past `draft` does the same; the
acceptance-table missing/no-rows fixtures adjust the `Scenarios:` count;
`at_ids_unique.md` adds a fourth row reusing an id and moves the `Scenarios:` count with
it, because every existing id is cited from §0). A fixture that could not fail is worse
than none.

## 13. `adopt.py` — the config and the CLAUDE.md section

A project is **adopted** when it has a config (§6) and its `CLAUDE.md` carries the promise
section, so every person and agent working in that repository is routed to this skill
instead of writing a design, plan or spec doc by hand.

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" [--cwd <path>] [--dry-run] [--docs-home <dir>] [--no-config] [--no-claude-md]
```

- **Config**: writes `.claude/promise.config.json` if absent — `"version": 1`, `docsHome`
  (from `--docs-home`, else orient's detection, else omitted), `commands` (detected;
  written only when at least one command was detected, then with all three keys, an
  undetected one as `null`, so the pinning is visible in the file — with nothing detected
  the object is omitted so detection stays on),
  and `"map": null` with a sibling `$comment` naming the starter map
  (`start_map.py`) that `arm` will offer, and pointing at `references/config.md`. It never overwrites an existing config, and says so. It does not
  create the docs folder: `--docs-home` records the user's choice, and the folder is made at
  the first `new`, on the user's explicit say-so (`render_outcome.py --create-docs-home`).
- **CLAUDE.md section**: renders `templates/claude-md-section.md` with `{docsHome}`,
  `{configPath}` and `{frameworkPath}`, and places it between `<!-- promise:begin` and
  `<!-- promise:end -->` markers: appended after a blank line when absent, replaced in place
  when present, `CLAUDE.md` created at the project root when no file exists. The rendered
  block is ≤ 20 lines and says: capability work goes through `/promise` in plain words (the
  mode is inferred); one doc per capability in the docs home, in the Outcome Framework
  shape; §0 is the human's verbatim block and agents only append notes below it; `Status:`
  reaches `agreed` and `shipped` only by a human's hand, `building` only after the human
  approves the red-test commit; where a map is configured it is the source of scenarios
  after `agreed`, §6 is then a snapshot nobody edits, and a verdict moves only at the
  altitude the row's own `Then` claims; before writing any design, plan or spec doc by
  hand, run `/promise` — a sibling doc is a bug.
- **Idempotent**: a second run with the same inputs changes no bytes and reports
  `"changed": false`. `--dry-run` prints a unified diff and writes nothing. A symlinked
  `CLAUDE.md` is written through its link and keeps its file mode; whitespace around the
  end marker is tolerated, and restoring a hand-edited block says so on stderr.
- Exit 0 on success or no-op; 2 on a usage error or a refusal — a `--docs-home` that is
  absolute (a drive letter included, on every OS — orient's own escape rule, imported),
  escapes the project, or holds a newline or a marker string; a `--docs-home` that
  disagrees with an already-loaded config's `docsHome` (edit the config instead; a
  `CLAUDE.md` naming one folder beside a config naming another is drift); a `CLAUDE.md` or
  config path that is a directory or sits under a file; a `CLAUDE.md` that is not UTF-8 —
  with the JSON result still on stdout and nothing written. A `--docs-home` written with
  backslashes is recorded with forward slashes, and a fresh config that would pin no
  `docsHome` says so on stderr. Prints one JSON object on stdout:
  `{"configWritten": bool, "configPath": "…", "claudeMdWritten": bool, "claudeMdPath": "…", "docsHome": "docs/designs or null", "changed": bool, "dryRun": bool}`.

### `start_map.py` — the starter capability map

```
python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" [--cwd <path>] [--dest <folder>] [--dry-run]
```

Copies `templates/starter-map/` into `--dest` (default `docs/capabilities`), filling
`{dir}` in the recipe with the destination and `{docRoot}` in `map.json` with the path
back to the project root, so a row's `doc` is its project-relative path. Then sets the
loaded config's `map` object — `recipe`, `find`, `row`, `nextId`, `rowIdPattern`
(`^CAP-\d+$`), `lanes` and `checks`, every command an argv line run from the project
root — and drops the top-level `$comment` only when it is `adopt.py`'s own "map is not
configured yet" note. Refuses, exit 2, writing nothing: no loaded config (adopt
first); a config whose `map` is already an object; a `--dest` that escapes the project,
is `.`, holds a space, or already holds files. `--dry-run` prints the files and the
config diff to stderr. One JSON object on stdout:
`{"dest": "…", "configPath": "…", "files": […], "filesWritten": […], "configWritten": bool, "changed": bool, "dryRun": bool}`.
`arm` and `adopt` offer it; neither runs it without the human's yes to the dry run.

The `adopt` mode confirms the docs home and the config contents with the user
(Recommended-first, one reason), runs the script, then runs `orient.py` and shows `adopted` is
now true. Every other mode offers `adopt` once per session when Phase 0 reports the project
is not adopted, and continues with the requested mode either way.

## 14. Scripts that exist, and scripts that are planned

Shipped (the nine in §3): `orient.py` (§5), `lint_outcome.py` (§9), `outcome_rows.py`
(§10), `adopt.py` and `start_map.py` (§13), `framework_section.py`, `adapter.py` (runs every configured
command with the user's text as one argument — never a composed shell string; `find
--query-file` reads the query from a file; `verify --only <op>` narrows the verify run;
refuses when `mapUsable` is false),
`render_outcome.py` (instantiates the template; refuses to overwrite; `--create-docs-home`
is the only way it makes a folder), `bridge_validate.py` (§10: checks a bridged doc's §6
Row ids, snapshot line and `Then` text against the project's current map). Each script's
flags are in the section cited for it.

Planned, in the order they pay back. Each replaces a step a mode performs today by reading
prose — the model follows the rule and no script checks it, so
`references/anti-rationalizations.md` is the guard until the script ships, and drift is
the cost of not having it:

| Script | Replaces | Used by |
|---|---|---|
| `inspect_outcome.py DOC` | status, BLOCKING count, lint result, §0 text, note count, UNTESTED rules, counts, Row references — one JSON for every close-out | new, revise, review, arm, reconcile |
| `diff_outcome.py BEFORE AFTER` | the three erosion classes and status movement, as a diff the model then judges | revise, review, merge |
| `evidence_probe.py --ref PR\|SHA\|BRANCH\|FILE` | changed files, declared row ids, cited and uncited test titles, ranked candidates | reconcile, intake |
| `kill_witness.py --test … --mutation …` | clean-tree check, apply the approved mutation, capture the named failure, restore exactly, rerun green, print the witness | intake, reconcile |
| `arm_gate.py DOC --branch SLUG` | the Git preflight, the red run, staged-path inspection, the two explicit-path commits (the red gate, then the doc) | arm |
| `issue_search.py --tracker … --row … --text …` | open and closed duplicate candidates before any issue is filed | intake, reconcile |
| `feedback_items.py INPUT` | numbering already-structured items and flagging compound sentences; the split stays a judgement | intake |
| `inventory.py --docs-home DIR --query TEXT` | §0 rules, §5 claims and §6 rows across docs, exact duplicates, ranked overlaps | new, merge |
