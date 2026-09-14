#!/usr/bin/env python3
"""Extract one outcome doc's §0 rules and §6 acceptance rows as JSON.

    python3 outcome_rows.py doc.md
    python3 outcome_rows.py doc.md --json
    python3 outcome_rows.py doc.md --write-counts
    python3 outcome_rows.py --search "<text>" --dir <docsHome>
    python3 outcome_rows.py --search-file <path> --dir <docsHome>

This is the bridge's input (references/architecture.md §10): what
``arm`` reads to file §6 rows into a capability map, and what
``reconcile`` reads to re-stamp §0 tags. Reuses lint_outcome.py's rule
and table parsing rather than re-implementing it, so the two scripts
cannot silently disagree on what a rule or a row is. Each row carries
its ``altitude`` — the §6 table's ``Altitude`` cell as lint_outcome.py
reads it by header name, or null when the table has no such column or
the cell is empty.

``--search`` takes its query inline; ``--search-file <path>`` (``-`` =
stdin) reads it from a file instead, so a verbatim feedback item that
may carry quotes never has to appear on a command line. ``--dir`` names
the docs folder to scan: the folder plus its immediate subdirectories,
the same depth lint_outcome.py walks in directory mode. A ``--dir`` that
does not exist or is not a directory is a refusal (exit 2), never a
silent "no matches".

Exit 0 on success; 2 on a usage error, an unreadable doc (missing, or not
UTF-8), or a doc whose ``**Scenarios:**`` line cannot be rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_outcome  # noqa: E402  (sibling-script import; see path insert above)

UTF8_BOM = b"\xef\xbb\xbf"

WORKED_EXAMPLE_NOUN_RE = re.compile(r"(\s*)worked examples?")


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings."""
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def extract(path: str) -> Dict[str, Any]:
    lines = read_text_tolerant(path).splitlines()

    status = lint_outcome.get_status(lines)
    records, _, _ = lint_outcome.parse_rules_block(lines)
    # tags is ["UNTESTED"] or the list of AT ids per the schema; a rule with
    # no resolvable tag (a malformed doc lint_outcome.py would flag via
    # RULES_TAGGED) has neither shape, so it is represented as [] rather
    # than guessed at.
    rules = [
        {
            "index": i + 1,
            "text": r["text"],
            "tags": r["tags"] if r["tags"] is not None else [],
        }
        for i, r in enumerate(records)
    ]

    rows = [
        {
            "id": row["id"],
            "given": row["given"],
            "when": row["when"],
            "then": row["then"],
            "altitude": row["altitude"],
            "row": row["row"],
        }
        for row in lint_outcome.parse_acceptance_rows(lines)
    ]

    signal = lint_outcome.parse_signal(lines)

    return {
        "path": path,
        "status": status,
        "rules": rules,
        "rows": rows,
        "signal": signal,
    }


def locate_scenarios_line(lines: List[str]) -> int:
    """0-indexed index of the §0 **Scenarios:** line, or -1 when there is none."""
    bounds = lint_outcome.tldr_block_bounds(lines)
    if bounds is None:
        return -1
    start, end = bounds
    idx = lint_outcome.find_line_index(lines, lambda l: "**Scenarios:**" in l, start=start)
    if idx is None or idx >= end:
        return -1
    return idx


def rewrite_scenarios_line(line: str, lines: List[str]) -> str:
    """`line` with its two counts replaced by the real §6/§3 counts, and
    the worked-example noun pluralised to match.

    Reuses lint_outcome.py's own SCENARIOS_RE, parse_acceptance_rows and
    worked_examples, so this can never disagree with what the lint counts.
    Only the two digit spans and the ``worked example(s)`` noun right
    after the second are touched — everything else on the line, including
    the "(§6)"/"(§3)" citations and trailing punctuation, is copied
    through unchanged. The worked-example count (M) is left as-is when §3
    is not parseable the way lint_outcome.py counts it (no ``### ``
    headings or bold-led paragraphs), matching SCENARIOS_COUNT's own "not
    checked" case for that half of the line.
    """
    m = lint_outcome.SCENARIOS_RE.search(line)
    if not m:
        raise ValueError(
            "the **Scenarios:** line does not match "
            "'<N> acceptance rows (§6), <M> worked example(s) (§3).'"
        )
    n_actual = len(lint_outcome.parse_acceptance_rows(lines))
    ranges, kind = lint_outcome.worked_examples(lines)
    m_value = len(ranges) if kind is not None else int(m.group(2))
    tail = line[m.end(2):]
    noun = "worked example" if m_value == 1 else "worked examples"
    tail = WORKED_EXAMPLE_NOUN_RE.sub(lambda nm: f"{nm.group(1)}{noun}", tail, count=1)
    return (
        line[: m.start(1)] + str(n_actual) + line[m.end(1) : m.start(2)]
        + str(m_value) + tail
    )


