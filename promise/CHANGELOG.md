# Changelog

## 1.0.0

First release. Supersedes the `outcome` plugin, which stays in this repository for one
release with a pointer here.

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
- **Tests.** `python3 -m unittest discover -s promise/tests -v` covers each lint rule
  with a one-change fixture, `orient.py` against a fixture repo and an empty directory,
  and `outcome_rows.py` round-trips.
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
