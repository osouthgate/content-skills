#!/usr/bin/env python3
"""Shape checks for one outcome doc, or every outcome doc in a directory.

    python3 lint_outcome.py doc.md
    python3 lint_outcome.py docs/designs --json
    python3 lint_outcome.py doc.md --strict

Checks the rules in references/architecture.md SS9 against the Outcome
Framework template shape (SS0 TLDR budget and fields, rule format and
tags, headings, the acceptance table, the Why lines, placeholders).
Exit 0 when there are no findings, 1 when there are findings (errors,
or warnings too under --strict), 2 on a usage error. Human output is
one line per finding: ``<path>:<line>: <RULE_ID> <message>``. ``--json``
prints one JSON object for a single file, or a JSON array of one such
object per file when a directory was given. Deterministic; no network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

TLDR_HEADING = "## 0. TLDR"
AGENT_NOTES_PREFIX = "Agent notes"

SECTION_NAMES = {
    0: "TLDR",
    1: "Problem",
    2: "Outcome",
    3: "Worked examples",
    4: "Invariants",
    5: "Mechanism",
    6: "Acceptance",
    7: "Build phases",
    8: "Decisions",
    9: "Open questions",
    10: "Out of scope",
}

CONTENTS_ANCHORS = [
    "#0-tldr", "#1-problem", "#2-outcome", "#3-worked-examples", "#4-invariants",
    "#5-mechanism", "#6-acceptance", "#7-build-phases", "#8-decisions",
    "#9-open-questions", "#10-out-of-scope",
]

VALID_STATUS_TOKENS = {"draft", "agreed", "building", "shipped", "superseded-by"}

WHY_SECTIONS = (4, 5, 6, 7)

PLACEHOLDER_TERMS = ("tbd", "todo", "<fill", "decide later")

HEADING_RE = re.compile(r"^## (\d+)\.\s*(.*?)\s*$")
ANY_HEADING_RE = re.compile(r"^## \d+\.")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
BULLET_START_RE = re.compile(r"^-\s+(.*)$")
NUMBERED_START_RE = re.compile(r"^(\d+)\.\s+(.*)$")
TAG_RE = re.compile(r"→\s*(UNTESTED|AT-\d+(?:\s*,\s*AT-\d+)*)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
AT_ID_RE = re.compile(r"^AT-\d+$")
WHY_LINE_RE = re.compile(r"^Why\s*[-—]\s*what breaks without it:")
SCENARIOS_RE = re.compile(
    r"\*\*Scenarios:\*\*\s*(\d+)\s*acceptance rows[^,]*,\s*(\d+)\s*worked examples"
)
NOTE_START_RE = re.compile(r"^(\d+)\.\s+")
H3_RE = re.compile(r"^###\s+\S")
BOLD_LED_RE = re.compile(r"^\*\*[^*]+\*\*")


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings."""
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def find_line_index(lines: List[str], predicate, start: int = 0) -> Optional[int]:
    """0-indexed position of the first line (from start) matching predicate, or None."""
    for i in range(start, len(lines)):
        if predicate(lines[i]):
            return i
    return None


def finding(rule: str, line: Optional[int], message: str, severity: str) -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


# ---------------------------------------------------------------------------
# Shared structural lookups (also used by outcome_rows.py)
# ---------------------------------------------------------------------------


def section_bounds(lines: List[str], n: int) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) line range for ``## n. ...`` through the next heading."""
    start = find_line_index(lines, lambda l: HEADING_RE.match(l) and HEADING_RE.match(l).group(1) == str(n))
    if start is None:
        return None
    end = find_line_index(lines, lambda l: ANY_HEADING_RE.match(l), start=start + 1)
    return start, end if end is not None else len(lines)


