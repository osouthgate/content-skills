Read before this: references/slates.md · references/anti-rationalizations.md · outcome-framework.md § The contract · § Lifecycle
Phase 0 line: mode `merge` (say if inferred), framework source, docs home and its source, `plansFolder` (or "none"), whether a map is configured, and whether the project is adopted.
Writes: the survivor doc under `docsHome`; deletes the folded docs once the user says yes.

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
doc to the user, **(Recommended)** first, each with one concrete reason and
a 1–10 completeness score:

- **Fold in** — the doc's live content has no home elsewhere once it's
  gone; migrate it into the survivor.
- **Delete** — fully superseded, nothing left to migrate.
- **Keep** — it is a different capability wearing an overlapping name; not
  a merge candidate at all.

`plansFolder` is not null and a plan doc there touches this surface →
migrate its still-live content into the survivor's §7, then propose
deleting the plan file the same way.

**Wait for the user's yes before deleting anything.**

## Write the survivor

- §0 rules from a folded doc enter the survivor only by verbatim
  confirmation, the same as any rule — references/slates.md's "rules are
  never slated" applies here too; a rule doesn't lose that protection for
  arriving via merge.
- Fill the `Supersedes:` header line with every doc deleted in this pass.
- §8 Decisions records the disposition of each, one row per doc:
  "Superseded and DELETED: `<doc>` — folded into §`<n>`" (or "deleted
  outright", or "kept — different capability").
- Set `Status: draft` on the survivor, even where a folded doc was `agreed`
  or later — the merge is a new draft until the human re-ratifies it.

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` and fix
every finding, or say why one stands.

## Close out

Paste §0 inline in chat, verbatim. Report: the survivor's path, every doc
deleted and its disposition, any migration you couldn't verify, and what
you could not check.
