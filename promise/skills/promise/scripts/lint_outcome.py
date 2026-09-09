#!/usr/bin/env python3
"""Shape checks for one outcome doc, or every outcome doc in a directory.

    python3 lint_outcome.py doc.md
    python3 lint_outcome.py docs/designs --json
    python3 lint_outcome.py doc.md --strict
    python3 lint_outcome.py doc.md --template

Checks the rules in references/architecture.md SS9 against the Outcome
Framework template shape: SS0 TLDR budget and non-empty fields, rule
bullet format and tags, headings, the SS6 acceptance table (rule id
ACCEPTANCE_TABLE: a qualifying header, at least one data row, non-empty
Given/When/Then cells), the Why lines, and placeholder text (rule id
PLACEHOLDER: TBD/TODO/etc markers plus any angle-bracket ``<...>`` run
in SS0, in the header ``Owner:``/``Last decision:`` values, or in a SS6
data cell), and status authority (rule id BUILDING_NEEDS_GATE: a
``building`` doc's header carries no red-gate commit sha). ``--template``
exempts angle-bracket placeholders and the literal ``YYYY-MM-DD`` so the
bundled template itself can be linted; every other rule stays active
under it. A path that cannot be read as UTF-8 text reports one
UNREADABLE finding for itself instead of raising.
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
TEMPLATE_DATE_PLACEHOLDER = "YYYY-MM-DD"

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
ANGLE_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")
COMMIT_SHA_RE = re.compile(r"\b[0-9a-fA-F]{7,40}\b")


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


def parse_header_field_value(
    lines: List[str], idx: int, marker: str, other_marker: Optional[str] = None
) -> str:
    """The text on ``lines[idx]`` after ``marker``.

    Stops before ``other_marker`` when it also appears later on the same
    line (so ``Owner:``'s value does not swallow a same-line
    ``Last decision:``); otherwise runs to the end of the line. Empty when
    ``marker`` is not actually on that line.
    """
    line = lines[idx]
    pos = line.find(marker)
    if pos == -1:
        return ""
    value = line[pos + len(marker):]
    if other_marker:
        other_pos = value.find(other_marker)
        if other_pos != -1:
            value = value[:other_pos]
    return value.strip()


def _rules_block_bounds(lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
    """0-indexed (rules_idx, how_idx) bracketing the SS0 rules block.

    ``rules_idx`` is the ``**Rules:**`` line, or None when it is absent.
    ``how_idx`` is the following ``**How we'll know:**`` line, or None when
    there is none after it.
    """
    rules_idx = find_line_index(lines, lambda l: "**Rules:**" in l)
    if rules_idx is None:
        return None, None
    how_idx = find_line_index(lines, lambda l: "**How we'll know:**" in l, start=rules_idx + 1)
    return rules_idx, how_idx


def parse_rules_block(lines: List[str]) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
    """Parse the SS0 rules between **Rules:** and **How we'll know:**.

    Returns (records, rules_line_idx, how_we_know_line_idx). Each record:
    ``{"start_line": 1-based, "format": "bullet"|"numbered", "raw_text": str,
    "tags": [...] or None}``. Continuation lines (indented, not starting a
    new ``- `` or ``N.`` item) are joined onto the currently open rule
    before the trailing tag is checked. A non-blank line that is neither a
    bullet, a numbered item, nor an indented continuation is excluded here
    entirely — ``check_rules_format`` reports it as a stray line. Returns
    ([], None, None) when the **Rules:** anchor is absent.
    """
    rules_idx, how_idx = _rules_block_bounds(lines)
    if rules_idx is None:
        return [], None, None
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
        elif current is not None and raw_line[:1].isspace():
            current["parts"].append(raw_line.strip())
        else:
            # Stray text: not a bullet/numbered start, and not an indented
            # continuation of the rule before it (or nothing is open).
            current = None

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


def find_stray_rule_lines(lines: List[str]) -> List[int]:
    """1-based line numbers in the SS0 rules block that are neither a
    ``- `` bullet, a numbered item, nor an indented continuation of the
    line before them. Empty when the **Rules:** anchor is absent."""
    rules_idx, how_idx = _rules_block_bounds(lines)
    if rules_idx is None:
        return []
    end = how_idx if how_idx is not None else len(lines)

    stray: List[int] = []
    open_rule = False
    for i in range(rules_idx + 1, end):
        raw_line = lines[i]
        if not raw_line.strip():
            open_rule = False
            continue
        if BULLET_START_RE.match(raw_line) or NUMBERED_START_RE.match(raw_line):
            open_rule = True
            continue
        if open_rule and raw_line[:1].isspace():
            continue
        stray.append(i + 1)
        open_rule = False
    return stray


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


def find_acceptance_tables(
    lines: List[str], start: int, end: int
) -> List[Tuple[int, List[str], List[Tuple[int, List[str]]]]]:
    """Tables in [start, end) that qualify as SS6's acceptance table.

    A table qualifies when its header's first cell is ``#``/``ID``/``AT``
    (case-insensitive, matching ``parse_table_data_rows``) *and* the header
    has 4 or 5 cells (``Given``, ``When``, ``Then``, optional ``Row``). A
    first-cell match at the wrong width does not qualify — ACCEPTANCE_TABLE
    reports it the same as no table at all. Returns a list of
    (header_line, header_cells, data_rows), each already separator-stripped.
    """
    found = []
    for table in split_tables(lines, start, end):
        header_line, header_cells = table[0]
        if not header_cells or not ACCEPTANCE_HEADER_RE.match(header_cells[0]):
            continue
        if len(header_cells) not in (4, 5):
            continue
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        found.append((header_line, header_cells, body))
    return found


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


def parse_bold_field_value(lines: List[str], marker: str) -> str:
    """The text after a ``**Field:**`` marker, with wrapped continuation
    lines joined. Continuation stops at a blank line, the next bold field,
    or a ``- `` bullet — whichever comes first. Empty when ``marker`` is
    not found in ``lines`` at all."""
    idx = find_line_index(lines, lambda l: marker in l)
    if idx is None:
        return ""
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


def parse_signal(lines: List[str]) -> str:
    """The **How we'll know:** text, with wrapped continuation lines joined."""
    return parse_bold_field_value(lines, "**How we'll know:**")


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
    match = STATUS_RE.match(lines[idx])
    token = match.group(1)
    if token not in VALID_STATUS_TOKENS:
        return [
            finding(
                "HEADER_STATUS",
                idx + 1,
                f"Status: token {token!r} is not one of draft, agreed, building, shipped, superseded-by",
                "error",
            )
        ]
    if token == "superseded-by" and not lines[idx][match.end():].strip():
        return [
            finding(
                "HEADER_STATUS",
                idx + 1,
                "Status: superseded-by must name a target",
                "error",
            )
        ]
    return []


