#!/usr/bin/env python3
"""The one reader of a starter capability map (map.json beside this file).

    python3 capability_find.py "<query>"      ranked matching rows, as a JSON array
    python3 capability_find.py --row <id>     one row, as a JSON object
    python3 capability_find.py --next-id      the id the next new row would take
    python3 capability_find.py --check        validate map.json's shape and each row's doc citation; exit 1 on a defect

This is what a project supplies behind `map.find`, `map.row`, `map.nextId`
and `map.checks` in its promise config. The promise skill ships this file as
`templates/starter-map/capability_find.py`, and `scripts/start_map.py` copies
it into a project; after that it is the project's own file. The skill only
calls it, with the query or the row id appended as exactly one argv
element. Python 3 stdlib only. `examples/minimap/` runs the same file.

Exit codes: 0 on success (a query with no hits still prints `[]` and exits
0); 2 on an unknown row id, a malformed id, or a usage error; 1 when
--check finds a defect. Every message that is not a result goes to stderr.

--check reads one thing besides the map: for every row whose `doc` names a
file, that doc must carry a §6 line
citing the row's id in its `Row` cell — the map-to-doc direction of the
recipe's lockstep rule, which `bridge_validate.py` (doc-to-map) does not
read. An optional `parent` must be a row id. A row's `doc` is resolved
against the map's optional top-level `docRoot` (a path relative to the map's
own directory, default "."), so a map kept in a subfolder can cite docs by
their project-relative path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAP = os.path.join(HERE, "map.json")

ROW_ID_RE = re.compile(r"^CAP-(\d+)$")
VERDICTS = ("not-built", "under-proven", "proven")
ALTITUDES = ("data", "response", "perception", "judgement", "sibling")
EVIDENCE_ARRAYS = ("tests", "e2eTests", "evalTests", "siblingTests")
TOKEN_RE = re.compile(r"[a-z0-9#]+")


def load_map(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def row_text(row: Dict[str, Any]) -> str:
    parts = [row.get("id", ""), row.get("story", "")]
    for scenario in row.get("scenarios", []):
        parts.extend(str(scenario.get(k, "")) for k in ("given", "when", "then"))
    return " ".join(parts).lower()


def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def find(rows: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Rows scored by how many distinct query tokens appear in the row's
    text (id, story, scenario cells), best first; equal scores are ordered
    by how often those tokens occur, then by map order. A row with no
    overlap at all is not returned."""
    wanted = sorted(set(tokens(query)))
    ranked = []
    for position, row in enumerate(rows):
        text = row_text(row)
        score = sum(1 for t in wanted if t in text)
        occurrences = sum(text.count(t) for t in wanted)
        if score:
            ranked.append((-score, -occurrences, position, row))
    ranked.sort(key=lambda item: item[:3])
    return [dict(row, score=-neg) for neg, _occ, _position, row in ranked]


