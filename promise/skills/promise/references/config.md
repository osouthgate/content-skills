# Config — `.claude/promise.config.json`

*The user-facing contract for the config file. `scripts/orient.py` checks key names
against an allowlist and the types in the tables below; there is no JSON Schema.
`references/architecture.md` §6 shows a complete example, verbatim from
`templates/promise.config.example.json`. This file explains what a project gets by
setting each field, not how the scripts parse it.*

## Location and fallback

- Primary: `<project>/.claude/promise.config.json`
- Fallback: `<project>/promise.config.json`, read only when the primary path is
  absent
- **All fields are optional.** A project with no config at all is fully supported —
  every mode falls back to detection (see "Without a map" below, and the detection
  rules `references/architecture.md` §5 lists for `docsHome`, `plansFolder` and
  `commands`).
- **Unknown top-level fields warn**, they do not error — a typo or a field from a
  future version does not stop a run.
- **`"version": 1` names the shape of this file.** It is the only version this skill
  reads; any other value warns. A `$schema` key from an earlier config is accepted
  with a deprecation warning. `$comment` is ignored wherever it appears, at the top
  level or inside `commands` or `map` — it is never read as a field.
- **Paths are project-relative with forward slashes.** A path written with
  backslashes is normalised and warned about. A path that escapes the project
  (`..` or absolute) warns: `docsHome`, `plansFolder` and `frameworkPath` then fall
  back to detection or the bundled copy; `map.recipe` and `map.index` are returned
  as written, since the map object is never rewritten.

## Trust model

Every `map.find`, `map.row`, `map.nextId`, `map.checks[]` and `commands.*` string runs
as you, with your permissions, in this project's directory — exactly like a
`package.json` script or a Makefile target. Anyone who can commit to the repo can
change them. `adapter.py` protects against a hostile *query* (the text is one argv
element, never a shell string); it does not and cannot protect against a hostile
*config*. `/promise` prints the commands (`adapter.py show`) and asks before the first
run in a session; review them yourself in a repository you did not write.

## Fields

| Field | Type | Default when absent | What changes when it is set |
|---|---|---|---|
| `version` | the number `1` | Read as `1` | Nothing today. A later shape of this file will carry a different number, and `orient.py` will say which one it reads |
| `docsHome` | string, a project-relative path | The first existing of the common docs-folder names detection checks for; `null` if none exist | Pins where outcome docs live — every mode searches and writes there instead of relying on detection. The folder need not exist yet: `orient.py` warns that it is missing, and it is created only on the user's explicit choice (`new` passes `--create-docs-home` to `render_outcome.py`) |
| `frameworkPath` | string, a project-relative path | The framework bundled with this plugin | A project's own copy of the framework wins over the bundled one — use this when the project wants to own and edit its contract. A path that does not exist warns and falls back to the bundled copy |
| `plansFolder` | string, a project-relative path | `plans` if it exists, else `null` | Names a legacy plans folder so writing modes can offer to migrate still-live content out of it |
| `commands` | object — `typeCheck`, `test`, `lint`, each an argv line (split, run with no shell — see the `map` rows below) or `null` | Detected from the project's build tooling; a command with nothing detected is `null` | Pins the exact commands the writing modes run at hand-back through `adapter.py verify`, instead of relying on detection. Once a `commands` object is present, detection is off for all three — a key that is `null` or absent means "this project has none". Delete the whole `commands` object to return to detection |
| `map` | object (below), `null`, or absent | Absent | Turns on everything that depends on a machine-checked map — `arm`'s bridge step, `intake`'s and `reconcile`'s row-filing and citation steps, the duplicate-issue search. Absent is a fully supported, first-class configuration |

A `commands` or `map` value that is not an object warns and is treated as absent; a
path field that is not a string warns and falls back to detection. `orient.py` does
not check that a configured command exists — a wrong command is found by the first
mode that runs it, as an exit 127 from `adapter.py`.

A freshly adopted config (below) carries `"version": 1`, all three `commands` keys —
an undetected one written as `null`, so the pinning is visible in the file — and
`map` explicitly as `null` with a `$comment` pointing back here. A `null` map is
functionally identical to leaving the key out entirely.

### The `map` object

Present only when the project keeps its own machine-checked register of promises.
This plugin ships no map. `examples/minimap/` at the plugin root is a runnable
stand-in — a small `map.json`, a stdlib `capability_find.py`, a `promise.config.json`
pointing at it and a `recipe.md` — so `arm`, `adapter.py` and `bridge_validate.py`
can be watched doing the bridge before a project writes its own.

**`map.recipe` is the authority for mechanics** — which files a row touches, what
its lockstep rule means, what a citation looks like there. No mode file restates a
project's mechanics; each says "read the recipe, work from the file." Look in the
recipe for the parts a mode will ask for by name: a **routing table** (which
relation a piece of feedback becomes), the **lockstep rule** (which files move
together, and in what order), a **lane table** (how a `Then`'s altitude picks a test
kind), a **verification block** (the commands to run before calling anything done),
and a **shipped-work section** — the mirror direction, code landed and a row needs
updating.

