#!/usr/bin/env python3
"""Shape checks for one outcome doc, or every outcome doc in a directory.

    python3 lint_outcome.py doc.md
    python3 lint_outcome.py docs/designs --json
    python3 lint_outcome.py doc.md --strict
    python3 lint_outcome.py doc.md --template

Checks the rules in references/architecture.md §9 against the Outcome
Framework template shape: §0 TLDR budget and non-empty fields, rule
bullet format and tags (and that ``**Rules:**`` holds at least one rule,
rule id RULES_PRESENT), headings, the §6 acceptance table (rule id
ACCEPTANCE_TABLE: a qualifying header, at least one data row, non-empty
Given/When/Then cells, and every row bounded by a leading and a trailing
pipe -- a row missing one is still read, GFM-style, and reported at its
own line rather than dropped with every row below it), the §6 Altitude
column (rule id ACCEPTANCE_ALTITUDE: every cell is one of ``data``,
``response``, ``perception``, ``judgement``, ``sibling``; and, as a
warning, ALTITUDE_MISSING when a table has no ``Altitude`` header), the
Why lines (rule id WHY_LINE: present in §4-§7, each with a value), and
placeholder text (rule id PLACEHOLDER: TBD/TODO/etc markers plus any
angle-bracket ``<...>`` run in §0, in the header ``Owner:``/``Last
decision:`` values, in a §6 data cell, in an agent note, on a §3
example's first line, in a §9 owner, or in a Why line's value), and
status authority (rule id BUILDING_NEEDS_GATE: a ``building`` doc's
header carries no red-gate commit sha). ``--template`` exempts
angle-bracket placeholders and the literal ``YYYY-MM-DD`` so the bundled
template itself can be linted; every other rule stays active under it.
Lines inside a fenced code block (``` or ~~~) are illustrations: no
heading, field marker, table row or placeholder inside one counts,
though the lines still count toward a line budget; a fence that is
opened and never closed is its own finding (rule id FENCE_UNCLOSED, at
the opening line), since every line after it would otherwise vanish
from the scan with nothing naming the cause. A path that cannot be
read as UTF-8 text reports one UNREADABLE finding for itself instead
of raising.
Exit 0 when there is no error finding (a warning on its own exits 0), 1
when there is an error finding (a warning too under --strict, which
promotes every warning to an error), 2 on a usage error. Human output is
one line per finding: ``<path>:<line>: <RULE_ID> <message>``. ``--json``
prints one JSON object for a single file, or a JSON array of one such
object per file when a directory was given. Deterministic; no network.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

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

# The five altitudes of references/altitude.md -- what a §6 row's Then
# asserts on. Matched exactly (after trimming), never case-folded.
ALTITUDES = ("data", "response", "perception", "judgement", "sibling")

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^## (\d+)\.\s*(.*?)\s*$")
ANY_HEADING_RE = re.compile(r"^## \d+\.")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
BULLET_START_RE = re.compile(r"^-\s+(.*)$")
NUMBERED_START_RE = re.compile(r"^(\d+)\.\s+(.*)$")
TAG_RE = re.compile(r"→\s*(UNTESTED|AT-\d+(?:\s*,\s*AT-\d+)*)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
AT_ID_RE = re.compile(r"^AT-\d+$")
WHY_LINE_RE = re.compile(r"^Why\s*[-—]\s*what breaks without it:(.*)$")
SCENARIOS_RE = re.compile(
    r"\*\*Scenarios:\*\*\s*(\d+)\s*acceptance rows[^,]*,\s*(\d+)\s*worked examples?"
)
NOTE_START_RE = re.compile(r"^(\d+)\.\s+")
H3_RE = re.compile(r"^###\s+\S")
BOLD_LED_RE = re.compile(r"^\*\*[^*]+\*\*")
BOLD_FIELD_RE = re.compile(r"^\s*\*\*[^*]+:\*\*")
ANGLE_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")
OPEN_QUESTION_OWNER_RE = re.compile(r"^Q\w*\s*[-—]\s*owner:\s*(<[^<>]+>)")
RED_GATE_LINE_RE = re.compile(
    r"^Red gate:\s+([0-9a-fA-F]{7,40})\s+(\d{4}-\d{2}-\d{2})\s*$"
)

RULES_MARKER = "**Rules:**"
# The How-we'll-know marker as a person sees it, plus the curly-apostrophe
# spelling (U+2019) a word processor substitutes -- both are the same
# field, so neither is reported as missing.
HOW_WE_KNOW_MARKER = "**How we'll know:**"
HOW_WE_KNOW_RE = re.compile(r"\*\*How we['’]ll know:\*\*")

Marker = Union[str, Pattern[str]]


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


def unfenced(lines: List[str]) -> List[str]:
    """A copy of ``lines`` with every line inside a fenced code block (and the
    fence lines themselves) replaced by "", so indices stay aligned with the
    original while no heading, marker, table row or placeholder inside a
    fence can match a structural scan. A fence opens and closes on any line
    starting with ``` or ~~~ (the same rule framework_section.py uses)."""
    out: List[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def finding(rule: str, line: Optional[int], message: str, severity: str) -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


def _marker_span(line: str, marker: Marker) -> Optional[Tuple[int, int]]:
    """(start, end) of ``marker`` -- a literal or a compiled pattern -- on
    ``line``, or None when it is not there."""
    if isinstance(marker, str):
        pos = line.find(marker)
        return (pos, pos + len(marker)) if pos != -1 else None
    m = marker.search(line)
    return (m.start(), m.end()) if m else None


# ---------------------------------------------------------------------------
# Shared structural lookups (also used by outcome_rows.py and bridge_validate.py)
# ---------------------------------------------------------------------------


def _heading_number(line: str) -> Optional[str]:
    m = HEADING_RE.match(line)
    return m.group(1) if m else None


def section_bounds(lines: List[str], n: int) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) line range for ``## n. ...`` through the next heading.

    Headings inside a fenced code block are illustrations, not sections."""
    scan = unfenced(lines)
    start = find_line_index(scan, lambda l: _heading_number(l) == str(n))
    if start is None:
        return None
    end = find_line_index(scan, lambda l: ANY_HEADING_RE.match(l) is not None, start=start + 1)
    return start, end if end is not None else len(lines)


def tldr_block_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) for §0: the heading line up to (not incl.) Agent notes / §1."""
    scan = unfenced(lines)
    start = find_line_index(scan, lambda l: l.startswith(TLDR_HEADING))
    if start is None:
        return None
    end = find_line_index(scan, lambda l: l.startswith(AGENT_NOTES_PREFIX), start=start + 1)
    if end is None:
        end = find_line_index(scan, lambda l: l.startswith("## 1."), start=start + 1)
    if end is None:
        end = len(lines)
    return start, end


def get_status(lines: List[str]) -> Optional[str]:
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return None
    return STATUS_RE.match(scan[idx]).group(1)


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


def _rules_block_bounds(lines: List[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """0-indexed (rules_idx, how_idx, end) bracketing the §0 rules block.

    ``rules_idx`` is the ``**Rules:**`` line inside §0 (or, when the doc has
    no §0 heading at all, the first one anywhere), or None when absent.
    ``end`` is where the block stops: the next bold ``**Field:**`` marker
    (normally ``**How we'll know:**``, else ``**Scenarios:**``), the next
    ``## `` heading, or the end of §0 -- whichever comes first. It is never
    the end of the file while any of those exists, so a missing or
    mistyped How-we'll-know marker cannot sweep the rest of the doc into
    the rules block. ``how_idx`` is the ``**How we'll know:**`` line (ASCII
    or curly apostrophe) when it is the line that ends the block, else None.
    """
    scan = unfenced(lines)
    tldr = tldr_block_bounds(lines)
    if tldr is not None:
        tldr_start, tldr_end = tldr
        rules_idx = find_line_index(scan, lambda l: RULES_MARKER in l, start=tldr_start)
        if rules_idx is not None and rules_idx >= tldr_end:
            rules_idx = None
    else:
        tldr_end = len(lines)
        rules_idx = find_line_index(scan, lambda l: RULES_MARKER in l)
    if rules_idx is None:
        return None, None, None
    end = tldr_end
    stop = find_line_index(
        scan,
        lambda l: BOLD_FIELD_RE.match(l) is not None or l.startswith("## "),
        start=rules_idx + 1,
    )
    if stop is not None and stop < end:
        end = stop
    how_idx = end if end < len(lines) and HOW_WE_KNOW_RE.search(scan[end]) else None
    return rules_idx, how_idx, end


def parse_rules_block(lines: List[str]) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
    """Parse the §0 rules between **Rules:** and the next bold field.

    Returns (records, rules_line_idx, how_we_know_line_idx). Each record:
    ``{"start_line": 1-based, "format": "bullet"|"numbered", "raw_text": str,
    "tags": [...] or None}``. Continuation lines (indented, not starting a
    new ``- `` or ``N.`` item) are joined onto the currently open rule
    before the trailing tag is checked. A non-blank line that is neither a
    bullet, a numbered item, nor an indented continuation is excluded here
    entirely — ``check_rules_format`` reports it as a stray line. Returns
    ([], None, None) when the **Rules:** anchor is absent.
    """
    rules_idx, how_idx, end = _rules_block_bounds(lines)
    if rules_idx is None:
        return [], None, None
    scan = unfenced(lines)

    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for i in range(rules_idx + 1, end):
        raw_line = scan[i]
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
    """1-based line numbers in the §0 rules block that are neither a
    ``- `` bullet, a numbered item, nor an indented continuation of the
    line before them. Empty when the **Rules:** anchor is absent."""
    rules_idx, _how_idx, end = _rules_block_bounds(lines)
    if rules_idx is None:
        return []
    scan = unfenced(lines)

    stray: List[int] = []
    open_rule = False
    for i in range(rules_idx + 1, end):
        raw_line = scan[i]
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


def split_tables(
    lines: List[str], start: int, end: int, pipeless: Optional[List[int]] = None
) -> List[List[Tuple[int, List[str]]]]:
    """Every pipe table in [start, end) as its own list of (line_no, cells).

    A table is a run of consecutive pipe rows; any other line ends it. A section may
    hold several tables, and only the acceptance table is subject to row-id rules.

    A line directly under a running table that contains a pipe but lacks its
    leading or trailing one is still a row of that table -- GFM treats the
    outer pipes as optional -- and is read with the outer pipes stripped, so
    a one-character slip never drops the row, nor every intact row below
    it. Its 1-based line number is appended to ``pipeless`` when a list is
    given, so ACCEPTANCE_TABLE can report it at its own line. Rows inside a
    fenced code block are not rows. A Why line or the Snapshot line -- the
    two structural lines the contract puts directly under the table -- ends
    the table even when its prose holds a pipe: a structural line is never
    a row.
    """
    scan = unfenced(lines)
    tables: List[List[Tuple[int, List[str]]]] = []
    current: List[Tuple[int, List[str]]] = []
    for i in range(start, end):
        line = scan[i].rstrip("\r\n")
        m = TABLE_ROW_RE.match(line)
        if m:
            current.append((i + 1, [c.strip() for c in m.group(1).split("|")]))
        elif current and "|" in line and not _is_structural_under_table(line):
            inner = line.strip().strip("|")
            current.append((i + 1, [c.strip() for c in inner.split("|")]))
            if pipeless is not None:
                pipeless.append(i + 1)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _is_structural_under_table(line: str) -> bool:
    """True for a Why line or a Snapshot line (a leading backtick or
    asterisk tolerated on the latter, as bridge_validate.py tolerates it):
    the lines the contract places directly under the §6 table, which end
    a table whatever characters their prose carries."""
    stripped = line.lstrip()
    if WHY_LINE_RE.match(stripped):
        return True
    return stripped.lstrip("`*").startswith("Snapshot taken at")


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