def write_counts(path: str) -> Tuple[str, str]:
    """Rewrite path's **Scenarios:** counts in place; return (old_line, new_line).

    Preserves the file's own line endings (CRLF is kept as CRLF), its
    leading BOM if it had one, and whether it ended in a trailing newline.
    Raises ValueError (never lets a malformed doc corrupt itself) when
    there is no **Scenarios:** line to rewrite, or its shape does not
    parse — the caller turns that into the documented exit-2 refusal.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    has_bom = raw.startswith(UTF8_BOM)
    text = raw.decode("utf-8-sig")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    trailing_newline = normalised.endswith("\n")
    lines = normalised.splitlines()

    idx = locate_scenarios_line(lines)
    if idx == -1:
        raise ValueError("doc has no **Scenarios:** line")

    old_line = lines[idx]
    new_line = rewrite_scenarios_line(old_line, lines)
    lines[idx] = new_line

    body = newline.join(lines)
    if trailing_newline:
        body += newline
    out = body.encode("utf-8")
    if has_bom:
        out = UTF8_BOM + out
    with open(path, "wb") as fh:
        fh.write(out)

    return old_line, new_line


# ---------------------------------------------------------------------------
# --search: rank §6 rows and §0 rules against a query by token overlap
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "by", "at", "as", "it", "this", "that",
}

_TOKEN_RE = re.compile(r"\w+")
_STEM_SUFFIXES = ("ing", "es", "ed", "s")


def _stem(word: str) -> str:
    """Strip a trailing s/es/ed/ing when what is left is >= 4 chars.

    Longest suffix first, so "boxes" loses "es" (-> "box") rather than
    just its trailing "s" (-> "boxe"); "es" and "ed" cannot both match one
    word, so their relative order does not matter.
    """
    for suffix in _STEM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> List[str]:
    """Lower-case, split on non-word characters, drop stop words, light-stem."""
    words = _TOKEN_RE.findall(text.lower())
    return [_stem(w) for w in words if w not in STOP_WORDS]


def contains_tldr_heading(path: str) -> bool:
    """True when path's text has a line starting the §0 TLDR heading outside
    any ``` / ~~~ fence — a fenced heading is an illustration, not structure."""
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError):
        return False
    return any(
        line.startswith(lint_outcome.TLDR_HEADING)
        for line in lint_outcome.unfenced(text.splitlines())
    )


def collect_search_docs(directory: str) -> List[str]:
    """Every *.md under directory with a §0 TLDR heading, one level of
    recursion deep — the folder and its immediate subdirectories.

    Delegates to lint_outcome.py's collect_directory_docs so ``--search``
    and ``lint_outcome.py <directory>`` always agree on which files are
    outcome docs and how deep a docs folder goes. An unreadable directory
    yields no docs rather than raising.
    """
    if not os.path.isdir(directory):
        return []
    try:
        return lint_outcome.collect_directory_docs(directory)
    except OSError:
        return []


def search_candidates(doc_path: str) -> List[Dict[str, Any]]:
    """Every §6 row (by its Then) and §0 rule in one doc, as scorable candidates."""
    try:
        lines = read_text_tolerant(doc_path).splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    candidates: List[Dict[str, Any]] = []
    for row in lint_outcome.parse_acceptance_rows(lines):
        candidates.append({"doc": doc_path, "kind": "row", "id": row["id"], "text": row["then"]})
    records, _, _ = lint_outcome.parse_rules_block(lines)
    for i, record in enumerate(records):
        candidates.append({"doc": doc_path, "kind": "rule", "id": i + 1, "text": record["text"]})
    return candidates


def score_candidates(query: str, directory: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Rank every row/rule candidate under directory by token overlap with query.

    Score = matched query tokens / total query tokens (both de-duplicated,
    so a repeated query word does not inflate its own weight). Only
    candidates that score above zero are kept; ties break on doc path,
    then id. Returns at most `limit` results — never raises and never
    requires a positive score, matching the documented "no matches" case.
    """
    query_tokens = set(tokenize(query))
    scored: List[Dict[str, Any]] = []
    if query_tokens:
        for doc_path in collect_search_docs(directory):
            for cand in search_candidates(doc_path):
                cand_tokens = set(tokenize(cand["text"]))
                overlap = len(query_tokens & cand_tokens)
                if overlap == 0:
                    continue
                score = round(overlap / len(query_tokens), 2)
                if score > 0:
                    scored.append({**cand, "score": score})
    scored.sort(key=lambda c: (-c["score"], c["doc"], str(c["id"])))
    return scored[:limit]


def read_search_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    """The query text in ``path`` (``-`` = stdin), or ``(None, reason)``.

    Read as UTF-8 tolerating a BOM; only trailing line terminators are
    dropped, since they are the file's, not the query's.
    """
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            # newline="" keeps an interior CRLF as written; universal-newlines
            # mode (newline=None) would rewrite it to LF before the child saw it.
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read --search-file {path!r}: {exc}"
    return text.rstrip("\r\n"), None


def format_search_human(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "no matches"
    out = []
    for r in results:
        label = r["id"] if r["kind"] == "row" else f"rule {r['id']}"
        out.append(f"{r['doc']} {label} {r['score']:.2f} {r['text'][:90]}")
    return "\n".join(out)


def format_human(data: Dict[str, Any]) -> str:
    out = [f"path:   {data['path']}", f"status: {data['status']}", ""]

    out.append("Rules:")
    if data["rules"]:
        idx_w = max(len(str(r["index"])) for r in data["rules"])
        tag_w = max(len(", ".join(r["tags"])) for r in data["rules"])
        for r in data["rules"]:
            tags_text = ", ".join(r["tags"])
            out.append(f"  {r['index']:>{idx_w}}  {tags_text:<{tag_w}}  {r['text']}")
    else:
        out.append("  (none)")

    out.append("")
    out.append("Rows:")
    if data["rows"]:
        id_w = max(len(r["id"]) for r in data["rows"])
        given_w = max(len(r["given"]) for r in data["rows"])
        when_w = max(len(r["when"]) for r in data["rows"])
        then_w = max(len(r["then"]) for r in data["rows"])
        altitude_w = max(len(r["altitude"] or "-") for r in data["rows"])
        for r in data["rows"]:
            row_text = r["row"] or "-"
            altitude_text = r["altitude"] or "-"
            out.append(
                f"  {r['id']:<{id_w}}  {r['given']:<{given_w}}  "
                f"{r['when']:<{when_w}}  {r['then']:<{then_w}}  "
                f"{altitude_text:<{altitude_w}}  {row_text}"
            )
    else:
        out.append("  (none)")

    out.append("")
    out.append(f"Signal: {data['signal']}")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="outcome_rows.py",
        description=(
            "Extract an outcome doc's §0 rules and §6 acceptance rows. "
            "--write-counts corrects the doc's Scenarios: line in place; "
            "--search --dir ranks §6 rows and §0 rules across a directory "
            "of docs by token overlap with a query, in lieu of a capability map."
        ),
    )
    parser.add_argument(
        "path", nargs="?", default=None, help="path to the outcome doc (omit with --search)"
    )
    parser.add_argument("--json", action="store_true", help="print as JSON")
    parser.add_argument(
        "--write-counts",
        action="store_true",
        help=(
            "rewrite the doc's **Scenarios:** counts from the real §6 row count "
            "(and the §3 example count, when §3 is parseable), in place; "
            "prints 'old: ... / new: ...' to stderr"
        ),
    )
    parser.add_argument(
        "--search",
        metavar="TEXT",
        default=None,
        help="rank §6 rows and §0 rules across --dir by token overlap with TEXT",
    )
    parser.add_argument(
        "--search-file",
        metavar="PATH",
        default=None,
        help=(
            "like --search, but read the query from PATH ('-' for stdin); use it "
            "whenever the text may contain quotes, so it never passes through a shell"
        ),
    )
    parser.add_argument(
        "--dir",
        metavar="DIRECTORY",
        default=None,
        help=(
            "docs folder to scan for --search: the folder and its immediate "
            "subdirectories (every *.md with a §0 TLDR heading)"
        ),
    )
    args = parser.parse_args(argv)

    if args.search is not None and args.search_file is not None:
        print("outcome_rows.py: --search and --search-file cannot be combined", file=sys.stderr)
        return 2

    query = args.search
    if args.search_file is not None:
        query, reason = read_search_file(args.search_file)
        if query is None:
            print(f"outcome_rows.py: {reason}", file=sys.stderr)
            return 2

    if query is not None:
        if args.dir is None:
            print("outcome_rows.py: --search requires --dir", file=sys.stderr)
            return 2
        if not os.path.isdir(args.dir):
            print(f"outcome_rows.py: --dir is not a directory: {args.dir}", file=sys.stderr)
            return 2
        results = score_candidates(query, args.dir)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(format_search_human(results))
        return 0

    if args.path is None:
        print("outcome_rows.py: a doc path is required (or use --search --dir)", file=sys.stderr)
        return 2

    if not os.path.isfile(args.path):
        print(f"outcome_rows.py: no such file: {args.path}", file=sys.stderr)
        return 2

    if args.write_counts:
        try:
            old_line, new_line = write_counts(args.path)
        except (OSError, ValueError) as exc:
            print(f"outcome_rows.py: {exc}", file=sys.stderr)
            return 2
        print(f"old: {old_line} / new: {new_line}", file=sys.stderr)

    try:
        data = extract(args.path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"outcome_rows.py: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_human(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
