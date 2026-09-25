# Changelog

## 1.4.0

The thin draft: start a promise with less.

- **`Depth: thin`.** A `draft` doc can now hold the human half only: §0–§2, §8–§10
  and any seed example, with §3–§7 marked "not written yet". `new` offers it,
  Recommended, when the outcome line is known but the rules, the signal or an
  example are not. Each gap is a BLOCKING §9 question, never text the model wrote
  for the human. Rules stay verbatim-confirmed. Framework decision F10.
- **`render_outcome.py --thin`** writes the shape: the `Depth: thin` line, one rule
  slot tagged `→ UNTESTED`, zero `Scenarios:` counts.
- **New lint rule `THIN_DRAFT`** (error): a `Depth:` line must read `Depth: thin`,
  and only on a `draft`. On a thin draft the lint does not require the §6 table or
  the §4–§7 Why lines, counts an empty §3 as zero, and reports an empty rules block
  as a warning. Past `draft` every rule applies in full, so a thin doc cannot be
  agreed or armed.
- **`revise` fills a thin draft** once the human half is complete, with `new`'s
  agent-half steps, and removes the line. `arm` names the thin line as a
  precondition.
- README: a "Why promise" section with a one-line and a thirty-second explanation.

## 1.3.0

Proof strength: a second axis beside altitude, for §4 invariants.

- **Three strengths.** `example` (chosen cases), `property` (the real code on
  generated cases), `model` (every reachable state of a model, by a machine-checked
  proof such as Lean or an exhaustive TLA+ check). Altitude says what evidence reaches;
  strength says how much of it. "Must never" is a claim about every case, and an
  invariant held only by examples now says so. New section
  `references/altitude.md` § Proof strength; framework decision F8.
- **§4 enforcement points** gain `property` and `proof` beside constraint, test and
  `file:line`, and name their strength when they are evidence — in the framework's
  Section rules, the template and `new`. The review rubric's depth item checks it.
- **A `model` proof never enforces an invariant alone.** It names a conformance test
  that runs the real code against the model, because the model is a second copy of the
  logic and can differ from the code while every theorem stays green.
- **Red and kill rules carry over.** A proof with `sorry`, `admit` or an unchosen axiom
  is red. The kill mutation is applied to the model (allow the forbidden transition,
  watch the proof fail, revert); the positive control proves the protected state is
  reachable.
- §6 rows, map lanes and the verdict rule are unchanged. Vocabulary gains
  **proof strength**.

The capability map becomes the goal, offered at the first agreed doc.

- **A starter map ships with the skill.** `templates/starter-map/` holds an empty
  `map.json`, its stdlib reader `capability_find.py` and a `recipe.md`. The new
  `scripts/start_map.py` copies it into a project (`docs/capabilities` by default),
  fills `{dir}` and `{docRoot}`, and writes the config's `map` object so `orient.py`
  reports `mapUsable: true` straight after. It refuses, writing nothing, when there is
  no config, when the config already has a `map` object (even a partial one), or when
  the destination escapes the project or already holds files; `--dry-run` shows the
  files and the config diff.
- **`arm` offers it, Recommended,** when no map is configured and `map` is null, before
  anything is filed; the files and the config ride the doc commit. **`adopt`**
  recommends it when an agreed doc already exists, and otherwise leaves `map` null and
  says `arm` will offer it. adopt's null-map `$comment` says so too; `start_map.py`
  removes exactly that comment when it fills the map.
- **The framework says why.** § Lifecycle gains "The capability map is the goal"; new
  decision F9. `config.md`, the README, the architecture (tree, §13, §14, vocabulary)
  and the example config stop saying the plugin ships no map.
- **The reader gains `docRoot`.** `capability_find.py --check` resolves a row's `doc`
  against the map's optional top-level `docRoot` (relative to the map, default `.`), so
  a map in a subfolder cites docs by their project-relative path. `examples/minimap/`
  runs the same file byte for byte; `tests/test_start_map.py` holds the two copies equal
  and covers install, refusal and `docRoot`.