REQUIRED_ACCEPTANCE_COLUMNS = ("given", "when", "then")
NAMED_ACCEPTANCE_COLUMNS = REQUIRED_ACCEPTANCE_COLUMNS + ("altitude", "row")


def acceptance_column_map(header_cells: List[str]) -> Optional[Dict[str, Optional[int]]]:
    """Column name -> 0-based index for one §6 acceptance-table header, or
    None when the header does not qualify as an acceptance table at all.

    Columns are matched by HEADER NAME, case-insensitive and trimmed, never
    by position — a real doc's header can read ``# | Label | Given | When |
    Then`` (an extra column before Given) or carry ``Row`` anywhere, and
    still qualify. The id column is always the first cell, and must be
    ``#``, ``ID`` or ``AT`` (case-insensitive) — this one column is
    positional by definition, not looked up by name. ``Given``, ``When``
    and ``Then`` must each appear by name somewhere in the header (any
    order); a header missing one of them does not qualify, the same as no
    table at all. ``Altitude`` and ``Row`` are optional: each maps to its
    index when a column carries that name, else None, so a doc without one
    reads every row's ``altitude``/``row`` as None rather than misreading
    some other column (ALTITUDE_MISSING warns about the absent Altitude
    column separately). Any other header cell (``Label``, ``Notes``, ...)
    sits in the table but is never read into a named field. A header that
    names ``Given``, ``When``, ``Then``, ``Altitude`` or ``Row`` more than
    once does not qualify either — there is no rule for which occurrence
    is "the" column, so this never guesses; ACCEPTANCE_TABLE reports it the
    same as a header missing one of them.
    """
    if not header_cells or not ACCEPTANCE_HEADER_RE.match(header_cells[0]):
        return None
    by_name: Dict[str, int] = {}
    duplicated: set = set()
    for i, cell in enumerate(header_cells):
        key = cell.strip().lower()
        if not key:
            continue
        if key in by_name:
            duplicated.add(key)
        else:
            by_name[key] = i
    if duplicated & set(NAMED_ACCEPTANCE_COLUMNS):
        return None
    for name in REQUIRED_ACCEPTANCE_COLUMNS:
        if name not in by_name:
            return None
    mapping: Dict[str, Optional[int]] = {"id": 0}
    mapping.update({name: by_name[name] for name in REQUIRED_ACCEPTANCE_COLUMNS})
    mapping["altitude"] = by_name.get("altitude")
    mapping["row"] = by_name.get("row")
    return mapping