def next_id(rows: List[Dict[str, Any]]) -> str:
    highest = 0
    for row in rows:
        m = ROW_ID_RE.match(str(row.get("id", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"CAP-{highest + 1}"


ROW_CELL_RE_TEMPLATE = r"^\| AT-\d+ \|.*\| {id} \|$"


def doc_cites_row(doc_path: str, row_id: str) -> bool:
    """True when the doc holds a §6 line whose last cell is exactly this
    row id — a line of the shape `| AT-n | … | <id> |`."""
    pattern = re.compile(ROW_CELL_RE_TEMPLATE.format(id=re.escape(row_id)))
    with open(doc_path, encoding="utf-8-sig") as fh:
        return any(pattern.match(line.rstrip("\r\n")) for line in fh)


def check(rows: Any, base_dir: str = HERE) -> List[str]:
    """Every defect in the map's shape, as one line each; empty when clean.

    ``base_dir`` is the directory a row's ``doc`` is resolved against — the
    map's own directory joined with its ``docRoot`` — and the doc must cite
    the row in a §6 ``Row`` cell.
    """
    problems: List[str] = []
    if not isinstance(rows, list):
        return ["rows is not a list"]
    seen = set()
    for i, row in enumerate(rows):
        label = f"rows[{i}]"
        if not isinstance(row, dict):
            problems.append(f"{label}: not an object")
            continue
        rid = row.get("id")
        if not isinstance(rid, str) or not ROW_ID_RE.match(rid):
            problems.append(f"{label}: id {rid!r} does not match ^CAP-\\d+$")
        elif rid in seen:
            problems.append(f"{label}: duplicate id {rid}")
        else:
            seen.add(rid)
            label = rid
        if not isinstance(row.get("story"), str) or not row["story"].strip():
            problems.append(f"{label}: story is missing or empty")
        scenarios = row.get("scenarios")
        if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 5:
            problems.append(f"{label}: scenarios must be a list of 1-5 entries")
        else:
            for j, scenario in enumerate(scenarios):
                if not isinstance(scenario, dict):
                    problems.append(f"{label}: scenarios[{j}] is not an object")
                    continue
                for key in ("given", "when", "then"):
                    if not isinstance(scenario.get(key), str) or not scenario[key].strip():
                        problems.append(f"{label}: scenarios[{j}].{key} is missing or empty")
                if scenario.get("altitude") not in ALTITUDES:
                    problems.append(f"{label}: scenarios[{j}].altitude {scenario.get('altitude')!r} is not one of {ALTITUDES}")
        for key in EVIDENCE_ARRAYS:
            value = row.get(key)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                problems.append(f"{label}: {key} must be an array of strings")
        if row.get("verdict") not in VERDICTS:
            problems.append(f"{label}: verdict {row.get('verdict')!r} is not one of {VERDICTS}")
        elif row["verdict"] == "proven" and not any(row.get(key) for key in EVIDENCE_ARRAYS):
            problems.append(f"{label}: verdict is proven with no citation in any evidence array")
        parent = row.get("parent")
        if parent is not None and (not isinstance(parent, str) or not ROW_ID_RE.match(parent)):
            problems.append(f"{label}: parent {parent!r} is not a row id")
        doc = row.get("doc")
        if doc is not None and not isinstance(doc, str):
            problems.append(f"{label}: doc {doc!r} is neither a path nor null")
        elif isinstance(doc, str) and isinstance(rid, str) and ROW_ID_RE.match(rid):
            doc_path = os.path.join(base_dir, doc)
            try:
                cited = doc_cites_row(doc_path, rid)
            except (OSError, UnicodeDecodeError) as exc:
                problems.append(f"{label}: doc {doc} cannot be read: {exc}")
            else:
                if not cited:
                    problems.append(f"{label}: doc {doc} has no §6 line citing it")
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capability_find.py", description=__doc__.split("\n\n")[1])
    parser.add_argument("--map", default=DEFAULT_MAP, help="path to map.json (default: beside this script)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--row", metavar="ID", help="print one row by id; exit 2 when there is no such row")
    group.add_argument("--next-id", action="store_true", help="print the id the next new row would take")
    group.add_argument("--check", action="store_true", help="validate map.json; exit 1 on any defect")
    parser.add_argument("query", nargs="?", help="search text; ranked matching rows are printed as a JSON array")
    return parser


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        data = load_map(args.map)
    except (OSError, ValueError) as exc:
        print(f"capability_find.py: cannot read map {args.map}: {exc}", file=sys.stderr)
        return 2
    rows = data.get("rows", []) if isinstance(data, dict) else []

    if args.check:
        doc_root = data.get("docRoot", ".") if isinstance(data, dict) else "."
        if not isinstance(doc_root, str) or os.path.isabs(doc_root):
            print(f"capability_find.py: docRoot {doc_root!r} is not a relative path", file=sys.stderr)
            print(f"capability-check: {len(rows)} rows, 1 problems")
            return 1
        problems = check(rows, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(args.map)), doc_root)))
        for line in problems:
            print(f"capability_find.py: {line}", file=sys.stderr)
        print(f"capability-check: {len(rows)} rows, {len(problems)} problems")
        return 1 if problems else 0

    if args.next_id:
        print(next_id(rows))
        return 0

    if args.row is not None:
        if not ROW_ID_RE.match(args.row):
            print(f"capability_find.py: {args.row!r} is not a row id (expected CAP-<n>)", file=sys.stderr)
            return 2
        for row in rows:
            if row.get("id") == args.row:
                print(json.dumps(row, indent=2, ensure_ascii=False))
                return 0
        print(f"capability_find.py: no such row: {args.row}", file=sys.stderr)
        return 2

    if args.query is None:
        parser.print_usage(sys.stderr)
        print("capability_find.py: a query, --row <id>, --next-id or --check is required", file=sys.stderr)
        return 2
    print(json.dumps(find(rows, args.query), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
