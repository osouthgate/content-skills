---
name: supergoal
description: Plan and autonomously build a software task end-to-end. Triggered by `/supergoal`, "plan and ship X", "supercharged plan", "autonomous build", "plan it out and don't stop until it's done", "I don't want to babysit this", or any non-trivial feature/refactor/redesign the user wants driven to completion. Strongly prefer over a plain plan when the user signals "every aspect", "fully", "perfectly", "until done", or wants depth + autonomous follow-through. Recons the codebase, applies preloaded memory, researches best practices with whatever tools are available, decomposes into the right number of phases, gets one confirmation, then prepares a single ready-to-paste `/goal` command — one paste between you and done — that drives the entire chain to completion with built-in retry, fix-spec recovery, and per-phase memory writeback. Works on Claude Code and Codex.
argument-hint: <describe what you want built, fixed, or shipped>
---

# Supergoal

You are running the Supergoal workflow. The user's task is:

$ARGUMENTS

Your job: **plan deeply, then auto-execute under a single `/goal`** until the task is verifiably complete across every phase.

## Cross-platform shell (Windows + Unix) — read first

Every helper script ships in **two parity forms**: a POSIX `*.sh` (macOS/Linux/Codex, git-bash/WSL) and a PowerShell `*.ps1` (Windows). They take identical subcommands, arguments, stdout, and exit codes — pick the one that matches the host shell.

**Detect the shell once, early (Stage 0), and reuse the choice everywhere.** A reliable signal: PowerShell defines the `$PSVersionTable` automatic variable and `$env:OS` is `Windows_NT`; a POSIX shell does not. Concretely:

- **Windows / PowerShell host** → invoke `pwsh -NoProfile -File "<script>.ps1" <args>` and use PowerShell builtins for inline snippets (`Get-Content`, `New-Item`, `$env:VAR`, etc.).
- **macOS / Linux / Codex / git-bash** → invoke `bash "<script>.sh" <args>` and use the POSIX snippets as written.

Throughout this document the **bash form is shown as canonical**; on Windows substitute the `.ps1` equivalent (same name, same args). Where a step runs a helper script, both forms are spelled out. Where a step is an inline shell snippet (memory preload, directory setup), a PowerShell equivalent is given inline. **Never invoke a bare `bash`/`.sh` on a Windows PowerShell host** — the platform's `bash.exe` may be a non-functional WSL stub.

## What "every aspect is perfect" means here

The user's bar is high. Translate it into measurable criteria, not vibes:

- **Functional** — the feature works for the golden path and the obvious edge cases
- **Engineering** — build, typecheck, lint, tests all pass; no new warnings
- **Polish** — UX/copy, error states, empty states, loading states are handled
- **Hardening** — security review, input validation, no obvious regressions
- **Verification** — every phase produces transcript evidence the evaluator can see

If a phase can't be measured, it isn't a phase. Rewrite it until it can.

## How this skill works (one-shot summary)

0. **Available context** — preload memory; detect available tools (Context7, WebSearch, MCPs, skills) **and host capabilities (Claude Code vs Codex: subagent fan-out, end-to-end verification surfaces)**; resume any in-progress Supergoal state
1. **Intake** — restate, classify, ask enough questions to cover every material gap. Greenfield walks the full category checklist (platform, stack, design direction, integrations, scope, audience, perf, data model) in batches of up to 4 until everything material is filled in; brownfield asks 0–2 since recon answers most structural questions.
2. **Recon** — parallel codebase + environment scan
3. **Deep think** — research best practices with whatever tools exist (optional, not required); list top-3 risks + dependencies
4. **Decompose** — derive phase count from the task itself; no fixed cap
5. **Write phase specs** — one work-spec file per phase under `.supergoal/phases/phase-N.md` (any length, no char budget)
6. **Plan review** — show summary + concrete revision menu; wait for explicit go/no-go
7. **Hand off one ready-to-paste `/goal`** with a short end-state condition; the user pastes once, and the agent inside that fresh `/goal` session executes phases sequentially with retry + fix-spec recovery + per-phase memory writeback, then runs a **final audit** that re-verifies the work against the original ROADMAP and self-heals any gaps before completion holds

Two human gates only: **clarifying questions for true gaps (Stage 1)** and **plan review (Stage 6)**. Everything else runs autonomously.

### Why one `/goal`, not a chain

`/goal` in both Claude Code and Codex takes a **short end-state condition**, not a long task body. A fast evaluator checks the condition against the transcript after each turn and auto-continues until it holds. Supergoal v3 leverages this directly: one `/goal` covers the whole run; phase work lives in files the agent reads from disk; the condition is "all phases done, `SUPERGOAL_RUN_COMPLETE` printed." No char budget, no inter-session chain dispatch, no fragility.

## Locate the skill directory

**Unix / git-bash:**

```bash
SUPERGOAL_DIR=$(dirname "$(ls -1 \
  "$HOME/.claude/skills/supergoal/SKILL.md" \
  "$PWD/.claude/skills/supergoal/SKILL.md" \
  2>/dev/null | head -n1)")
export SUPERGOAL_DIR
export SUPERGOAL_ROOT="${SUPERGOAL_ROOT:-.supergoal}"
mkdir -p "$SUPERGOAL_ROOT/goals"
echo "SUPERGOAL_DIR=$SUPERGOAL_DIR"
echo "SUPERGOAL_ROOT=$SUPERGOAL_ROOT"
```

**Windows / PowerShell:**

```powershell
$cand = @(
  "$env:USERPROFILE\.claude\skills\supergoal\SKILL.md",
  "$PWD\.claude\skills\supergoal\SKILL.md"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $cand) { throw "supergoal: SKILL.md not found under ~\.claude\skills\supergoal or .\.claude\skills\supergoal" }
$env:SUPERGOAL_DIR = Split-Path -Parent $cand
if (-not $env:SUPERGOAL_ROOT) { $env:SUPERGOAL_ROOT = '.supergoal' }
New-Item -ItemType Directory -Force -Path "$env:SUPERGOAL_ROOT\goals" | Out-Null
"SUPERGOAL_DIR=$env:SUPERGOAL_DIR"
"SUPERGOAL_ROOT=$env:SUPERGOAL_ROOT"
```