def find_acceptance_tables(
    lines: List[str], start: int, end: int
) -> List[Tuple[int, List[str], List[Tuple[int, List[str]]], Optional[Dict[str, Optional[int]]], List[int]]]:
    """Every #/ID/AT-headed candidate table in [start, end), qualifying or not.

    A table is a candidate the instant its header's first cell is
    #/ID/AT -- acceptance_column_map then says whether it QUALIFIES (a
    dict) or not (None -- missing or duplicate Given/When/Then/Altitude/Row).
    Every candidate is returned either way, so a malformed table is still
    reported by ACCEPTANCE_TABLE even when a sibling table in the same
    section qualifies fine -- the two are never conflated into one verdict
    for the section. A table whose first cell does not match at all is not
    a candidate (a Decisions-style table, say) and is not returned. Returns
    a list of (header_line, header_cells, data_rows, column_map_or_None,
    pipeless_row_lines), each already separator-stripped; the last element
    is the 1-based line of every row in that table that lacks its leading
    or trailing pipe (see split_tables).
    """
    pipeless: List[int] = []
    found = []
    for table in split_tables(lines, start, end, pipeless):
        header_line, header_cells = table[0]
        if not header_cells or not ACCEPTANCE_HEADER_RE.match(header_cells[0]):
            continue
        column_map = acceptance_column_map(header_cells)
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        own_lines = {line_no for line_no, _cells in body}
        found.append(
            (header_line, header_cells, body, column_map, [n for n in pipeless if n in own_lines])
        )
    return found


