#!/usr/bin/env python3
"""Conservative worktree inventory and explicitly approved removal. Python 3.10+."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

VERSION = 1
ARTIFACTS = {"node_modules", ".next", ".turbo", "__pycache__", ".pytest_cache"}


class Refused(Exception):
    pass


def run(argv, cwd=None, ok=(0,)):
    env = os.environ.copy()
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    # A caller's Git environment must not redirect inspection into another repo.
    for key in list(env):
        if key.startswith("GIT_") and key not in {"GIT_OPTIONAL_LOCKS", "GIT_TERMINAL_PROMPT"}:
            del env[key]
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f"Command unavailable or timed out: {argv[0]}") from exc
    if p.returncode not in ok:
        raise Refused(f"Command failed ({p.returncode}): {argv[0]} {argv[-1]}")
    return p.stdout.decode("utf-8", "surrogateescape")


def git(repo, *args, ok=(0,)):
    return run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                "-c", "protocol.ext.allow=never", "-C", str(repo), *args], ok=ok)


def identity():
    return {"host": socket.gethostname(), "home": str(Path.home().resolve()), "uid": os.getuid()}


def worktrees(repo):
    rows, row = [], {}
    for field in git(repo, "worktree", "list", "--porcelain", "-z").split("\0"):
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


def activity_paths():
    """Best effort: same-user Linux cwd/open descriptors; locks remain authoritative."""
    paths = set()
    if not Path("/proc/self/cwd").exists():
        raise Refused("Linux /proc required for activity checks")
    for proc in Path("/proc").iterdir():
        try:
            if not proc.name.isdigit() or proc.stat().st_uid != os.getuid():
                continue
            links = [proc / "cwd"]
            try:
                links.extend((proc / "fd").iterdir())
            except OSError:
                pass
            for link in links:
                try:
                    value = os.readlink(link)
                    if value.startswith("/"):
                        paths.add(value.removesuffix(" (deleted)"))
                except OSError:
                    pass
        except OSError:
            pass
    return paths


def size(path):
    return int(run(["du", "-sx", "-B1", "--", str(path)]).split()[0])


def repo_context(repo, github):
    repo = str(Path(repo).resolve(strict=True))
    common = str(Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()).resolve())
    base = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD").strip()
    if not base.startswith("refs/remotes/origin/"):
        raise Refused("origin/HEAD does not name an origin branch")
    branch = base.removeprefix("refs/remotes/origin/")
    oid = git(repo, "rev-parse", "--verify", base + "^{commit}").strip()
    url = git(repo, "remote", "get-url", "origin").strip()
    remote = git(repo, "ls-remote", "--exit-code", "origin", "refs/heads/" + branch).split()
    if not remote or remote[0] != oid:
        raise Refused("origin tracking branch is stale; fetch origin, then make a new plan")
    slug = None
    if github:
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?", url)
        if not match:
            raise Refused("--github needs an HTTPS or SSH github.com origin")
        slug = match[1]
    return {"repo": repo, "common": common, "base": base, "base_oid": oid,
            "base_branch": branch, "origin_sha256": hashlib.sha256(url.encode()).hexdigest(),
            "github": github, "slug": slug}


def inspect(ctx, row, cutoff, active, measure=False):
    path = row["worktree"]
    out = {"path": path, "head": row.get("HEAD"), "branch": row.get("branch"), "status": "KEEP"}

    def keep(why):
        out["reason"] = why
        return out

    if row.get("bare") or "locked" in row:
        return keep("bare repository or locked worktree")
    p = Path(path)
    if not p.is_dir() or p.is_symlink() or str(p.resolve()) != path:
        return keep("missing, symlinked or non-canonical path")
    dotgit = p / ".git"
    if not dotgit.is_file() or dotgit.is_symlink():
        return keep("main worktree or unsupported .git entry")
    gd = Path(git(path, "rev-parse", "--absolute-git-dir").strip()).resolve()
    if gd.parent != Path(ctx["common"]) / "worktrees":
        return keep("worktree registration does not match repository")
    if any(a == path or a.startswith(path + os.sep) for a in active):
        return keep("live process has its cwd or an open file here")
    if (p / ".keep-worktree").exists():
        return keep(".keep-worktree marker")
    for marker in ("index.lock", "HEAD.lock", "rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG"):
        if (gd / marker).exists():
            return keep("Git operation in progress")
    latest = max(q.stat().st_mtime for q in (p, gd, gd / "HEAD", gd / "index", gd / "logs/HEAD") if q.exists())
    if latest > cutoff:
        return keep("recent checkout or Git activity")
    if git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"):
        return keep("tracked changes or untracked files")
    ignored = [x for x in git(path, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z").split("\0") if x]
    # Only explicitly recognisable build/cache trees may be discarded with the checkout.
    protected = [x for x in ignored if not any(part in ARTIFACTS for part in Path(x.rstrip("/")).parts)]
    if protected:
        return keep("protected ignored files/directories (including possible secrets or saved data)")
    if git(path, "ls-files", "--stage").find("160000 ") >= 0:
        return keep("submodules require manual review")
    prs = []
    if ctx["github"] and out["branch"]:
        prs = json.loads(run(["gh", "pr", "list", "--repo", ctx["slug"], "--head",
                              out["branch"].removeprefix("refs/heads/"), "--state", "all",
                              "--limit", "100", "--json", "state,headRefOid,baseRefName,url"]))
        if any(pr["state"] == "OPEN" for pr in prs):
            return keep("open pull request")
    # rev-list errors must refuse removal rather than be mistaken for integration.
    integrated = git(ctx["repo"], "rev-list", "--count", ctx["base_oid"] + ".." + out["head"]).strip() == "0"
    proof = "ancestor of current origin default branch" if integrated else None
    if not integrated:
        matches = [pr for pr in prs if pr["state"] == "MERGED" and pr["headRefOid"] == out["head"] and pr["baseRefName"] == ctx["base_branch"]]
        if matches:
            proof = "exact HEAD of merged PR into default branch: " + matches[0]["url"]
    if proof is None:
        return keep("HEAD not proven integrated; closed PRs and pushed branches are insufficient")
    st = p.stat()
    out.update(status="REMOVE", reason=proof, gitdir=str(gd), device=st.st_dev, inode=st.st_ino,
               ignored_artifacts=ignored)
    if measure:
        out["bytes"] = size(path)
    return out


def scan(repos, github, age, measure=True):
    now = time.time()
    active = activity_paths()
    result = {"version": VERSION, "kind": "worktree-cleanup", "identity": identity(),
              "created": now, "cutoff": now - age * 86400, "repos": [], "items": [], "errors": []}
    seen = set()
    for repo in repos:
        try:
            ctx = repo_context(repo, github)
            if ctx["common"] in seen:
                continue
            seen.add(ctx["common"])
            result["repos"].append(ctx)
            for row in worktrees(ctx["repo"]):
                try:
                    item = inspect(ctx, row, result["cutoff"], active, measure)
                except (Refused, OSError, ValueError) as exc:
                    item = {"path": row["worktree"], "status": "KEEP", "reason": str(exc)}
                if measure and "bytes" not in item and Path(row["worktree"]).is_dir():
                    try:
                        item["bytes"] = size(row["worktree"])
                    except Refused:
                        item["size_error"] = "size unavailable"
                item["repo"] = ctx["repo"]
                result["items"].append(item)
        except (Refused, OSError, ValueError) as exc:
            result["errors"].append({"repo": repo, "error": str(exc)})
            # Still show the inventory when remote proof is unavailable. Nothing is eligible.
            try:
                for row in worktrees(repo):
                    result["items"].append({"repo": repo, "path": row["worktree"],
                                            "status": "KEEP", "reason": str(exc)})
            except Refused:
                pass
    return result


def save_plan(plan, output):
    data = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def load_plan(path, approval):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != approval:
        raise Refused("Approval digest does not match this plan")
    plan = json.loads(data)
    if plan.get("version") != VERSION or plan.get("kind") != "worktree-cleanup" or plan.get("identity") != identity():
        raise Refused("Wrong plan type, version, machine or user")
    age = time.time() - plan["created"]
    if not 0 <= age <= 3600:
        raise Refused("Plan expired (one hour); scan and review again")
    if not 0 <= plan["cutoff"] <= plan["created"]:
        raise Refused("Invalid activity cutoff")
    return plan


def apply(plan):
    contexts = {}
    for old in plan["repos"]:
        ctx = repo_context(old["repo"], old["github"])
        if ctx != old:
            raise Refused("Repository or default branch changed; make a new plan")
        contexts[ctx["repo"]] = ctx

    def verify(item):
        if item.get("status") != "REMOVE":
            raise Refused("Plan contains an unapproved KEEP item")
        ctx = contexts[item["repo"]]
        rows = [r for r in worktrees(ctx["repo"]) if r["worktree"] == item["path"]]
        if len(rows) != 1:
            raise Refused("Worktree registration changed")
        fresh = inspect(ctx, rows[0], plan["cutoff"], activity_paths())
        for key in ("status", "head", "branch", "gitdir", "device", "inode", "reason", "ignored_artifacts"):
            if fresh.get(key) != item.get(key):
                raise Refused(f"Worktree changed or is no longer eligible: {item['path']} ({fresh.get('reason')})")

    if not plan["items"]:
        raise Refused("Empty removal plan")
    # Preflight the entire selection before changing anything, then recheck each removal.
    for item in plan["items"]:
        verify(item)
    for item in plan["items"]:
        verify(item)
        git(item["repo"], "worktree", "remove", "--", item["path"])
        print(json.dumps({"removed": item["path"], "branch_preserved": item["branch"]}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("report", "plan"):
        s = sub.add_parser(name)
        s.add_argument("repos", nargs="+")
        s.add_argument("--github", action="store_true", help="Check open PRs and exact merged PR heads (requires gh)")
        s.add_argument("--min-age-days", type=float, default=2)
        if name == "plan":
            s.add_argument("--select", action="append", required=True, help="Exact worktree path; repeat to select")
            s.add_argument("--output", required=True)
    a = sub.add_parser("apply")
    a.add_argument("plan")
    a.add_argument("--approve", required=True, help="SHA256 of the reviewed plan")
    args = p.parse_args()
    try:
        if args.command == "apply":
            apply(load_plan(args.plan, args.approve))
            return 0
        if not math.isfinite(args.min_age_days) or args.min_age_days < 0:
            raise Refused("Minimum age must be finite and non-negative")
        result = scan(args.repos, args.github, args.min_age_days)
        if args.command == "plan":
            if result["errors"]:
                raise Refused(json.dumps(result["errors"]))
            selected = {str(Path(x).absolute()) for x in args.select}
            items = [x for x in result["items"] if x["path"] in selected]
            if {x["path"] for x in items} != selected or any(x["status"] != "REMOVE" for x in items):
                raise Refused("Every selected path must be an eligible REMOVE row; nothing planned")
            result["items"] = items
            digest = save_plan(result, args.output)
            result["approval_sha256"] = digest
            result["plan_file"] = args.output
        print(json.dumps(result, indent=2))
        return 1 if result["errors"] else 0
    except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
