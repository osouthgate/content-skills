Read before this: references/config.md
Phase 0 line: mode `adopt` (say if inferred), framework source, docs home and its source, `claudeMd.path` and `hasPromiseSection`, whether a config is loaded (and from where), whether a map is configured (orient's `mapUsable`), and `adopted`.
Writes: `.claude/promise.config.json` (only if absent) and the `<!-- promise:begin -->…<!-- promise:end -->` section of `CLAUDE.md` (created if absent, else replaced in place) — both only through `scripts/adopt.py`, never by hand.

# Adopt — route the project through `/promise`

A project is **adopted** once it has a config (§6) and its `CLAUDE.md` carries the
promise section, so every person and agent working there is routed to `/promise`
instead of writing a design, plan or spec doc by hand. `scripts/adopt.py -h` states
exactly what the script writes; this mode is the conversation around running it.

## Show the current state

Read Phase 0's JSON and show, in one line each: `claudeMd.path` and
`hasPromiseSection`, whether a `config` was loaded (and from where), and `adopted`.
Already `adopted` → say so and stop; nothing below needs to run.

## Confirm the docs home

Put the docs home to the user as a choice, **(Recommended)** first, each with one
concrete reason:

- **(Recommended)** — Phase 0's own detection (`docsHome` / `docsHomeSource`).
  Right whenever a docs folder already exists and holds real documents.
- A different existing folder the user names. Right only when detection picked
  the wrong one.
- A new folder. Only on the user's explicit choice — this skill never creates one
  unprompted. Pass it as `--docs-home <dir>` so the config pins it; `new` creates
  it (`render_outcome.py --create-docs-home`) the first time it writes there.

`docsHomeSource` is `none` → the detection option does not exist; the
**(Recommended)** option is then a new folder (default `docs/designs`, passed as
`--docs-home docs/designs`), because without it the config pins nothing and every
later `new` asks again.

## Decide whether to configure a map now

- **(Recommended)** — leave `map` null. Right for any project with no
  machine-checked register of promises yet; `intake` and `reconcile` work the docs
  directly, and `map` can be configured later without re-adopting.
- Configure it now. Correct only when the project already keeps its own
  machine-checked register of promises and the tests that prove them. A map
  counts as configured (orient's `mapUsable`) once `recipe`, `find`, `row` and
  `lanes` are set; `nextId`, `checks`, `rowIdPattern` and `issueTracker` are
  optional — `references/config.md` names every key.

## Run the script

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" --dry-run [--docs-home <dir>]
```

Show the diff it prints — the config it would write (if one is absent, with
`"version": 1` as its first key) and the `CLAUDE.md` section it would insert or
replace. On the user's yes, run the same command without `--dry-run`. On a project
that already has a config, a `--docs-home` that disagrees with its `docsHome` is
refused (exit 2): change the config, not the flag, so `CLAUDE.md` and the config
never name different folders.

## Verify

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py"` again and show `adopted:
true`.

## Rules

- **Never overwrite an existing config.** `adopt.py` refuses to; a config is
  already there → say so and move on to the `CLAUDE.md` section alone.
- **Never edit `CLAUDE.md` outside the `<!-- promise:begin` / `<!-- promise:end
  -->` markers.** Everything else in the file is the project's own.
- **The block is rendered from `templates/claude-md-section.md`, never
  hand-written.** The block needs to say something the template does not → that is
  a template change, not a one-off edit.

## Close out

Paste the inserted (or replaced) `CLAUDE.md` block verbatim. List the files
written. Say what was left undone — most often, `map` still `null`, and what it
would take to fill in.
