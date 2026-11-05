#!/usr/bin/env python3
"""Write a cross-harness handoff document, or print a git snapshot.

Stdlib only. Prints HANDOFF_FILE=<path> on success when writing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TARGETS = {
    "cursor": "agent",
    "claude": "claude",
    "codex": "codex",
    "agy": "agy",
    "google": "agy",
}

PLACEHOLDER_KEYS = (
    "TARGET",
    "CLI",
    "TITLE",
    "TIMESTAMP",
    "REPO",
    "CWD",
    "BRANCH",
    "SOURCE_HARNESS",
    "GIT_STATUS",
    "GIT_LOG",
    "SUMMARY",
    "DECISIONS",
    "FILES",
    "REMAINING",
    "FIRST_MOVE",
    "PASTE_PROMPT",
)


def run_git(args: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def detect_cwd(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.cwd().resolve()


def git_root(cwd: Path) -> Path | None:
    out = run_git(["rev-parse", "--show-toplevel"], cwd)
    if not out:
        return None
    return Path(out)


def repo_slug(cwd: Path) -> str:
    root = git_root(cwd)
    if root is not None:
        return root.name
    return cwd.name or "cwd"


def git_snapshot(cwd: Path) -> dict:
    root = git_root(cwd)
    base = root if root is not None else cwd
    branch = run_git(["branch", "--show-current"], base) or "(detached/unknown)"
    status = run_git(["status", "--short", "--branch"], base) or "(not a git repo or git unavailable)"
    log = run_git(["log", "-8", "--oneline", "--decorate"], base) or "(no recent commits)"
    return {
        "cwd": str(cwd),
        "repo": repo_slug(cwd),
        "git_root": str(root) if root else "",
        "branch": branch,
        "status": status,
        "log": log,
    }


def handoff_dir(slug: str) -> Path:
    base = Path.home() / ".local" / "share" / "handoffs" / slug
    base.mkdir(parents=True, exist_ok=True)
    return base


def resolve_target(raw: str) -> tuple[str, str]:
    key = raw.strip().lower()
    if key not in TARGETS:
        aliases = ", ".join(sorted(TARGETS))
        raise SystemExit(f"Unknown target {raw!r}. Supported: {aliases}")
    # Canonicalize google → agy for filenames/display
    canonical = "agy" if key == "google" else key
    return canonical, TARGETS[key]


def load_payload(path: str | None, inline: str | None) -> dict:
    if path and inline:
        raise SystemExit("Pass only one of --payload / --payload-json")
    if path:
        text = Path(path).expanduser().read_text(encoding="utf-8")
        return json.loads(text)
    if inline:
        return json.loads(inline)
    raise SystemExit("Provide --payload PATH or --payload-json JSON")


def as_block(value) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, list):
        if not value:
            return "(none)"
        lines = []
        for item in value:
            s = str(item).strip()
            if not s:
                continue
            if s.startswith("- ") or s.startswith("* ") or re.match(r"^\d+\.", s):
                lines.append(s)
            else:
                lines.append(f"- {s}")
        return "\n".join(lines) if lines else "(none)"
    text = str(value).strip()
    return text if text else "(none)"


def build_paste_prompt(
    handoff_file: Path,
    cwd: Path,
    first_move: str,
) -> str:
    move = first_move.strip() or "Continue from Remaining work in the handoff file."
    return (
        f"Read first: {handoff_file}\n"
        f"Then: {move}\n"
        f"Continue the work in {cwd}. Do not re-litigate decisions already listed."
    )


def fill_template(template: str, values: dict[str, str]) -> str:
    out = template
    for key in PLACEHOLDER_KEYS:
        out = out.replace("{{" + key + "}}", values.get(key, ""))
    return out


def write_handoff(
    *,
    target: str,
    payload: dict,
    cwd: Path,
    title: str | None,
    source_harness: str,
    template_path: Path,
) -> Path:
    canonical, cli = resolve_target(target)
    snap = git_snapshot(cwd)
    now = datetime.now(timezone.utc).astimezone()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    out_dir = handoff_dir(snap["repo"])
    out_path = out_dir / f"{stamp}-{canonical}.md"

    summary = as_block(payload.get("summary"))
    decisions = as_block(payload.get("decisions"))
    files = as_block(payload.get("files"))
    remaining = as_block(payload.get("remaining"))
    first_move = as_block(payload.get("first_move"))
    if first_move == "(none)":
        first_move = "Continue from Remaining work in the handoff file."

    doc_title = (title or payload.get("title") or f"Handoff to {canonical}").strip()
    paste = build_paste_prompt(out_path, cwd, first_move)

    values = {
        "TARGET": canonical,
        "CLI": cli,
        "TITLE": doc_title,
        "TIMESTAMP": now.isoformat(timespec="seconds"),
        "REPO": snap["repo"],
        "CWD": str(cwd),
        "BRANCH": snap["branch"],
        "SOURCE_HARNESS": source_harness or payload.get("source_harness") or "unknown",
        "GIT_STATUS": snap["status"],
        "GIT_LOG": snap["log"],
        "SUMMARY": summary,
        "DECISIONS": decisions,
        "FILES": files,
        "REMAINING": remaining,
        "FIRST_MOVE": first_move,
        "PASTE_PROMPT": paste,
    }

    template = template_path.read_text(encoding="utf-8")
    body = fill_template(template, values)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def default_template() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "handoff.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--git-snapshot",
        action="store_true",
        help="Print git snapshot JSON for the agent; do not write a file",
    )
    parser.add_argument("--cwd", default=None, help="Working directory (default: pwd)")
    parser.add_argument("--target", default=None, help="cursor|claude|codex|agy|google")
    parser.add_argument("--title", default=None, help="Optional handoff title")
    parser.add_argument(
        "--source-harness",
        default=os.environ.get("HANDOFF_SOURCE_HARNESS", "unknown"),
        help="Name of the sending harness (cursor/claude/codex/agy)",
    )
    parser.add_argument("--payload", default=None, help="Path to JSON payload")
    parser.add_argument("--payload-json", default=None, help="Inline JSON payload")
    parser.add_argument(
        "--template",
        default=None,
        help="Template path (default: ../templates/handoff.md)",
    )
    args = parser.parse_args(argv)

    cwd = detect_cwd(args.cwd)

    if args.git_snapshot:
        print(json.dumps(git_snapshot(cwd), indent=2))
        return 0

    if not args.target:
        raise SystemExit("--target is required unless --git-snapshot")

    payload = load_payload(args.payload, args.payload_json)
    template_path = Path(args.template).expanduser() if args.template else default_template()
    if not template_path.is_file():
        raise SystemExit(f"Template not found: {template_path}")

    path = write_handoff(
        target=args.target,
        payload=payload,
        cwd=cwd,
        title=args.title,
        source_harness=args.source_harness,
        template_path=template_path,
    )
    print(f"HANDOFF_FILE={path}")
    # Also emit paste prompt for the skill to surface without re-reading.
    text = path.read_text(encoding="utf-8")
    m = re.search(r"## Paste-ready prompt\n\n```\n(.*?)```", text, re.S)
    if m:
        print("PASTE_PROMPT_BEGIN")
        print(m.group(1).rstrip())
        print("PASTE_PROMPT_END")
    return 0


if __name__ == "__main__":
    sys.exit(main())
