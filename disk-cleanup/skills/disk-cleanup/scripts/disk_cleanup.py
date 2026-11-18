#!/usr/bin/env python3
"""Read-only disk/Docker review, selected cache files, and approved Docker clean-up."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

VERSION = 1
# Download caches only. No app profiles, model stores, package build checkouts or databases.
CACHES = {"pip": ".cache/pip", "mise-downloads": ".cache/mise/invocation-downloads",
          "mise-cas": ".cache/mise/downloads-cas"}
ID = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class Refused(Exception):
    pass


def run(argv):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f"Command unavailable or timed out: {argv[0]}") from exc
    if p.returncode:
        # Do not emit raw daemon responses, which can include application details.
        raise Refused(f"Command failed ({p.returncode}): {' '.join(argv[:4])}")
    return p.stdout


def identity():
    return {"host": socket.gethostname(), "home": str(Path.home().resolve()), "uid": os.getuid()}


def local_endpoint(endpoint):
    return endpoint.startswith("unix:///") or endpoint.startswith("npipe://")


def docker_target(context=None):
    # Pin a context for every command; do not accidentally clean a remote daemon.
    if os.environ.get("DOCKER_HOST"):
        raise Refused("Unset DOCKER_HOST and select an explicit local Docker context first")
    context = context or run(["docker", "context", "show"]).strip()
    if not context or context.startswith("-"):
        raise Refused("Invalid Docker context")
    endpoint = json.loads(run(["docker", "context", "inspect", context, "--format", "{{json .Endpoints.docker.Host}}"] ))
    if not local_endpoint(endpoint):
        raise Refused("Remote Docker endpoints are report-only; use a local context for plans")
    daemon = json.loads(run(["docker", "--context", context, "info", "--format", "{{json .ID}}"] ))
    if not daemon:
        raise Refused("Docker daemon identity unavailable")
    return {"context": context, "endpoint": endpoint, "daemon_id": daemon}


def docker(target, *args):
    return run(["docker", "--context", target["context"], *args])


def builder_info(target):
    # The implicit builder for a context has that context's name. Do not use the
    # selected builder or BUILDX_BUILDER, which can point outside this daemon.
    name = target["context"]
    text = docker(target, "buildx", "inspect", name)
    names = re.findall(r"^Name:\s+(.+)$", text, re.MULTILINE)
    drivers = re.findall(r"^Driver:\s+(.+)$", text, re.MULTILINE)
    endpoints = re.findall(r"^Endpoint:\s+(.+)$", text, re.MULTILINE)
    if not names or names[0].strip() != name or drivers != ["docker"] or len(endpoints) != 1:
        raise Refused("Build-cache clean-up requires the context's single-node built-in docker builder")
    endpoint = endpoints[0].strip()
    if endpoint not in {target["context"], target["endpoint"]}:
        raise Refused("Builder endpoint does not match the approved local Docker context")
    help_text = docker(target, "buildx", "prune", "--help")
    if "--reserved-space" not in help_text or "--builder" not in help_text:
        raise Refused("This Buildx version lacks the required builder and reserved-space options")
    return {"name": name, "driver": "docker", "endpoint": endpoint, "reserved_space": "10GB"}


def timestamp(value):
    # Docker emits up to nine fractional digits; datetime accepts microseconds.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def container_info(target, object_id, cutoff):
    if not ID.fullmatch(object_id):
        raise Refused("Container selection requires a full 64-character ID")
    template = '{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},"created":{{json .Created}},"state":{{json .State.Status}},"finished":{{json .State.FinishedAt}},"started":{{json .State.StartedAt}},"restart":{{json .HostConfig.RestartPolicy.Name}}}'
    item = json.loads(docker(target, "container", "inspect", "--format", template, object_id))
    if item["state"] not in {"exited", "dead"} or item["restart"] not in {"", "no"}:
        raise Refused("Selected container is active, restart-managed, or has never exited")
    if timestamp(item["created"]) > cutoff or timestamp(item["finished"]) > cutoff:
        raise Refused("Selected container was created or stopped too recently")
    return {"kind": "container", **item}


def image_info(target, object_id, cutoff):
    if not ID.fullmatch(object_id):
        raise Refused("Image selection requires a full sha256 ID")
    template = '{"id":{{json .Id}},"created":{{json .Created}},"tags":{{json .RepoTags}},"digests":{{json .RepoDigests}}}'
    item = json.loads(docker(target, "image", "inspect", "--format", template, object_id))
    if item["tags"] or item["digests"] or timestamp(item["created"]) > cutoff:
        raise Refused("Only old, untagged, undigested images can be selected")
    if docker(target, "container", "ls", "--all", "--quiet", "--filter", "ancestor=" + item["id"]).strip():
        raise Refused("Selected image is referenced by a container")
    return {"kind": "image", **item}


def cache_root(name):
    if name not in CACHES:
        raise Refused("Unknown cache name")
    home = Path.home().resolve()
    path = home / CACHES[name]
    # Do not traverse symlinks at any level of the allowed cache root.
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents] if p != home):
        raise Refused("Cache root or parent is symlinked")
    return path


def fingerprint(path):
    s = path.lstat()
    if not path.is_file() or path.is_symlink() or s.st_uid != os.getuid() or s.st_nlink != 1:
        raise Refused("Cache entry is not a single-link regular file owned by this user")
    return {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size,
            "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns}


def cache_files(name, cutoff):
    root = cache_root(name)
    if not root.exists():
        return []
    device = root.stat().st_dev
    files = []

    def fail(exc):
        raise Refused("Could not inspect every selected cache entry") from exc

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        dirs[:] = [n for n in dirs if not (Path(directory) / n).is_symlink()
                   and (Path(directory) / n).stat().st_dev == device]
        for name_in_dir in names:
            path = Path(directory) / name_in_dir
            try:
                st = fingerprint(path)
            except Refused:
                continue
            if st["device"] == device and st["mtime_ns"] / 1e9 <= cutoff:
                files.append({"kind": "cache-file", "cache": name,
                              "relative": str(path.relative_to(root)), **st})
    return sorted(files, key=lambda x: x["relative"])


def verify_file(item, cutoff):
    root = cache_root(item["cache"])
    relative = Path(item["relative"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise Refused("Invalid cache-relative path")
    path = root / relative
    if path.resolve() != path or not path.is_relative_to(root):
        raise Refused("Cache entry or parent became symlinked")
    if fingerprint(path) != {k: item[k] for k in ("device", "inode", "size", "mtime_ns", "ctime_ns")}:
        raise Refused("Cache file changed since review")
    if path.stat().st_mtime > cutoff:
        raise Refused("Cache file is too recent")
    return path


def unlink_file(item, cutoff):
    """Keep parent directory descriptors open so a symlink swap cannot redirect unlink."""
    verify_file(item, cutoff)
    relative = Path(item["relative"])
    components = [*Path(CACHES[item["cache"]]).parts, *relative.parts]
    fd = os.open(Path.home().resolve(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        s = os.stat(components[-1], dir_fd=fd, follow_symlinks=False)
        current = {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size,
                   "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns}
        expected = {k: item[k] for k in current}
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1 or current != expected:
            raise Refused("Cache file changed immediately before removal")
        os.unlink(components[-1], dir_fd=fd)
    finally:
        os.close(fd)


def report(paths, context=None, skip_docker=False):
    out = {"identity": identity(), "filesystems": run(["df", "-hT"]), "folders": [],
           "cache_allowlist": CACHES, "caches": [], "notes": [
               "Btrfs compression, reflinks and snapshots mean folder totals are not additive.",
               "Docker reclaimable volumes can contain databases; volumes are report-only.",
               "Build-cache pruning has no exact dry run. Only its age/storage scope can be reviewed."]}
    for name in CACHES:
        try:
            root = cache_root(name)
            used = int(run(["du", "-sx", "-B1", "--", str(root)]).split()[0]) if root.exists() else 0
            out["caches"].append({"name": name, "path": str(root), "bytes": used})
        except (Refused, OSError, ValueError) as exc:
            out["caches"].append({"name": name, "error": str(exc)})
    for path in paths:
        p = Path(path).expanduser().absolute()
        try:
            if p.is_symlink():
                raise Refused("Refusing to scan a symlink")
            out["folders"].append({"path": str(p), "du": run(["du", "-x", "-h", "--max-depth=1", "--threshold=1G", "--", str(p)])})
        except Refused as exc:
            out["folders"].append({"path": str(p), "error": str(exc)})
    if not skip_docker:
        try:
            target = docker_target(context)
            out["docker"] = {"target": target, "usage": docker(target, "system", "df"),
                             "stopped_containers": docker(target, "container", "ls", "--all", "--no-trunc", "--filter", "status=exited", "--filter", "status=dead", "--format", '{"id":{{json .ID}},"names":{{json .Names}},"status":{{json .Status}},"image":{{json .Image}}}'),
                             "dangling_images": docker(target, "image", "ls", "--no-trunc", "--filter", "dangling=true", "--format", "{{json .}}"),
                             "volume_count": len(docker(target, "volume", "ls", "--quiet").splitlines())}
        except Refused as exc:
            out["docker_error"] = str(exc)
    return out


def make_plan(args):
    now = time.time()
    if not 1 <= args.min_age_days <= 3650:
        raise Refused("Minimum age must be between 1 and 3650 days")
    plan = {"kind": "disk-cleanup", "version": VERSION, "identity": identity(),
            "created": now, "cutoff": now - args.min_age_days * 86400,
            "docker": None, "items": []}
    if args.build_cache or args.container or args.image:
        target = docker_target(args.context)
        plan["docker"] = target
        if args.build_cache:
            plan["items"].append({"kind": "build-cache", "builder": builder_info(target),
                                  "scope": "unused built-in builder cache; age policy with an extra one-hour margin"})
        for object_id in sorted(set(args.container)):
            plan["items"].append(container_info(target, object_id, plan["cutoff"]))
        for object_id in sorted(set(args.image)):
            plan["items"].append(image_info(target, object_id, plan["cutoff"]))
    for name in sorted(set(args.cache)):
        plan["items"].extend(cache_files(name, plan["cutoff"]))
    if not plan["items"]:
        raise Refused("No selected eligible files or Docker actions")
    return plan


def save_plan(plan, path):
    data = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return hashlib.sha256(data).hexdigest()


def load_plan(path, approval):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != approval:
        raise Refused("Approval digest does not match this plan")
    plan = json.loads(data)
    if plan.get("version") != VERSION or plan.get("kind") != "disk-cleanup" or plan.get("identity") != identity():
        raise Refused("Wrong plan type, version, machine or user")
    if not 0 <= time.time() - plan["created"] <= 3600:
        raise Refused("Plan expired (one hour); review again")
    if not 0 <= plan["cutoff"] <= plan["created"] - 86400:
        raise Refused("Invalid age cutoff")
    return plan


def apply(plan):
    target = plan["docker"]
    if target and docker_target(target["context"]) != target:
        raise Refused("Docker context, endpoint or daemon changed")

    def verify(item):
        kind = item["kind"]
        if kind == "cache-file":
            verify_file(item, plan["cutoff"])
        elif kind == "container":
            if container_info(target, item["id"], plan["cutoff"]) != item:
                raise Refused("Container changed since review")
        elif kind == "image":
            if image_info(target, item["id"], plan["cutoff"]) != item:
                raise Refused("Image changed since review")
        elif kind == "build-cache":
            if not target or builder_info(target) != item.get("builder"):
                raise Refused("Builder changed or build-cache scope is invalid")
        else:
            raise Refused("Unsupported removal kind; volumes, networks and arbitrary folders are never removed")

    if not plan["items"]:
        raise Refused("Empty removal plan")
    for item in plan["items"]:
        verify(item)
    for item in plan["items"]:
        verify(item)
        kind = item["kind"]
        if kind != "cache-file" and docker_target(target["context"]) != target:
            raise Refused("Docker target changed before removal")
        if kind == "cache-file":
            # rmtree is deliberately absent: only the reviewed unchanged regular file is unlinked.
            unlink_file(item, plan["cutoff"])
            result = {"removed_cache_file": item["relative"], "cache": item["cache"], "bytes": item["size"]}
        elif kind == "container":
            docker(target, "container", "rm", item["id"])
            result = {"removed_container": item["id"], "volumes_preserved": True}
        elif kind == "image":
            docker(target, "image", "rm", item["id"])
            result = {"removed_image": item["id"]}
        else:
            # Buildx accepts durations, not absolute timestamps. Recompute the
            # age from the reviewed cutoff and add an hour to err toward keeping.
            until = str(math.ceil(time.time() - plan["cutoff"]) + 3600) + "s"
            result = {"build_cache_result": docker(target, "buildx", "prune", "--builder", item["builder"]["name"],
                       "--force", "--all", "--filter", "until=" + until, "--reserved-space", "10GB")}
        print(json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("report")
    r.add_argument("--scan", action="append", default=[], help="Explicit local folder to measure; repeat")
    r.add_argument("--context")
    r.add_argument("--skip-docker", action="store_true")
    s = sub.add_parser("plan")
    s.add_argument("--context")
    s.add_argument("--min-age-days", type=float, default=7)
    s.add_argument("--build-cache", action="store_true")
    s.add_argument("--container", action="append", default=[], help="Full ID of an old stopped container")
    s.add_argument("--image", action="append", default=[], help="Full ID of an old dangling image")
    s.add_argument("--cache", action="append", default=[], choices=sorted(CACHES))
    s.add_argument("--output", required=True)
    a = sub.add_parser("apply")
    a.add_argument("plan")
    a.add_argument("--approve", required=True)
    args = p.parse_args()
    try:
        if args.command == "report":
            print(json.dumps(report(args.scan, args.context, args.skip_docker), indent=2))
        elif args.command == "plan":
            plan = make_plan(args)
            digest = save_plan(plan, args.output)
            print(json.dumps({"plan_file": args.output, "approval_sha256": digest,
                              "actions": {k: sum(i["kind"] == k for i in plan["items"]) for k in sorted({i["kind"] for i in plan["items"]})},
                              "cache_bytes": sum(i.get("size", 0) for i in plan["items"]),
                              "cutoff": plan["cutoff"], "items": [i for i in plan["items"] if i["kind"] != "cache-file"]}, indent=2))
        else:
            apply(load_plan(args.plan, args.approve))
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
