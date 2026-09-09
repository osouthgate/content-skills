---
name: promise
description: |
  Carries a capability from intent to proof, in one skill: an outcome doc records
  the promise before anything is built, its acceptance rows become rows in a
  capability map once the project keeps one, red tests prove them, and
  reconciliation moves a row's verdict only when the evidence catches up. A
  leading mode word is optional — the skill infers the mode from plain words
  and says which one it picked. Use when the user says "/promise", "outcome
  doc for X", "design this", "plan this", "spec this", "write a plan/design
  for X", or hands over a braindump/transcript/ticket to structure — new
  mode, the default. Also covers: a path to an existing doc plus a requested
  change (revise mode); "review this doc/pack" (review mode); "merge these
  docs" (merge mode); "arm <doc>" (arm mode); "turn this feedback into
  gherkins", "map this feedback to capabilities", "which capability covers
  this", "add this as a scenario to <row>" (intake mode); "we already do
  this", "isn't <row> already covered", "I just landed the test, update the
  map" (reconcile mode); and "set this project up for promise", "install /
  configure promise here", "add promise to CLAUDE.md" (adopt mode).
argument-hint: "[new|revise|review|merge|arm|intake|reconcile|adopt] <what you want, in plain words>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
---

# /promise

`outcome-framework.md`, beside this file, is the contract for the doc — the
template, the section rules, the lifecycle, and the review rubric. When this
skill and the framework disagree, the framework wins. This skill produces the
doc up to `draft` and carries out the transitions a human calls for after
that; it never implements the capability the doc describes.

Where the project configures a capability map, the map becomes the source of
the doc's scenarios from the moment a human marks the doc `agreed` — the
doc's acceptance rows are filed there as rows, and `intake`/`reconcile` read
and write the map, not a second copy inside the doc. No map configured →
the doc stays the only home, always.

## Other hosts

This file follows the shared SKILL.md standard, so Codex and Cursor read it too. Three
things below are Claude Code notation, which Claude expands at load time and other hosts
show literally; translate them there: the CLAUDE_SKILL_DIR variable is the directory
containing this file; the ARGUMENTS variable is the user's whole message; a line that
starts with an exclamation mark and a backtick is a command the host runs at load time —
if it did not run, run that command by hand as the first action.

## Phase 0 — orient

!`python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py"`

If the block above is empty or shows an error, run that exact command by
hand before anything else — every mode below depends on its JSON. If
`python3` itself is missing, say so, name the one-line install for the host
(`winget install Python.Python.3.12` on Windows, `xcode-select --install` on
macOS, the distribution's package on Linux), and continue: every check a
script performs is also written as a rule in the mode files and the
framework, so it can be applied by hand for this run. Never substitute a
second implementation of a script.

The block above deliberately carries no part of the user's message: a message
with a quote in it would break a shell line, and user text is never composed
into a command. For the deterministic mode hint, write the message to a
scratch file with the Write tool, then run
`python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py" --input-file <that file>`
and read `suggestedMode`, `signals[]` and `ambiguous`. Treat them as a hint:
the Modes section below decides, and says so.

State, in one line, what Phase 0 resolved: mode (and that it was inferred,
if it was), framework source, docs home and its source, whether a map is
configured, and whether the project is adopted.

Configured commands never run as composed shell strings. Every `map.find`,
`map.row`, `map.nextId`, `map.checks` and verify command runs through
`python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py"`, which passes the user's
text as one argument. When a map is configured, print
`adapter.py show` once per session so the person sees exactly which
repository-supplied commands this skill will run before any of them runs.

`adopted: false` → offer `adopt` once per session, **(Recommended)**, with
one reason: every agent and person in the repo gets routed here instead of
writing a design, plan or spec doc by hand. Continue with the requested mode
whether or not they take it.

## Modes

The user types `/promise` and says what they want, in plain words. A leading
mode word is a shortcut, never a requirement — people will not remember
eight mode names and must not have to. Read the input and Phase 0's
findings, name the mode inferred in one line ("Reading this as
**reconcile** — you named a PR"), and proceed. Never answer "use
`/promise <mode>`", never refuse for syntax, and ask only when two modes are
genuinely plausible — then as one question with a **(Recommended)** option
first, one reason, and a completeness score per option.

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

Inference uses Phase 0 too: an input naming or matching the title of a doc
in `existingDocs` leans `revise` (with a change) or `review` (with a
critique verb); an input matching `map.rowIdPattern` leans `intake` or
`reconcile`; an input naming a test file or a commit leans `reconcile`. A
recognised first word (`new`, `revise`, `review`, `merge`, `arm`, `intake`,
`reconcile`, `adopt`) wins outright and skips inference.

Read only the detected mode file, plus the references its own header
names. Never load all eight. Where the header names framework sections
(`outcome-framework.md § The contract · § Lifecycle`), read only those:
`python3 "${CLAUDE_SKILL_DIR}/scripts/framework_section.py" "The contract" "Lifecycle"`
prints them from the resolved framework; `--list` shows every section.

## Rules that hold in every mode

- Every decision put to the user is one option marked **(Recommended)**
  first, with one concrete reason and a 1–10 completeness score per option —
  never a silent pick.
- The user's edit enters the doc, not the candidate it started from.
- Verify before believing: a current-state claim carries `file:line` read
  this run, not remembered from an earlier one.
- `agreed` and `shipped` are typed by a human, never by this skill. `building` is the
  one exception: `arm` writes it, and only after the human has seen the red gate
  commit and said yes — the commit is the human act the status records.
- Every mode that writes a doc closes out by pasting §0 inline, verbatim; every
  mode states its own close-out and says what it could not check.
- Never require syntax. A mode word is a shortcut; the input decides.
  `/promise fix the doc` gets `revise`, not a usage message.

Read `references/anti-rationalizations.md` before any mode that writes — new,
revise, merge, arm, intake, reconcile. It is required reading there, not
optional background.