def _cell_at(cells: List[str], idx: Optional[int]) -> str:
    """cells[idx], or "" when idx is None or past the row's own length --
    a short row (ACCEPTANCE_TABLE's own concern) never raises here."""
    return cells[idx] if idx is not None and idx < len(cells) else ""


def parse_acceptance_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """Well-formed §6 rows (id, given, when, then, altitude, row) keyed on AT-\\d+.

    Reuses find_acceptance_tables so a table is a candidate on exactly the
    same terms ACCEPTANCE_TABLE judges it by. A QUALIFYING header (see
    acceptance_column_map) is read by name -- an extra column (a Label) or
    a reordered Row never shifts what a cell means, and altitude/row are
    None whenever no header cell is named Altitude/Row (or the cell is
    empty). A candidate whose header does NOT qualify (missing or duplicate
    Given/When/Then/Altitude/Row -- ACCEPTANCE_TABLE reports the header
    itself as broken) still contributes its row ids, for SCENARIOS_COUNT's
    count and TAGS_RESOLVE's lookup -- but ONLY that: given/when/then come
    back empty and altitude/row come back None, never a value read from a
    position that might belong to an entirely different column (the
    concrete failure this guards: a duplicate Then column, read
    positionally, put the second Then's text into row).
    """
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    rows = []
    for _header_line, _header_cells, body, column_map, _pipeless in find_acceptance_tables(
        lines, start + 1, end
    ):
        for line_no, cells in body:
            if not cells or not AT_ID_RE.match(cells[0]):
                continue
            if column_map is None:
                rows.append(
                    {
                        "line": line_no,
                        "id": cells[0],
                        "given": "",
                        "when": "",
                        "then": "",
                        "altitude": None,
                        "row": None,
                    }
                )
                continue
            given = _cell_at(cells, column_map["given"])
            when = _cell_at(cells, column_map["when"])
            then = _cell_at(cells, column_map["then"])
            altitude_text = _cell_at(cells, column_map["altitude"]).strip()
            row_text = _cell_at(cells, column_map["row"]).strip()
            rows.append(
                {
                    "line": line_no,
                    "id": cells[0],
                    "given": given,
                    "when": when,
                    "then": then,
                    "altitude": altitude_text or None,
                    "row": row_text or None,
                }
            )
    return rows


def parse_bold_field_value(lines: List[str], marker: Marker) -> str:
    """The text after a ``**Field:**`` marker (a literal, or a compiled
    pattern such as HOW_WE_KNOW_RE), with wrapped continuation lines
    joined. Continuation stops at a blank line, the next bold field, or a
    ``- `` bullet — whichever comes first. Empty when ``marker`` is not
    found in ``lines`` at all. Fenced lines never carry the marker."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: _marker_span(l, marker) is not None)
    if idx is None:
        return ""
    _start, end_of_marker = _marker_span(scan[idx], marker)
    parts = [scan[idx][end_of_marker:].strip()]
    i = idx + 1
    while i < len(scan):
        stripped = scan[i].strip()
        if not stripped or stripped.startswith("**") or stripped.startswith("-"):
            break
        parts.append(stripped)
        i += 1
    return " ".join(p for p in parts if p).strip()


def parse_signal(lines: List[str]) -> str:
    """The **How we'll know:** text, with wrapped continuation lines joined."""
    return parse_bold_field_value(lines, HOW_WE_KNOW_RE)