## 1.2.0

The `outcome` plugin is removed from this repository; its framework lives on here.
The doc contract gains one column, every script is hardened against the inputs a real
project hands it, the router gains a confirmation gate, and every pre-install surface
is brought level with the plugin.

### Doc contract

- **Altitude column in §6.** The acceptance table gains a fifth column between `Then`
  and `Row`: `| #    | Given | When | Then | Altitude | Row |`, with exactly one of
  `data`, `response`, `perception`, `judgement`, `sibling` per row — the machine-readable
  left operand of the verdict rule (`references/altitude.md`). `lint_outcome.py` gains
  `ACCEPTANCE_ALTITUDE` (error: the column is present and a cell is empty or not one of
  the five) and `ALTITUDE_MISSING` (warning: a §6 table has no `Altitude` header, so
  older docs keep linting). `outcome_rows.py` emits `"altitude"` per row (`null` when
  the column is absent). The framework, the template, `altitude.md`, `new`, `arm`,
  `reconcile`, architecture §9/§10 and the fixtures all carry the column.
- **The framework states the two lines its tooling already required.** A `building`
  doc's `Red gate: <sha> <YYYY-MM-DD>` header line, directly under `Supersedes:`
  (`lint_outcome.py BUILDING_NEEDS_GATE`), and a bridged doc's
  `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of these scenarios from here on. ``
  line under the §6 table (`bridge_validate.py SNAPSHOT_LINE_MISSING`) are now in
  `outcome-framework.md`'s Lifecycle, not only in `modes/arm.md`.
- **One home for the template.** `outcome-framework.md` no longer embeds a second copy
  of the skeleton; `templates/outcome-doc.md` is the one shape and the framework points
  at it. The §4 boundary guidance that lived only in the embedded copy moved into
  Section rules.
- **§0 carries only the human's words.** The template's five-line note to the agent,
  which every rendered doc carried inside the protected block and counted against its
  40 lines, is gone; the "Agent notes" line takes the framework's wording. The
  `**Scenarios:**` line pluralises correctly: the lint accepts `worked example` and
  `worked examples`, `outcome_rows.py --write-counts` writes the right one, and the
  template says `1 worked example`.
- **Worked-example minimum reworded.** "the happy path, the disconnect/undo path, the
  permission-removal path" — one product's shape — becomes "the happy path, the
  undo/reverse path, and any permission or visibility edge the capability has" in the
  framework, the template and `new`.

### Scripts

- **`§`, never `SS`.** `lint_outcome.py`, `outcome_rows.py`, `orient.py` and `adopt.py`
  print `§` where they printed the digraph `SS`; stdout is reconfigured to degrade to
  `?` on a console that cannot encode it instead of crashing.
- **Config `"version": 1`.** Replaces `"$schema": "promise.config/v1"`, a reserved key
  holding a value nothing resolved. `orient.py` accepts both and warns on `$schema` as
  deprecated; `adopt.py` writes `"version": 1`; the example config, the fixtures and
  `config.md` say so.
- **Query files.** `adapter.py find --query-file <path>` and
  `outcome_rows.py --search-file <path>` read the query from a file (`-` = stdin); the
  inline form stays. `intake` and `reconcile` write the verbatim item to a scratch file
  with the Write tool and pass the flag, so "no composed shell strings" now holds for
  both hops, not only the adapter's.
- **Map usability is one field.** `orient.py`'s `mapUsable` is the single source of "is
  a map configured". When it is false, `adapter.py` refuses map operations (exit 2) and
  `bridge_validate.py` reports `MAP_NOT_CONFIGURED`, both naming the missing keys,
  instead of running against a partial map; `adapter.py show` still prints the partial
  map with a note. Mode files say "whether a map is configured (orient's `mapUsable`)".
- **`render_outcome.py --create-docs-home`.** The docs folder is created only when that
  flag is passed — the user's explicit choice in `new` or `adopt` — never unprompted; a
  `--dry-run` needs neither the folder nor the flag. Also new: `--slug <name>` for a
  title with no ASCII letter or digit (an empty slug is refused instead of writing a
  hidden `.md`), `--date` must be a real calendar date, `--title` and `--owner` must be
  non-blank single lines, and a docs home that is a file is refused.
- **`lint_outcome.py` hardening.** New error rule `RULES_PRESENT` (a `**Rules:**` marker
  with no rule bullet). Lines inside a ``` or ~~~ fence are illustrations — no heading,
  field marker, table row or placeholder inside one counts — so a framework copy in
  `docsHome` is no longer linted as a doc. `ACCEPTANCE_TABLE` reads a row missing its
  leading or trailing pipe GFM-style and reports it at its own line instead of dropping
  it and every row below. `TLDR_FIELDS` accepts a curly apostrophe in
  `**How we'll know:**` and bounds the rules block by the next field, heading or the
  end of §0 — one finding, not a cascade. `WHY_LINE` fires on an empty value;
  `PLACEHOLDER` also scans agent notes, the first line of each §3 example, a §9 owner
  and every Why-line value. A Why line or the snapshot line directly under the §6
  table is never read as a table row, pipe in its prose or not. A fence that is
  opened and never closed is its own error, `FENCE_UNCLOSED`, at the opening line —
  every line after it is an illustration to every other rule, and the wall of
  missing-heading findings that produces now has a named cause. The exit contract is
  documented as it is: 0 with no error finding, 1 on an error (or a warning under
  `--strict`), 2 on usage. `HUMAN_HALF_BUDGET` gains its one-change fixture, so every
  lint rule now has one.
