#!/usr/bin/env python3
"""Detect Herdr and spawn an interactive target agent with a first-message prompt.

Stdlib only. Never uses headless -p / exec modes.
The skill must ask the human before calling --launch.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TARGETS = {
    "cursor": "agent",
    "claude": "claude",
    "codex": "codex",
    "agy": "agy",
    "google": "agy",
}


def which(name: str) -> str | None:
    return shutil.which(name)


def run_cmd(
    argv: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def resolve_target(raw: str) -> tuple[str, str]:
    key = raw.strip().lower()
    if key not in TARGETS:
        aliases = ", ".join(sorted(TARGETS))
        raise SystemExit(f"Unknown target {raw!r}. Supported: {aliases}")
    canonical = "agy" if key == "google" else key
    return canonical, TARGETS[key]


def herdr_app_available() -> bool:
    if not which("herdr-app"):
        return False
    # status talks to the running window; failure means no usable window.
    proc = run_cmd(["herdr-app", "status"])
    if proc.returncode != 0:
        return False
    out = (proc.stdout or "") + (proc.stderr or "")
    if '"error"' in out.lower() and "no" in out.lower():
        # Soft check — some errors still mean the binary works; try commands.
        pass
    return True


def hc_available() -> bool:
    if not which("hc"):
        return False
    proc = run_cmd(["hc", "ls", "--json"])
    # hc ls may fail if core is down; treat nonzero as unavailable for spawn.
    return proc.returncode == 0


def detect() -> dict:
    app = which("herdr-app") is not None
    app_ready = herdr_app_available() if app else False
    hc = which("hc") is not None
    hc_ready = hc_available() if hc else False
    return {
        "herdr_app_bin": which("herdr-app"),
        "herdr_app_ready": app_ready,
        "hc_bin": which("hc"),
        "hc_ready": hc_ready,
        "preferred": (
            "herdr-app"
            if app_ready
            else ("hc" if hc_ready else None)
        ),
        "targets": {k: v for k, v in TARGETS.items()},
    }


def sanitize_name(name: str) -> str:
    # hc --name: 1-32 of a-z 0-9 - _
    cleaned = re.sub(r"[^a-z0-9_-]", "-", name.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-_") or "handoff"
    return cleaned[:32]


def load_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        raise SystemExit("Pass only one of --prompt / --prompt-file")
    if prompt_file:
        return Path(prompt_file).expanduser().read_text(encoding="utf-8").strip()
    if prompt is not None:
        return prompt.strip()
    raise SystemExit("Provide --prompt TEXT or --prompt-file PATH")


def launch_herdr_app(
    *,
    target: str,
    cli: str,
    cwd: Path,
    prompt: str,
    tab_name: str,
) -> dict:
    argv_json = json.dumps([cli])
    cmd = [
        "herdr-app",
        "do",
        "tab.new",
        "--name",
        tab_name,
        "--folder",
        str(cwd),
        "--argv",
        argv_json,
        "--task",
        prompt,
    ]
    proc = run_cmd(cmd)
    result = {
        "method": "herdr-app",
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "ok": proc.returncode == 0,
        "target": target,
        "cli": cli,
    }
    # Parse JSON reply if present
    for stream in (proc.stdout, proc.stderr):
        text = (stream or "").strip()
        if not text:
            continue
        try:
            result["reply"] = json.loads(text)
            if isinstance(result["reply"], dict) and result["reply"].get("error"):
                result["ok"] = False
            break
        except json.JSONDecodeError:
            continue
    return result


def launch_hc(
    *,
    target: str,
    cli: str,
    cwd: Path,
    prompt: str,
    name: str,
) -> dict:
    # Interactive only: bare CLI + first message as trailing arg (not -p).
    cmd = [
        "hc",
        "run",
        "--json",
        "--bg",
        "--outlive-parent",
        "--name",
        name,
        "--cwd",
        str(cwd),
        cli,
        prompt,
    ]
    proc = run_cmd(cmd)
    result = {
        "method": "hc",
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "ok": proc.returncode == 0,
        "target": target,
        "cli": cli,
        "name": name,
        "recovery_hint": (
            "If the first message may not have been delivered, run "
            f"`hc get {name}` and `hc read {name}` before resending. "
            "Do not blindly resend."
        ),
    }
    text = (proc.stdout or "").strip()
    if text:
        try:
            reply = json.loads(text)
            result["reply"] = reply
            # Surface first_message.sent when present
            fm = None
            if isinstance(reply, dict):
                fm = reply.get("first_message")
                if fm is None and isinstance(reply.get("terminal"), dict):
                    fm = reply["terminal"].get("first_message")
            if isinstance(fm, dict) and fm.get("sent") is False:
                result["ok"] = False
                result["first_message_sent"] = False
                result["first_message_reason"] = fm.get("reason")
            elif isinstance(fm, dict):
                result["first_message_sent"] = fm.get("sent")
        except json.JSONDecodeError:
            pass
    return result


def launch(
    *,
    target_raw: str,
    cwd: Path,
    prompt: str,
    prefer: str | None,
    dry_run: bool,
) -> dict:
    canonical, cli = resolve_target(target_raw)
    if which(cli) is None:
        return {
            "ok": False,
            "error": f"CLI {cli!r} not found on PATH for target {canonical}",
            "target": canonical,
            "cli": cli,
        }

    info = detect()
    method = prefer or info["preferred"]
    tab_name = f"handoff → {canonical}"
    hc_name = sanitize_name(f"handoff-{canonical}")

    if method is None:
        return {
            "ok": False,
            "error": "Herdr not available; paste the prompt into the target CLI yourself.",
            "target": canonical,
            "cli": cli,
            "detect": info,
            "paste_prompt": prompt,
        }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "method": method,
            "target": canonical,
            "cli": cli,
            "cwd": str(cwd),
            "tab_name": tab_name,
            "hc_name": hc_name,
            "prompt": prompt,
            "detect": info,
        }

    if method == "herdr-app":
        if not info["herdr_app_ready"]:
            # Fall through to hc if possible
            if info["hc_ready"]:
                method = "hc"
            else:
                return {
                    "ok": False,
                    "error": "herdr-app is installed but no usable window; hc also unavailable.",
                    "detect": info,
                    "paste_prompt": prompt,
                    "target": canonical,
                    "cli": cli,
                }
        else:
            return launch_herdr_app(
                target=canonical,
                cli=cli,
                cwd=cwd,
                prompt=prompt,
                tab_name=tab_name,
            )

    if method == "hc":
        if not info["hc_ready"]:
            return {
                "ok": False,
                "error": "hc is not ready (is herdr-core running?).",
                "detect": info,
                "paste_prompt": prompt,
                "target": canonical,
                "cli": cli,
            }
        return launch_hc(
            target=canonical,
            cli=cli,
            cwd=cwd,
            prompt=prompt,
            name=hc_name,
        )

    return {
        "ok": False,
        "error": f"Unknown launch method {method!r}",
        "detect": info,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Print Herdr availability JSON and exit",
    )
    parser.add_argument(
        "--resolve",
        metavar="TARGET",
        help="Resolve a target alias to canonical name + CLI JSON",
    )
    parser.add_argument("--target", help="cursor|claude|codex|agy|google")
    parser.add_argument("--cwd", default=None, help="Working directory for the agent")
    parser.add_argument("--prompt", default=None, help="First-message prompt text")
    parser.add_argument("--prompt-file", default=None, help="Read prompt from file")
    parser.add_argument(
        "--prefer",
        choices=("herdr-app", "hc"),
        default=None,
        help="Force launch method when both are available",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would launch without launching",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Actually launch (skill must have confirmed with the user first)",
    )
    args = parser.parse_args(argv)

    if args.detect:
        print(json.dumps(detect(), indent=2))
        return 0

    if args.resolve:
        canonical, cli = resolve_target(args.resolve)
        print(json.dumps({"target": canonical, "cli": cli, "aliases": TARGETS}, indent=2))
        return 0

    if not args.target:
        raise SystemExit("--target is required unless --detect / --resolve")

    if not args.launch and not args.dry_run:
        raise SystemExit(
            "Refusing to spawn without --launch or --dry-run. "
            "Ask the user to confirm, then pass --launch."
        )

    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else Path.cwd().resolve()
    prompt = load_prompt(args.prompt, args.prompt_file)
    # --launch wins over --dry-run if both are passed.
    result = launch(
        target_raw=args.target,
        cwd=cwd,
        prompt=prompt,
        prefer=args.prefer,
        dry_run=bool(args.dry_run and not args.launch),
    )

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