def worked_examples(lines: List[str]) -> Tuple[List[Tuple[int, int]], Optional[str]]:
    """§3 example (start, end) 0-indexed ranges, and which pattern was used.

    Tries ``### `` headings first, then bold-led paragraphs. Returns
    ``([], None)`` when neither pattern yields at least one example.
    """
    bounds = section_bounds(lines, 3)
    if bounds is None:
        return [], None
    start, end = bounds
    scan = unfenced(lines)
    for pattern, kind in ((H3_RE, "heading"), (BOLD_LED_RE, "bold")):
        starts = [i for i in range(start + 1, end) if pattern.match(scan[i])]
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
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return [finding("HEADER_STATUS", 1, "missing a 'Status:' line", "error")]
    match = STATUS_RE.match(scan[idx])
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
    if token == "superseded-by" and not scan[idx][match.end():].strip():
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
    scan = unfenced(lines)
    out = []
    owner_idx = find_line_index(scan, lambda l: "Owner:" in l)
    if owner_idx is None:
        out.append(finding("HEADER_OWNER", 1, "missing an 'Owner:' field", "error"))
    elif not parse_header_field_value(scan, owner_idx, "Owner:", "Last decision:"):
        out.append(finding("HEADER_OWNER", owner_idx + 1, "'Owner:' value is empty", "error"))

    last_decision_idx = find_line_index(scan, lambda l: "Last decision:" in l)
    if last_decision_idx is None:
        out.append(
            finding(
                "HEADER_OWNER",
                owner_idx + 1 if owner_idx is not None else 1,
                "missing a 'Last decision:' field",
                "error",
            )
        )
    elif not parse_header_field_value(scan, last_decision_idx, "Last decision:"):
        out.append(
            finding("HEADER_OWNER", last_decision_idx + 1, "'Last decision:' value is empty", "error")
        )
    return out


def check_contents_line(lines: List[str]) -> List[Dict[str, Any]]:
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: l.strip().startswith("Contents:"))
    if idx is None:
        return [finding("CONTENTS_LINE", 1, "missing a 'Contents:' line", "error")]
    block = [scan[idx]]
    i = idx + 1
    while i < len(scan) and scan[i].strip():
        block.append(scan[i])
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
    for i, line in enumerate(unfenced(lines)):
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
                f"§0 TLDR block is {count} lines (max 40)",
                "error",
            )
        ]
    return []


