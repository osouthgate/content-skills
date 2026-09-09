#!/usr/bin/env python3
"""Phase 0 orientation for the promise skill.

Resolves the framework path, the project config, the docs home, the
project's type-check/test/lint commands, existing outcome docs, and
CLAUDE.md adoption state, then prints one JSON object to stdout.

See references/architecture.md SS5 (schema and detection rules) and
SS6 (config contract). This script never exits non-zero: every problem
is recorded in the "warnings" list of the emitted JSON instead of
raising or failing the process, so a caller can always parse stdout as
JSON and always finds every schema key present (null when unknown).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

RECOGNISED_MODES = (
    "new", "revise", "review", "merge", "arm", "intake", "reconcile", "adopt",
)

KNOWN_CONFIG_KEYS = {
    "$schema", "$comment", "docsHome", "frameworkPath", "plansFolder",
    "commands", "map",
}

DOCS_HOME_CANDIDATES = (
    "docs/designs", "docs/design", "docs/specs", "docs/rfcs", "design", "docs",
)

TYPE_CHECK_SCRIPT_NAMES = ("type-check", "typecheck", "tsc")

PROMISE_BEGIN_MARKER = "<!-- promise:begin"

TLDR_HEADING = "## 0. TLDR"

H1_RE = re.compile(r"^#\s+(.+?)\s*$")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
LAST_DECISION_RE = re.compile(r"Last decision:\s*(\S+)")
TARGET_NAME_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)")

# --- FEATURE 1: --input mode suggestion (architecture.md SS4 rules 1-10) ---

_MODE_WORD_PUNCT = ".,;:!?'\"()[]{}"

CRITIQUE_VERB_RE = re.compile(
    r"\b(?:review|critique|feedback|check|is this any good)\b", re.IGNORECASE
)
ARM_PHRASE_RE = re.compile(
    r"\b(?:arm|start building|red tests|kick off|file the rows)\b", re.IGNORECASE
)
RECONCILE_PATTERN_RE = re.compile(
    r"#\d+"
    r"|\b[0-9a-f]{7,40}\b"
    r"|\b(?:feat|fix)/"
    r"|\.test\."
    r"|\.spec\."
    r"|/tests/"
    r"|/test/",
    re.IGNORECASE,
)
RECONCILE_PHRASE_RE = re.compile(
    r"\b(?:shipped|landed|already do|already covered)\b"
    r"|isn't .* covered"
    r"|update the (?:map|row)",
    re.IGNORECASE,
)
INTAKE_WORD_RE = re.compile(
    r"\b(?:feedback|complaints|bug reports|wishes|feature requests)\b", re.IGNORECASE
)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")
ADOPT_TRIGGER_RE = re.compile(r"\b(?:set up|setup|install|configure|adopt)\b", re.IGNORECASE)
PROMISE_WORD_RE = re.compile(r"\bpromise\b", re.IGNORECASE)
ROW_ID_TOKEN_RE = re.compile(r"[^\s,;]+")


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings.

    ``utf-8-sig`` strips a leading BOM if present and is otherwise a
    plain UTF-8 decode; the default universal-newlines text mode
    (``newline=None``) normalises CRLF and CR to LF.
    """
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def get_skill_dir() -> str:
    """Return the absolute path to skills/promise (the parent of scripts/)."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(scripts_dir)


def load_config(cwd: str) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Load .claude/promise.config.json, falling back to promise.config.json.

    Returns (raw_config_or_None, path_or_None, warnings). Unknown
    top-level keys warn; "$schema" and "$comment" are always ignored,
    at the top level and wherever else they appear.
    """
    warnings: List[str] = []
    candidates = [
        os.path.join(cwd, ".claude", "promise.config.json"),
        os.path.join(cwd, "promise.config.json"),
    ]
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            raw = json.loads(read_text_tolerant(candidate))
        except (OSError, ValueError) as exc:
            warnings.append(
                f"could not read or parse config at {candidate}: {exc}; using detection"
            )
            return None, candidate, warnings
        if not isinstance(raw, dict):
            warnings.append(
                f"config at {candidate} is not a JSON object; using detection"
            )
            return None, candidate, warnings
        unknown = sorted(k for k in raw.keys() if k not in KNOWN_CONFIG_KEYS)
        for key in unknown:
            warnings.append(f"unknown config key: {key}")
        return raw, candidate, warnings
    warnings.append("no config found at .claude/promise.config.json; using detection")
    return None, None, warnings


