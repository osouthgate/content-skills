# The five levers — in depth

This reference expands each lever from `SKILL.md`: the failure mode it prevents,
how to detect availability, the exact action, and how the levers compound. The
short version lives in `SKILL.md`; read this when you need the reasoning or the
edge cases.

The unifying idea: an unattended run fails for boring reasons — it blocks on a
prompt, it stops early thinking it's done, the laptop sleeps, or it reports a
success it never checked. Each lever removes one of those failure modes.

---

## Lever 1 — Auto permissions

**Failure it prevents:** the run halts at a permission prompt at 2am and does
nothing until morning. This is the most common cause of a wasted overnight run.

**Detection:** permission mode is not readable from inside the session. Either ask
the user, or infer from context — a cloud session launched from the web/app
usually starts in a more permissive mode than a fresh local CLI.

**Action, in order of preference:**

1. **Scoped allowlist (safest).** Pre-allow the specific command and tool families
   the run needs in `.claude/settings.json` (`permissions.allow`). An unattended
   run with a tight allowlist can't be hijacked into something destructive. The
   `fewer-permission-prompts` skill builds this from your recent transcripts.
2. **Accept-edits / auto mode.** Cycle the mode (commonly **Shift+Tab**) to
   auto-accept edits. Good when the work is mostly file edits + safe commands.
3. **Bypass permissions (broadest).** Only when the environment is sandboxed/
   ephemeral (a cloud container) and the blast radius is contained. Never
   recommend blanket bypass on a machine with credentials, production access, or
   irreplaceable local state.

**Interaction:** pointless without lever 3 — auto-permissions only matters once
something is driving the run long enough to hit a prompt.

---

## Lever 2 — Dynamic workflows (subagent fan-out)

**Failure it prevents:** a large task crawls through independent work single-file,
burning hours it didn't need to, and bloating the main context until quality
degrades.

**Detection:** the `Agent`/Task tool is in the tool list (Claude Code). Codex has
no equivalent — if the host is Codex, this lever is simply unavailable.

**Action:**

- Map the upcoming work into **independent** vs **dependent** units. Independent =
  no shared files, no ordering constraint, no shared mutable state.
- Dispatch independent units as **parallel subagents in a single message**; keep
  dependent work sequential.
- For very large tasks, an **orchestrator** subagent can spawn its own workers —
  the "hundreds/thousands of agents" shape. Use a worktree per worker if they'd
  otherwise collide on the same files.
- Each subagent returns only its **conclusion**, not its full transcript, so the
  main thread stays lean — which is what lets a run go for hours without context
  rot.

**Interaction:** multiplies lever 3 — more work completes per turn, so the
end-state condition is reached sooner. Has a real failure mode of its own: parallel
workers editing the same files corrupt each other. Isolate (worktrees) or
serialize anything that shares state.

**With supergoal:** supergoal's capability layer already makes the per-phase
fan-out decision from phase dependency metadata. Don't re-derive it here — confirm
the lever is on and let supergoal drive.

---

## Lever 3 — `/goal` or `/loop` (persistence)

**Failure it prevents:** agentic turns end when the model believes it's finished,
which on a long task is often premature. Persistence keeps re-engaging until a
**measurable** end state holds.

**Detection / choice:**

| You want… | Use | Shape |
|---|---|---|
| One task driven to completion | `/goal "<end-state>"` | Fast evaluator re-checks the condition each turn, auto-continues until it holds |
| Recurring / interval work | `/loop <interval> <prompt\|/command>` | Re-runs on a timer (poll a deploy, keep a PR green) |
| A planned multi-phase build | `supergoal` | One `/goal` wrapped around a phase chain with retry + audit |

**Writing a good `/goal` condition:**

- **Verifiable from the transcript.** The evaluator only sees the conversation — it
  does not run tools or read files. `"all 12 endpoints return 200, count printed"`
  is checkable; `"the API works"` is not.
- **Short.** The argument is an end-state, not a task body. Long detail goes in
  files the agent reads from disk.
- **Terminal.** There must be a state where it's unambiguously done, or the loop
  never clears.

**Interaction:** this is the lever that actually *runs* the others. Levers 1, 2, 4,
5 are all in service of letting this one run unattended and finish honestly.

---

## Lever 4 — Cloud execution

**Failure it prevents:** the run is tied to a local process that dies when the
laptop sleeps, the terminal closes, or the network drops.

**Detection:** if the environment is an ephemeral remote container (repo freshly
cloned, no persistent local state, reclaimed on idle), you're already cloud-hosted.
Otherwise it's a local CLI.

**Action:**

- **Local + long run** → move it to a cloud session (Claude Code on the web, or the
  desktop/mobile app). The user closes the laptop and checks from their phone.
- **Already cloud** → the container is **ephemeral**. Anything worth keeping must be
  committed and pushed before the session goes idle; un-pushed work is lost when the
  container is reclaimed. For a multi-hour run, prefer committing at milestones over
  one giant commit at the end.

**Interaction:** orthogonal to the others but it's what makes "for hours/days"
literal rather than "for as long as I keep my laptop open."

---

## Lever 5 — End-to-end self-verification

**Failure it prevents:** the worst long-run outcome — Claude reports success it
never verified, and the user discovers the app was broken the whole time. Unit
checks (build/typecheck/lint/test) are necessary but never sufficient: they don't
prove the running thing works.

**Detection — what surface can exercise the real app:**

| Surface | Signal | Capability unlocked |
|---|---|---|
| Web | browser-driver MCP (Claude in Chrome, Playwright, `mcp__*` browser tools) | Load the running app, click, assert on real DOM/UI |
| Mobile | iOS/Android simulator MCP | Boot the sim, drive the app, screenshot |
| Backend | dev/run command (`package.json` scripts, `Makefile`, `Procfile`, `docker compose`) | Start the full service, hit real endpoints |

**Action:**

- Require the run to **self-verify end to end against the detected surface** as part
  of "done" — not just green unit checks. Load the page and assert; drive the sim
  and screenshot; boot the server and curl the endpoint, then read the response.
- Fold the evidence into whatever proves completion (the `/goal` condition, the
  supergoal phase VERIFY block) so the persistence loop can't clear on unit checks
  alone.
- **No surface available** → say so explicitly. Verification stops at build/test/
  lint, and the user should eyeball the result before trusting it. Claiming
  end-to-end coverage you can't produce is the exact dishonesty this lever exists to
  kill.

**Interaction:** this is what makes the other four *safe* to leave unattended.
Auto-permissions + persistence + fan-out + cloud will run a long way without you —
this lever ensures where they run *to* is actually working, not just plausibly
reported as working.

---

## How the levers compound

```
        cloud (4)  ── keeps the process alive
            │
   /goal or /loop (3)  ── keeps re-engaging toward a measurable end state
            │
   ┌────────┴────────┐
auto-perms (1)   fan-out (2)   ── removes stalls; does more per turn
   └────────┬────────┘
   end-to-end verify (5)  ── makes "done" mean working, not just reported
```

Drop any one and the run degrades in a predictable way: no (1) it stalls, no (2)
it's slow, no (3) it stops early, no (4) it dies with the laptop, no (5) it lies.
A genuinely hands-off multi-hour run wants all five — or an honest account of which
are missing and what that costs.
