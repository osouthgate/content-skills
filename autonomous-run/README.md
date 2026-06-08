# autonomous-run

> Set the operating posture for a long unattended run on Claude Code — so Claude
> keeps working for hours or days without babysitting, and "done" means actually
> working.

This is a **setup/posture** skill, not a planner. It wires up the five levers that
make hands-off runs reliable, detects which are available in the current session,
and hands off cleanly. It pairs with [`supergoal`](../supergoal) (which does the
planning + phase execution).

## The five levers

1. **Auto permissions** — so Claude never stalls on an approval prompt nobody answers.
2. **Dynamic workflows** — fan out independent work to parallel subagents (the lever Codex lacks).
3. **`/goal` or `/loop`** — keep re-engaging until a measurable end state holds.
4. **Cloud execution** — run server-side so the laptop can close.
5. **End-to-end self-verification** — exercise the real app (web / simulator / running service), not just unit checks.

Drop any one and the run degrades predictably: no (1) it stalls, no (2) it's slow,
no (3) it stops early, no (4) it dies with the laptop, no (5) it lies. The skill
either turns all five on or gives an honest account of which are missing and what
that costs.

> **Claude Code only.** These are Claude Code features. On Codex, only lever 3
> (`/goal` persistence) applies; the skill detects the host and says so.

## Install

From Claude Code:

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install autonomous-run@content-skills
```

Then in a session: `/autonomous-run <optional: the task you want to run unattended>`.

## Relationship to supergoal

| Skill | Owns |
|---|---|
| `supergoal` | *What gets built and how it's verified per phase* — recon, phase decomposition, the single `/goal`, retry, audit. |
| `autonomous-run` | *Whether the session can run for hours without a human* — the five levers around any run. |

Typical flow: invoke `autonomous-run` to set posture → invoke `supergoal` to plan +
dispatch. If you already know the task is a planned build, go straight to
`supergoal`; use `autonomous-run` for the run-it-overnight framing or to harden a
session before a big dispatch.

## License

MIT — see [`LICENSE`](LICENSE).