def tldr_block_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) for SS0: the heading line up to (not incl.) Agent notes / SS1."""
    start = find_line_index(lines, lambda l: l.startswith(TLDR_HEADING))
    if start is None:
        return None
    end = find_line_index(lines, lambda l: l.startswith(AGENT_NOTES_PREFIX), start=start + 1)
    if end is None:
        end = find_line_index(lines, lambda l: l.startswith("## 1."), start=start + 1)
    if end is None:
        end = len(lines)
    return start, end


def get_status(lines: List[str]) -> Optional[str]:
    idx = find_line_index(lines, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return None
    return STATUS_RE.match(lines[idx]).group(1)


def parse_rules_block(lines: List[str]) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
    """Parse the SS0 rules between **Rules:** and **How we'll know:**.

    Returns (records, rules_line_idx, how_we_know_line_idx). Each record:
    ``{"start_line": 1-based, "format": "bullet"|"numbered", "raw_text": str,
    "tags": [...] or None}``. Continuation lines (indented, not starting a
    new ``- `` or ``N.`` item) are joined onto the currently open rule
    before the trailing tag is checked. Returns ([], None, None) when the
    **Rules:** anchor is absent.
    """
    rules_idx = find_line_index(lines, lambda l: "**Rules:**" in l)
    if rules_idx is None:
        return [], None, None
    how_idx = find_line_index(lines, lambda l: "**How we'll know:**" in l, start=rules_idx + 1)
    end = how_idx if how_idx is not None else len(lines)

    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for i in range(rules_idx + 1, end):
        raw_line = lines[i]
        if not raw_line.strip():
            current = None
            continue
        m_bullet = BULLET_START_RE.match(raw_line)
        m_numbered = NUMBERED_START_RE.match(raw_line)
        if m_bullet:
            current = {"start_line": i + 1, "format": "bullet", "parts": [m_bullet.group(1).rstrip()]}
            records.append(current)
        elif m_numbered:
            current = {"start_line": i + 1, "format": "numbered", "parts": [m_numbered.group(2).rstrip()]}
            records.append(current)
        elif current is not None:
            current["parts"].append(raw_line.strip())
        # else: stray text before any rule has started; not part of any rule.

    for record in records:
        record["raw_text"] = " ".join(record.pop("parts")).strip()
        tag_match = TAG_RE.search(record["raw_text"])
        if tag_match:
            tag_text = tag_match.group(1)
            record["tags"] = ["UNTESTED"] if tag_text == "UNTESTED" else [
                t.strip() for t in tag_text.split(",")
            ]
            record["text"] = record["raw_text"][: tag_match.start()].rstrip()
        else:
            record["tags"] = None
            record["text"] = record["raw_text"]
    return records, rules_idx, how_idx


ACCEPTANCE_HEADER_RE = re.compile(r"^(#|id|at)$", re.IGNORECASE)


def split_tables(lines: List[str], start: int, end: int) -> List[List[Tuple[int, List[str]]]]:
    """Every pipe table in [start, end) as its own list of (line_no, cells).

    A table is a run of consecutive pipe rows; any other line ends it. A section may
    hold several tables, and only the acceptance table is subject to row-id rules.
    """
    tables: List[List[Tuple[int, List[str]]]] = []
    current: List[Tuple[int, List[str]]] = []
    for i in range(start, end):
        m = TABLE_ROW_RE.match(lines[i].rstrip("\r\n"))
        if m:
            current.append((i + 1, [c.strip() for c in m.group(1).split("|")]))
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def is_separator(cells: List[str]) -> bool:
    return bool(any(cells)) and all(SEPARATOR_CELL_RE.match(c) for c in cells if c)


def parse_table_data_rows(lines: List[str], start: int, end: int) -> List[Tuple[int, List[str]]]:
    """Data rows of the acceptance tables in [start, end): header and separator skipped.

    An acceptance table is one whose header's first cell is ``#`` (the template's
    shape) or ``ID``/``AT``. Other tables in the section — a classification table,
    a summary — are not acceptance rows and are left alone.
    """
    out: List[Tuple[int, List[str]]] = []
    for table in split_tables(lines, start, end):
        header = table[0][1]
        if not header or not ACCEPTANCE_HEADER_RE.match(header[0]):
            continue
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        out.extend(body)
    return out


def parse_acceptance_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """Well-formed SS6 rows (id, given, when, then, row) keyed on ``AT-\\d+``."""
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    rows = []
    for line_no, cells in parse_table_data_rows(lines, start + 1, end):
        if not cells or not AT_ID_RE.match(cells[0]):
            continue
        given = cells[1] if len(cells) > 1 else ""
        when = cells[2] if len(cells) > 2 else ""
        then = cells[3] if len(cells) > 3 else ""
        row_col = cells[4].strip() if len(cells) > 4 and cells[4].strip() else None
        rows.append(
            {
                "line": line_no,
                "id": cells[0],
                "given": given,
                "when": when,
                "then": then,
                "row": row_col,
            }
        )
    return rows


def parse_signal(lines: List[str]) -> str:
    """The **How we'll know:** text, with wrapped continuation lines joined."""
    idx = find_line_index(lines, lambda l: "**How we'll know:**" in l)
    if idx is None:
        return ""
    marker = "**How we'll know:**"
    pos = lines[idx].find(marker)
    parts = [lines[idx][pos + len(marker):].strip()]
    i = idx + 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("**") or stripped.startswith("-"):
            break
        parts.append(stripped)
        i += 1
    return " ".join(p for p in parts if p).strip()