def detect_docs_home(cwd: str) -> Optional[str]:
    """Return the first existing candidate docs-home directory, or None."""
    for rel in DOCS_HOME_CANDIDATES:
        if os.path.isdir(os.path.join(cwd, rel)):
            return rel
    return None


def detect_plans_folder(cwd: str) -> Optional[str]:
    """Return "plans" if that directory exists under cwd, else None."""
    return "plans" if os.path.isdir(os.path.join(cwd, "plans")) else None


def _package_manager_prefix(cwd: str) -> str:
    if os.path.isfile(os.path.join(cwd, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.isfile(os.path.join(cwd, "yarn.lock")):
        return "yarn"
    if os.path.isfile(os.path.join(cwd, "bun.lockb")):
        return "bun"
    return "npm run"


def _detect_commands_from_package_json(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "package.json")
    if not os.path.isfile(path):
        return None
    try:
        raw = json.loads(read_text_tolerant(path))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    scripts = raw.get("scripts")
    if not isinstance(scripts, dict):
        return None
    prefix = _package_manager_prefix(cwd)
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in scripts), None)
    result: Dict[str, Optional[str]] = {
        "typeCheck": f"{prefix} {type_check_name}" if type_check_name else None,
        "test": f"{prefix} test" if "test" in scripts else None,
        "lint": f"{prefix} lint" if "lint" in scripts else None,
    }
    return result if any(result.values()) else None


def _parse_target_names(text: str) -> List[str]:
    """Return target/recipe names defined at column 0 of a line.

    Matches Makefile targets (``name:``) and simple justfile recipes
    (``name:``), while a leading tab (a Makefile recipe body) or a
    ``:=`` variable assignment never matches.
    """
    names = []
    for line in text.splitlines():
        m = TARGET_NAME_RE.match(line)
        if m:
            names.append(m.group(1))
    return names


def _detect_commands_from_makefile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "Makefile")
    if not os.path.isfile(path):
        return None
    try:
        targets = set(_parse_target_names(read_text_tolerant(path)))
    except OSError:
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in targets), None)
    result = {
        "typeCheck": f"make {type_check_name}" if type_check_name else None,
        "test": "make test" if "test" in targets else None,
        "lint": "make lint" if "lint" in targets else None,
    }
    return result if any(result.values()) else None


def _detect_commands_from_justfile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = None
    for name in ("justfile", "Justfile"):
        candidate = os.path.join(cwd, name)
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        return None
    try:
        recipes = set(_parse_target_names(read_text_tolerant(path)))
    except OSError:
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in recipes), None)
    result = {
        "typeCheck": f"just {type_check_name}" if type_check_name else None,
        "test": "just test" if "test" in recipes else None,
        "lint": "just lint" if "lint" in recipes else None,
    }
    return result if any(result.values()) else None


def detect_commands(cwd: str) -> Dict[str, Optional[str]]:
    """Detect typeCheck/test/lint commands: package.json, else Makefile, else justfile.

    The first source that yields at least one command wins outright
    (architecture.md SS5's "else" chain is a whole-strategy fallback,
    not a per-field merge across sources).
    """
    for detector in (
        _detect_commands_from_package_json,
        _detect_commands_from_makefile,
        _detect_commands_from_justfile,
    ):
        found = detector(cwd)
        if found:
            found = dict(found)
            found["source"] = "detected"
            return found
    return {"typeCheck": None, "test": None, "lint": None, "source": "none"}


def resolve_commands(cwd: str, config: Optional[dict]) -> Dict[str, Optional[str]]:
    """Config wins outright when it declares a commands object; else detect."""
    if isinstance(config, dict) and isinstance(config.get("commands"), dict):
        raw = config["commands"]
        return {
            "typeCheck": raw.get("typeCheck"),
            "test": raw.get("test"),
            "lint": raw.get("lint"),
            "source": "config",
        }
    return detect_commands(cwd)


def resolve_docs_home(cwd: str, config: Optional[dict]) -> Tuple[Optional[str], str]:
    if isinstance(config, dict) and config.get("docsHome"):
        return config["docsHome"], "config"
    detected = detect_docs_home(cwd)
    if detected is not None:
        return detected, "detected"
    return None, "none"


def resolve_plans_folder(cwd: str, config: Optional[dict]) -> Optional[str]:
    if isinstance(config, dict) and config.get("plansFolder"):
        return config["plansFolder"]
    return detect_plans_folder(cwd)


