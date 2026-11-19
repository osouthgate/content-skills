#!/usr/bin/env python3
"""Read-only search for Git worktrees under explicit directory roots. Python 3.10+."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

VERSION = 1
PRUNE = {
    "node_modules", ".pnpm", ".cache", ".npm", ".cargo", ".rustup", ".local",
    "__pycache__", ".venv", "venv", "site-packages", ".next", ".turbo",
    "proc", "sys", "dev", "run",
}
VIRTUAL = (Path("/proc"), Path("/sys"), Path("/dev"), Path("/run"))


class Refused(Exception):
    pass


def git_env():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_") and key not in {"GIT_OPTIONAL_LOCKS", "GIT_TERMINAL_PROMPT"}:
            del env[key]
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    return env


def run_git(argv):
    try:
        proc = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
             "-c", "protocol.ext.allow=never", *argv],
            env=git_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused("git unavailable or timed out") from exc
    if proc.returncode != 0:
        raise Refused("git failed")
    return proc.stdout.decode("utf-8", "surrogateescape")


def parse_worktrees(text):
    rows, row = [], {}
    for field in text.split("\0"):
        if not field:
            if row:
                rows.append(row)
                row = {}
            continue
        key, _, value = field.partition(" ")
        row[key] = value if value else True
    if row:
        rows.append(row)
    return rows


def worktrees(repo):
    return parse_worktrees(run_git(["-C", str(repo), "worktree", "list", "--porcelain", "-z"]))


def normalize_root(root):
    path = Path(root)
    if not path.is_absolute():
        raise Refused("Discover root must be an absolute path")
    if path.is_symlink():
        raise Refused("Discover root must not be a symlink")
    if not path.is_dir():
        raise Refused("Discover root must be a directory")
    if any(path == banned or path.is_relative_to(banned) for banned in VIRTUAL):
        raise Refused("Refusing to search virtual filesystems")
    return path


def walk(root):
    """Return checkout directories, skipped mount points, and unreadable paths."""
    found, skipped, errors = [], [], []
    device = root.stat().st_dev
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            errors.append({"path": str(directory), "error": exc.strerror or str(exc)})
            continue
        for entry in entries:
            try:
                if entry.name == ".git":
                    if entry.is_symlink():
                        errors.append({"path": entry.path, "error": "symlinked .git"})
                    elif entry.is_file(follow_symlinks=False) or entry.is_dir(follow_symlinks=False):
                        found.append(str(directory))
                    continue
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False) or entry.name in PRUNE:
                    continue
                if entry.stat(follow_symlinks=False).st_dev != device:
                    skipped.append({"path": entry.path, "reason": "different filesystem"})
                    continue
            except OSError as exc:
                errors.append({"path": entry.path, "error": exc.strerror or str(exc)})
                continue
            stack.append(Path(entry.path))
    return found, skipped, errors


def linked_gitdir(path):
    dot = Path(path) / ".git"
    if dot.is_symlink() or not dot.is_file():
        return None
    line = dot.read_text(encoding="utf-8", errors="replace").splitlines()
    if not line or not line[0].strip().startswith("gitdir:"):
        return None
    raw = line[0].split(":", 1)[1].strip()
    gitdir = Path(raw)
    if not gitdir.is_absolute():
        gitdir = Path(path) / gitdir
    return Path(os.path.abspath(gitdir))


def kind_of(path):
    dot = Path(path) / ".git"
    if dot.is_symlink():
        return None
    if dot.is_dir():
        return "main"
    gitdir = linked_gitdir(path)
    if gitdir is None:
        return None
    parts = set(gitdir.parts)
    if "worktrees" in parts:
        return "linked"
    return None


def choose_repo(rows):
    for row in rows:
        if row.get("bare") or "worktree" not in row:
            continue
        dot = Path(row["worktree"]) / ".git"
        if dot.is_dir() and not dot.is_symlink():
            return row["worktree"]
    for row in rows:
        if not row.get("bare") and row.get("worktree") and Path(row["worktree"]).is_dir():
            return row["worktree"]
    return None


def common_guess(path, kind):
    if kind == "main":
        return os.path.normpath(Path(path) / ".git")
    gitdir = linked_gitdir(path)
    if gitdir is not None and gitdir.parent.name == "worktrees":
        return os.path.normpath(gitdir.parent.parent)
    return None


def registered_rows(common, checkouts):
    for path in checkouts:
        try:
            return worktrees(path)
        except Refused:
            continue
    return parse_worktrees(run_git(["--git-dir", common, "worktree", "list", "--porcelain", "-z"]))


def hunt(roots):
    roots = [normalize_root(root) for root in roots]
    found, skipped, errors = [], [], []
    for root in roots:
        one_found, one_skipped, one_errors = walk(root)
        found.extend(one_found)
        skipped.extend(one_skipped)
        errors.extend(one_errors)

    groups = {}
    for path in found:
        kind = kind_of(path)
        if kind is None:
            continue
        guess = common_guess(path, kind)
        try:
            common = os.path.normpath(run_git(
                ["-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"]).strip())
        except Refused:
            common = guess
        if common is None:
            errors.append({"path": path, "error": "git checkout could not be identified"})
            continue
        groups.setdefault(common, []).append(path)

    repos, unregistered = [], []
    for common, paths in groups.items():
        try:
            rows = registered_rows(common, paths)
        except Refused as exc:
            for path in paths:
                errors.append({"path": path, "error": str(exc)})
            continue
        registered = {os.path.normpath(row["worktree"]) for row in rows if row.get("worktree")}
        for path in paths:
            if os.path.normpath(path) not in registered:
                unregistered.append({
                    "path": path,
                    "common": common,
                    "reason": "checkout is not registered with git worktree list",
                })
        repo = choose_repo(rows)
        if repo:
            repos.append({"path": repo, "common": common})
    return {
        "version": VERSION,
        "kind": "worktree-hunt",
        "roots": [str(root) for root in roots],
        "repos": repos,
        "unregistered": unregistered,
        "skipped": skipped,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="Absolute directory to search; repeat for several roots")
    args = parser.parse_args()
    try:
        print(json.dumps(hunt(args.roots), indent=2))
        return 0
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
