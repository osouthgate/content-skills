---
name: autonomous-run
description: Configure Claude Code for a long unattended run — set the operating posture so Claude keeps working autonomously for hours or days without babysitting. Triggered by `/autonomous-run`, "run this overnight", "run Opus autonomously", "set up a long autonomous run", "I want to close my laptop and let it work", "keep going until it's done without asking me", or right before dispatching a big `/goal`/supergoal. This is a setup/posture skill, not a planner — it wires up the five levers that make unattended runs reliable (auto permissions, dynamic-workflow fan-out, /goal or /loop persistence, cloud execution, end-to-end self-verification), detects which are available this session, and hands off cleanly. Pairs with the `supergoal` skill (which does the planning + phase execution); run this to harden the run before or at supergoal's dispatch.
argument-hint: <optional: describe the task you want to run unattended>
---

# Autonomous Run

You are setting up a **long unattended run** on Claude Code. The user wants Claude
to keep working for hours or days without approving each step. Your job is **not**
to plan or execute the task itself — it is to put the session into the right
**operating posture** so that whatever runs next (a `/goal`, a `supergoal` chain,
a `/loop`, or plain agentic work) survives without a human at the keyboard.

The task, if given:

$ARGUMENTS

> **Claude Code only.** These levers are Claude Code features. On Codex, most of
> them do not exist — if you detect a Codex host (see capability detection below),
> say so plainly and fall back to the one portable lever (`/goal` persistence),
> then stop. Don't pretend the rest are available.

## The five levers

A run that lasts hours without a babysitter needs all five. Walk them in order;
each section says how to **detect** whether it's available and what **action** to
take. Skip nothing silently — if a lever is unavailable, name it and move on.

### 1. Auto permissions — so Claude never blocks on approval

A run dies the moment it hits a permission prompt nobody answers. The single
biggest cause of a stalled overnight run.

- **Detect:** You cannot read the current permission mode from inside the session.
  Ask the user, or infer from context (a fresh cloud session started from the web
  app usually defaults to a more permissive mode).