- **`orient.py`.** `mode` is `null` when `--mode` was not passed. It warns when a
  configured `docsHome`, `map.recipe` or `map.index` is not on disk (the value is still
  returned; `mapUsable` stays a shape check), when a path uses backslashes (normalised
  for `docsHome`, `plansFolder` and `frameworkPath`), and when `map.checks` or
  `map.issueTracker` is malformed, and when a loaded config pins no `docsHome` in a
  project where detection finds no docs folder either. A path that escapes the project
  includes a Windows drive-letter path (`C:\\x`, `C:/x`, `D:docs`) on every OS. The
  existing-docs scan reads one level deep — the folder and its immediate subdirectories,
  the same scan the lint and `--search` use — ignores fenced headings and
  skips a non-UTF-8 file with a warning. A digit-only 7–40 run is no longer read as a
  commit sha; a plain complaint sentence ("users say X is broken") leans `intake`;
  `bun.lock` is detected. A `--cwd` that is not a directory or a non-UTF-8
  `--input-file` exits 2 with one line, never a traceback.
- **`framework_section.py`.** Resolves `frameworkPath` through `orient.py`, so an
  escaping or missing path falls back to the bundled copy exactly as Phase 0 does; no
  section name and no `--list` prints usage and exits 2.
- **`adapter.py`.** `verify --only typeCheck|test|lint` (repeatable) narrows the verify
  run; `show` prints a note line for an incomplete map and for nothing configured; a
  non-string configured command is a plain refusal, never a traceback. `--query-file`
  and `outcome_rows.py --search-file` keep an interior CRLF as written — only the
  trailing line terminator is dropped.
- **`bridge_validate.py`.** New error rule `STATUS_UNKNOWN` (a missing or invalid
  `Status:`), checked before `NOT_BRIDGED`; `THEN_NOT_IN_MAP` names all three causes —
  the map moved on, the row was filed differently, or §6 was edited after the snapshot.
- **`outcome_rows.py`.** `--search --dir` walks the folder plus its immediate
  subdirectories, as the lint does, and refuses a missing or non-directory `--dir` with
  exit 2; a non-UTF-8 doc is an exit-2 refusal.
