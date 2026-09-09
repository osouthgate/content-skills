Read before this: references/config.md
Phase 0 line: mode `adopt` (say if inferred), framework source, docs home and its source, `claudeMd.path` and `hasPromiseSection`, whether a config is loaded (and from where), whether a map is configured, and `adopted`.
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
reason and a completeness score:

- **(Recommended), 9/10** — Phase 0's own detection (`docsHome` / `docsHomeSource`).
  Right whenever a docs folder already exists and holds real documents.
- **7/10** — a different existing folder the user names. Right only when detection
  picked the wrong one.
- **4/10** — a new folder, created now. Only on the user's explicit say-so; this
  skill never creates one unprompted, and nothing lives there yet.

## Decide whether to configure a map now

- **(Recommended), 9/10** — leave `map` null. Right for any project with no
  machine-checked register of promises yet; `intake` and `reconcile` work the docs
  directly, and `map` can be configured later without re-adopting.
- **10/10, but only when the precondition holds** — configure it now. Correct only
  when the project already keeps its own machine-checked register of promises and
  the tests that prove them. Needs `recipe`, `find` / `row` / `nextId`, `lanes`
  and, optionally, `issueTracker` — `references/config.md` names every key.

## Run the script

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" --dry-run [--docs-home <dir>]
```

Show the diff it prints — the config it would write (if one is absent) and the
`CLAUDE.md` section it would insert or replace. On the user's yes, run the same
command without `--dry-run`.

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
