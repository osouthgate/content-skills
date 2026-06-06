# NOTICE — Attribution & provenance

This plugin (`supergoal`, as distributed in the `content-skills` marketplace) is a
**derivative work**. It adapts an upstream project for Windows and bundles it for this
marketplace.

## Original work

- **Project:** supergoal
- **Author:** Robert Courson (`robzilla1738`)
- **Source:** https://github.com/robzilla1738/supergoal
- **Upstream baseline:** v0.6.1
- **License:** MIT (see [`LICENSE`](LICENSE), which preserves the original copyright notice
  as the MIT license requires)

The original `LICENSE` and its `Copyright (c) 2026 Robert Courson` notice are retained
verbatim in this directory. This adaptation is **not endorsed by or affiliated with** the
original author.

## Changes made in this adaptation

This fork is functionally equivalent to upstream v0.6.1, with cross-platform support added:

- **PowerShell ports** of all five helper scripts so the skill runs natively on Windows
  (where the platform `bash.exe` is often a non-functional WSL stub):
  `detect-env.ps1`, `detect-stack.ps1`, `summarize-repo.ps1`, `repo-state.ps1`,
  `validate-phase.ps1`. Each is a parity port of its `*.sh` counterpart — identical
  subcommands, arguments, stdout, and exit codes. The original `*.sh` scripts are retained
  unchanged for macOS / Linux / Codex.
- **`repo-state.ps1`** (the runtime-critical comparison helper) is verified against the same
  fixture scenarios as the bash original via `tests/repo-state.test.ps1`.
- **`SKILL.md`, `templates/PROTOCOL.md`, and the reference docs** were made OS-aware: a host
  shell is detected once, and helper invocations / inline snippets are spelled out in both
  bash and PowerShell forms. The bash form remains canonical; Windows substitutes the `.ps1`
  form.
- Packaged as a plugin under the `content-skills` marketplace (new `.claude-plugin/plugin.json`,
  this `NOTICE.md`, and an adaptation `README.md`).

Version `0.6.1-win.1` denotes: upstream baseline `0.6.1`, Windows-adaptation revision `1`.

## License of this adaptation

MIT, same as upstream. See [`LICENSE`](LICENSE).