def worked_examples(lines: List[str]) -> Tuple[List[Tuple[int, int]], Optional[str]]:
    """SS3 example (start, end) 0-indexed ranges, and which pattern was used.

    Tries ``### `` headings first, then bold-led paragraphs. Returns
    ``([], None)`` when neither pattern yields at least one example.
    """
    bounds = section_bounds(lines, 3)
    if bounds is None:
        return [], None
    start, end = bounds
    for pattern, kind in ((H3_RE, "heading"), (BOLD_LED_RE, "bold")):
        starts = [i for i in range(start + 1, end) if pattern.match(lines[i])]
        if starts:
            ranges = []
            for idx, s in enumerate(starts):
                e = starts[idx + 1] if idx + 1 < len(starts) else end
                ranges.append((s, e))
            return ranges, kind
    return [], None


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------


def check_header_status(lines: List[str]) -> List[Dict[str, Any]]:
    idx = find_line_index(lines, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return [finding("HEADER_STATUS", 1, "missing a 'Status:' line", "error")]
    token = STATUS_RE.match(lines[idx]).group(1)
    if token not in VALID_STATUS_TOKENS:
        return [
            finding(
                "HEADER_STATUS",
                idx + 1,
                f"Status: token {token!r} is not one of draft, agreed, building, shipped, superseded-by",
                "error",
            )
        ]
    return []


def check_header_owner(lines: List[str]) -> List[Dict[str, Any]]:
    out = []
    owner_idx = find_line_index(lines, lambda l: "Owner:" in l)
    if owner_idx is None:
        out.append(finding("HEADER_OWNER", 1, "missing an 'Owner:' field", "error"))
    last_decision_idx = find_line_index(lines, lambda l: "Last decision:" in l)
    if last_decision_idx is None:
        out.append(
            finding(
                "HEADER_OWNER",
                owner_idx + 1 if owner_idx is not None else 1,
                "missing a 'Last decision:' field",
                "error",
            )
        )
    return out


def check_contents_line(lines: List[str]) -> List[Dict[str, Any]]:
    idx = find_line_index(lines, lambda l: l.strip().startswith("Contents:"))
    if idx is None:
        return [finding("CONTENTS_LINE", 1, "missing a 'Contents:' line", "error")]
    block = [lines[idx]]
    i = idx + 1
    while i < len(lines) and lines[i].strip():
        block.append(lines[i])
        i += 1
    text = " ".join(block)
    missing = [a for a in CONTENTS_ANCHORS if a not in text]
    if missing:
        return [
            finding(
                "CONTENTS_LINE",
                idx + 1,
                "Contents: line is missing anchor(s): " + ", ".join(missing),
                "error",
            )
        ]
    return []


def check_headings_bare(lines: List[str]) -> List[Dict[str, Any]]:
    by_number: Dict[int, List[Tuple[int, str]]] = {}
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if not m:
            continue
        n = int(m.group(1))
        by_number.setdefault(n, []).append((i + 1, m.group(2)))

    out = []
    for n in range(0, 11):
        expected = f"{n}. {SECTION_NAMES[n]}"
        entries = by_number.get(n, [])
        good = [e for e in entries if e[1] == SECTION_NAMES[n]]
        if not good:
            if entries:
                line_no, actual = entries[0]
                out.append(
                    finding(
                        "HEADINGS_BARE",
                        line_no,
                        f"heading must read exactly '## {expected}' (found '## {n}. {actual}')",
                        "error",
                    )
                )
            else:
                out.append(finding("HEADINGS_BARE", 1, f"missing heading '## {expected}'", "error"))
        elif len(good) > 1:
            out.append(
                finding(
                    "HEADINGS_BARE",
                    good[1][0],
                    f"heading '## {expected}' appears more than once",
                    "error",
                )
            )
    return out


def check_tldr_budget(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    count = end - start
    if count > 40:
        return [
            finding(
                "TLDR_BUDGET",
                start + 1,
                f"SS0 TLDR block is {count} lines (max 40)",
                "error",
            )
        ]
    return []


def check_tldr_fields(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    block_text = " ".join(lines[start:end])
    out = []
    for field in ("**Outcome:**", "**Rules:**", "**How we'll know:**", "**Scenarios:**"):
        if field not in block_text:
            out.append(finding("TLDR_FIELDS", start + 1, f"SS0 is missing {field}", "error"))
    return out


def check_rules_format(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    return [
        finding("RULES_FORMAT", r["start_line"], "rule must be a '- ' bullet, not numbered", "error")
        for r in records
        if r["format"] == "numbered"
    ]


def check_rules_tagged(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    return [
        finding(
            "RULES_TAGGED",
            r["start_line"],
            "rule does not end with '→ AT-n[, AT-m]' or '→ UNTESTED'",
            "error",
        )
        for r in records
        if r["tags"] is None
    ]


def check_tags_resolve(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    row_ids = {r["id"] for r in parse_acceptance_rows(lines)}
    out = []
    for r in records:
        if not r["tags"] or r["tags"] == ["UNTESTED"]:
            continue
        for tag in r["tags"]:
            if tag not in row_ids:
                out.append(
                    finding(
                        "TAGS_RESOLVE",
                        r["start_line"],
                        f"{tag} cited in SS0 does not exist as a SS6 row id",
                        "error",
                    )
                )
    return out


def check_at_ids_unique(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    out = []
    seen: Dict[str, int] = {}
    for line_no, cells in parse_table_data_rows(lines, start + 1, end):
        if not cells:
            continue
        row_id = cells[0]
        if not AT_ID_RE.match(row_id):
            out.append(
                finding("AT_IDS_UNIQUE", line_no, f"SS6 row id {row_id!r} does not match AT-\\d+", "error")
            )
            continue
        if row_id in seen:
            out.append(finding("AT_IDS_UNIQUE", line_no, f"duplicate SS6 row id {row_id}", "error"))
        else:
            seen[row_id] = line_no
    return out


def check_scenarios_count(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    idx = find_line_index(lines, lambda l: "**Scenarios:**" in l, start=start)
    if idx is None or idx >= end:
        return []
    m = SCENARIOS_RE.search(lines[idx])
    if not m:
        return [
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                "Scenarios: line does not match '<N> acceptance rows (SS6), <M> worked examples (SS3).'",
                "error",
            )
        ]
    out = []
    n_claimed, m_claimed = int(m.group(1)), int(m.group(2))
    n_actual = len(parse_acceptance_rows(lines))
    if n_claimed != n_actual:
        out.append(
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                f"Scenarios: claims {n_claimed} acceptance rows but SS6 has {n_actual}",
                "error",
            )
        )
    ranges, kind = worked_examples(lines)
    if kind is None:
        out.append(
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                "SS3 worked-example count not checked (no '### ' headings or bold-led paragraphs found)",
                "warn",
            )
        )
    else:
        m_actual = len(ranges)
        if m_claimed != m_actual:
            out.append(
                finding(
                    "SCENARIOS_COUNT",
                    idx + 1,
                    f"Scenarios: claims {m_claimed} worked examples but SS3 has {m_actual}",
                    "error",
                )
            )
    return out


def check_why_line(lines: List[str]) -> List[Dict[str, Any]]:
    out = []
    for n in WHY_SECTIONS:
        bounds = section_bounds(lines, n)
        if bounds is None:
            continue
        start, end = bounds
        if not any(WHY_LINE_RE.match(lines[i].lstrip()) for i in range(start, end)):
            out.append(
                finding(
                    "WHY_LINE",
                    start + 1,
                    f"SS{n} is missing a line beginning 'Why — what breaks without it:'",
                    "error",
                )
            )
    return out


def check_untested_on_agreed(lines: List[str]) -> List[Dict[str, Any]]:
    status = get_status(lines)
    if status not in ("agreed", "building", "shipped"):
        return []
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    return [
        finding(
            "UNTESTED_ON_AGREED",
            r["start_line"],
            f"rule is tagged UNTESTED while Status: is {status}",
            "error",
        )
        for r in records
        if r["tags"] == ["UNTESTED"]
    ]


def check_placeholder(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    seen_terms = set()
    out = []
    for i in range(start, end):
        lowered = lines[i].lower()
        for term in PLACEHOLDER_TERMS:
            if term in lowered and term not in seen_terms:
                seen_terms.add(term)
                out.append(finding("PLACEHOLDER", i + 1, f"placeholder text {term!r} found in SS0", "error"))
    return out


def check_agent_notes_many(lines: List[str]) -> List[Dict[str, Any]]:
    idx = find_line_index(lines, lambda l: l.startswith(AGENT_NOTES_PREFIX))
    if idx is None:
        return []
    end = find_line_index(lines, lambda l: l.startswith("## 1."), start=idx + 1)
    if end is None:
        end = len(lines)
    count = sum(1 for i in range(idx + 1, end) if NOTE_START_RE.match(lines[i]))
    if count > 8:
        return [
            finding(
                "AGENT_NOTES_MANY",
                idx + 1,
                f"SS0 has {count} agent notes (consolidate past 8)",
                "warn",
            )
        ]
    return []


def check_human_half_budget(lines: List[str]) -> List[Dict[str, Any]]:
    tldr_bounds = tldr_block_bounds(lines)
    start = tldr_bounds[0] if tldr_bounds is not None else find_line_index(lines, lambda l: l.startswith(TLDR_HEADING))
    if start is None:
        return []
    section2 = section_bounds(lines, 2)
    if section2 is None:
        return []
    _, end_of_2 = section2
    ranges, kind = worked_examples(lines)
    if kind is None:
        end = end_of_2
        measured_note = "SS3 not measured (no parseable example found)"
    else:
        end = ranges[0][1]
        measured_note = "through the first SS3 example"
    count = end - start
    if count > 150:
        return [
            finding(
                "HUMAN_HALF_BUDGET",
                start + 1,
                f"human half is {count} lines (max 150), {measured_note}",
                "warn",
            )
        ]
    return []


RULE_CHECKS = (
    check_header_status,
    check_header_owner,
    check_contents_line,
    check_headings_bare,
    check_tldr_budget,
    check_tldr_fields,
    check_rules_format,
    check_rules_tagged,
    check_tags_resolve,
    check_at_ids_unique,
    check_scenarios_count,
    check_why_line,
    check_untested_on_agreed,
    check_placeholder,
    check_agent_notes_many,
    check_human_half_budget,
)


def lint_lines(lines: List[str], strict: bool) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for check in RULE_CHECKS:
        findings.extend(check(lines))
    if strict:
        for f in findings:
            if f["severity"] == "warn":
                f["severity"] = "error"
    findings.sort(key=lambda f: (f["line"] if f["line"] is not None else 0, f["rule"]))
    return findings


def lint_file(path: str, strict: bool) -> Dict[str, Any]:
    text = read_text_tolerant(path)
    lines = text.splitlines()
    findings = lint_lines(lines, strict)
    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": path,
        "findings": findings,
        "stats": {"errors": errors, "warnings": warns, "total": len(findings)},
    }


def contains_tldr(path: str) -> bool:
    try:
        text = read_text_tolerant(path)
    except OSError:
        return False
    return any(line.startswith(TLDR_HEADING) for line in text.splitlines())


def collect_directory_docs(root: str) -> List[str]:
    """Every *.md under root containing a SS0 TLDR heading, one level of recursion deep."""
    found = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isfile(full) and name.endswith(".md") and contains_tldr(full):
            found.append(full)
        elif os.path.isdir(full):
            for name2 in sorted(os.listdir(full)):
                full2 = os.path.join(full, name2)
                if os.path.isfile(full2) and name2.endswith(".md") and contains_tldr(full2):
                    found.append(full2)
    return found


def format_human(results: List[Dict[str, Any]]) -> str:
    lines_out = []
    for result in results:
        for f in result["findings"]:
            line_part = f["line"] if f["line"] is not None else "?"
            lines_out.append(f"{result['path']}:{line_part}: {f['rule']} {f['message']}")
    return "\n".join(lines_out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_outcome.py",
        description="Check an outcome doc (or a directory of them) against the framework shape.",
    )
    parser.add_argument("path", help="a doc.md, or a directory to scan one level deep")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--strict", action="store_true", help="promote warn findings to error")
    args = parser.parse_args(argv)

    if not os.path.exists(args.path):
        print(f"lint_outcome.py: no such file or directory: {args.path}", file=sys.stderr)
        return 2

    if os.path.isdir(args.path):
        doc_paths = collect_directory_docs(args.path)
    elif os.path.isfile(args.path):
        doc_paths = [args.path]
    else:
        print(f"lint_outcome.py: not a file or directory: {args.path}", file=sys.stderr)
        return 2

    try:
        results = [lint_file(p, args.strict) for p in doc_paths]
    except OSError as exc:
        print(f"lint_outcome.py: {exc}", file=sys.stderr)
        return 2

    # Exit 1 only for error-severity findings. --strict has already
    # promoted warn to error in place (inside lint_lines) by this point,
    # so a plain warning that was never promoted does not fail the run.
    any_errors = any(f["severity"] == "error" for r in results for f in r["findings"])

    if args.json:
        payload = results[0] if os.path.isfile(args.path) else results
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        text = format_human(results)
        if text:
            print(text)

    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