def resolve_framework_path(cwd: str, config: Optional[dict], skill_dir: str) -> Tuple[str, str]:
    """The project's own framework copy wins when config names one and it exists."""
    if isinstance(config, dict) and config.get("frameworkPath"):
        candidate = config["frameworkPath"]
        abs_candidate = candidate if os.path.isabs(candidate) else os.path.join(cwd, candidate)
        if os.path.isfile(abs_candidate):
            return os.path.abspath(abs_candidate), "project"
    return os.path.join(skill_dir, "outcome-framework.md"), "bundled"


def detect_claude_md(cwd: str) -> Dict[str, Any]:
    """CLAUDE.md at the project root, else .claude/CLAUDE.md, else absent."""
    for candidate in (
        os.path.join(cwd, "CLAUDE.md"),
        os.path.join(cwd, ".claude", "CLAUDE.md"),
    ):
        if os.path.isfile(candidate):
            try:
                text = read_text_tolerant(candidate)
            except OSError:
                text = ""
            return {
                "path": os.path.abspath(candidate),
                "hasPromiseSection": PROMISE_BEGIN_MARKER in text,
            }
    return {"path": None, "hasPromiseSection": False}


def scan_existing_docs(cwd: str, docs_home: Optional[str]) -> List[Dict[str, Any]]:
    """Every *.md directly under docsHome (one level deep) with a SS0 TLDR heading."""
    if not docs_home:
        return []
    docs_dir = os.path.join(cwd, docs_home)
    if not os.path.isdir(docs_dir):
        return []
    results = []
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith(".md"):
            continue
        full = os.path.join(docs_dir, name)
        if not os.path.isfile(full):
            continue
        try:
            text = read_text_tolerant(full)
        except OSError:
            continue
        lines = text.splitlines()
        if not any(line.startswith(TLDR_HEADING) for line in lines):
            continue
        title = None
        status = None
        last_decision = None
        for line in lines:
            if title is None:
                m = H1_RE.match(line)
                if m:
                    title = m.group(1)
            if status is None:
                m = STATUS_RE.match(line)
                if m:
                    status = m.group(1)
            if last_decision is None:
                m = LAST_DECISION_RE.search(line)
                if m:
                    last_decision = m.group(1)
        results.append(
            {
                "path": "/".join([docs_home, name]),
                "title": title,
                "status": status,
                "lastDecision": last_decision,
            }
        )
    return sorted(results, key=lambda d: d["path"])


def _first_word(text: str) -> str:
    """The input's first whitespace-delimited token, lower-cased and unpunctuated."""
    stripped = text.strip()
    if not stripped:
        return ""
    token = stripped.split(None, 1)[0]
    return token.strip(_MODE_WORD_PUNCT).lower()


def _doc_basename_stem(doc: Dict[str, Any]) -> str:
    """A doc's path basename with a trailing .md removed, for substring matching."""
    path = doc.get("path") or ""
    name = os.path.basename(path)
    if name.lower().endswith(".md"):
        name = name[: -len(".md")]
    return name


