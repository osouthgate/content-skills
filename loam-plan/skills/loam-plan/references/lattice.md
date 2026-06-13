# The lattice — reading design → how-to → plan as state

loam-plan's core move is treating the repo's existing doc/plan taxonomy as a state machine.
You don't invent frontmatter status — **the folder a thing lives in IS its status.**

## The three layers

| Layer | Meaning | loam-web location | What you read it for |
|---|---|---|---|
| **Design** | The spec / PRD — *what and why* | `docs/designs/X.md` | Does a decided design exist? Plans must conform to it. |
| **How-to** | Operability — *how to run/extend it* | `docs/how-to/X.md`, runbooks | Is there a named pattern to conform to? Is one owed? |
| **Plan** | Task-breakdown — *the build* | `plans/{backlog,toDo,in_progress,done}/plan-X.md` | Is there a plan already? The folder = its status. |

osdb and other repos differ — resolve the real paths in Phase 0 from `.claude/loam-plan.yml`
or auto-detection. The *concept* is portable; the paths are not.

## The routing table

| design? | how-to? | plan status | Output | Why |
|---|---|---|---|---|
| ✓ | ✓ | done | **Delta plan** | Already built + operable. Plan the gap/regression, not a rebuild. Consider `/investigate` if it's a bug. |
| ✓ | ✓ | toDo/in_progress | **Implementation plan** | Design + pattern exist; plan conforms to both. |
| ✓ | — | toDo/in_progress | **Implementation plan**, how-to owed-on-ship | Design exists, operability guide doesn't yet. Register the debt. |
| ✓ | — | none | **From-design plan** | Designed but unplanned. Build the breakdown from the design; register how-to debt. |
| — | * | * | **GATE — stop** | Not designed. Route to design first, or take an explicit `--exempt-design` with a reason. |

## The gate is the discipline

The bottom row is the whole point. "If it isn't designed, design it first" is enforced at the
front door instead of on the honor system. The only way past an undesigned subject is an
**explicit** exemption the user types — recorded in frontmatter as `design: exempt — <reason>`.
A silent "I get the gist" bypass is the failure mode this gate exists to prevent.

## How-to debt

When you plan something whose how-to doesn't exist yet, you don't block — you **register the
debt**: note in the plan's `## How-to debt` section which guide must be written when the work
ships. This keeps the lattice honest over time (every shipped design ends up with a how-to)
without making the plan wait on documentation.