- **Action:** Tell the user to switch to **auto / accept-edits mode** (Claude Code:
  `/permissions` or the mode toggle, commonly **Shift+Tab** to cycle to "auto
  accept edits"/"bypass permissions"). If the run touches anything destructive or
  outward-facing, recommend pre-allowing the *specific* command/tool families in
  `.claude/settings.json` rather than blanket bypass — narrower is safer for an
  unattended run. The `fewer-permission-prompts` skill, if present, can build that
  allowlist from past transcripts; note it.
- **Confirm** the user has done this before you hand off. An unattended run with
  manual permissions is the failure mode this whole skill exists to prevent.

### 2. Dynamic workflows — fan out to subagents to get more done per unit of time

Claude can orchestrate many subagents in parallel (the `Agent`/Task tool). For a
big task, independent units of work run concurrently instead of single-file. This
is the lever Codex does not have, and the one most often left on the table.

- **Detect:** The `Agent` (subagent / Task) tool is in the tool list. If present →
  dynamic workflows are available.
- **Action:** Identify which parts of the upcoming task are **independent** (no
  shared files, no ordering dependency) and plan to dispatch them as parallel
  subagents in a single message; keep dependent work sequential. For very large
  tasks, an orchestrator subagent can itself spawn workers. Each subagent returns
  only its conclusion, so the main thread's context stays lean over a long run.
- **Pair with supergoal:** if the run is a supergoal chain, supergoal's capability
  layer already decides per-phase whether to fan out — point the user there and
  don't duplicate the decision. This skill's job is just to confirm the lever is
  on and the host supports it.

### 3. `/goal` or `/loop` — keep Claude going until the end state holds

Agentic turns stop when the model thinks it's done. For a long run you want a
persistence mechanism that keeps re-engaging until a **measurable end state** is
reached.

- **Detect:** `/goal` is the Claude Code persistence command (a fast evaluator
  re-checks an end-state condition each turn and auto-continues). `/loop` (the
  `loop` skill, if listed) re-runs a prompt/command on an interval — right for
  *recurring* work (poll a deploy, keep a PR green), not for drive-to-done.
- **Action — pick the shape:**
  - **Drive one task to completion** → `/goal "<short measurable end-state>"`.
    The condition must be verifiable from the transcript ("X printed", "0 failures
    reported"), never something the evaluator can't see ("tests pass"). Long task
    detail belongs in files on disk, not in the `/goal` argument.
  - **Recurring / interval work** → `/loop <interval> <prompt-or-command>`.
  - **Planned multi-phase build** → hand off to `supergoal`, which wraps a single
    `/goal` around a phase chain with retry + audit. Don't hand-roll what supergoal
    already does.
- **Slash commands fire only from user input.** You cannot dispatch `/goal` or
  `/loop` from your own message — print the ready-to-paste line and have the user
  paste it once.

### 4. Cloud execution — so the laptop can close

A run pinned to a local terminal dies when the machine sleeps. Claude Code in the
cloud (web / desktop / mobile app) keeps running server-side.

- **Detect:** If you are already in a managed remote/cloud environment (ephemeral
  container, repo freshly cloned, no persistent local state), you're **already in
  the cloud** — say so and skip the move. Otherwise you're on a local CLI.
- **Action:** If local and the run is long, recommend moving it to a cloud session
  (Claude Code on the web at claude.com/code, or the desktop/mobile app) so the
  user can close their laptop and check from their phone. If already cloud-hosted,
  remind the user the container is **ephemeral** — anything worth keeping must be
  committed and pushed before the session goes idle.

### 5. End-to-end self-verification — so "done" means actually working

The most dangerous long run is one that reports success it never verified. Build +
typecheck + lint + unit tests are necessary but not sufficient — they don't prove
the app actually *works*. Give Claude a way to exercise the real thing.

- **Detect** what verification surface this session has, by scanning the tool list
  and the project:
  - **Web** — a browser-driver MCP/tool (Claude in Chrome extension, Playwright,
    or similar `mcp__*` browser tools) → Claude can load the running app and assert
    on real UI.
  - **Mobile** — an iOS/Android **simulator MCP** → Claude can boot the sim, drive
    the app, screenshot.
  - **Backend / service** — a way to **start the full server/service** (a dev/run
    command in `package.json`/`Makefile`/`Procfile`) and hit real endpoints.
- **Action:** Require the upcoming run to **self-verify end to end against the
  detected surface**, not just pass unit checks — load the page and assert,
  drive the sim and screenshot, boot the server and curl the endpoint. If **no**
  end-to-end surface exists, say so explicitly and set expectations: verification
  will stop at build/test/lint and the user should eyeball the result before
  trusting it. Never claim end-to-end coverage you can't produce.

## Capability detection (run this first)

Before walking the five levers, sense the session once and record a compact
profile. Detect by inspecting the **tool list** and **environment**, not by
guessing:

| Capability | Signal | If absent |
|---|---|---|
| Host = Claude Code | `Agent`/Task tool, `AskUserQuestion`, skills list present | If Codex → only lever 3 (`/goal`) applies; say so and stop |
| Dynamic workflows | `Agent`/Task tool in tool list | Run sequentially; note fan-out unavailable |
| Web self-verify | browser-driver MCP / Chrome / Playwright tools | No web E2E; fall back to build/test |
| Mobile self-verify | iOS/Android simulator MCP tools | No mobile E2E; fall back to build/test |
| Backend self-verify | dev/run command in repo (`package.json` scripts, `Makefile`, `Procfile`) | No service E2E; fall back to build/test |
| Cloud execution | remote/ephemeral container env | Recommend moving to cloud |
| `/loop` available | `loop` in the skills list | Use `/goal` only |

Print a short profile so the user sees what's on and what's missing — this is also
the honest record of how far "autonomous" can actually go this session.

## Hand-off

After the five levers, end with a tight checklist the user can act on in one pass:

```
Autonomous-run posture for: <task or "this session">

  [on/off/n-a] 1. Auto permissions   — <what to toggle, or "confirmed on">
  [on/off/n-a] 2. Dynamic workflows   — <fan-out plan, or "sequential — no Agent tool">
  [on/off/n-a] 3. Persistence         — </goal | /loop | supergoal — which and why>
  [on/off/n-a] 4. Cloud execution     — <already cloud | move to web/app>
  [on/off/n-a] 5. End-to-end verify   — <surface detected, or "unit-only — eyeball before trusting">

Next: <the one paste-ready line — /goal "...", /loop ..., or "invoke /supergoal <task>">
```

Then **stop**. If a `/goal`, `/loop`, or `/supergoal` line is the next step, the
user pastes it; slash commands don't fire from your message text.

## Composing with supergoal

These two skills are complementary, not overlapping:

- **`supergoal`** = the planner + executor: recon, phase decomposition, the single
  `/goal`, retry, fix-spec recovery, final audit. It owns *what gets built and how
  it's verified per phase*. Its capability layer decides per-phase fan-out and
  end-to-end verification on Claude.
- **`autonomous-run`** (this skill) = the operating posture around any run: the
  five levers that keep a session alive and honest while unattended. It owns
  *whether the session can run for hours without a human*.

Typical flow: invoke `autonomous-run` to set posture (or confirm it) → invoke
`supergoal` to plan + dispatch. If the user already knows their task is a planned
build, send them straight to `supergoal`; this skill is for the run-it-overnight
framing, smaller one-off long runs, or hardening a session before any big dispatch.

## When not to use this

- **Short task** (minutes, one or two files): unattended posture is overkill —
  just do the work.
- **The user is actively watching and steering:** auto-permissions and persistence
  fight an interactive workflow. Use this only when the intent is genuinely
  hands-off.

## References

- `references/levers.md` — the five levers in depth: detection signals, exact
  toggles, failure modes each one prevents, and how they interact over a long run.