- **`adopt.py`.** Writes the `commands` object only when at least one command was
  detected, then with all three keys (undetected as `null`); writes through a symlinked
  `CLAUDE.md` and keeps its mode; refuses a `--docs-home` that is absolute, escapes the
  project, or holds a newline or a marker string, a `CLAUDE.md` or config path that is
  a directory or sits under a file, and a non-UTF-8 `CLAUDE.md` — JSON still on stdout,
  nothing written; tolerates whitespace around the end marker and says on stderr when
  it restores a hand-edited block. A `--docs-home` written with backslashes is recorded
  with forward slashes; a `--docs-home` that disagrees with an already-loaded config's
  `docsHome` is refused (exit 2) rather than re-rendering `CLAUDE.md` against a folder
  the config does not name; a fresh config that would pin no `docsHome` says so on
  stderr; the JSON result carries `docsHome`. The escape rule is orient's, imported,
  not a second copy.

### Router and modes

- **A missing interpreter no longer aborts the skill.** The load-time line ends in
  `|| true`; the fallback paragraph tries `python`, then `py -3`, before asking for an
  install, and uses the first spelling that runs for every script that session.
- **Configured commands run on a yes, not a print.** Before the first configured command
  runs in a session, `adapter.py show` is printed and the person is asked
  ((Recommended) first, one reason); nothing configured runs until the yes, and on no
  the session continues as if no map and no `commands` were configured. `config.md`
  gains a "Trust model" section: every configured string runs as the caller, like a
  `package.json` script; the adapter protects against a hostile query, not a hostile
  config.
- **Completeness scores dropped.** "(Recommended) first, with one concrete reason"
  stays; the mandatory 1–10 completeness score is gone from every mode and reference,
  along with `adopt`'s pre-baked numbers. Reading-assignment close-outs in `intake` and
  `reconcile` are an offer, not a requirement.
- **`arm` in order.** The branch is cut first; the bridge runs on `feat/<slug>` behind
  a reachability gate (`adapter.py --json next-id` / `row` must succeed before anything
  is filed) with a per-rule table for every `bridge_validate.py` finding; the red run is
  `adapter.py --json verify`; the doc — and, with a map, the recipe's row files — is
  committed by explicit path as the branch's second commit. Loosening `rowIdPattern`, a
  checker or a ratchet is never a fix. The unreachable "protected branch" refusal became:
  name the base branch and ask when it is not the project's main branch.
- **§6 is a snapshot once bridged.** `revise` edits §6 only while it carries no `Row`
  ids and no snapshot line, and runs `bridge_validate.py` before and after an edit to a
  bridged doc; `review` folds `THEN_NOT_IN_MAP` and `SNAPSHOT_LINE_MISSING` in as
  findings; `reconcile` runs it before reading the map.
- **`merge` names its mechanics.** `git rm` by explicit path and one commit with the
  survivor; a bridged folded doc's map rows are re-pointed or retired per the recipe,
  with the user; a `building` folded doc's red gate is retired in §8 and the branch's
  disposition asked; `Status: superseded-by <survivor>` is written only on a folded doc
  the user chooses to keep, and the framework's Lifecycle says so.