def check_tldr_fields(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    block_lines = unfenced(lines)[start:end]
    out = []
    fields: List[Tuple[str, Marker]] = [
        ("**Outcome:**", "**Outcome:**"),
        ("**Rules:**", RULES_MARKER),
        (HOW_WE_KNOW_MARKER, HOW_WE_KNOW_RE),
        ("**Scenarios:**", "**Scenarios:**"),
    ]
    present = {
        name: find_line_index(block_lines, lambda l, m=marker: _marker_span(l, m) is not None)
        for name, marker in fields
    }
    for name, _marker in fields:
        if present[name] is None:
            out.append(finding("TLDR_FIELDS", start + 1, f"§0 is missing {name}", "error"))

    # A field that IS present must still carry a value — text on the marker's
    # own line, or on indented/plain continuation lines before the next bold
    # field. **Rules:** has its own shape rules (RULES_PRESENT for an empty
    # block, RULES_FORMAT/RULES_TAGGED for each bullet) and **Scenarios:**
    # has SCENARIOS_COUNT, so only the two freeform fields are checked for
    # emptiness here.
    for name, marker in fields:
        if name not in ("**Outcome:**", HOW_WE_KNOW_MARKER) or present[name] is None:
            continue
        if not parse_bold_field_value(block_lines, marker):
            out.append(finding("TLDR_FIELDS", start + present[name] + 1, f"{name} has no value", "error"))
    return out


def check_rules_present(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``**Rules:**`` marker with no rule bullet under it is an error at
    every status: a field checked for presence is also checked for a value,
    the same as ``**Outcome:**`` and ``**How we'll know:**``. A block that
    holds only stray text is left to RULES_FORMAT, which already names the
    stray line, so the two never fire together on the same defect."""
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None or records or find_stray_rule_lines(lines):
        return []
    return [
        finding(
            "RULES_PRESENT",
            rules_idx + 1,
            "**Rules:** has no rule bullets (at least one '- ' rule is required)",
            "error",
        )
    ]


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
                        f"{tag} cited in §0 does not exist as a §6 row id",
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
                finding("AT_IDS_UNIQUE", line_no, f"§6 row id {row_id!r} does not match AT-\\d+", "error")
            )
            continue
        if row_id in seen:
            out.append(finding("AT_IDS_UNIQUE", line_no, f"duplicate §6 row id {row_id}", "error"))
        else:
            seen[row_id] = line_no
    return out


def check_acceptance_table(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = section_bounds(lines, 6)
    if bounds is None:
        # HEADINGS_BARE already reports a missing "## 6." heading.
        return []
    start, end = bounds
    tables = find_acceptance_tables(lines, start + 1, end)  # every candidate, qualifying or not
    if not tables:
        return [
            finding(
                "ACCEPTANCE_TABLE",
                start + 1,
                "§6 has no acceptance table (need a header row whose first cell is "
                "'#', 'ID' or 'AT' and which names Given, When and Then)",
                "error",
            )
        ]

    qualifying = [t for t in tables if t[3] is not None]
    malformed = [t for t in tables if t[3] is None]

    out: List[Dict[str, Any]] = []

    # A row missing its leading or trailing pipe is read anyway (see
    # split_tables) and reported at its own line, for every candidate table.
    for _header_line, _header_cells, _body, _column_map, pipeless in tables:
        for line_no in pipeless:
            out.append(
                finding(
                    "ACCEPTANCE_TABLE",
                    line_no,
                    "acceptance table row is missing its leading or trailing pipe "
                    "(a line with a pipe directly under a table is read as one of its rows)",
                    "error",
                )
            )

    if not qualifying:
        # Every #/ID/AT-headed candidate failed its own header check --
        # report each on the "no acceptance table" terms (matches the
        # single-candidate case's long-standing message), at its own line.
        for header_line, _header_cells, _body, _column_map, _pipeless in malformed:
            out.append(
                finding(
                    "ACCEPTANCE_TABLE",
                    header_line,
                    "§6 has no acceptance table (need a header row whose first cell is "
                    "'#', 'ID' or 'AT' and which names Given, When and Then)",
                    "error",
                )
            )
        return out

    # At least one candidate qualifies: a malformed SIBLING is reported on
    # its own terms -- never silently dropped just because another table
    # in the same section is fine (that used to make a duplicate-column
    # sibling produce zero findings at all).
    for header_line, _header_cells, _body, _column_map, _pipeless in malformed:
        out.append(
            finding(
                "ACCEPTANCE_TABLE",
                header_line,
                "a second acceptance-shaped table's header does not qualify — Given, When "
                "and Then must each appear exactly once (Altitude and Row at most once)",
                "error",
            )
        )

    total_rows = 0
    required_cell_names = ("Given", "When", "Then")
    for header_line, header_cells, body, column_map, _pipeless in qualifying:
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
            for name in required_cell_names:
                idx = column_map[name.lower()]
                if not cells[idx].strip():
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
            finding("ACCEPTANCE_TABLE", qualifying[0][0], "acceptance table has no data rows", "error")
        )
    return out


def check_acceptance_altitude(lines: List[str]) -> List[Dict[str, Any]]:
    """Every qualifying §6 table names each row's altitude.

    ACCEPTANCE_ALTITUDE (error, every status): the ``Altitude`` column is
    present and a data cell is empty or not exactly one of ``data``,
    ``response``, ``perception``, ``judgement``, ``sibling``. A cell that
    is an angle-bracket placeholder (``<altitude>``) is PLACEHOLDER's
    concern, not this rule's, so the bundled template reports it once. A
    row whose cell count differs from the header's is ACCEPTANCE_TABLE's
    concern and is skipped here. ALTITUDE_MISSING (warn): a qualifying
    table has no ``Altitude`` header at all -- an older doc keeps linting,
    and the warning says what to add.
    """
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    out: List[Dict[str, Any]] = []
    for header_line, header_cells, body, column_map, _pipeless in find_acceptance_tables(
        lines, start + 1, end
    ):
        if column_map is None:
            continue
        idx = column_map["altitude"]
        if idx is None:
            out.append(
                finding(
                    "ALTITUDE_MISSING",
                    header_line,
                    "§6 acceptance table has no Altitude column (add one between Then and Row; "
                    "each cell is data, response, perception, judgement or sibling)",
                    "warn",
                )
            )
            continue
        for line_no, cells in body:
            if len(cells) != len(header_cells):
                continue
            value = cells[idx].strip()
            if ANGLE_PLACEHOLDER_RE.fullmatch(value):
                continue
            if not value:
                out.append(
                    finding(
                        "ACCEPTANCE_ALTITUDE",
                        line_no,
                        "acceptance table row's Altitude cell is empty "
                        "(one of data, response, perception, judgement, sibling)",
                        "error",
                    )
                )
            elif value not in ALTITUDES:
                out.append(
                    finding(
                        "ACCEPTANCE_ALTITUDE",
                        line_no,
                        f"acceptance table row's Altitude {value!r} is not one of "
                        "data, response, perception, judgement, sibling",
                        "error",
                    )
                )
    return out


def check_scenarios_count(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: "**Scenarios:**" in l, start=start)
    if idx is None or idx >= end:
        return []
    m = SCENARIOS_RE.search(scan[idx])
    if not m:
        return [
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                "Scenarios: line does not match '<N> acceptance rows (§6), <M> worked examples (§3).'",
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
                f"Scenarios: claims {n_claimed} acceptance rows but §6 has {n_actual}",
                "error",
            )
        )
    ranges, kind = worked_examples(lines)
    if kind is None:
        out.append(
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                "§3 worked-example count not checked (no '### ' headings or bold-led paragraphs found)",
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
                    f"Scenarios: claims {m_claimed} worked examples but §3 has {m_actual}",
                    "error",
                )
            )
    return out


def _why_lines(lines: List[str], n: int) -> List[Tuple[int, str]]:
    """(0-indexed line, value after the colon) of every Why line in section n."""
    bounds = section_bounds(lines, n)
    if bounds is None:
        return []
    start, end = bounds
    scan = unfenced(lines)
    out = []
    for i in range(start, end):
        m = WHY_LINE_RE.match(scan[i].lstrip())
        if m:
            out.append((i, m.group(1).strip()))
    return out


def check_why_line(lines: List[str]) -> List[Dict[str, Any]]:
    """§4-§7 each carry a ``Why — what breaks without it:`` line, and the line
    carries a value. An angle-bracket value (``<one line>``) is a
    placeholder, reported by PLACEHOLDER rather than here, so the template
    lints under ``--template`` and a raw render reports each slot once."""
    out = []
    for n in WHY_SECTIONS:
        bounds = section_bounds(lines, n)
        if bounds is None:
            continue
        found = _why_lines(lines, n)
        if not found:
            out.append(
                finding(
                    "WHY_LINE",
                    bounds[0] + 1,
                    f"§{n} is missing a line beginning 'Why — what breaks without it:'",
                    "error",
                )
            )
            continue
        for i, value in found:
            if not value:
                out.append(
                    finding(
                        "WHY_LINE",
                        i + 1,
                        f"§{n} 'Why — what breaks without it:' has no value",
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
    red-gate commit, as its own header line matching ``RED_GATE_LINE_RE``
    exactly — ``Red gate: <sha> <YYYY-MM-DD>``, sha 7-40 hex characters
    (digits alone qualify), date a real calendar date. Error when `Status:`
    is `building` and no line in the header block (everything before the
    first ``## `` heading, fenced lines excluded the way every other scan
    excludes them) matches it. Position among the header lines is not
    enforced, the line's own shape is: a hex-looking run inside some other
    header value (``Supersedes: deadbeef``, a digit-only ``Last decision:``)
    does not satisfy it, nor does a ``Red gate:`` line sitting inside a
    fenced code block (an illustration, not the doc's own header) — only a
    real, unfenced ``Red gate:`` line with a real date does. A line matching
    the sha/date shape but naming a date that does not exist (a day past
    the last of its month) is reported on its own terms, not silently
    treated as no line at all.
    """
    status = get_status(lines)
    if status != "building":
        return []

    scan = unfenced(lines)
    header_end = find_line_index(scan, lambda l: l.startswith("## "))
    if header_end is None:
        header_end = len(lines)

    bad_date_finding: Optional[Dict[str, Any]] = None
    for i in range(header_end):
        m = RED_GATE_LINE_RE.match(scan[i])
        if not m:
            continue
        date_text = m.group(2)
        try:
            datetime.date.fromisoformat(date_text)
        except ValueError:
            if bad_date_finding is None:
                bad_date_finding = finding(
                    "BUILDING_NEEDS_GATE",
                    i + 1,
                    f"'Red gate:' line found, but {date_text!r} is not a real calendar date",
                    "error",
                )
            continue
        return []  # a real, unfenced Red gate line with a real date clears the rule

    if bad_date_finding is not None:
        return [bad_date_finding]
    return [
        finding(
            "BUILDING_NEEDS_GATE",
            1,
            "arm records the red-gate commit in the header as its own line "
            "'Red gate: <sha> <YYYY-MM-DD>'; none found",
            "error",
        )
    ]


def _agent_notes_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) from the Agent notes line up to ``## 1.``."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: l.startswith(AGENT_NOTES_PREFIX))
    if idx is None:
        return None
    end = find_line_index(scan, lambda l: l.startswith("## 1."), start=idx + 1)
    return idx, end if end is not None else len(lines)


def check_placeholder(lines: List[str], template: bool = False) -> List[Dict[str, Any]]:
    """TBD/TODO-style terms in §0, plus angle-bracket ``<...>`` placeholders
    in §0, the header ``Owner:``/``Last decision:`` values, §6 data cells,
    agent notes, the first line of each §3 worked example, a §9 question's
    owner, and the value of each §4-§7 Why line. The scans are scoped on
    purpose: §5's body may legitimately hold generics such as
    ``Map<string, Row>``, so no whole-document scan is made.

    ``template=True`` exempts angle-bracket placeholders and the literal
    ``YYYY-MM-DD`` (the bundled template's own placeholder shapes) so the
    template can be linted in template mode; the TBD/TODO-style terms stay
    active either way.
    """
    out: List[Dict[str, Any]] = []
    seen_terms = set()
    scan = unfenced(lines)

    bounds = tldr_block_bounds(lines)
    if bounds is not None:
        start, end = bounds
        for i in range(start, end):
            lowered = scan[i].lower()
            for term in PLACEHOLDER_TERMS:
                if term in lowered and term not in seen_terms:
                    seen_terms.add(term)
                    out.append(finding("PLACEHOLDER", i + 1, f"placeholder text {term!r} found in §0", "error"))
            if not template:
                for m in ANGLE_PLACEHOLDER_RE.finditer(scan[i]):
                    out.append(
                        finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in §0", "error")
                    )

    if template:
        return out

    owner_idx = find_line_index(scan, lambda l: "Owner:" in l)
    if owner_idx is not None:
        value = parse_header_field_value(scan, owner_idx, "Owner:", "Last decision:")
        for m in ANGLE_PLACEHOLDER_RE.finditer(value):
            out.append(
                finding(
                    "PLACEHOLDER",
                    owner_idx + 1,
                    f"placeholder {m.group(0)!r} found in the header 'Owner:' value",
                    "error",
                )
            )

    last_decision_idx = find_line_index(scan, lambda l: "Last decision:" in l)
    if last_decision_idx is not None:
        value = parse_header_field_value(scan, last_decision_idx, "Last decision:")
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
                            f"placeholder {m.group(0)!r} found in a §6 data cell",
                            "error",
                        )
                    )

    notes = _agent_notes_bounds(lines)
    if notes is not None:
        for i in range(notes[0] + 1, notes[1]):
            if not NOTE_START_RE.match(scan[i]):
                continue
            for m in ANGLE_PLACEHOLDER_RE.finditer(scan[i]):
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in an agent note", "error")
                )

    ranges, _kind = worked_examples(lines)
    for s, _e in ranges:
        for m in ANGLE_PLACEHOLDER_RE.finditer(scan[s]):
            out.append(
                finding("PLACEHOLDER", s + 1, f"placeholder {m.group(0)!r} found in a §3 worked example", "error")
            )

    bounds9 = section_bounds(lines, 9)
    if bounds9 is not None:
        for i in range(bounds9[0] + 1, bounds9[1]):
            m = OPEN_QUESTION_OWNER_RE.match(scan[i])
            if m:
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(1)!r} found in a §9 owner", "error")
                )

    for n in WHY_SECTIONS:
        for i, value in _why_lines(lines, n):
            for m in ANGLE_PLACEHOLDER_RE.finditer(value):
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in a §{n} Why line", "error")
                )
    return out


