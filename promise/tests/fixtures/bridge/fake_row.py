#!/usr/bin/env python3
"""Stand-in for a project's `map.row` command, for bridge_validate.py's tests.

    python3 fake_row.py <id>

Prints its own argv (excluding the script path) as one ``repr(...)`` line —
so a test can confirm a row id, however it is spelled, arrived as exactly
one argv element rather than being parsed or expanded by a shell — then,
for a known id, the id's canned scenario text; an unknown id exits 2 with
nothing else on stdout, matching how a real row-lookup command behaves when
a row does not exist.

R1's text contains, verbatim, both AT-1's and AT-2's `Then` text from
agreed_bridged.md, so neither drifts. R2's text is deliberately reworded
against AT-3's `Then` in that same fixture, so the drift check has
something real to catch.
"""

from __future__ import annotations

import sys

SCENARIOS = {
    "R1": (
        "Row R1 -- a member mutes a busy channel: muting it means "
        "she gets no push or badge from it, and unmuting it means "
        "notifications resume immediately."
    ),
    "R2": (
        "Row R2 -- a mute is per member: a second, unmuted member "
        "keeps getting a push for every new message in the channel."
    ),
}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(repr(args))
    if len(args) != 1 or args[0] not in SCENARIOS:
        print(f"fake_row.py: no such row: {args!r}", file=sys.stderr)
        return 2
    print(SCENARIOS[args[0]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