- **One hand-back sequence.** `arm`, `intake` and `reconcile` all run
  `adapter.py checks` if a map is configured (and `map.checks` is set),
  `adapter.py verify` if any `commands.*` is configured (`[]` is reported as "not
  verified", never a pass), and the lint always. Each writing mode says in one line that
  the lint checks shape, not truth.
- **`new` asks for the whole human half.** Five prompts in one turn — outcome, why,
  rules echoed for verbatim confirmation, how-we'll-know, one concrete example — plus
  the owner, with `git config user.name` as the recommended default. The §3 minimum is
  the happy path, the undo/reverse path and any permission or visibility edge.

### Packaging and docs

- **The `outcome` plugin is removed** — its directory, its marketplace entry and the root
  README's install line. Every remaining supersession sentence says so.
- **The pre-install surfaces agree with the plugin.** The marketplace entry and the root
  README undercounted the modes by one; there are eight. The marketplace description is now the same
  string as `plugin.json`'s, and neither lists `agreed` among the modes — `agreed` is a
  status a human types; `arm` is the mode that files rows and commits the red tests
  once a human has typed it.
- **The README leads with the doc, not the map.** A filled §0, the four-step path that
  needs no config and no capability map, a table of what a script checks versus what
  the model is instructed to do, a definition of "capability map" at first use with a
  plain statement that this plugin ships none, a Codex/Cursor install path, a
  ten-word glossary and a prior-art paragraph. The Scripts block runs verbatim from
  `promise/`.
- **Examples outside `tests/`.** `examples/channel-muting.md` (a lint-clean doc),
  `examples/transcript.md` (a short annotated session) and `examples/minimap/` (a tiny
  capability map with a stdlib `capability_find.py`, so `arm`, `bridge_validate.py`
  and `adapter.py` can be watched doing the bridge). The minimap's
  `capability_find.py --check` also reads each row's `doc` and requires a §6 line
  citing the row — the map-to-doc direction `bridge_validate.py` does not read — and
  validates an optional `parent` as a row id. `tests/test_examples.py` lints
  the examples and runs `bridge_validate.py` against the minimap.
- **Tests and CI.** New suites `test_orient_render.py`, `test_adopt_hardening.py`,
  `test_examples.py` and `test_packaging.py` (the pre-install surfaces agree with the
  plugin: marketplace description, mode count, version). `.github/workflows/tests.yml`
  runs `python3 -m unittest discover -s promise/tests -v` on ubuntu-latest with Python
  3.12 on every push and pull request.
- **Config contract corrected.** `map.find` / `row` / `nextId` / `checks` and
  `commands.*` are documented as argv lines run with no shell, which is what
  `adapter.py` does. `orient.py`'s warnings are described as what they are — key names,
  types, path escapes, whether `frameworkPath`, `docsHome`, `map.recipe` and `map.index`
  exist on disk, map completeness, `rowIdPattern` compilation — never as a check that the
  configured commands exist or run.
- **Architecture doc brought level.** §3's file tree lists every script, the Codex
  metadata file and every test file; the example config is byte-identical to
  `templates/promise.config.example.json` (a shape test pins both); §7's vocabulary
  gains slate, recipe, lockstep, ratchet, red gate, kill mutation and snapshot line;
  §9 and §10 list every rule above.
- A root `LICENSE`, editor and OS artefacts in `.gitignore`, and the marketplace's own
  metadata (version 0.2.0) now names the plugins it lists.

## 1.1.0

`bridge_validate.py` closes the gap between a bridged doc's §6 and the capability
map it cites: Row ids against `rowIdPattern`, every AT row mapped, the snapshot
line present, and each row's `Then` against the map's current text — read through
`adapter.py`, so a row id always travels as one argv element, never a shell string
composed from configuration plus doc content. `NOT_BRIDGED` is checked before
`MAP_NOT_CONFIGURED`, so a still-`draft` doc reads as not-yet-bridged even in a
project with no map, never as a map problem. An invalid `map.rowIdPattern` (bad
regex syntax) is its own error, `INVALID_ROW_ID_PATTERN`, carrying the compiler's
own exception text — never silently folded into `NO_ROW_ID_PATTERN`'s "absent"
warning, which stays for a pattern that is genuinely not configured. `arm` runs it
once the `Row` column and snapshot line are written, and fixes every error before
continuing; `reconcile` runs it before reading the map, because a drift finding
means §6 no longer says what the map says.

`lint_outcome.py` gains `BUILDING_NEEDS_GATE` (error): a `building` doc's header
must carry its own line matching `Red gate: <sha> <YYYY-MM-DD>` exactly — position
among the header lines is not enforced, the line's own shape is, so a hex-looking
run inside some other header value never quietly satisfies it. `arm` records the
line there, so the status stays traceable to the act that earned it. A new test
locks the wider rule this is one piece of: `agreed` and `shipped` are typed by a
human, never by this skill; `building` is the one exception, written only after
the human confirms the red gate. `acceptance_column_map` now also rejects a header
that names `Given`, `When`, `Then` or `Row` more than once — never a guessed
mapping, the same `ACCEPTANCE_TABLE` error as a header missing one of them.

## 1.0.0

First release. Supersedes the `outcome` plugin, which stays in this repository with a
pointer here; its framework lives on here. [The `outcome` plugin was removed in 1.2.0.]

### What it contains

- **One skill, eight modes.** `new`, `revise`, `review`, `merge` cover the doc's
  lifecycle; `arm`, `intake`, `reconcile` carry the promise past `agreed` into a
  project's capability map, its red tests, and its reconciliation with shipped work;
  `adopt` sets a project up. A thin `SKILL.md` infers the mode; only that mode's file loads.
- **The Outcome Framework, with its decisions recorded.** The outcome line and the
  success signal are forced choices from verbatim candidate slates; rules are never
  slated. Revise has an explicit procedure. §0 has exactly two agent-maintained
  carve-outs (rule test tags and the `Scenarios:` count); agent notes sit below the
  block and do not count toward its 40 lines. The framework's own decision table (F1–F7)
  states each choice and its reason.
- **The map is the source after `agreed`.** Where a project keeps a machine-checked
  capability map, `arm` files the §6 rows into it as not-built rows and the doc's §6
  cites them through a `Row` column instead of carrying a second copy. §0 keeps the
  doc-local `AT-n` aliases.
- **Config over fork.** A project supplies `.claude/promise.config.json` (docs home,
  framework path, commands, and an optional `map` adapter naming its recipe, search
  commands, evidence lanes, checks and issue tracker). Nothing project-specific is
  hard-coded. See `skills/promise/references/config.md`.
- **Scripts.** `orient.py` resolves the project shape in Phase 0 and prints one JSON
  object. `lint_outcome.py` checks every shape rule the framework states (§0 budget, bare
  headings, contents anchors, rule format and tags, tag resolution, scenario counts,
  why-lines, placeholders, UNTESTED-on-agreed) with stable rule ids and exit codes.
  `outcome_rows.py` extracts §0 rules and §6 rows as JSON for the bridge.
  `framework_section.py` prints only the framework sections a mode names in its header,
  so a run loads what it needs rather than the whole contract. Standard library only;
  one implementation for every OS.
- **No composed shell strings.** `adapter.py` runs every configured project command with
  the user's text as one argument, and `show` lists them before any runs. `render_outcome.py`
  instantiates the template and refuses to overwrite.
- **Tests.** `python3 -m unittest discover -s promise/tests -v` covers every lint rule
  except `HUMAN_HALF_BUDGET` (a warning) with a one-change fixture, `orient.py` against a
  fixture repo and an empty directory, and `outcome_rows.py` round-trips.
- **A proof taxonomy shared with the map.** `references/altitude.md` maps §0's four
  signal kinds onto the four `Then` altitudes and their lanes, and states the verdict
  rule: evidence moves a verdict only when it reaches the altitude the row's own `Then`
  claims.
- **Plain words, not syntax.** A leading mode word is a shortcut, never a requirement. The
  router infers the mode from the input and from Phase 0 (existing docs, configured map),
  states the inference in one line, and asks only when two modes are genuinely plausible.
  `orient.py --input` reads the same signals deterministically and names the rule that
  fired, as a hint the router confirms.
- **Adopt.** `/promise adopt` writes the project config and inserts a fenced section into the
  project's `CLAUDE.md` that routes every agent and person to the skill. `orient.py` reports
  `adopted` and every mode offers the step once when it is false.

### Why the rename

An outcome doc *makes* a promise; a proven row *keeps* it; a defect *breaks* it. The
skill now spans both halves, so it takes the word that covers both. The framework keeps
its name — the Outcome Framework is how a promise is written down.
