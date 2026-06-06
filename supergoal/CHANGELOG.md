# Changelog

This is the changelog for the **content-skills adaptation** of `supergoal`. For the upstream
project's history, see https://github.com/robzilla1738/supergoal.

## 0.6.1-win.1

Cross-platform adaptation of upstream **v0.6.1**. Functionally equivalent; adds native Windows
support.

- Added PowerShell parity ports of all five helper scripts: `detect-env.ps1`,
  `detect-stack.ps1`, `summarize-repo.ps1`, `repo-state.ps1`, `validate-phase.ps1`. Identical
  subcommands, arguments, stdout, and exit codes to the `*.sh` originals, which are retained
  unchanged.
- Added `tests/repo-state.test.ps1` — the same fixture scenarios as `tests/repo-state.test.sh`,
  run against the PowerShell port. All scenarios pass.
- Made `SKILL.md`, `templates/PROTOCOL.md`, and the reference docs OS-aware: detect the host
  shell once, then invoke `.ps1` (Windows) or `.sh` (Unix). Stage 7 now copies **both** forms
  of `repo-state` into `.supergoal/`.
- Packaged for the `content-skills` marketplace with attribution preserved (`LICENSE`,
  `NOTICE.md`, `README.md`).