def check_agent_notes_many(lines: List[str]) -> List[Dict[str, Any]]:
    notes = _agent_notes_bounds(lines)
    if notes is None:
        return []
    idx, end = notes
    scan = unfenced(lines)
    count = sum(1 for i in range(idx + 1, end) if NOTE_START_RE.match(scan[i]))
    if count > 8:
        return [
            finding(
                "AGENT_NOTES_MANY",
                idx + 1,
                f"§0 has {count} agent notes (consolidate past 8)",
                "warn",
            )
        ]
    return []


def check_human_half_budget(lines: List[str]) -> List[Dict[str, Any]]:
    tldr_bounds = tldr_block_bounds(lines)
    if tldr_bounds is None:
        return []
    start = tldr_bounds[0]
    section2 = section_bounds(lines, 2)
    if section2 is None:
        return []
    _, end_of_2 = section2
    ranges, kind = worked_examples(lines)
    if kind is None:
        end = end_of_2
        measured_note = "§3 not measured (no parseable example found)"
    else:
        end = ranges[0][1]
        measured_note = "through the first §3 example"
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


def check_unclosed_fence(lines: List[str]) -> List[Dict[str, Any]]:
    """FENCE_UNCLOSED (error): a ``` / ~~~ fence opened and never closed.

    Every line after such a fence is read as an illustration by every
    other rule, so the doc would otherwise report a wall of "missing
    heading" findings at line 1 and nothing naming the fence. Reported at
    the opening fence's own line."""
    in_fence = False
    open_line: Optional[int] = None
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            open_line = i + 1 if in_fence else None
    if in_fence and open_line is not None:
        return [
            finding(
                "FENCE_UNCLOSED",
                open_line,
                "fenced code block opened here is never closed, so every line after it "
                "is read as an illustration (no heading, field, table row or placeholder counts)",
                "error",
            )
        ]
    return []


RULE_CHECKS = (
    check_unclosed_fence,
    check_header_status,
    check_header_owner,
    check_contents_line,
    check_headings_bare,
    check_tldr_budget,
    check_tldr_fields,
    check_rules_present,
    check_rules_format,
    check_rules_tagged,
    check_tags_resolve,
    check_at_ids_unique,
    check_acceptance_table,
    check_acceptance_altitude,
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
    """True when ``path`` is UTF-8 text containing the §0 TLDR heading
    outside any fenced code block (a framework or how-to that only shows
    the heading inside a fence is not an outcome doc).

    A file that cannot be read or decoded also counts as True: a directory
    scan surfaces a broken doc as an UNREADABLE finding (via ``lint_file``)
    rather than silently excluding it from the scan.
    """
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError):
        return True
    return any(line.startswith(TLDR_HEADING) for line in unfenced(text.splitlines()))


def collect_directory_docs(root: str) -> List[str]:
    """Every *.md under root containing a §0 TLDR heading, one level of recursion deep."""
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
    # Findings carry '§', '→' and '—'. A console that cannot encode them
    # (a cp1252 pipe on Windows, a C locale) prints '?' in their place
    # rather than dying with UnicodeEncodeError and no findings at all.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

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