def _matching_docs(text_lower: str, existing_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """existingDocs whose path basename (sans .md) or title is a substring of the input."""
    matches = []
    for doc in existing_docs:
        basename = _doc_basename_stem(doc).lower()
        title = (doc.get("title") or "").lower()
        if (basename and basename in text_lower) or (title and title in text_lower):
            matches.append(doc)
    return matches


def _doc_label(doc: Dict[str, Any]) -> str:
    """The name to show for a doc in a signal: its title, else its basename."""
    return doc.get("title") or _doc_basename_stem(doc)


def _near(text_lower: str, re_a: re.Pattern[str], re_b: re.Pattern[str], window_chars: int = 30) -> bool:
    """True when some re_a match and some re_b match sit within window_chars of each other."""
    a_spans = [m.span() for m in re_a.finditer(text_lower)]
    if not a_spans:
        return False
    b_spans = [m.span() for m in re_b.finditer(text_lower)]
    if not b_spans:
        return False
    for a_start, a_end in a_spans:
        for b_start, b_end in b_spans:
            gap = max(a_start, b_start) - min(a_end, b_end)
            if gap <= window_chars:
                return True
    return False


def suggest_mode(
    input_text: str,
    existing_docs: List[Dict[str, Any]],
    map_value: Optional[dict],
) -> Tuple[Optional[str], List[str], List[str]]:
    """A mode hint for the --input text (architecture.md SS4's dispatch table).

    Ten rules fire in this fixed order, every match case-insensitive; the
    first rule whose condition holds wins. Returns (suggestedMode, signals,
    extraWarnings) — extraWarnings folds into the caller's own warnings[]
    (currently only rule 7's bad-regex case). This never raises: an input
    that trips nothing falls through to rule 10, because this is a hint for
    the router, not a second router that could itself be "wrong".
    """
    text = input_text or ""
    text_lower = text.lower()
    extra_warnings: List[str] = []

    # Rule 1 — a recognised first word wins outright.
    first = _first_word(text)
    if first in RECOGNISED_MODES:
        return first, ["first word is a mode name"], extra_warnings

    # Rules 2-5 share one existingDocs match set.
    matches = _matching_docs(text_lower, existing_docs)

    if matches and CRITIQUE_VERB_RE.search(text):
        label = _doc_label(matches[0])
        return "review", [f"matches existing doc {label!r} + critique verb"], extra_warnings

    if len(matches) >= 2:
        return "merge", [f"matches {len(matches)} distinct existing docs"], extra_warnings

    if len(matches) == 1:
        doc = matches[0]
        status = (doc.get("status") or "").lower()
        label = _doc_label(doc)
        if status == "agreed" and ARM_PHRASE_RE.search(text):
            return "arm", [f"matches existing doc {label!r} (agreed) + arm phrase"], extra_warnings
        return "revise", [f"matches existing doc {label!r}"], extra_warnings

    # Rule 6 — reconcile: a PR/commit/branch/test-file pattern, or a shipped/landed phrase.
    m = RECONCILE_PATTERN_RE.search(text)
    if m:
        return (
            "reconcile",
            [f"matches a PR/commit/branch/test-file pattern: {m.group(0)!r}"],
            extra_warnings,
        )
    m = RECONCILE_PHRASE_RE.search(text)
    if m:
        return "reconcile", [f"matches a shipped/landed phrase: {m.group(0)!r}"], extra_warnings

    # Rule 7 — intake: the input names a row id shaped by the project's own map.
    if isinstance(map_value, dict) and map_value.get("rowIdPattern"):
        pattern_text = map_value["rowIdPattern"]
        try:
            row_id_re = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            extra_warnings.append(f"bad map.rowIdPattern {pattern_text!r}: {exc}; skipping rule 7")
        else:
            for token in ROW_ID_TOKEN_RE.findall(text):
                candidate = token.strip(_MODE_WORD_PUNCT)
                if candidate and row_id_re.fullmatch(candidate):
                    return (
                        "intake",
                        [f"token {candidate!r} matches map.rowIdPattern"],
                        extra_warnings,
                    )

    # Rule 8 — intake: a list shape, or feedback vocabulary.
    list_item_count = sum(1 for line in text.splitlines() if LIST_ITEM_RE.match(line))
    if list_item_count >= 3:
        return "intake", [f"{list_item_count} list items (>= 3)"], extra_warnings
    m = INTAKE_WORD_RE.search(text)
    if m:
        return "intake", [f"contains intake word {m.group(0)!r}"], extra_warnings

    # Rule 9 — adopt: an install/setup verb near "promise", or the literal CLAUDE.md.
    if "claude.md" in text_lower:
        return "adopt", ["contains 'CLAUDE.md'"], extra_warnings
    if _near(text_lower, ADOPT_TRIGGER_RE, PROMISE_WORD_RE):
        return "adopt", ["adopt trigger word near 'promise'"], extra_warnings

    # Rule 10 — default.
    return "new", ["no stronger signal; default"], extra_warnings


def build_orientation(
    mode_arg: Optional[str], cwd_arg: Optional[str], input_arg: Optional[str] = None
) -> Dict[str, Any]:
    warnings: List[str] = []
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()

    if not mode_arg:
        mode = "new"
    elif mode_arg in RECOGNISED_MODES:
        mode = mode_arg
    else:
        mode = "infer"

    try:
        raw_config, config_path, config_warnings = load_config(cwd)
    except Exception as exc:  # pragma: no cover - defensive, never fail hard
        raw_config, config_path, config_warnings = None, None, [f"config detection failed: {exc}"]
    warnings.extend(config_warnings)

    try:
        docs_home, docs_home_source = resolve_docs_home(cwd, raw_config)
    except Exception as exc:  # pragma: no cover
        docs_home, docs_home_source = None, "none"
        warnings.append(f"docsHome detection failed: {exc}")

    try:
        plans_folder = resolve_plans_folder(cwd, raw_config)
    except Exception as exc:  # pragma: no cover
        plans_folder = None
        warnings.append(f"plansFolder detection failed: {exc}")

    try:
        commands = resolve_commands(cwd, raw_config)
    except Exception as exc:  # pragma: no cover
        commands = {"typeCheck": None, "test": None, "lint": None, "source": "none"}
        warnings.append(f"commands detection failed: {exc}")

    try:
        framework_path, framework_source = resolve_framework_path(cwd, raw_config, skill_dir)
    except Exception as exc:  # pragma: no cover
        framework_path = os.path.join(skill_dir, "outcome-framework.md")
        framework_source = "bundled"
        warnings.append(f"frameworkPath resolution failed: {exc}")

    map_value = raw_config.get("map") if isinstance(raw_config, dict) else None

    try:
        claude_md = detect_claude_md(cwd)
    except Exception as exc:  # pragma: no cover
        claude_md = {"path": None, "hasPromiseSection": False}
        warnings.append(f"claudeMd detection failed: {exc}")

    try:
        existing_docs = scan_existing_docs(cwd, docs_home)
    except Exception as exc:  # pragma: no cover
        existing_docs = []
        warnings.append(f"existingDocs scan failed: {exc}")

    config_loaded = raw_config is not None
    adopted = bool(config_loaded and claude_md.get("hasPromiseSection"))
    if not adopted:
        warnings.append("project not adopted — run /promise adopt")

    suggested_mode: Optional[str] = None
    signals: List[str] = []
    if input_arg is not None:
        try:
            suggested_mode, signals, suggest_warnings = suggest_mode(
                input_arg, existing_docs, map_value
            )
            warnings.extend(suggest_warnings)
        except Exception as exc:  # pragma: no cover - defensive, never fail hard
            suggested_mode, signals = None, []
            warnings.append(f"mode suggestion failed: {exc}")

    return {
        "skillDir": skill_dir,
        "cwd": cwd,
        "mode": mode,
        "frameworkPath": framework_path,
        "frameworkSource": framework_source,
        "config": {
            "path": config_path,
            "loaded": config_loaded,
            "raw": raw_config if config_loaded else {},
        },
        "docsHome": docs_home,
        "docsHomeSource": docs_home_source,
        "plansFolder": plans_folder,
        "commands": commands,
        "map": map_value,
        "claudeMd": claude_md,
        "adopted": adopted,
        "existingDocs": existing_docs,
        "suggestedMode": suggested_mode,
        "signals": signals,
        "warnings": warnings,
    }


def _fallback_result(mode_arg: Optional[str], cwd_arg: Optional[str], error: Exception) -> Dict[str, Any]:
    """Absolute last resort so the process can still print a valid, complete schema."""
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()
    if not mode_arg:
        mode = "new"
    elif mode_arg in RECOGNISED_MODES:
        mode = mode_arg
    else:
        mode = "infer"
    return {
        "skillDir": skill_dir,
        "cwd": cwd,
        "mode": mode,
        "frameworkPath": os.path.join(skill_dir, "outcome-framework.md"),
        "frameworkSource": "bundled",
        "config": {"path": None, "loaded": False, "raw": {}},
        "docsHome": None,
        "docsHomeSource": "none",
        "plansFolder": None,
        "commands": {"typeCheck": None, "test": None, "lint": None, "source": "none"},
        "map": None,
        "claudeMd": {"path": None, "hasPromiseSection": False},
        "adopted": False,
        "existingDocs": [],
        "suggestedMode": None,
        "signals": [],
        "warnings": [f"orient.py internal error: {error}", "project not adopted — run /promise adopt"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orient.py",
        description=(
            "Resolve promise skill Phase 0 orientation (framework, config, "
            "docs home, commands, existing docs, CLAUDE.md adoption) and "
            "print it as one JSON object. Always exits 0."
        ),
    )
    parser.add_argument("--mode", default=None, help="the mode word the skill was invoked with")
    parser.add_argument(
        "--cwd", default=None, help="project root to orient against (default: current directory)"
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "the user's full argument string; when given, the JSON gains "
            "suggestedMode and signals (a router hint, architecture.md SS4)"
        ),
    )
    args = parser.parse_args(argv)

    try:
        result = build_orientation(args.mode, args.cwd, args.input)
    except Exception as exc:  # pragma: no cover - absolute last resort
        result = _fallback_result(args.mode, args.cwd, exc)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
