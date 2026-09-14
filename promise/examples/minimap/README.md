# minimap — a capability map small enough to watch

The promise plugin ships no capability map and no map tooling. A project that
keeps one supplies three commands (`find`, `row`, `nextId`) and a recipe, and
the plugin calls them. This directory is the smallest such project that works
end to end, so `orient.py`, `adapter.py`, `bridge_validate.py` and `arm` can be
watched doing the bridge instead of read about.

| File | What it is |
|---|---|
| `map.json` | The map: three rows, `CAP-1`..`CAP-3`, each a story, scenarios, four evidence arrays and a verdict. |
| `capability_find.py` | The map's only reader — `find`, `--row`, `--next-id`, `--check` (the map's shape, plus: every row whose `doc` names a file is cited by a §6 line in it). Python 3 stdlib. |
| `promise.config.json` | The config that points the plugin at the two files above. It sits at the fallback location so it is visible; a real project uses `.claude/promise.config.json`. |
| `recipe.md` | How a row is added in lockstep, the routing table, the lane table, the verification block. |
| `docs/designs/channel-muting.md` | [`../channel-muting.md`](../channel-muting.md) after the bridge: `Status: agreed`, a `Row` column citing `CAP-1`/`CAP-2`, and the snapshot line. |

Every command below runs from this directory. `SKILL` is the skill folder:

```
cd promise/examples/minimap
SKILL=../../skills/promise
```

## Watch orient see the map

```
python3 $SKILL/scripts/orient.py | python3 -c "import json,sys; o=json.load(sys.stdin); print(o['mapUsable'], o['docsHome'], [d['path'] for d in o['existingDocs']])"
```

Prints `True docs/designs ['docs/designs/channel-muting.md']`. `mapUsable` is
the one field every mode reads to decide whether a map is configured; it is
true because `recipe`, `find` and `row` are strings and `lanes` is an object of
strings. Delete `lanes` from the config and run it again: `mapUsable` turns
false and `warnings[]` names the missing key.

## Watch adapter.py run the map's commands

`adapter.py` never composes a shell string. It splits each configured command
like a shell would and appends the query or the id as one argv element.

```
python3 $SKILL/scripts/adapter.py show
python3 $SKILL/scripts/adapter.py find "mute a channel"
python3 $SKILL/scripts/adapter.py row CAP-1
python3 $SKILL/scripts/adapter.py next-id
python3 $SKILL/scripts/adapter.py checks
```

`show` prints the four configured map commands (`find`, `row`, `nextId`,
`checks[0]`) and runs nothing — `/promise` shows this and
asks before the first configured command runs in a session. `find` prints the
rows ranked by how many of the query's words they contain, then by how often
(`CAP-1` first, then `CAP-2` and `CAP-3`). `row CAP-1` prints the row as JSON; `row CAP-9` exits 2
because `capability_find.py` has no such row, and `row nope` exits 2 before
anything runs because `nope` fails `rowIdPattern`. `next-id` prints `CAP-4`.
`checks` runs `capability_find.py --check` and exits 0.

A query that carries quotes goes through a file instead of the command line:

```
printf '%s' 'the "quiet hours" mute' > /tmp/query.txt
python3 $SKILL/scripts/adapter.py find --query-file /tmp/query.txt
```

## Watch bridge_validate.py check the bridge

```
python3 $SKILL/scripts/bridge_validate.py docs/designs/channel-muting.md
```

```
bridge: 3 rows, 3 mapped, 0 drifted
```

Every `Row` cell matches `rowIdPattern`, every id is found by `map.row`, each
row's `Then` still appears in the map's text for that row, and the snapshot line
is present. Three edits show the three things it catches:

- Change `"then": "Ben is still notified normally"` in `map.json` to
  `"then": "Ben keeps getting pushes"` and run it again: `THEN_NOT_IN_MAP` on
  AT-3's line, `1 drifted`. The map moved and the doc's snapshot did not — the
  map is the suspect, never the doc.
- Blank AT-2's `Row` cell in the doc: `ROW_MISSING`, an error, because the doc
  is `agreed`.
- Delete the `Snapshot taken at` line: `SNAPSHOT_LINE_MISSING`, an error.

Revert the edits with `git checkout -- .` when done.

## Watch arm do the bridge itself

`docs/designs/channel-muting.md` is the state *after* `arm`'s bridge step. To
watch the step happen, put the doc back to the state before it and run the
mode in a copy of this directory that is its own git repository:

```
cp -r . /tmp/minimap && cp ../channel-muting.md /tmp/minimap/docs/designs/channel-muting.md && cd /tmp/minimap
sed -i 's/^Status: draft$/Status: agreed/' docs/designs/channel-muting.md   # the draft, no Row column, marked agreed by hand
python3 - <<'EOF'
import json; p="map.json"; m=json.load(open(p))
m["rows"]=[r for r in m["rows"] if r["id"]=="CAP-3"]      # keep the pre-existing row only
json.dump(m, open(p,"w"), indent=2); open(p,"a").write("\n")
EOF
git init -q && git add -A && git commit -qm "minimap before arm"
```

Then, in Claude Code with this directory as the project:

```
/promise arm docs/designs/channel-muting.md
```

`arm` shows `adapter.py show` and asks before running anything configured, cuts
`feat/channel-muting`, reads `recipe.md`, proposes grouping the three AT rows by
the §0 rule each is tagged from (AT-1 and AT-2 under rule 1, AT-3 under rule 2),
and on your yes files two not-built rows — `next-id` says `CAP-4`, then `CAP-5` —
writes the ids into the `Row` column, adds the snapshot line, runs
`bridge_validate.py`, writes the three rows as failing tests and commits only
those files, and asks before writing `Status: building`. `git log --oneline -2`
afterwards shows the two commits; `git show --stat HEAD` shows the lockstep the
recipe describes: `map.json` and the doc in one commit — the doc's §6 `Row`
column and snapshot line, plus the `Red gate:` and `Status:` header lines arm
writes — and nothing else.

## What the test locks

`tests/test_examples.py` lints both docs, checks that the bridged doc is the
draft plus exactly the bridge's edits, runs `orient.py` here expecting
`mapUsable: true`, runs each `adapter.py` operation, and runs
`bridge_validate.py` on the bridged doc expecting zero errors and zero drift —
so this example cannot rot without the suite saying so.
