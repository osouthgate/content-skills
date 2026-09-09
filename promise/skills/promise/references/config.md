# Config — `.claude/promise.config.json`

*The user-facing contract for the config file. The machine-checked version of this
contract is what `scripts/orient.py` validates; see `references/architecture.md` §6
for the schema it validates against. This file explains what a project gets by
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
- **`$schema` and `$comment` are ignored** wherever they appear, at the top level or
  inside `commands` or `map` — they are never read as required fields.

## Fields

| Field | Type | Default when absent | What changes when it is set |
|---|---|---|---|
| `docsHome` | string, a project-relative path | The first existing of the common docs-folder names detection checks for; `null` if none exist | Pins where outcome docs live — every mode searches and writes there instead of relying on detection |
| `frameworkPath` | string, a project-relative path | The framework bundled with this plugin | A project's own copy of the framework wins over the bundled one — use this when the project wants to own and edit its contract |
| `plansFolder` | string, a project-relative path | `plans` if it exists, else `null` | Names a legacy plans folder so writing modes can offer to migrate still-live content out of it |
| `commands` | object — `typeCheck`, `test`, `lint`, each a shell command string or `null` | Detected from the project's build tooling; a command with nothing detected is `null` | Pins the exact commands `arm`, `intake` and `reconcile` run to verify a change, instead of relying on detection. Set a command to `null` explicitly to say "this project has none," rather than leaving detection to guess wrong |
| `map` | object (below), or absent | Absent | Turns on everything that depends on a machine-checked map — `arm`'s bridge step, `intake`'s and `reconcile`'s row-filing and citation steps, the duplicate-issue search. Absent is a fully supported, first-class configuration |

A freshly adopted config (below) writes `map` explicitly as `null` rather than
omitting the key, with a `$comment` pointing back here — functionally identical to
leaving the key out entirely.

### The `map` object

Present only when the project keeps its own machine-checked register of promises.
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
| `recipe` | Path to the project's how-to for writing a row. Authoritative for mechanics, per above. |
| `index` | Path to the project's own reference for the map's shape — what each backing file is, what the evidence arrays mean, what each checker does and does not see. Read it alongside the recipe when the recipe assumes a concept — an evidence-array name, a checker — that this index actually defines. |
| `find` | A shell command. Run verbatim with the query appended in quotes: `<find> "<query>"`. |
| `row` | A shell command. Run verbatim with a row id appended: `<row> <id>`. |
| `nextId` | A shell command, run verbatim with no argument, that prints the id the next new row would take. |
| `rowIdPattern` | A regular expression every row id must match. |
| `lanes` | An object mapping the four altitudes plus `sibling` to the project's own evidence-array names. This is what lets `references/altitude.md` stay generic — a mode cites "the lane the altitude picks," and `map.lanes.<altitude>` is where that array name comes from. |
| `checks` | An array of shell commands, run in order at the end of `arm`, `intake` and `reconcile`, before the mode hands back. |
| `issueTracker` | An object `{ kind, repo, template }` naming the project's issue tracker. When present, `intake` and `reconcile` search it — by row id and by the promise in plain words, open and closed — before filing anything new. |

## Without a map

Each writing mode has a fully defined behaviour when `map` is absent, and each
states "no map configured" in its Phase 0 line:

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
there — `docsHome`, detected `commands`, and `map: null` with a `$comment` pointing
back to this file — and inserts, or on a later run replaces, a short section in the
project's `CLAUDE.md` between `<!-- promise:begin` and `<!-- promise:end -->`
markers. That section is what routes every person and agent in the project to
`/promise` instead of a hand-written design, plan or spec doc — see
`references/architecture.md` §13 for the script's exact contract. Adopting never
overwrites an existing config, and the `CLAUDE.md` edit never touches anything
outside its own markers; the section itself is rendered from a template, never
hand-written.

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
4. **Run `scripts/orient.py`** and read its `warnings[]`. A missing `docsHome`, an
   unresolved command, or an unknown key all surface here before any mode runs.
5. **Run `scripts/lint_outcome.py` over `docsHome` once**, and read what it finds.
   Docs written before this config existed will not conform on the first pass —
   that is the adoption cost, not a bug.
