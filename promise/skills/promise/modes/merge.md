Read before this: references/slates.md · references/anti-rationalizations.md · outcome-framework.md § The contract · § Lifecycle
Read at the fold step: the project's `map.recipe` and `map.index`, if a map is configured and any doc to fold is past `draft`.
Phase 0 line: mode `merge` (say if inferred), framework source, docs home and its source, `plansFolder` (or "none"), whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: the survivor doc under `docsHome`; `git rm`s the folded docs and commits both together once the user says yes; `Status: superseded-by <survivor>` on a folded doc the user chose to keep instead; with a map, the folded docs' rows re-pointed or retired per the recipe.

# Merge — consolidating overlapping docs

The one-doc-per-capability rule, in action — framework § The contract: "a
sibling doc covering overlapping surface is a bug: merge and delete, don't
cross-reference." Input is the docs named by the user, or the overlap `new`'s
capability hunt already found.

## Build the overlap table

Read every named doc in full. Build one screen: which §0 rules, which §6
rows, and which §5 claims overlap or contradict, across the docs. A rule or
row with no counterpart in another doc is not overlap — leave it alone; a
doc that only shares a topic, not a promise, is a different capability, not
a merge candidate.

## Propose the survivor

For the survivor, and for every other doc's disposition, put one option per
doc to the user, **(Recommended)** first, each with one concrete reason:

- **Fold in and delete** — the doc's live content has no home elsewhere
  once it's gone; migrate it into the survivor, then `git rm` the file.
- **Fold in and keep the file** — the same migration, but the user wants the
  file to stay (inbound links, history). The kept doc gets
  `Status: superseded-by <survivor path>` — the one case any mode writes
  that status — and nothing else in it changes again.
- **Delete** — fully superseded, nothing left to migrate.
- **Keep** — it is a different capability wearing an overlapping name; not
  a merge candidate at all.

`plansFolder` is not null and a plan doc there touches this surface →
migrate its still-live content into the survivor's §7, then propose
deleting the plan file in the same option table, and delete it in the same
commit.

**Wait for the user's yes before deleting anything.**

## Write the survivor

- §0 rules from a folded doc enter the survivor only by verbatim
  confirmation, the same as any rule — references/slates.md's "rules are
  never slated" applies here too; a rule doesn't lose that protection for
  arriving via merge.
- Fill the `Supersedes:` header line with every doc deleted or marked
  `superseded-by` in this pass. This is the only mode that fills it.
- §8 Decisions records the disposition of each, one row per doc:
  "Superseded and DELETED: `<doc>` — folded into §`<n>`" (or "superseded,
  file kept", "deleted outright", or "kept — different capability").
- Set `Status: draft` on the survivor, even where a folded doc was `agreed`
  or later — the merge is a new draft until the human re-ratifies it.

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and fix
every finding, or say why one stands.

## Folding a bridged doc (map configured)

A folded doc whose §6 carries `Row` ids has filed rows in the map, and those
rows are the live promise — the doc's §6 is a snapshot nobody edits
(framework § Lifecycle). Read `map.recipe` from the file, list the rows
(`adapter.py row <id>` for each `Row` cell; gated once per session — SKILL.md
Phase 0 asks before the first configured command runs), and put each row's
disposition to the user, **(Recommended)** first, with one reason:

- **Re-point** — the survivor carries the row's scenarios: write the existing
  row id into the survivor's §6 `Row` cell on each migrated AT line, so a later
  `arm` files nothing new for it.
- **Retire** — per the recipe's own mechanics, with a dated finding naming the
  survivor; never hand-delete a row file.

The survivor stays `draft`, and `bridge_validate.py` reports `NOT_BRIDGED` on
it until a human re-ratifies it and `arm` runs again. A row that names a
deleted doc and was neither re-pointed nor retired is a bug; list every row
re-pointed or retired in the close-out.

No map configured, or every folded doc is `draft` → nothing in this section
applies; §6 is the only home.

## Folding a `building` doc

A `building` doc carries `Red gate: <sha> <YYYY-MM-DD>` in its header and a
`feat/<slug>` branch whose first commit is its red tests. Do not copy the
`Red gate:` line into the survivor — the survivor is `draft`, and a later
`arm` writes its own line. Record it in the survivor's §8 instead: "Red gate
`<sha>` retired — tests at `<paths>` on `feat/<slug>` no longer gate this
capability." Name the branch in the close-out and put its disposition to the
user (keep for cherry-pick, or delete) — never delete it without a yes — and
say that `arm` refuses the survivor's slug while a branch of that name exists.

## Delete and commit

On the user's yes: `git rm <path>` for each folded doc and each `plansFolder`
file the yes named (an untracked file is `rm`'d and named as such in the
close-out). Show `git status --short`, then commit the survivor, every
deletion, every `superseded-by` edit and — with a map — the recipe's row files
together, by explicit path: `docs(<scope>): merge <folded…> into <survivor>`,
so no commit exists in which `Supersedes:` names a file still present and
unmarked in the tree. Refuse and say why if HEAD is detached, or staged
changes exist that are not the survivor and the named deletions; name the branch
the commit lands on, and if it is the project's main branch say so and ask before
committing there. Never `git rm` a file the user did not name in the yes.

## Close out

Paste §0 inline in chat, verbatim. Report: the survivor's path, every doc
deleted, kept as `superseded-by` or left alone, and its disposition; every
map row re-pointed or retired; the red-test branch and its disposition; the
commit sha; any migration you couldn't verify; and what you could not check.