> **Shell-session note (Windows).** `$env:SUPERGOAL_DIR` / `$env:SUPERGOAL_ROOT` live in the current shell. If your host runs each command in a fresh process (env vars don't persist between separate tool calls), either set them in the **same** command that invokes a helper, or substitute the absolute path. The same caveat applies to the bash `export`s above.

All artifacts live under `$SUPERGOAL_ROOT`. Skill assets (scripts, references, templates) live under `$SUPERGOAL_DIR`.

---

## Stage 0 — Available context (memory + tools)

Before doing anything else, sense what's available this session. This is what makes the run frictionless — if memory already knows the user's preferences, don't ask; if a tool isn't available, don't try to call it.

### Memory preload

**Unix / git-bash:**

```bash
# Detect a memory directory. Common locations:
MEM_DIR=""
for cand in \
  "$HOME/.claude/projects/-Users-$(whoami)/memory" \
  "$HOME/.claude/memory" \
  "$PWD/.claude/memory" \
  "$SUPERGOAL_ROOT/memory"; do
  [[ -d "$cand" ]] && MEM_DIR="$cand" && break
done
echo "MEM_DIR=$MEM_DIR"

if [[ -n "$MEM_DIR" && -f "$MEM_DIR/MEMORY.md" ]]; then
  echo "--- MEMORY INDEX ---"
  cat "$MEM_DIR/MEMORY.md"
fi
```

**Windows / PowerShell** (the Claude projects dir mangles the cwd path, e.g. `C--Users-osout`; probe the glob plus the common fallbacks):

```powershell
# Build a FLAT candidate list (+= flattens; a comma-array would nest the glob
# result and stringify multiple project dirs into one space-joined path).
$candidates = @()
$candidates += (Get-ChildItem "$env:USERPROFILE\.claude\projects\*\memory" -Directory -ErrorAction SilentlyContinue | ForEach-Object FullName)
$candidates += "$env:USERPROFILE\.claude\memory"
$candidates += "$PWD\.claude\memory"
$candidates += "$env:SUPERGOAL_ROOT\memory"
# Prefer a dir that actually holds a MEMORY.md index (matters when there are
# several project memory dirs); else fall back to the first existing dir.
$MemDir = $candidates | Where-Object { $_ -and (Test-Path (Join-Path $_ 'MEMORY.md')) } | Select-Object -First 1
if (-not $MemDir) { $MemDir = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1 }
"MEM_DIR=$MemDir"
if ($MemDir -and (Test-Path (Join-Path $MemDir 'MEMORY.md'))) {
  "--- MEMORY INDEX ---"
  Get-Content (Join-Path $MemDir 'MEMORY.md')
}
```

Read the index. Then **selectively** read individual memory files that look relevant to the task (feedback memories about the stack/domain, user role memories, related project memories). Don't dump them all into context — pull what matters.

Capture applicable memory hits in `$SUPERGOAL_ROOT/applied-memories.md` (one line per memory: name, why-applicable, what-it-changes). Surface them in Stage 1 as "Applied from memory: …" so the user can see what's being inherited and correct anything stale.

### Tool discovery

Tools differ between sessions and hosts (Claude Code vs Codex, different MCP server sets). Detect, don't assume:

- **Context7** — available if `mcp__claude_ai_Context7__resolve-library-id` or similar is in the tool list. If absent, skip it; rely on training-cutoff knowledge + WebSearch if that's present.
- **WebSearch / WebFetch** — available if listed. If neither, skip web research.
- **Project skills** — check the available-skills list for domain-relevant skills (e.g. `mobile-ios-design`, `clerk-auth`, `expo-dev-client`) and note them in `$SUPERGOAL_ROOT/applied-skills.md` to invoke from inside phase goals if relevant.
- **Prior Supergoal state** — if `$SUPERGOAL_ROOT/STATE.md` exists from a previous run, read it; resume rather than restart.

Write detected tools to `$SUPERGOAL_ROOT/tools.md`. Stage 3 and the phase goals reference this file when deciding what to invoke.

### Host & capability detection

The plan Supergoal produces is host-agnostic, but Claude Code and Codex have different **execution** capabilities — and a run that ignores the difference leaves Claude's strengths unused. Detect the capability profile once here and record it; later stages read it to decide *how* phases are driven, never *what the plan is*.

Inspect the tool list and environment (don't guess) and write `$SUPERGOAL_ROOT/capabilities.md`, one line per field (`field: <value> — <signal>`):

- **Host** — `Agent`/Task tool + `AskUserQuestion` + a skills list ⇒ **Claude Code**; otherwise **Codex**.
- **Subagent fan-out** — `Agent`/Task tool present ⇒ independent phases can run in parallel (Stage 4 / phase loop). Absent ⇒ sequential single-session execution (the portable default).
- **End-to-end verify surfaces** — browser-driver tools (Claude in Chrome, Playwright, `mcp__*` browser) ⇒ web E2E; iOS/Android simulator MCP ⇒ mobile E2E; a runnable dev/serve command (`package.json` scripts, `Makefile`, `Procfile`, `docker compose`) ⇒ service E2E. None ⇒ unit evidence only.
- **`/loop`, cloud/ephemeral** — record for the Stage 7 hand-off (commit-cadence note on cloud); these are operating-posture levers owned by the `autonomous-run` companion skill, not toggled by Supergoal.

**Capabilities are additive and degrade gracefully** — a missing capability means "use the portable fallback," never "fail." Full profile and exactly how each capability changes execution: `references/claude-capabilities.md`.

### Resume detection

If `STATE.md` exists and shows `Status: READY_TO_DISPATCH` or `Status: IN_PROGRESS`, **do not re-plan** — a previous run already produced the plan, and at `READY_TO_DISPATCH` or beyond it also persisted the dispatch line at `.supergoal/goals/goal_prompt.md`. Print a one-line "Resuming Supergoal from phase N", then re-validate before re-issuing:

- **Baseline still matches** (`STATE.md`'s `Baseline ref:` equals `git rev-parse HEAD`) **and pre-flight (Stage 6.5) still green** → point the user straight at **`.supergoal/goals/goal_prompt.md`** as the canonical re-dispatch line. Its `/goal` command is verbatim-identical to the end-state condition the original run committed to, so re-pasting from this file is what guarantees the host evaluator can still clear — a line reconstructed from memory may differ and never resolve.
- **Baseline drifted** (work landed since) **or pre-flight now red** → re-capture the baseline and re-run pre-flight, then fall through to Stage 6 (plan review) / Stage 7, which **regenerates** `goal_prompt.md` with the fresh baseline before handing it back.

---

## Stage 1 — Intake & clarifying questions

Echo the task back in **one sentence**. Then classify it (tags can combine):

| Tag | Trigger |
|---|---|
| `greenfield` | Request implies a new project; cwd has no `.git/` or empty tree |
| `brownfield` | Change in an existing repo |
| `bugfix` | Mentions "bug", "broken", "fails", "regression" |
| `refactor` | Mentions "refactor", "clean up", "restructure" |
| `ui` | Mentions "design", "polish", "UI", "UX", "responsive", "redesign" |

**Calibrate the question count to the context.** Greenfield has no codebase to scan, so it needs enough verbal context to plan well — never artificially limit questions when material info is missing. Brownfield runs lean on recon, so questions are sparse.

### Greenfield — gather enough context to plan well

A new project has no signal beyond the user's prompt + memory. The planner's job in Stage 1 is to **enumerate every category that meaningfully shapes the plan, eliminate the ones already answered by memory or prompt, and ask about every remaining one**. Don't stop until every material gap is filled.

**Category checklist — work through this for every greenfield run:**

| Category | Why it shapes the plan |
|---|---|
| **Target platform / surface** | iOS, Android, web, desktop, CLI, multi — the biggest fork. Different stacks, different phases. |
| **Stack / framework preference** | Next.js vs SvelteKit, Expo vs bare RN, FastAPI vs Django, Swift vs SwiftUI vs UIKit, etc. Affects every phase. |
| **Design direction / aesthetic** | Minimal-mono, brutalist, glass morphism, Apple-native, dashboardy-corporate, retro, etc. Determines tokens, component shapes, Polish phase content. |
| **Integration anchors** | Auth provider, database, payments, hosting, analytics, file storage, email — anything that locks in a vendor up front. |
| **Scope cut-line** | MVP-this-week vs full feature; what's explicitly out of scope vs deferred to v2. |
| **Primary use case / audience** | Solo-dev tool, team SaaS, public consumer app, internal admin — drives auth flow, onboarding shape, error tolerance. |
| **Performance / scale constraints** | "Realtime sub-100ms" vs "background batch ok"; expected traffic; offline-first or online-only. Only ask if non-trivial. |
| **Data model anchors** | If the prompt implies data, ask the shape ("users + posts? users + projects + tasks?"). Only if not obvious. |

**Process:**

1. For each category, ask: *did the user's prompt mention it? Does memory have a relevant preference?*
2. If yes → use that, surface as "Applied from memory: …" or "From your prompt: …"
3. If no → that category becomes a question.
4. Ask all remaining questions in **batches of up to 4** (the `AskUserQuestion` tool ceiling) until every material gap is filled. Two batches is fine for greenfield; three is rare but allowed if a complex task genuinely warrants it.
5. Within each batch, lead with the highest-leverage choices (the ones that change the phase shape most).

**Anti-patterns:**

- **Don't ask one batch and then plan around silent assumptions for the rest.** If you're about to assume the design direction, the auth provider, AND the scope cut-line, that's 3 assumptions and one batch of follow-up is cheaper than getting it wrong.
- **Don't pad questions when memory/prompt already covers them.** Reading "I want a SwiftUI iOS app with Liquid Glass" → don't ask "what platform?", "what stack?", or "what aesthetic?". Just ask about integrations, scope, and use case.
- **Don't ask micro-details** that belong in plan review: naming, file paths, copy wording, color palette specifics, library minor versions, default test framework if the stack has one. Those go into ROADMAP.md as assumptions and surface in Stage 6's revision menu.

### Brownfield — 0–2 questions, one batch

The codebase plus recon scripts already answer most structural questions (stack, package manager, build/test/lint, conventions, what exists). Ask only for **true gaps** memory + prompt + recon leave open:

- Scope cut-line ("just this surface, or also touch the related ones?")
- Compatibility surface ("backwards compat with the old API path, or break it?")
- Primary fork when ambiguous ("which of these two existing patterns do you want me to extend?")

Most well-described brownfield tasks ask **zero questions**.

### In both modes

1. Lead with "Applied from memory: …" and "From your prompt: …" so the user sees what's being inherited or read off before answering.
2. Each `AskUserQuestion` batch caps at 4 (tool limit). Greenfield can use multiple sequential batches; brownfield is one batch max.
3. If you genuinely need zero questions, say "No clarifying questions — proceeding from prompt + memory + recon." and move straight to Stage 2.
4. Never ask about anything you can responsibly assume — those go into the Stage 6 plan review for one-click correction.

---

## Stage 2 — Recon (parallel)

Run recon scripts in parallel. They populate context files under `$SUPERGOAL_ROOT/`.

### Brownfield path

```bash
# Unix / git-bash
bash "$SUPERGOAL_DIR/scripts/detect-stack.sh"   > "$SUPERGOAL_ROOT/context.md"
bash "$SUPERGOAL_DIR/scripts/summarize-repo.sh" > "$SUPERGOAL_ROOT/repo-map.md"
```

```powershell
# Windows / PowerShell
pwsh -NoProfile -File "$env:SUPERGOAL_DIR\scripts\detect-stack.ps1"   > "$env:SUPERGOAL_ROOT\context.md"
pwsh -NoProfile -File "$env:SUPERGOAL_DIR\scripts\summarize-repo.ps1" > "$env:SUPERGOAL_ROOT\repo-map.md"
```

### Greenfield path

```bash
# Unix / git-bash
bash "$SUPERGOAL_DIR/scripts/detect-env.sh" > "$SUPERGOAL_ROOT/context.md"
```

```powershell
# Windows / PowerShell
pwsh -NoProfile -File "$env:SUPERGOAL_DIR\scripts\detect-env.ps1" > "$env:SUPERGOAL_ROOT\context.md"
```

Read the outputs. Then print a **5-line summary** to the user: stack, package manager, build/test/lint commands, notable modules (if any), risky areas. This is what tells them you've actually understood their codebase before planning.

---

## Stage 3 — Deep think

This is the difference between a generic plan and a Supergoal. Spend real cycles here — but use only what's available.

**Required regardless of tools:**
- Identify the **top 3 risks**: what's most likely to go wrong, what's hardest to undo, what's easy to miss until shipped.
- Identify **non-obvious dependencies**: things that have to happen in a specific order or block other work.
- Apply memory hits from `$SUPERGOAL_ROOT/applied-memories.md` — bake them into goals, constraints, or risk mitigations.

**Optional, use if available** (check `$SUPERGOAL_ROOT/tools.md`):
- **Context7** — if available, query current docs for any third-party SDK touched. Don't plan against stale APIs. If unavailable, lean on training-cutoff knowledge and call it out as an assumption ("planned against my training-cutoff understanding of Expo SDK — verify in phase 1").
- **WebSearch** — if available, look up current consensus on patterns you're unsure about (auth flows, payment idempotency, accessibility standards). If unavailable, skip.
- **Project skills** — if relevant skills are listed in `$SUPERGOAL_ROOT/applied-skills.md` (e.g. `clerk-auth`, `mobile-ios-design`), note them in THINKING.md as "consult `<skill>` skill during phase N" so the executor invokes them at the right moment.

**Write `$SUPERGOAL_ROOT/THINKING.md`** with sections: Goals, Constraints, Risks, Dependencies, Open Questions (already-assumed), Memory hits applied, Tools/skills relied on, Best Practices Applied. Keep it tight — 1–2 pages. This is the substrate the roadmap derives from.

See `references/planning-depth.md` for the bar to clear here.

---

## Stage 4 — Decompose into phases

Break the work into **as many phases as the task actually needs** — no fixed count, no upper or lower cap. The right number falls out of the work itself: how many independently verifiable units exist between empty repo (or current state) and "done perfectly." A trivial change might need 2 phases; a typical feature 4–6; a full-stack greenfield app 8–12; a major migration 15+. Read `references/phase-design.md` for how to slice well — the short version:

- Each phase delivers something **verifiable on its own** (it builds, it passes its own tests, you could ship it as a partial increment)
- Phases have **explicit dependencies** (phase 3 depends on 1 and 2)
- The **last phase is always a "Polish & Harden" phase** covering edge cases, error states, security, accessibility, copy, perf — this is how "every aspect is perfect" gets enforced
- For UI work, include a dedicated **visual polish** phase with screenshot/visual evidence requirements
- For brownfield, include an early **safety net** phase if test coverage is thin (add characterization tests before changing behavior)

Each phase has:
- **Name** (5 words max, action-first: "Build auth foundation")
- **Why** (1 sentence)
- **Deliverables** (concrete files/features that will exist when done)
- **Acceptance criteria** (5–10 measurable items)
- **Mandatory commands** (build, typecheck, lint, test that must pass)
- **Evidence required** (what the agent must print into the transcript to prove completion — when `capabilities.md` records an E2E surface, the behavior-shipping phases must include an **end-to-end self-verification** against it, not just unit checks; see `references/claude-capabilities.md`)
- **Dependencies** (which prior phases must be done)

**Make dependencies precise — they double as the parallelization gate.** The `Depends on phases:` line is not just documentation: on Claude Code (subagent fan-out available per `capabilities.md`), the phase loop runs every **ready set** (phases whose dependencies are already complete) concurrently, then recomputes. So an accurate dependency graph directly buys parallel speed. State the *minimal* real dependencies — don't write `2 → 3 → 4` if 3 and 4 both only need 2. Two cautions: phases that fan out in parallel must have **non-overlapping deliverables** (parallel workers editing the same files corrupt each other — serialize or worktree-isolate those), and the Polish & Harden phase depends on everything, so it always runs last and solo. On Codex (no `Agent` tool), the same graph just executes sequentially — identical plan, different drive.

---

## Stage 5 — Write the roadmap and phase specs

Three files, all under `$SUPERGOAL_ROOT/`:

1. **`ROADMAP.md`** — the plan (template at `$SUPERGOAL_DIR/templates/ROADMAP.md`).
2. **`STATE.md`** — live progress file the executor updates per phase (template at `$SUPERGOAL_DIR/templates/STATE.md`).
3. **`phases/phase-N.md`** — one work-spec file per phase (template at `$SUPERGOAL_DIR/templates/phase-goal.txt`, renamed conceptually to "phase spec"). **Any length** — these are read from disk by the executor, not passed to `/goal`, so no char budget.

Each phase spec must include these markers so the agent and evaluator both have stable anchors:

```
SUPERGOAL_PHASE_START
Phase: <N> of <total> — <name>
Task: <one-line>
Mandatory commands: <list>
Acceptance criteria: <count>
Evidence required: <list>
Depends on phases: <list or "none">

[... full work description, acceptance criteria, evidence requirements ...]

[Agent will print SUPERGOAL_PHASE_VERIFY and SUPERGOAL_PHASE_DONE here during execution]
```

Validate each spec — it confirms the required markers exist. No char budget.
- Unix / git-bash: `bash "$SUPERGOAL_DIR/scripts/validate-phase.sh" .supergoal/phases/phase-N.md`
- Windows / PowerShell: `pwsh -NoProfile -File "$env:SUPERGOAL_DIR\scripts\validate-phase.ps1" .supergoal\phases\phase-N.md`

---

## Stage 6 — Plan review & confirmation (hard gate)

Before any `/goal` is dispatched, show the user the full plan and **ask for explicit confirmation**. The chain runs unsupervised once it starts, so this is the last cheap moment to correct course. Skipping this step is a bug.

### Stage 6a — Self-critique pass (cheap, runs once)

Plan-time is the cheapest moment to catch the most expensive bugs (vague criteria, mis-sliced phases, weak dependencies). Before printing the summary, run **one** self-critique turn answering exactly three questions:

1. **Falsifiability:** Is every acceptance criterion across every phase a yes/no test, not a vibe? Flag any that say "works", "good", "ready", "correct" without a measurable predicate.
2. **Phase atomicity:** Is any phase secretly two coherent units packed into one (deliverables that don't share a verify gate, names containing "and", split-able dependency lines)?
3. **Weakest dependency:** Where would a partial failure cascade worst? (e.g., phase 2 unblocks 3, 4, and 5 — if 2 ships shaky, three phases inherit the bug.)

**Output:**

- If clean: record `Self-critique: clean.` and proceed.
- If findings: list 1–3 specific findings (no padding). For falsifiability issues, **rewrite the offending criteria in place** in the affected `phase-N.md` files and `ROADMAP.md` before printing the summary. Re-run `validate-phase.sh` on any touched spec. Surface the rewrites in the Stage 6 summary so the user sees the post-critique version, not the pre-critique one.

Honesty check: this pass must produce findings *or* a "clean" verdict per run. If it silently always says "clean" on real plans, it's theater and we remove it in the next release.

### Stage 6b — Summary print

Print a scannable summary in this exact shape:

```
✓ Plan ready for review. <N> phases.

Applied from memory:
  - <memory hit 1>
  - <memory hit 2>
  (or: "none — clean run")

Phases:
  1. <name> — <one-line deliverable>
  2. <name> — <one-line deliverable>
  ...
  N. Polish & Harden — every aspect verified

Stack: <stack> · pkg: <pm> · build/test/lint: <commands>

Key assumptions (correct any that are wrong):
  - <assumption 1>
  - <assumption 2>
  - <assumption 3>

Top risks & mitigations:
  1. <risk> → <mitigation>
  2. <risk> → <mitigation>
  3. <risk> → <mitigation>

Self-critique:
  - <finding 1, or "clean">
  - <finding 2 (optional)>
  - <finding 3 (optional)>
  (criteria rewrites applied in-place if any were flagged)

Artifacts:
  Roadmap: .supergoal/ROADMAP.md
  Progress: .supergoal/STATE.md (auto-updates)
  Phase specs: .supergoal/phases/phase-1..N.md

Once you confirm, I'll print a ready-to-paste `/goal` line. Paste it
once and the chain runs through to completion, with auto-retry and
fix-spec recovery.
```

Then call `AskUserQuestion` with one question, header "Start chain?", offering **concrete revision modes** (not a vague "revise plan"):

- **Start now** — run pre-flight smoke check (Stage 6.5), then print the ready-to-paste `/goal` line; I paste it and the chain runs unsupervised
- **Adjust an assumption** — pick one to change (will re-show plan)
- **Tweak a phase** — change criteria, scope, or commands for a specific phase
- **Restructure phases** — merge, split, add, or remove a phase

Keep options at 4 max. If the user picks any revision option, follow up with a second `AskUserQuestion` to pin down exactly what (e.g., "Which assumption?" with the assumptions listed). Apply the change, update ROADMAP/THINKING/STATE and the affected phase specs, re-run `validate-phase.sh` on each touched spec, then re-show the Stage 6 summary and ask again. Loop until "Start now" or user aborts.

**If a revision changes the phase count, any phase spec, or `ROADMAP.md`, and `.supergoal/goals/goal_prompt.md` already exists** (a prior dispatch is being resumed and re-edited), **regenerate `goal_prompt.md` from the revised plan in the same step** — header and verbatim `/goal` command both. The persisted dispatch condition must never drift from the plan it drives; a stale paste line pointing at an obsolete phase set is exactly the failure this file is meant to prevent.

**Wait for the answer.** Do not dispatch `/goal` until the user picks "Start now". Never assume confirmation; never start the chain on silence.

---

## Stage 6.5 — Pre-flight smoke check

After Stage 6 returns "Start now" and **before** printing the `/goal` block, run a single pre-flight pass against the deduplicated mandatory commands. This catches the case where the baseline is already broken (e.g., `pnpm build` red before phase 1 ever ran) — without this, the 3-strike loop would thrash trying to "fix" phase 1 work that was never the cause.

**Procedure:**

1. Read every `phase-N.md` spec and union their `Mandatory commands:` lines into a deduplicated set.
2. Run each once. Capture exit code and last ~5 lines.
3. **If all green:**
   - Append a `Notable events` line to `.supergoal/STATE.md`: `<DATE> — Pre-flight green: <N> commands clean.`
   - Print `PREFLIGHT_GREEN` with the per-command summary.
   - Proceed to Stage 7.
4. **If any red:**
   - Append `<DATE> — Pre-flight red: <cmd> exited <code>.` to `STATE.md`.
   - Print `PREFLIGHT_RED` with the failing command, exit code, last ~5 lines.
   - Re-show the Stage 6 summary with the failures surfaced and a revised menu (still 4 options to stay under the `AskUserQuestion` ceiling): **"Skip pre-flight, dispatch anyway"** (replaces "Start now" — the user might know the baseline is intentionally broken, e.g., phase 1's whole job is to fix it) / **"Adjust an assumption"** / **"Tweak a phase"** / **"Restructure phases"**. If "Skip pre-flight, dispatch anyway" → log `<DATE> — Pre-flight bypassed by user.` and proceed to Stage 7. Any other choice loops back through the normal Stage 6 revision flow; after the user finishes revising, Stage 6.5 re-runs.

**Honesty test:** real command run, real exit code. The "skip anyway" option keeps the user in control — no forced re-plan if the baseline being red is the point.

---

## Stage 7 — Hand off the `/goal` dispatch (one paste)

Slash commands on both Claude Code and Codex fire **only from user input** — agent message text is never parsed as a command. So Stage 7 is not an automatic dispatch; it's an honest one-paste handoff. After explicit "Start now" in Stage 6:

1. Update `STATE.md`: `Status: READY_TO_DISPATCH`, `Current phase: 1`, and **capture the baseline ref** — set `Baseline ref:` to the output of `git rev-parse HEAD 2>/dev/null || echo "no-git"`. The audit reads this to diff deliverables against the working tree.
2. Copy `$SUPERGOAL_DIR/templates/PROTOCOL.md` to `.supergoal/PROTOCOL.md` (the operating manual the executing agent reads at the start of the `/goal` session), and copy **both** comparison helpers — `$SUPERGOAL_DIR/scripts/repo-state.sh` **and** `$SUPERGOAL_DIR/scripts/repo-state.ps1` — into `.supergoal/` (the complete-working-tree comparison helper the cleanliness + deliverable checks invoke; the executor picks the form matching its host. Strategy in `references/repo-state-comparison.md`). Copy both so the `/goal` session works regardless of host shell.
3. Verify each `.supergoal/phases/phase-N.md` exists; validate each:
   - Unix / git-bash: `bash "$SUPERGOAL_DIR/scripts/validate-phase.sh" .supergoal/phases/phase-<N>.md`
   - Windows / PowerShell: `pwsh -NoProfile -File "$env:SUPERGOAL_DIR\scripts\validate-phase.ps1" .supergoal\phases\phase-<N>.md`
4. **Persist the dispatch line to disk.** Write `.supergoal/goals/goal_prompt.md` — the trigger that binds ROADMAP/STATE/phases/PROTOCOL together is otherwise the one load-bearing artifact of a Supergoal run that lives only in chat scrollback. Persisting it means a deferred dispatch survives context compaction and closed sessions, a re-dispatch after BLOCKED/interruption uses a verbatim-identical end-state condition (reconstruction from memory risks a condition the evaluator never clears), and a teammate or second machine can dispatch from the repo checkout alone. The file contains, in order:
   - **A short header** — task title, dispatch date, total phase count, and the baseline ref(s) captured in step 1. A multi-repo run records one SHA per repo, one line each. (The dispatch date + baseline ref are the staleness guard: they make a stale paste detectable against `git rev-parse HEAD`.)
   - **The exact `/goal` command, verbatim, in a fenced block** — byte-for-byte identical to what step 5 prints in chat (same command string; do not reword or re-wrap it). This file is the canonical copy; the chat print is the convenience copy.
   - **One line of instructions**, exactly: "Paste the `/goal` line into your input to dispatch. If significant time has passed or the baseline ref no longer matches HEAD, re-run `/supergoal` to resume — it will re-capture the baseline and re-run pre-flight before re-issuing this file."
5. Print a fenced code block with the **ready-to-paste `/goal` command** — identical to the one just written to `goal_prompt.md`; the condition below is short, instructional but measurable, and well under the 4000-char `/goal` argument limit:

````
```
/goal "Execute all phases of .supergoal/ROADMAP.md in dependency order (read .supergoal/capabilities.md; if subagent fan-out is available, run each ready set of independent phases in parallel, else sequentially). Read .supergoal/phases/phase-N.md for each phase; do the work; run mandatory commands; print SUPERGOAL_PHASE_VERIFY then SUPERGOAL_PHASE_DONE for each phase; follow the failure-recovery protocol in .supergoal/PROTOCOL.md if any criterion fails. After the last phase, run the FINAL AUDIT in PROTOCOL.md (re-verify against ROADMAP.md; re-run aggregated mandatory commands; spot-check criteria; on gaps, write audit-fix-<round>.md and execute inline). Only after AUDIT_COMPLETE, print SUPERGOAL_RUN_COMPLETE. Done when SUPERGOAL_RUN_COMPLETE appears in the transcript with one SUPERGOAL_PHASE_DONE per phase, AUDIT_COMPLETE printed before SUPERGOAL_RUN_COMPLETE, and no FAILURE_HANDOFF or AUDIT_HANDOFF this run."
```
````

6. Follow the fenced block with **exactly this one-line instruction**:

> **Paste the `/goal` line above into your input to dispatch the chain.** It's also saved at `.supergoal/goals/goal_prompt.md`, so you can dispatch later or from another checkout even if this session closes. From there it runs autonomously — auto-retry, fix-spec recovery, per-phase memory writeback — until `SUPERGOAL_RUN_COMPLETE` appears.

7. **Stop.** Do not generate any further output. The Supergoal invocation ends here. The user's paste begins the autonomous run under a fresh `/goal` session, which reads `PROTOCOL.md`, `ROADMAP.md`, `STATE.md`, and the phase specs from disk and runs the loop documented in the next sections.

Once `/goal` is active (you'll see the `◎ /goal active` indicator on Claude Code), the per-turn evaluator keeps the agent working until the end-state condition holds. On Codex, the auto-continuation loop does the same. The agent inside the `/goal` session has zero special context from the Supergoal invocation; everything it needs is in the files on disk — by design.

---

## Phase execution loop (inside the single `/goal` session)

The agent's loop, repeated until `SUPERGOAL_RUN_COMPLETE`:

1. Read `STATE.md` → find current phase N.
2. Read `.supergoal/phases/phase-N.md` → full work spec.
3. Print `SUPERGOAL_PHASE_START` block with values from the spec.
4. Do the work; run mandatory commands; surface evidence into the transcript.
5. Print `SUPERGOAL_PHASE_VERIFY` block (every criterion `pass|fail` + engineering checks + **cleanliness checks** — get the complete added/new lines since baseline, **including uncommitted and untracked work**, with `bash .supergoal/repo-state.sh added-lines <Baseline ref>` on Unix or `pwsh -NoProfile -File .supergoal/repo-state.ps1 added-lines <Baseline ref>` on Windows, then grep/`Select-String` for stack-specific debug prints, session TODO/FIXME, dead imports; non-zero counts trigger 3-strike unless the phase spec declares `Cleanliness override:`).
6. **Memory writeback check** — anything non-obvious learned? If yes, write a memory file under the detected MEM_DIR; print `MEMORY_SAVED: <name>` (or `MEMORY_SAVED: none`).
7. Print `SUPERGOAL_PHASE_DONE`, update `STATE.md` (mark phase N complete, set Current phase = N+1, append events line).
8. **User-interrupt check** — if a new user message has arrived since the last turn, pause and address it before continuing.
9. If N < total: loop to step 1 for phase N+1.
10. If N == total: do **not** print `SUPERGOAL_RUN_COMPLETE` yet. Run the **Final audit** (next section). Only after `AUDIT_COMPLETE`, print `SUPERGOAL_RUN_COMPLETE` with a 5-line summary. The `/goal` condition is now satisfied and clears.

### Final audit (Stage 10 of the loop — before completion)

Per-phase VERIFY blocks are self-reports. A phase can pass its own check while a later phase silently breaks it (a type added in phase 2 violated in phase 5; tests that passed mid-run break after refactor; etc.). The audit closes that loophole by re-validating against the **original** ROADMAP.md, not against the run's own self-reports.

The audit runs once after the final phase. If it finds gaps, it writes a focused fix spec and re-runs itself. Cap at 3 audit rounds; on the 3rd round's failure, `AUDIT_HANDOFF`.

**Audit steps:**

1. Print `AUDIT_START` with round number, total phase count, criteria count, and the deduplicated set of mandatory commands to re-run.
2. **Re-read `ROADMAP.md`** — pull every phase's acceptance criteria fresh from the original plan. Do not trust prior VERIFY summaries.
3. **Phase completeness check** — scan the transcript: does every phase 1..N have a `SUPERGOAL_PHASE_DONE` block? Surface any missing.
4. **Re-run aggregated mandatory commands** once each (build, typecheck, lint, full test suite). Surface last ~10 lines + exit code for each. Any non-zero exit → an `AUDIT_GAP`.
5. **Spot-check verifiable criteria** — for each acceptance criterion across all phases:
   - "File X exists" / "Function Y exported" / "Config key Z set" / "No `console.log` in app code" → re-check via `ls`/`grep`/`cat`.
   - "Screenshot showed X" / "Manual smoke test passed" / other non-deterministic checks → mark `trust-prior-verify`, do not re-run.
5b. **Deliverable check** — for each phase block in `ROADMAP.md`, parse the `**Deliverables:**` bullets. For each bullet that names a file path or glob, run the comparison helper for the host — `bash .supergoal/repo-state.sh deliverable <Baseline ref> "<path>"` on Unix, or `pwsh -NoProfile -File .supergoal/repo-state.ps1 deliverable <Baseline ref> "<path>"` on Windows. It checks the **complete working tree** (committed + staged + unstaged + deleted) against the baseline and detects untracked new files separately. `missing` (exit 1) → `AUDIT_GAP: phase <N> deliverable "<bullet>" not present`. Repository ground-truth — catches "agent said done but didn't ship," even when the run never committed. Strategy: `references/repo-state-comparison.md`.
6. Print `AUDIT_VERIFY` block:
   - Per-phase status (DONE present or missing)
   - Each mandatory command's exit code
   - Each criterion's `pass | fail | trust-prior-verify` with evidence
   - `Deliverables:` block from step 5b — `phase N / "<bullet>": present | missing`
7. **If any gaps:**
   - Print `AUDIT_GAPS` with the list.
   - Write `.supergoal/phases/audit-fix-<round>.md` — a focused fix spec targeting **only** the failing criteria, with the original phase's VERIFY as the success gate, scope creep forbidden.
   - Execute the fix spec inline (same agent, same `/goal`, same 3-strike per-criterion protocol from regular phases).
   - On fix success: loop back to step 1 (round + 1). On 3rd round's failure: print `AUDIT_HANDOFF` (full gap history + suggested next move), update `STATE.md` to `BLOCKED`, stop. Do not print `SUPERGOAL_RUN_COMPLETE`.
8. **If clean:**
   - Compute `audit coverage` = `re_verified / (re_verified + trust_prior)` as a percentage (where `re_verified` = criteria with `pass` + deliverables marked `present`; `trust_prior` = criteria marked `trust-prior-verify`).
   - Print `AUDIT_COMPLETE` with phases verified, commands re-run clean, criteria pass/trust-prior counts, deliverables present/missing counts, and the audit coverage %.
   - Print `SUPERGOAL_RUN_COMPLETE`. If `trust_prior / (re_verified + trust_prior)` > 30%, prepend an honesty banner: `⚠ Audit coverage: X re-verified, Y trust-prior (Z%). Eyeball UI/UX before merging.` Below 30%, print the plain coverage line without the warning prefix.

The audit is the difference between "every phase passed its own self-report" and "the final state matches the plan I originally approved." That is the bar.

### Failure recovery (3-strike, built into the protocol)

**First failure of any criterion:**
1. Print `FAILURE_PROBE` (what failed, what tried, root-cause hypothesis).
2. Append probe to `STATE.md` failure log.
3. **Auto-retry the same phase once** with the probe injected as feedback. Do not advance.

**Second failure (auto-retry also failed):**
1. Print `FAILURE_ESCALATE`.
2. Write a focused **fix spec** at `.supergoal/phases/phase-N.fix.md` (targets only the failing criterion, no scope creep).
3. Execute the fix spec inline (same agent, same `/goal` — no new dispatch). On success, re-run the original phase's VERIFY block; on pass, advance to N+1.

**Third failure (fix spec also failed):**
1. Print `FAILURE_HANDOFF` with: failing criterion, full probe history, three things tried, suggested next move.
2. Update `STATE.md`: `Status: BLOCKED`. The user takes the wheel.
3. The `/goal` condition will not be satisfied; the host's evaluator will keep evaluating but the agent should stop attempting and surface the handoff clearly.

This recovers from flaky envs, simple typos, and missed deps automatically. Only real blockers escalate.

### Mid-run interruption

If the user sends any message during the `/goal` run, the agent pauses at the next phase boundary, addresses the message, and asks before resuming. Phase boundaries are after `SUPERGOAL_PHASE_DONE` and before reading the next phase spec.

---

## Memory writeback rules (referenced by PROTOCOL.md)

Memory is load-bearing. Future runs start smarter because past runs wrote down what they learned. The phase execution loop's step 6 references these rules.

**At each phase boundary**, ask: "Did this phase surface anything a future Supergoal run on a similar task would benefit from knowing?"

Worth saving:
- A library API quirk that wasn't in the docs
- A user preference confirmed during this run ("user accepted dark-only UI without pushback")
- A project-level fact ("auth lives in `lib/auth/` not `app/api/auth/`")
- A failure pattern + fix ("X always fails on first build; second build works")

Write the memory file under the detected MEM_DIR using the standard `name` / `description` / `metadata.type` frontmatter. Link it from `MEMORY.md`. Print `MEMORY_SAVED: <name>` to the transcript. If nothing non-obvious this phase: print `MEMORY_SAVED: none`.

**At the final phase**, always write a `project_<slug>.md` memory pointing at the new/changed project (location, stack, status, ROADMAP link). Guarantees future Supergoal runs on the same project start from the latest state.

**Never save:** secrets, transient task details, ephemeral state. Bar is "useful to a future run." When in doubt, skip.

---

## Operating principles (read every run)

- **One `/goal`, short condition.** `/goal` takes an end-state, not a task body. Long content lives in files the agent reads from disk. This is the natural shape on both Claude Code and Codex.
- **Frictionless is the goal.** Memory + prompt + recon should answer most questions. Zero clarifying questions on well-described tasks is a win.
- **Adapt to available tools.** Detect what's there (Context7, WebSearch, MCPs, skills). Use what's available; degrade gracefully without it. Never hard-require a tool that might not be present.
- **Adapt to host capabilities.** Detect host + capabilities at Stage 0 (`capabilities.md`). On Claude Code, drive independent phases in parallel via subagent fan-out and verify behavior end-to-end against any detected surface; on Codex, run the same plan sequentially with unit evidence. Capabilities change *how* phases are driven and *how deeply* verified — never *what the plan is*. Degrade gracefully; the portable path is always the default. See `references/claude-capabilities.md`.
- **Memory is load-bearing.** Preload at Stage 0, surface as "Applied from memory: …" in Stage 1, write back at every phase boundary.
- **"Perfect" is not a stopping condition — criteria are.** Translate every "perfect" into observable, falsifiable criteria.
- **Two human gates, no more.** Clarifying gaps (Stage 1 — walk the full category checklist for greenfield in batches of up to 4 until all material info is gathered; often zero for brownfield) and plan review (Stage 6). Between and after, autonomous.
- **The loop self-heals.** Auto-retry once, then write a fix spec and execute inline, then escalate. Don't stop on first failure.
- **The evaluator only sees the transcript.** Phase specs require the agent to surface their contract — START, commands, evidence, VERIFY, DONE — into the conversation, not just point at files.
- **Each phase is independently shippable** in spirit. If phase 3 can't build/test on its own, the slicing is wrong.
- **The Polish & Harden phase is mandatory.** It's how "every aspect is perfect" gets enforced.

---

## When to deviate from the workflow

- **Very small task** (< 1 hour of work, single file): tell the user this doesn't need Supergoal, suggest just doing it. Don't force the machinery.
- **The user pushes back on a phase during intake**: collapse, re-plan, continue.
- **Mid-run interruption**: if the user stops the run and asks for a change, update the affected `.supergoal/phases/phase-N.md` spec, run `validate-phase.sh` on it, then ask the user to resume (they can re-dispatch the same `/goal` or just say "continue"). No need to restart phase 1.

---

## Reference files

- `references/planning-depth.md` — what makes a plan deep enough to deserve "Super"
- `references/phase-design.md` — how to slice phases that auto-chain cleanly
- `references/goal-format.md` — what `/goal` is on Claude Code + Codex, Supergoal's single-`/goal` shape, required transcript blocks
- `references/claude-capabilities.md` — Claude vs Codex capability profile (`capabilities.md`): subagent fan-out for independent phases, end-to-end self-verification surfaces, and how each changes execution
- `references/repo-state-comparison.md` — complete-working-tree-vs-baseline comparison strategy used by the cleanliness + deliverable checks

## Scripts

Each script ships in two parity forms — `*.sh` (POSIX) and `*.ps1` (PowerShell/Windows) — with identical CLI and output. Pick by host (see "Cross-platform shell" at the top).

- `scripts/detect-stack.{sh,ps1}` — identifies language, package manager, framework, build/test/lint commands (brownfield)
- `scripts/detect-env.{sh,ps1}` — greenfield environment recon
- `scripts/summarize-repo.{sh,ps1}` — compressed repo map (brownfield)
- `scripts/validate-phase.{sh,ps1}` — checks a phase spec has the required SUPERGOAL_PHASE_START marker and a non-empty acceptance criteria section
- `scripts/repo-state.{sh,ps1}` — complete-working-tree-vs-baseline comparison (deliverable / changed-files / added-lines); copied into `.supergoal/` at Stage 7

## Templates

- `templates/ROADMAP.md` — phase plan with dependencies
- `templates/STATE.md` — live progress file
- `templates/phase-goal.txt` — phase spec skeleton (work, criteria, evidence, mandatory commands)
- `templates/PROTOCOL.md` — phase execution loop, failure recovery, memory writeback (copied to `.supergoal/PROTOCOL.md` at dispatch)