def check_header_owner(lines: List[str]) -> List[Dict[str, Any]]:
    out = []
    owner_idx = find_line_index(lines, lambda l: "Owner:" in l)
    if owner_idx is None:
        out.append(finding("HEADER_OWNER", 1, "missing an 'Owner:' field", "error"))
    elif not parse_header_field_value(lines, owner_idx, "Owner:", "Last decision:"):
        out.append(finding("HEADER_OWNER", owner_idx + 1, "'Owner:' value is empty", "error"))

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
    elif not parse_header_field_value(lines, last_decision_idx, "Last decision:"):
        out.append(
            finding("HEADER_OWNER", last_decision_idx + 1, "'Last decision:' value is empty", "error")
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
        if not entries:
            out.append(finding("HEADINGS_BARE", 1, f"missing heading '## {expected}'", "error"))
            continue
        # Every malformed heading fires, whether or not a well-formed one for
        # the same number also exists — a valid heading must never mask a
        # malformed duplicate.
        good = [e for e in entries if e[1] == SECTION_NAMES[n]]
        bad = [e for e in entries if e[1] != SECTION_NAMES[n]]
        for line_no, actual in bad:
            out.append(
                finding(
                    "HEADINGS_BARE",
                    line_no,
                    f"heading must read exactly '## {expected}' (found '## {n}. {actual}')",
                    "error",
                )
            )
        if len(good) > 1:
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
    block_lines = lines[start:end]
    block_text = " ".join(block_lines)
    out = []
    for field in ("**Outcome:**", "**Rules:**", "**How we'll know:**", "**Scenarios:**"):
        if field not in block_text:
            out.append(finding("TLDR_FIELDS", start + 1, f"SS0 is missing {field}", "error"))

    # A field that IS present must still carry a value — text on the marker's
    # own line, or on indented/plain continuation lines before the next bold
    # field. **Rules:** and **Scenarios:** have their own dedicated shape
    # rules (RULES_FORMAT/RULES_TAGGED, SCENARIOS_COUNT) so only the two
    # freeform fields are checked for emptiness here.
    for field in ("**Outcome:**", "**How we'll know:**"):
        if field not in block_text:
            continue
        if not parse_bold_field_value(block_lines, field):
            rel_idx = find_line_index(block_lines, lambda l, field=field: field in l)
            out.append(finding("TLDR_FIELDS", start + rel_idx + 1, f"{field} has no value", "error"))
    return out


def check_rules_format(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    out = [
        finding("RULES_FORMAT", r["start_line"], "rule must be a '- ' bullet, not numbered", "error")
        for r in records
        if r["format"] == "numbered"
    ]
    out.extend(
        finding("RULES_FORMAT", line_no, "text in the rules block is not a rule bullet", "error")
        for line_no in find_stray_rule_lines(lines)
    )
    out.extend(
        finding("RULES_FORMAT", r["start_line"], "rule bullet has no text before its tag", "error")
        for r in records
        if r["format"] == "bullet" and r["tags"] is not None and not r["text"]
    )
    return out


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


def check_acceptance_table(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = section_bounds(lines, 6)
    if bounds is None:
        # HEADINGS_BARE already reports a missing "## 6." heading.
        return []
    start, end = bounds
    tables = find_acceptance_tables(lines, start + 1, end)
    if not tables:
        return [
            finding(
                "ACCEPTANCE_TABLE",
                start + 1,
                "SS6 has no acceptance table (need a header whose first cell is "
                "'#', 'ID' or 'AT', with 4 or 5 columns)",
                "error",
            )
        ]

    out: List[Dict[str, Any]] = []
    total_rows = 0
    cell_names = ("Given", "When", "Then")
    for header_line, header_cells, body in tables:
        width = len(header_cells)
        for line_no, cells in body:
            total_rows += 1
            if len(cells) != width:
                out.append(
                    finding(
                        "ACCEPTANCE_TABLE",
                        line_no,
                        f"acceptance table row has {len(cells)} cells, expected {width}",
                        "error",
                    )
                )
                continue
            for offset, name in enumerate(cell_names, start=1):
                if not cells[offset].strip():
                    out.append(
                        finding(
                            "ACCEPTANCE_TABLE",
                            line_no,
                            f"acceptance table row's {name} cell is empty",
                            "error",
                        )
                    )
    if total_rows == 0:
        out.append(
            finding("ACCEPTANCE_TABLE", tables[0][0], "acceptance table has no data rows", "error")
        )
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


def check_building_needs_gate(lines: List[str]) -> List[Dict[str, Any]]:
    """`building` records the human-confirmed act that earned the status: the
    red-gate commit. Warn when the header (every line before ``## 0.``)
    carries no 7-40 character hexadecimal run — `arm` writes it as
    ``Red gate: <sha> <YYYY-MM-DD>``, directly under ``Supersedes:``."""
    status = get_status(lines)
    if status != "building":
        return []
    tldr_idx = find_line_index(lines, lambda l: l.startswith(TLDR_HEADING))
    header_end = tldr_idx if tldr_idx is not None else len(lines)
    if any(COMMIT_SHA_RE.search(line) for line in lines[:header_end]):
        return []
    return [
        finding(
            "BUILDING_NEEDS_GATE",
            1,
            "arm records the red-gate commit in the header as "
            "'Red gate: <sha> <YYYY-MM-DD>'; none found",
            "warn",
        )
    ]


def check_placeholder(lines: List[str], template: bool = False) -> List[Dict[str, Any]]:
    """TBD/TODO-style terms, plus angle-bracket ``<...>`` placeholders, in SS0,
    the header ``Owner:``/``Last decision:`` values, and SS6 data cells.

    ``template=True`` exempts angle-bracket placeholders and the literal
    ``YYYY-MM-DD`` (the bundled template's own placeholder shapes) so the
    template can be linted in template mode; the TBD/TODO-style terms stay
    active either way.
    """
    out: List[Dict[str, Any]] = []
    seen_terms = set()

    bounds = tldr_block_bounds(lines)
    if bounds is not None:
        start, end = bounds
        for i in range(start, end):
            lowered = lines[i].lower()
            for term in PLACEHOLDER_TERMS:
                if term in lowered and term not in seen_terms:
                    seen_terms.add(term)
                    out.append(finding("PLACEHOLDER", i + 1, f"placeholder text {term!r} found in SS0", "error"))
            if not template:
                for m in ANGLE_PLACEHOLDER_RE.finditer(lines[i]):
                    out.append(
                        finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in SS0", "error")
                    )

    if not template:
        owner_idx = find_line_index(lines, lambda l: "Owner:" in l)
        if owner_idx is not None:
            value = parse_header_field_value(lines, owner_idx, "Owner:", "Last decision:")
            for m in ANGLE_PLACEHOLDER_RE.finditer(value):
                out.append(
                    finding(
                        "PLACEHOLDER",
                        owner_idx + 1,
                        f"placeholder {m.group(0)!r} found in the header 'Owner:' value",
                        "error",
                    )
                )

        last_decision_idx = find_line_index(lines, lambda l: "Last decision:" in l)
        if last_decision_idx is not None:
            value = parse_header_field_value(lines, last_decision_idx, "Last decision:")
            for m in ANGLE_PLACEHOLDER_RE.finditer(value):
                out.append(
                    finding(
                        "PLACEHOLDER",
                        last_decision_idx + 1,
                        f"placeholder {m.group(0)!r} found in the header 'Last decision:' value",
                        "error",
                    )
                )
            if value == TEMPLATE_DATE_PLACEHOLDER:
                out.append(
                    finding(
                        "PLACEHOLDER",
                        last_decision_idx + 1,
                        f"placeholder {TEMPLATE_DATE_PLACEHOLDER!r} found in the header 'Last decision:' value",
                        "error",
                    )
                )

        bounds6 = section_bounds(lines, 6)
        if bounds6 is not None:
            start6, end6 = bounds6
            for line_no, cells in parse_table_data_rows(lines, start6 + 1, end6):
                for cell in cells:
                    for m in ANGLE_PLACEHOLDER_RE.finditer(cell):
                        out.append(
                            finding(
                                "PLACEHOLDER",
                                line_no,
                                f"placeholder {m.group(0)!r} found in an SS6 data cell",
                                "error",
                            )
                        )
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
    check_acceptance_table,
    check_scenarios_count,
    check_why_line,
    check_untested_on_agreed,
    check_building_needs_gate,
    check_agent_notes_many,
    check_human_half_budget,
)


def lint_lines(lines: List[str], strict: bool, template: bool = False) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for check in RULE_CHECKS:
        findings.extend(check(lines))
    findings.extend(check_placeholder(lines, template))
    if strict:
        for f in findings:
            if f["severity"] == "warn":
                f["severity"] = "error"
    findings.sort(key=lambda f: (f["line"] if f["line"] is not None else 0, f["rule"]))
    return findings


def lint_file(path: str, strict: bool, template: bool = False) -> Dict[str, Any]:
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError) as exc:
        findings = [finding("UNREADABLE", None, f"cannot read {path}: {exc}", "error")]
        return {"path": path, "findings": findings, "stats": {"errors": 1, "warnings": 0, "total": 1}}
    lines = text.splitlines()
    findings = lint_lines(lines, strict, template)
    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": path,
        "findings": findings,
        "stats": {"errors": errors, "warnings": warns, "total": len(findings)},
    }


def contains_tldr(path: str) -> bool:
    """True when ``path`` is UTF-8 text containing the SS0 TLDR heading.

    A file that cannot be read or decoded also counts as True: a directory
    scan surfaces a broken doc as an UNREADABLE finding (via ``lint_file``)
    rather than silently excluding it from the scan.
    """
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError):
        return True
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
    parser.add_argument(
        "--template",
        action="store_true",
        help="exempt angle-bracket and literal YYYY-MM-DD placeholders, for linting the bundled template",
    )
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

    # Every path is read inside lint_file, which turns an unreadable file or
    # a decoding failure into an UNREADABLE finding rather than raising, so
    # nothing here needs to guard against that.
    results = [lint_file(p, args.strict, args.template) for p in doc_paths]

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
