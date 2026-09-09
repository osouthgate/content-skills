#!/usr/bin/env python3
"""Check a bridged outcome doc's §6 rows against the project's capability map.

    python3 bridge_validate.py doc.md
    python3 bridge_validate.py doc.md --cwd path/to/project --json
    python3 bridge_validate.py doc.md --strict

Once a doc is bridged (architecture.md § The bridge), §6's `Row` column is a
citation into the project's capability map, not a second copy of the
scenarios. This script is the staleness check: it confirms every acceptance
row that must be mapped has a `Row` id, that each id matches the project's
`map.rowIdPattern`, that the doc records a snapshot line, and that each
row's `Then` text can still be found in the map's own current text for that
row — read through `adapter.py`, never a shell string composed from
configuration plus doc content, so a row id (however it is spelled) always
travels as exactly one argv element.

A doc still at `draft` or `superseded-by` has not been bridged at all:
`bridged: false` is reported and no other check runs. A project with no
`map` configured has nothing to validate against.

Exit 0 when there are no error-severity findings; 1 when there are (or, under
--strict, any warning); 2 on a usage error. Human output is one line per
finding: ``<path>:<line>: <RULE_ID> <message>``, then a summary line
``bridge: <n> rows, <m> mapped, <k> drifted``. ``--json`` prints one JSON
object; stdout is always exactly one parseable value under ``--json``.
Deterministic; every file is read tolerating a BOM and CRLF; never a
traceback on plausible input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_outcome  # noqa: E402  (sibling-script import; see path insert above)
import orient  # noqa: E402
import outcome_rows  # noqa: E402

ADAPTER_PATH = os.path.join(_SCRIPTS_DIR, "adapter.py")

BRIDGE_REQUIRED_STATUSES = ("agreed", "building", "shipped")
NOT_BRIDGED_STATUSES = ("draft", "superseded-by")

SNAPSHOT_LINE_RE = re.compile(r"^[`*]*\s*snapshot taken at\b", re.IGNORECASE)
LEADING_THEN_AND_RE = re.compile(r"^(then|and)\b[\s:,-]*", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")


def finding(rule: str, line: Optional[int], message: str, severity: str) -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


def section6_heading_line(lines: List[str]) -> Optional[int]:
    """1-based line number of the ``## 6.`` heading, or None when there is none."""
    bounds = lint_outcome.section_bounds(lines, 6)
    return bounds[0] + 1 if bounds is not None else None


def has_snapshot_line(lines: List[str]) -> bool:
    """True when some line inside §6 starts (a leading backtick/asterisk
    tolerated) with "Snapshot taken at", case-insensitive."""
    bounds = lint_outcome.section_bounds(lines, 6)
    if bounds is None:
        return False
    start, end = bounds
    return any(SNAPSHOT_LINE_RE.match(lines[i].strip()) for i in range(start, end))


def normalize(text: str) -> str:
    """Lower-case; drop a leading ``then``/``and`` keyword; strip punctuation
    to spaces; collapse whitespace. Used to compare a §6 ``Then`` against the
    map's own current scenario text without either side's exact wording of
    connectives or punctuation defeating a real match."""
    lowered = (text or "").strip().lower()
    lowered = LEADING_THEN_AND_RE.sub("", lowered, count=1)
    no_punct = NON_WORD_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", no_punct).strip()


def lookup_row(cwd: str, row_id: str) -> Tuple[bool, str]:
    """Run ``adapter.py --cwd cwd --json row row_id`` as a real subprocess.

    Returns ``(found, scenario_text)``. ``found`` is False whenever the
    adapter subprocess exits non-zero, prints nothing parseable, reports a
    non-zero child exit, or the child's own stdout is empty — every one of
    these means there is nothing to compare a ``Then`` against. This never
    composes a shell string: ``row_id`` reaches ``adapter.py`` as exactly
    one argv element, whatever characters it contains.
    """
    try:
        proc = subprocess.run(
            [sys.executable, ADAPTER_PATH, "--cwd", cwd, "--json", "row", row_id],
            shell=False,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False, ""
    stdout = proc.stdout or ""
    if proc.returncode != 0 or not stdout.strip():
        return False, ""
    try:
        payload = json.loads(stdout)
    except ValueError:
        return False, ""
    if not isinstance(payload, dict) or payload.get("exit") != 0:
        return False, ""
    child_stdout = payload.get("stdout")
    if not isinstance(child_stdout, str) or not child_stdout.strip():
        return False, ""
    return True, child_stdout


def finalize(
    doc_path: str,
    status: Optional[str],
    bridged: bool,
    map_configured: bool,
    rows_out: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    strict: bool,
    mapped: int = 0,
    drifted: int = 0,
) -> Dict[str, Any]:
    if strict:
        for f in findings:
            if f["severity"] == "warn":
                f["severity"] = "error"
    findings = sorted(findings, key=lambda f: (f["line"] if f["line"] is not None else 0, f["rule"]))
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": doc_path,
        "status": status,
        "bridged": bridged,
        "mapConfigured": map_configured,
        "rows": rows_out,
        "findings": findings,
        "stats": {
            "rows": len(rows_out),
            "mapped": mapped,
            "drifted": drifted,
            "errors": errors,
            "warnings": warnings,
        },
    }


