# A session, annotated

*Illustrative, not a recording.* This is what one `/promise` run looks like in
a project that has no config, no capability map and no `CLAUDE.md` section: the
lines the scripts print are real (they were produced by this repository's
scripts), and the model's lines are what `SKILL.md` and `modes/new.md` instruct,
in the shape they instruct it. A live session says the same things in its own
words. Lines the human types are marked `you:`; lines the model prints are
marked `model:`; script output is in fenced blocks.

## The request

```
you: /promise design a way for a member to mute a channel
```

## Phase 0 — orient

The load-time line in `SKILL.md` runs `scripts/orient.py` before the model
reads anything else. The model reads its JSON and states one line:

```
model: Phase 0: mode `new`, inferred; framework: bundled; docs home: none
       detected (no config, no docs folder); map: not configured (mapUsable
       false); project not adopted.
```

Every clause but the mode comes from a field in the JSON — `frameworkSource`,
`docsHome`/`docsHomeSource`, `mapUsable`, `adopted`; the mode is the model's
inference (next section), with `suggestedMode` as a hint only when the message
was passed through `--input-file`. A project with a config would show
`docs home: docs/designs (config)` here instead.

## Mode inference

No leading mode word was typed, so the model names the mode it inferred, and
why, in one line:

```
model: Reading this as **new** — "design a way to…" names a capability, and no
       existing doc matches it.
```

## The adopt offer

`adopted` is false, so the offer is made once this session, with one reason,
and the requested mode continues whether or not it is taken:

```
model: This project is not set up for /promise. (Recommended) run `/promise
       adopt` first — it writes `.claude/promise.config.json` and a short
       CLAUDE.md section so every agent and person here is routed to
       /promise instead of writing a design doc by hand. Or continue without;
       I will ask where outcome docs should live.
you:   continue without
```

## One interview turn

The human half is asked for in one turn — five prompts, six lines back is
enough. Nothing is drafted ahead of the answer.

```
model: Five things, in your own words:
       1. What is true after this ships?
       2. Why do we need it?
       3. What must always, or never, be true? (one line each — I will echo
          them back for confirmation before they enter the doc)
       4. How will we know it worked?
       5. Walk me through one concrete example.
       And who owns the doc? (Recommended) Priya, from `git config user.name`.
you:   1. A member can mute a channel so it stops notifying them.
       2. People leave busy channels entirely rather than muting them, and
          lose search and history.
       3. A muted channel never sends a push or a badge count until it is
          unmuted. Muting is per member; it never changes what other members
          see.
       4. Ana mutes a busy channel and gets zero notifications from it for a
          day, then unmutes and notifications resume.
       5. Ana is in #general, which is noisy. She mutes it, sends herself a
          test message from another account: no push, no badge. She unmutes;
          the next message notifies her normally.
       Owner Priya is right.
model: Two rules, echoed back verbatim — confirm each, or edit it:
       - A muted channel never sends a push or a badge count until it is unmuted.
       - Muting is per member; it never changes what other members see.
you:   both, as written
model: docsHome is null. Where should outcome docs live? (Recommended)
       `docs/designs` — the first folder detection looks for, so a later
       `adopt` pins the same place. I will create it only on your yes.
you:   docs/designs, yes
```

Rules are never offered as a menu of paraphrases: the two lines above enter §0
exactly as confirmed, and §0 is protected from that moment. The folder is
created only because the human said so.

## The render command

```
python3 "${CLAUDE_SKILL_DIR}/scripts/render_outcome.py" --title "Channel muting" --owner "Priya" --docs-home docs/designs --create-docs-home
```

```
wrote /work/app/docs/designs/channel-muting.md
```

The script prints the absolute path it wrote. The template is instantiated with every interview placeholder left in place;
the model then fills §0 from the confirmed lines, extends the seed example into
§3, and derives §4–§7. The finished doc is
[`channel-muting.md`](channel-muting.md), beside this file.

## One lint finding and its fix

Before close-out the model runs the lint on the doc. Here one §6 cell was left
as the template's placeholder:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" docs/designs/channel-muting.md
```

```
docs/designs/channel-muting.md:81: PLACEHOLDER placeholder '<then>' found in a §6 data cell
```

```
model: AT-3's Then is still the template placeholder. Filling it from the
       second worked example: "Ben is still notified normally", altitude
       perception — it is what Ben receives, not a stored fact.
```

The lint runs again and prints nothing (exit 0). Every finding is fixed or
argued for by name before the close-out; the lint checks shape only, and
`modes/new.md` lists what it cannot see.

## The pasted §0

The close-out deliverable is §0, inline and verbatim — the reviewer reacts to
it in the conversation, not to a file path:

```markdown
## 0. TLDR
*(author: Priya, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member can mute a channel so it stops notifying them.
**Rules:**
- A muted channel never sends a push or a badge count until it is unmuted.  → AT-1, AT-2
- Muting is per member; it never changes what other members see.  → AT-3
**How we'll know:** Ana mutes a busy channel and gets zero notifications from it
for a day, then unmutes and notifications resume.
**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Confirmed there is no existing mute primitive to reuse.
```

```
model: docs/designs/channel-muting.md at `draft`. 1 agent note, 0 BLOCKING
       questions, no rule tagged UNTESTED, nothing proposed for deletion.
       Not checked this run: no map is configured, so nothing was filed and
       bridge_validate.py did not run; no test command is configured, so
       nothing was verified. Moving to `agreed` is yours to do.
```

## What happens next

If the human edits `Status:` to `agreed`, `/promise arm docs/designs/channel-muting.md`
branches, writes the three §6 rows as failing tests, commits only those files,
and — after the human has seen the red output and said yes — writes
`Status: building`. With a capability map configured it also files the rows;
[`minimap/`](minimap/README.md) is a project small enough to watch that
happen.