| Key | Meaning |
|---|---|
| `recipe` | Path to the project's how-to for writing a row. Authoritative for mechanics, per above. `orient.py` warns when the file does not exist. |
| `index` | Path to the project's own reference for the map's shape — what each backing file is, what the evidence arrays mean, what each checker does and does not see. Read it alongside the recipe when the recipe assumes a concept — an evidence-array name, a checker — that this index actually defines. `orient.py` warns when the file does not exist. |
| `find` | An argv line, not a shell command: it is split like a shell would split it and run with no shell, and the query is appended as one extra argv element (`adapter.py find <query>`, or `--query-file <path>` when the query lives in a file). Pipes, `&&`, `VAR=x` prefixes, `cd` and globs are not interpreted — they arrive as literal arguments or fail with exit 127. Put such logic in a script in the repo and name that script here. |
| `row` | An argv line (as above); the row id is appended as one element (`adapter.py row <id>`). |
| `nextId` | An argv line, run with no argument appended, that prints the id the next new row would take. |
| `rowIdPattern` | A regular expression every row id must match. `orient.py` warns when it does not compile. |
| `lanes` | An object mapping the four altitudes plus `sibling` to the project's own evidence-array names. This is what lets `references/altitude.md` stay generic — a mode cites "the lane the altitude picks," and `map.lanes.<altitude>` is where that array name comes from. |
| `checks` | An array of argv lines, each run with no shell, in order, at the end of `arm`, `intake` and `reconcile`, before the mode hands back. Optional, but a project with no checks writes `[]` explicitly: with the key absent, `adapter.py checks` refuses with exit 2 (`map.checks is not configured`), and the modes run it only when a map is configured and `checks` is set — a refusal is reported as not run, never as a failed check. |
| `issueTracker` | Optional. An object `{ kind, repo, template }` of three strings naming the project's issue tracker. When present, `intake` and `reconcile` search it — by row id and by the promise in plain words, open and closed — before filing anything new. |

A map counts as configured only when `recipe`, `find` and `row` are strings and
`lanes` is an object of strings — the `mapUsable` rule `references/architecture.md`
§5 states. A map missing any of these is reported by `orient.py` as `map incomplete:
missing …` with `mapUsable: false`; every mode then treats it as no map, `adapter.py`
refuses map operations (exit 2, naming the missing keys) and `bridge_validate.py`
reports `MAP_NOT_CONFIGURED` with the same keys named — neither works from a partial
map. A missing `recipe` or `index` file, a
`checks` value that is not an array of strings, an `issueTracker` that is not three
strings, and a `rowIdPattern` that does not compile each warn without changing
`mapUsable` — the map a project configured is the map every script sees.

Scripts read `find`, `row`, `nextId`, `rowIdPattern` and `checks` (`adapter.py`,
`bridge_validate.py`). `recipe`, `index`, `lanes` and `issueTracker` are read by the
modes, from the file, never by a script.

## Without a map

Each writing mode has a fully defined behaviour when `map` is absent, `null`, or
incomplete (`mapUsable: false`), and each states "no map configured" in its Phase 0
line:

- **`arm`** writes the acceptance rows as red tests and nothing more. There is no
  bridge step, no not-built row is filed anywhere, and there is no row id to write
  into a `Row` column.
- **`intake`** matches feedback against the outcome docs already in `docsHome` —
  specifically their §6 (Acceptance) rows — instead of a map, and files its routing
  table into the doc itself: §6 for a new or extended row, §9 (Open questions) for a
  decision.
- **`reconcile`** updates the doc only: it re-stamps §0's rule tags and the
  `Scenarios:` count, and appends a dated §8 entry. There is no evidence array to
  cite into and no kill witness to record, because there is no map row to promote.

## Adopting in a project

The fast path is **`/promise adopt`** (`modes/adopt.md`). It runs
`scripts/adopt.py`, which writes `.claude/promise.config.json` if one is not already
there — `"version": 1`, `docsHome`, the three `commands` keys as detected, and
`map: null` with a `$comment` pointing back to this file — and inserts, or on a
later run replaces, a short section in the project's `CLAUDE.md` between
`<!-- promise:begin` and `<!-- promise:end -->` markers. That section is what routes
every person and agent in the project to `/promise` instead of a hand-written
design, plan or spec doc — see `references/architecture.md` §13 for the script's
exact contract. Adopting never overwrites an existing config, never creates a docs
folder unprompted (a folder is created only on the user's explicit choice), and the
`CLAUDE.md` edit never touches anything outside its own markers; the section itself
is rendered from a template, never hand-written.

`orient.py` reports an `adopted` boolean in its JSON — true only when a config was
loaded **and** the `CLAUDE.md` section exists — and warns `project not adopted — run
/promise adopt` when it is false. Every mode's Phase 0 line states it, and offers
`adopt` once per session when it is false, continuing with the requested mode either
way.

### Adopting by hand

The same outcome as `/promise adopt`, done manually — for a project that wants to
write its own config without the script:

1. **Pick `docsHome`.** Use an existing docs folder, or decide where outcome docs
   will live if the project has none yet.
2. **Optionally copy the framework.** The bundled framework works as-is; copy it
   into the project — and point `frameworkPath` at the copy — only when the project
   wants to own and edit its own contract.
3. **Write the config** at `.claude/promise.config.json`, starting from
   `templates/promise.config.example.json` and deleting what does not apply. Most
   projects start with no `map` at all.
4. **Run `scripts/orient.py`** and read its `warnings[]`. An unknown key, a
   wrong-typed field, a path that escapes the project or uses backslashes, a
   `docsHome`, `frameworkPath`, `map.recipe` or `map.index` that does not exist, an
   incomplete `map`, a `rowIdPattern` that does not compile, a malformed `checks`
   or `issueTracker`, a `version` other than `1`, and a deprecated `$schema` key
   all surface here before any mode runs. orient does **not** check
   that the configured commands exist — a wrong command is found by the first mode
   that runs it.
5. **Run `scripts/lint_outcome.py` over `docsHome` once**, and read what it finds.
   Docs written before this config existed will not conform on the first pass —
   that is the adoption cost, not a bug.