def validate(doc_path: str, cwd: str, strict: bool) -> Dict[str, Any]:
    orientation = orient.build_orientation(None, cwd)
    map_value = orientation.get("map")
    map_configured = isinstance(map_value, dict)

    try:
        text = lint_outcome.read_text_tolerant(doc_path)
    except (OSError, UnicodeDecodeError) as exc:
        findings = [finding("UNREADABLE", None, f"cannot read {doc_path}: {exc}", "error")]
        return finalize(doc_path, None, False, map_configured, [], findings, strict)

    lines = text.splitlines()
    status = lint_outcome.get_status(lines)
    six_line = section6_heading_line(lines)

    if not map_configured:
        findings = [
            finding(
                "MAP_NOT_CONFIGURED",
                six_line,
                "no map is configured for this project — there is nothing to validate the bridge against",
                "error",
            )
        ]
        return finalize(doc_path, status, False, False, [], findings, strict)

    if status in NOT_BRIDGED_STATUSES:
        findings = [
            finding(
                "NOT_BRIDGED",
                six_line,
                f"Status: {status} — the bridge has not happened yet",
                "info",
            )
        ]
        return finalize(doc_path, status, False, True, [], findings, strict)

    data = outcome_rows.extract(doc_path)
    line_by_id = {r["id"]: r["line"] for r in lint_outcome.parse_acceptance_rows(lines)}
    row_required = status in BRIDGE_REQUIRED_STATUSES

    row_id_pattern = map_value.get("rowIdPattern")
    pattern_configured = isinstance(row_id_pattern, str) and bool(row_id_pattern)
    compiled_pattern = None
    if pattern_configured:
        try:
            compiled_pattern = re.compile(row_id_pattern)
        except re.error:
            pattern_configured = False

    row_command = map_value.get("row")
    row_command_configured = isinstance(row_command, str) and bool(row_command)

    findings: List[Dict[str, Any]] = []
    if not pattern_configured:
        findings.append(
            finding(
                "NO_ROW_ID_PATTERN",
                six_line,
                "map.rowIdPattern is not configured; ROW_ID_FORMAT is not checked",
                "warn",
            )
        )
    if not row_command_configured:
        findings.append(
            finding(
                "NO_MAP_ROW_COMMAND",
                six_line,
                "map.row is not configured; the drift check against the map is skipped",
                "warn",
            )
        )

    rows_out: List[Dict[str, Any]] = []
    mapped = 0
    drifted = 0
    row_cache: Dict[str, Tuple[bool, str]] = {}

    for r in data["rows"]:
        row_id = r["id"]
        row_value = r["row"]
        line_no = line_by_id.get(row_id)
        entry: Dict[str, Any] = {"id": row_id, "row": row_value, "line": line_no, "found": None, "inSync": None}

        if not row_value:
            if row_required:
                findings.append(
                    finding(
                        "ROW_MISSING",
                        line_no,
                        f"{row_id} has no Row value while Status: is {status}",
                        "error",
                    )
                )
            rows_out.append(entry)
            continue

        mapped += 1

        if pattern_configured and compiled_pattern.fullmatch(row_value) is None:
            findings.append(
                finding(
                    "ROW_ID_FORMAT",
                    line_no,
                    f"{row_id}'s Row value {row_value!r} does not match map.rowIdPattern {row_id_pattern!r}",
                    "error",
                )
            )
            rows_out.append(entry)
            continue

        if not row_command_configured:
            rows_out.append(entry)
            continue

        if row_value not in row_cache:
            row_cache[row_value] = lookup_row(cwd, row_value)
        found, map_text = row_cache[row_value]
        entry["found"] = found

        if not found:
            findings.append(
                finding(
                    "ROW_NOT_FOUND",
                    line_no,
                    f"{row_id}'s row {row_value} was not found by map.row",
                    "error",
                )
            )
            rows_out.append(entry)
            continue

        then_norm = normalize(r["then"])
        in_sync = (not then_norm) or (then_norm in normalize(map_text))
        entry["inSync"] = in_sync
        if not in_sync:
            drifted += 1
            findings.append(
                finding(
                    "THEN_NOT_IN_MAP",
                    line_no,
                    f"{row_id}'s Then no longer appears in {row_value}'s scenario text in the "
                    "map — the map has moved on since the snapshot, or the row was filed differently",
                    "warn",
                )
            )

        rows_out.append(entry)

    if not has_snapshot_line(lines):
        findings.append(
            finding(
                "SNAPSHOT_LINE_MISSING",
                six_line,
                "§6 has no line beginning 'Snapshot taken at' — the bridge is not recorded",
                "error",
            )
        )

    return finalize(doc_path, status, True, True, rows_out, findings, strict, mapped=mapped, drifted=drifted)


def format_human(result: Dict[str, Any]) -> str:
    out = []
    for f in result["findings"]:
        line_part = f["line"] if f["line"] is not None else "?"
        out.append(f"{result['path']}:{line_part}: {f['rule']} {f['message']}")
    stats = result["stats"]
    out.append(f"bridge: {stats['rows']} rows, {stats['mapped']} mapped, {stats['drifted']} drifted")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge_validate.py",
        description=(
            "Check a bridged outcome doc's §6 Row ids, snapshot line and Then text "
            "against the project's capability map."
        ),
    )
    parser.add_argument("doc", help="path to the outcome doc")
    parser.add_argument(
        "--cwd", default=None, help="project root to resolve the config against (default: current directory)"
    )
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of human-readable lines")
    parser.add_argument("--strict", action="store_true", help="promote warn findings to error")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"bridge_validate.py: no such directory: {cwd}", file=sys.stderr)
        return 2
    doc_path = args.doc if os.path.isabs(args.doc) else os.path.join(cwd, args.doc)

    try:
        result = validate(doc_path, cwd, args.strict)
    except Exception as exc:  # pragma: no cover - last-resort guard, never a traceback for the caller
        print(f"bridge_validate.py: internal error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_human(result))

    any_errors = any(f["severity"] == "error" for f in result["findings"])
    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
